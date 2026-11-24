from html import escape
from io import BytesIO
from pathlib import Path

import reportlab
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase.pdfmetrics import registerFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

FONT_DIR = Path(reportlab.__file__).with_name("fonts")
registerFont(TTFont("NAC Certificate", str(FONT_DIR / "Vera.ttf")))
registerFont(TTFont("NAC Certificate Bold", str(FONT_DIR / "VeraBd.ttf")))


def certificate_pdf(*, title, attempt_number, score, awarded, learner, wordmark):
    buffer = BytesIO()
    width, height = landscape(letter)
    page = canvas.Canvas(buffer, pagesize=(width, height))
    page.setTitle(f"NAC Connect Certificate of Completion - {title}")
    page.setAuthor("National Ability Center")

    navy = HexColor("#003c69")
    ink = HexColor("#122e43")
    page.setStrokeColor(navy)
    page.setLineWidth(2)
    page.roundRect(28, 28, width - 56, height - 56, 16)
    page.setFillColor(navy)
    page.roundRect(48, 486, width - 96, 74, 10, stroke=0, fill=1)
    page.drawImage(str(wordmark), (width - 220) / 2, 496, width=220, height=54,
                   preserveAspectRatio=True, anchor="c", mask="auto")

    def centered(text, y, size, *, bold=False, color=ink):
        page.setFillColor(color)
        page.setFont("NAC Certificate Bold" if bold else "NAC Certificate", size)
        page.drawCentredString(width / 2, y, text)

    centered("Certificate of Completion", 426, 34, bold=True, color=navy)
    if learner:
        centered("Awarded to", 393, 13)
        name_style = ParagraphStyle("Learner", fontName="NAC Certificate Bold", fontSize=22,
                                    leading=25, alignment=TA_CENTER, textColor=ink)
        name = Paragraph(escape(learner), name_style)
        _, name_height = name.wrap(width - 120, 125)
        name.drawOn(page, 60, 382 - name_height)

    centered(title, 263 if learner else 324, 25, bold=True)
    centered(f"Full attempt {attempt_number} · Score {score}", 228 if learner else 289, 16)
    centered(f"Awarded {awarded}", 166 if learner else 213, 14)
    centered("NAC Connect · Employee onboarding", 75, 12, color=navy)
    page.showPage()
    page.save()
    return buffer.getvalue()
