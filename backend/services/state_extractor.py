import json
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db_models import Episode, Character, PlotHook, HookStatus
from backend.services.llm_service import chat_completion

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """你是一個 JSON 資料分析器。請根據以下小說集數內容，分析出角色狀態變化、新伏筆、引用的舊伏筆以及本集摘要。

【角色目前已知狀態】
{characters_json}

【活躍伏筆列表】
{hooks_json}

【本集內容（第{episode_number}集）】
{content}

請回傳一個 JSON 物件，格式如下：
{{
  "episode_title": "本集的標題（簡短有力，3-10字）",
  "episode_summary": "本集的摘要（100-200字，包含主要事件與角色行動）",
  "character_updates": [
    {{
      "name": "角色名",
      "updates": {{
        "field_name": "new_value"
      }}
    }}
  ],
  "new_characters": [
    {{
      "name": "新角色名",
      "description": "簡短描述",
      "current_state": {{"位置": "...", "身體狀況": "..."}},
      "traits": {{"說話方式": "...", "習慣": "..."}}
    }}
  ],
  "new_hooks": [
    {{
      "description": "新埋下的伏筆描述"
    }}
  ],
  "referenced_hook_ids": [1, 2],
  "resolved_hook_ids": [3]
}}

規則：
- character_updates 中的 updates 只需列出「有變化的」欄位。常見欄位包括：位置、身體狀況、情緒、持有物品、受傷部位等。
- 如果角色失去了身體部位（如斷手斷腿），務必記錄。
- new_characters 只列出本集新出現的角色。
- referenced_hook_ids 列出本集有引用到的伏筆 ID。
- resolved_hook_ids 列出本集已經完全解決/揭曉的伏筆 ID。
- 如果某個分類沒有變化，給空陣列 []。

只回傳 JSON，不要其他文字。"""


async def _fallback_title(episode: Episode):
    """Try to generate just a title when full extraction fails."""
    if not episode.content or episode.title != f"第{episode.episode_number}集":
        return  # already has a title or no content to work with
    try:
        raw = await chat_completion(
            [{"role": "user", "content": f"請為以下小說章節取一個簡短有力的標題（3-10字），只回傳標題文字，不要引號或其他內容：\n\n{episode.content[:1500]}"}],
            temperature=0.3,
        )
        title = raw.strip().strip('"\'「」《》')
        if title:
            episode.title = title
    except Exception:
        logger.warning("Fallback title generation also failed for episode %s", episode.episode_number)


async def extract_and_apply(db: AsyncSession, story_id: int, episode: Episode):
    """Run a second LLM call to extract state changes, then apply to DB."""
    try:
        # Gather current state
        chars = (await db.execute(
            select(Character).where(Character.story_id == story_id)
        )).scalars().all()
        chars_data = [
            {"name": c.name, "id": c.id, "current_state": c.current_state or {}, "traits": c.traits or {}}
            for c in chars
        ]

        hooks = (await db.execute(
            select(PlotHook).where(
                PlotHook.story_id == story_id,
                PlotHook.status == HookStatus.active,
            )
        )).scalars().all()
        hooks_data = [{"id": h.id, "description": h.description} for h in hooks]

        prompt = EXTRACTION_PROMPT.format(
            characters_json=json.dumps(chars_data, ensure_ascii=False, indent=2),
            hooks_json=json.dumps(hooks_data, ensure_ascii=False, indent=2),
            episode_number=episode.episode_number,
            content=episode.content,
        )

        raw = await chat_completion(
            [{"role": "user", "content": prompt}],
            json_mode=True,
            temperature=0.2,
        )

        logger.info(f"[Extract EP{episode.episode_number}] Raw LLM response ({len(raw)} chars):\n{raw[:2000]}")

        # Strip markdown code fences if present
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            # Remove opening fence (```json or ```)
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        data = json.loads(cleaned)
        logger.info(f"[Extract EP{episode.episode_number}] Parsed keys: {list(data.keys())}, title={data.get('episode_title', '<missing>')}")

        # Apply episode title & summary
        title = data.get("episode_title", "")
        if title and title.strip():
            episode.title = title.strip()
        episode.summary = data.get("episode_summary", "")

        # Apply character updates
        char_map = {c.name: c for c in chars}
        for update in data.get("character_updates", []):
            name = update.get("name", "")
            char = char_map.get(name)
            if char and update.get("updates"):
                state = dict(char.current_state or {})
                state.update(update["updates"])
                char.current_state = state

        # New characters
        for nc in data.get("new_characters", []):
            new_char = Character(
                story_id=story_id,
                name=nc.get("name", "未知"),
                description=nc.get("description", ""),
                current_state=nc.get("current_state", {}),
                traits=nc.get("traits", {}),
            )
            db.add(new_char)

        # New hooks
        for nh in data.get("new_hooks", []):
            new_hook = PlotHook(
                story_id=story_id,
                description=nh.get("description", ""),
                planted_episode=episode.episode_number,
                status=HookStatus.active,
            )
            db.add(new_hook)

        # Referenced hooks
        hook_map = {h.id: h for h in hooks}
        for hid in data.get("referenced_hook_ids", []):
            hook = hook_map.get(hid)
            if hook:
                refs = list(hook.referenced_episodes or [])
                if episode.episode_number not in refs:
                    refs.append(episode.episode_number)
                hook.referenced_episodes = refs
                hook.status = HookStatus.referenced

        # Resolved hooks
        for hid in data.get("resolved_hook_ids", []):
            hook = hook_map.get(hid)
            if hook:
                hook.status = HookStatus.resolved

        await db.flush()
        logger.info(f"State extraction applied for episode {episode.episode_number}")

    except Exception as e:
        logger.exception(f"State extraction failed for EP{episode.episode_number}: {type(e).__name__}: {e}")
        # Fallback: try to at least generate a title
        await _fallback_title(episode)
