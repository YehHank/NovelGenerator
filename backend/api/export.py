import io
import logging
from pathlib import Path
from urllib.parse import quote

import markdown
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from fpdf import FPDF
from fpdf.html import HTML2FPDF
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.db_models import Episode, Story

router = APIRouter(prefix="/api", tags=["export"])
logger = logging.getLogger(__name__)

# Possible CJK font paths (Debian/Ubuntu fonts-noto-cjk)
_CJK_FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
]


def _find_cjk_font() -> str | None:
    for p in _CJK_FONT_CANDIDATES:
        if Path(p).exists():
            return p
    # Try a broader search
    for root in [Path("/usr/share/fonts")]:
        if root.exists():
            for f in root.rglob("NotoSansCJK*Regular*"):
                return str(f)
    return None


class NovelPDF(FPDF):
    def header(self):
        pass

    def footer(self):
        self.set_y(-15)
        self.set_font_size(9)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f"- {self.page_no()} -", align="C")


@router.get("/stories/{story_id}/export/pdf")
async def export_story_pdf(story_id: int, db: AsyncSession = Depends(get_db)):
    """Export all episodes of a story as a single PDF."""
    story = await db.get(Story, story_id)
    if not story:
        raise HTTPException(404, "Story not found")

    episodes = (await db.execute(
        select(Episode)
        .where(Episode.story_id == story_id)
        .order_by(Episode.episode_number)
    )).scalars().all()

    if not episodes:
        raise HTTPException(400, "Story has no episodes to export")

    # Build markdown then convert to HTML
    md_parts = []
    for i, ep in enumerate(episodes):
        ep_title = ep.title or f"第{ep.episode_number}集"
        md_parts.append(f"## {ep_title}\n\n")
        md_parts.append(ep.content + "\n\n---\n\n")

    md_content = "".join(md_parts)
    html_body = markdown.markdown(md_content, extensions=["extra", "nl2br"])

    # Create PDF
    pdf = NovelPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.set_margins(20, 20, 20)

    # Register CJK font
    font_path = _find_cjk_font()
    if font_path:
        pdf.add_font("NotoSansCJK", style="", fname=font_path)
        pdf.add_font("NotoSansCJK", style="B", fname=font_path)
        pdf.add_font("NotoSansCJK", style="I", fname=font_path)
        pdf.add_font("NotoSansCJK", style="BI", fname=font_path)
        pdf.set_font("NotoSansCJK", size=12)
    else:
        logger.warning("CJK font not found, PDF may not render Chinese correctly")
        pdf.add_page()
        pdf.set_font("Helvetica", size=12)

    # Title page
    pdf.add_page()
    pdf.ln(60)
    pdf.set_font_size(28)
    pdf.cell(0, 20, story.title, align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(10)
    pdf.set_font_size(14)
    info_text = f"共 {len(episodes)} 集"
    if story.genre:
        info_text += f" | {story.genre}"
    pdf.cell(0, 10, info_text, align="C", new_x="LMARGIN", new_y="NEXT")

    # Content pages
    pdf.add_page()
    pdf.set_font_size(12)
    pdf.write_html(html_body)

    # Output
    pdf_bytes = pdf.output()

    filename = f"{story.title}.pdf"
    encoded_filename = quote(filename)
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"},
    )
