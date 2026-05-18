import asyncio
import json
import logging
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.db_models import Story, Episode, Character, PlotHook, HookStatus
from backend.services.llm_service import chat_completion, chat_completion_stream
from backend.services.state_extractor import extract_and_apply

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_TEMPLATE = """你是一位頂尖的長篇小說作家。你正在創作一部名為「{title}」的{genre}小說。

【世界觀設定】
{world_setting}

【寫作風格】
{writing_style}

【重要規則】
1. 嚴格遵守角色目前的身體與心理狀態。如果一個角色失去了左手，後續就不能用左手做任何事。
2. 注意引用活躍的伏筆——如果某個伏筆已經埋下，你可以在適當的時機揭露或推進它。
3. 維持角色的個性特質、說話習慣、行為模式的一致性。
4. 每一集要有明確的劇情推進，結尾留下懸念或鉤子。
5. 自然地銜接前文的情節，不要突然跳躍。
6. 每集約 1500-3000 字。
"""

CONTEXT_HEADER = """
【角色目前狀態】
{characters_json}

【活躍伏筆】
{hooks_json}

【前情摘要（較早的集數）】
{summaries}

【最近幾集完整內容】
{recent_episodes}
"""

GENERATION_USER_PROMPT = """請寫出第 {episode_number} 集。

{direction_section}

直接開始寫正文，不要加標題或集數標記。"""


async def build_context(db: AsyncSession, story: Story, next_ep_num: int) -> list[dict]:
    """Assemble the full prompt messages for episode generation."""

    # 1) Characters
    chars = (await db.execute(
        select(Character).where(Character.story_id == story.id)
    )).scalars().all()
    chars_data = []
    for c in chars:
        chars_data.append({
            "name": c.name,
            "description": c.description,
            "current_state": c.current_state or {},
            "traits": c.traits or {},
            "relationships": c.relationship_map or {},
        })
    characters_json = json.dumps(chars_data, ensure_ascii=False, indent=2) if chars_data else "（尚無角色資料，請在本集中自由創建角色）"

    # 2) Active plot hooks
    hooks = (await db.execute(
        select(PlotHook).where(
            PlotHook.story_id == story.id,
            PlotHook.status == HookStatus.active,
        )
    )).scalars().all()
    hooks_data = [{"id": h.id, "description": h.description, "planted_episode": h.planted_episode} for h in hooks]
    hooks_json = json.dumps(hooks_data, ensure_ascii=False, indent=2) if hooks_data else "（尚無活躍伏筆）"

    # 3) All episodes ordered
    episodes = (await db.execute(
        select(Episode)
        .where(Episode.story_id == story.id)
        .order_by(Episode.episode_number)
    )).scalars().all()

    # Split into recent full-text vs older summaries
    full_count = settings.context_full_episodes
    summary_count = settings.context_summary_episodes

    recent_eps = episodes[-full_count:] if len(episodes) >= full_count else episodes
    older_eps = episodes[:-full_count] if len(episodes) > full_count else []
    # Only keep last N summaries
    older_eps = older_eps[-summary_count:] if len(older_eps) > summary_count else older_eps

    summaries = ""
    for ep in older_eps:
        s = ep.summary or "(無摘要)"
        summaries += f"第{ep.episode_number}集摘要：{s}\n"
    if not summaries:
        summaries = "（這是開頭幾集，尚無更早的摘要）"

    recent_text = ""
    for ep in recent_eps:
        recent_text += f"\n--- 第{ep.episode_number}集 ---\n{ep.content}\n"
    if not recent_text:
        recent_text = "（這是第一集，尚無前文）"

    # Build messages
    system_msg = SYSTEM_PROMPT_TEMPLATE.format(
        title=story.title,
        genre=story.genre or "奇幻",
        world_setting=story.world_setting or "（由作者自由發揮）",
        writing_style=story.writing_style or "生動有趣、節奏明快",
    )
    context_msg = CONTEXT_HEADER.format(
        characters_json=characters_json,
        hooks_json=hooks_json,
        summaries=summaries,
        recent_episodes=recent_text,
    )

    return [
        {"role": "system", "content": system_msg + context_msg},
    ]


async def generate_episode(
    db: AsyncSession,
    story_id: int,
    direction_hint: str = "",
    stream: bool = False,
):
    """Generate a new episode. Returns (Episode, generator|None).
    
    If stream=True, returns (episode_stub, async_generator) where the caller
    should iterate the generator to get content chunks, and the episode
    will be finalised when the generator is exhausted.
    If stream=False, returns (episode, None).
    """
    story = await db.get(Story, story_id)
    if not story:
        raise ValueError(f"Story {story_id} not found")

    # Determine next episode number
    max_num = (await db.execute(
        select(func.max(Episode.episode_number)).where(Episode.story_id == story_id)
    )).scalar() or 0
    next_num = max_num + 1

    messages = await build_context(db, story, next_num)

    direction_section = ""
    if direction_hint:
        direction_section = f"【本集方向提示】\n{direction_hint}"

    messages.append({
        "role": "user",
        "content": GENERATION_USER_PROMPT.format(
            episode_number=next_num,
            direction_section=direction_section,
        ),
    })

    if stream:
        # Create a stub episode, will be filled after streaming
        episode = Episode(
            story_id=story_id,
            episode_number=next_num,
            direction_hint=direction_hint,
            content="",
            title=f"第{next_num}集",
        )
        db.add(episode)
        await db.flush()  # get ID

        async def content_stream():
            async for chunk in chat_completion_stream(messages):
                yield chunk

        async def finalize(full_content: str):
            """Save the full content, extract state, then commit."""
            episode.content = full_content
            await db.flush()
            await db.commit()
            # Await extraction so summary is ready before done is sent
            await extract_and_apply(db, story_id, episode)
            await db.commit()

        return episode, content_stream(), finalize
    else:
        content = await chat_completion(messages)
        episode = Episode(
            story_id=story_id,
            episode_number=next_num,
            title=f"第{next_num}集",
            content=content,
            direction_hint=direction_hint,
        )
        db.add(episode)
        await db.flush()

        # Extract state updates
        await extract_and_apply(db, story_id, episode)
        await db.commit()
        await db.refresh(episode)
        return episode, None, None
