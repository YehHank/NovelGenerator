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

# Possible CJK font paths (Linux and Windows common locations)
_CJK_FONT_CANDIDATES = [
    # Linux / Debian Noto CJK
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    # Common Windows CJK fonts
    "C:\\Windows\\Fonts\\msyh.ttc",
    "C:\\Windows\\Fonts\\msyh.ttf",
    "C:\\Windows\\Fonts\\msyhbd.ttc",
    "C:\\Windows\\Fonts\\simsun.ttc",
    "C:\\Windows\\Fonts\\simhei.ttf",
    "C:\\Windows\\Fonts\\mingliu.ttc",
    "C:\\Windows\\Fonts\\mingliu.ttf",
    # Other common fonts
    "C:\\Windows\\Fonts\\DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def _find_cjk_font() -> str | None:
    # Check explicit candidates first
    for p in _CJK_FONT_CANDIDATES:
        if Path(p).exists():
            return p
    # Check for a local fonts folder inside the project (data/fonts)
    try:
        project_root = Path(__file__).resolve().parents[2]
        local_fonts_dir = project_root / "data" / "fonts"
        if local_fonts_dir.exists():
            for f in local_fonts_dir.rglob("*.ttf"):
                return str(f)
            for f in local_fonts_dir.rglob("*.otf"):
                return str(f)
    except Exception:
        pass
    # Search common font directories for CJK fonts
    search_roots = [Path("/usr/share/fonts"), Path("C:/Windows/Fonts")]
    patterns = [
        "*NotoSansCJK*",
        "*NotoSerifCJK*",
        "*msyh*",
        "*simsun*",
        "*simhei*",
        "*mingliu*",
        "*DejaVuSans*",
    ]
    for root in search_roots:
        if root.exists():
            try:
                for pat in patterns:
                    for f in root.rglob(pat):
                        return str(f)
            except Exception:
                continue
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

    # Register CJK font (must be a TTF/OTF or otherwise unicode-capable font)
    font_path = _find_cjk_font()
    if not font_path:
        logger.error("No CJK font found. Checked candidates and system fonts.")
        raise HTTPException(500, "No CJK font found on server. Install Noto Sans CJK or ensure a CJK font is available under system fonts.")
    try:
        # Register as a unicode TrueType/OpenType font for multiple styles.
        # HTML generator may reference family names in different cases and append style
        # suffixes, so register both capitalized and lowercase family names and
        # all common styles to avoid "Undefined font" errors.
        families = ["NotoSansCJK", "notosanscjk"]
        styles = ("", "B", "I", "BI")
        for fam in families:
            for style in styles:
                try:
                    pdf.add_font(fam, style, str(font_path), uni=True)
                except Exception:
                    # If one style registration fails, continue trying others
                    logger.debug("Could not register font %s style %s", fam, style)
        pdf.set_font("NotoSansCJK", size=12)
    except Exception as e:
        logger.exception("Failed to register CJK font: %s", e)
        raise HTTPException(500, "Failed to register CJK font for PDF generation")

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
    pdf_bytes = pdf.output(dest="S")
    if isinstance(pdf_bytes, str):
        pdf_bytes = pdf_bytes.encode("latin-1")

    filename = f"{story.title}.pdf"
    encoded_filename = quote(filename)
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"},
    )
