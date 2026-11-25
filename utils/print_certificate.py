"""Render the print edition of the NAC Connect completion certificate."""

from html import escape
from io import BytesIO
from math import cos, pi, sin
from pathlib import Path

import reportlab
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase.pdfmetrics import registerFont, stringWidth
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

FONT_DIR = Path(reportlab.__file__).with_name("fonts")
registerFont(TTFont("NAC Certificate", str(FONT_DIR / "Vera.ttf")))
registerFont(TTFont("NAC Certificate Bold", str(FONT_DIR / "VeraBd.ttf")))
registerFont(TTFont("Baskervville", str(Path(__file__).resolve().parents[1] / "assets/fonts/Baskervville.ttf")))

PAPER = HexColor("#faf6ed")
INK = HexColor("#132c40")
BRAND = HexColor("#003c69")
COPPER = HexColor("#a34d27")
GOLD = HexColor("#edc39b")
RULE = HexColor("#c6b394")
SERIF = "Baskervville"
SANS = "NAC Certificate"
BOLD = "NAC Certificate Bold"


def _label(page, text, x, y, *, color=COPPER, size=8, centered=False):
    tracking = 1.55
    if centered:
        x -= (stringWidth(text, BOLD, size) + (len(text) - 1) * tracking) / 2
    page.saveState()
    label = page.beginText(x, y)
    label.setFont(BOLD, size)
    label.setFillColor(color)
    label.setCharSpace(tracking)
    label.textOut(text)
    page.drawText(label)
    page.restoreState()


def _polygon(page, points):
    shape = page.beginPath()
    shape.moveTo(*points[0])
    for point in points[1:]:
        shape.lineTo(*point)
    shape.close()
    return shape


def _mountain_art(page):
    """Draw an original alpine landscape in the panel's local coordinates."""
    page.setStrokeColor(HexColor("#647d88"))
    page.setLineWidth(0.45)
    page.circle(184, 391, 47, stroke=1, fill=0)
    page.setFillColor(GOLD)
    page.circle(184, 438, 2.1, stroke=0, fill=1)

    page.saveState()
    page.translate(0, 166)
    # Draw the silhouette and the lit and shaded faces of the central ridge.
    ridge = ((-8, 85), (30, 114), (54, 152), (66, 157), (78, 150), (108, 180),
             (122, 186), (154, 231), (167, 217), (172, 202), (188, 182),
             (200, 170), (213, 177), (229, 154), (241, 146), (274, 116), (274, 4), (-8, 4))
    for color, points in (
        ("#27607a", ridge),
        ("#528598", ((-8, 85), (30, 114), (54, 152), (66, 157), (52, 123), (61, 110), (19, 80), (-8, 72))),
        ("#7a9eaa", ((66, 157), (78, 150), (108, 180), (122, 186), (154, 231),
                     (148, 201), (127, 176), (123, 158), (101, 143), (80, 111), (59, 104), (82, 137))),
        ("#b6c6c1", ((108, 180), (122, 186), (154, 231), (148, 201), (134, 185),
                     (130, 193), (117, 168), (105, 165), (96, 154))),
        ("#153c54", ((154, 231), (167, 217), (172, 202), (188, 182), (200, 170),
                     (213, 177), (203, 151), (231, 110), (201, 120), (185, 146), (166, 154), (148, 201))),
        ("#548396", ((213, 177), (229, 154), (241, 146), (274, 116), (274, 75), (230, 103), (221, 135), (206, 150))),
    ):
        page.setFillColor(HexColor(color))
        page.drawPath(_polygon(page, points), stroke=0, fill=1)

    page.saveState()
    page.clipPath(_polygon(page, ridge), stroke=0, fill=0)
    page.setStrokeColor(HexColor("#aeccc8"))
    page.setStrokeAlpha(0.34)
    page.setLineWidth(0.35)
    for offset in range(-124, 270, 3):
        page.line(offset, 4, offset + 126, 226)
    page.restoreState()

    terrain = page.beginPath()
    terrain.moveTo(-8, 76)
    terrain.curveTo(37, 108, 62, 104, 93, 80)
    terrain.curveTo(126, 53, 157, 57, 190, 78)
    terrain.curveTo(220, 97, 256, 97, 274, 78)
    terrain.lineTo(274, -166)
    terrain.lineTo(-8, -166)
    terrain.close()
    page.saveState()
    page.clipPath(terrain, stroke=0, fill=0)
    page.linearGradient(0, -166, 0, 76, (BRAND, HexColor("#0d334e")))
    page.restoreState()

    page.setLineWidth(0.45)
    for index, offset in enumerate(range(0, 112, 7)):
        page.setStrokeColor(HexColor("#8f796f" if index in (3, 11) else "#43687c"))
        contour = page.beginPath()
        contour.moveTo(-8, 66 - offset)
        contour.curveTo(44, 105 - offset, 71, 88 - offset, 102, 63 - offset * 0.9)
        contour.curveTo(163, 15 - offset, 203, 112 - offset * 0.8, 274, 68 - offset)
        page.drawPath(contour, stroke=1, fill=0)
    page.restoreState()


def _seal(page, x, y, score):
    # A finely fluted edge makes the seal read as foil even on a standard printer.
    edge = []
    for step in range(240):
        angle = step * 2 * pi / 240
        radius = 53.5 + 1.4 * cos(60 * angle)
        edge.append((x + radius * cos(angle), y + radius * sin(angle)))
    page.setFillColor(HexColor("#0b2840"))
    page.setStrokeColor(GOLD)
    page.setLineWidth(0.8)
    page.drawPath(_polygon(page, edge), fill=1, stroke=1)
    page.setLineWidth(0.45)
    page.circle(x, y, 48.5, stroke=1, fill=0)
    page.setLineWidth(0.35)
    page.line(x - 10, y + 29, x + 10, y + 29)
    page.setFillColor(GOLD)
    page.setFont(SERIF, 30)
    page.drawCentredString(x, y + 2, "100%")
    _label(page, "PERFECT SCORE", x, y - 12, color=GOLD, size=6.1, centered=True)
    page.setFont(SANS, 8)
    page.drawCentredString(x, y - 27, score)


def _recipient(page, learner, left, width):
    _label(page, "PRESENTED TO", left, 310)
    if not learner:
        page.setStrokeColor(RULE)
        page.setLineWidth(0.65)
        page.line(left, 245, left + width, 245)
        return

    for size in range(34, 13, -2):
        style = ParagraphStyle("Recipient", fontName=BOLD, fontSize=size, leading=size * 1.12, textColor=INK)
        name = Paragraph(escape(learner), style)
        _, height = name.wrap(width, 86)
        if height <= 86:
            break
    name.drawOn(page, left, 259 - height / 2)


def certificate_pdf(*, title, attempt_number, score, awarded, learner, wordmark):
    buffer = BytesIO()
    width, height = landscape(letter)
    page = canvas.Canvas(buffer, pagesize=(width, height), pageCompression=1)
    page.setTitle(f"NAC Connect Certificate of Completion - {title}")
    page.setAuthor("National Ability Center")

    margin, left, split = 28, 68, 495
    panel_width = width - margin - split
    panel_height = height - 2 * margin
    page.setFillColor(PAPER)
    page.setStrokeColor(RULE)
    page.setLineWidth(0.6)
    page.rect(margin, margin, width - 2 * margin, panel_height, stroke=1, fill=1)
    page.rect(margin + 6, margin + 6, split - margin - 6, panel_height - 12, stroke=1, fill=0)

    page.saveState()
    page.translate(split, margin)
    panel = page.beginPath()
    panel.rect(0, 0, panel_width, panel_height)
    page.clipPath(panel, stroke=0, fill=0)
    page.linearGradient(0, 0, 0, panel_height, (BRAND, HexColor("#0b263c")))
    _mountain_art(page)
    page.setStrokeColor(HexColor("#b49b85"))
    page.setLineWidth(0.45)
    page.rect(6, 6, panel_width - 12, panel_height - 12, stroke=1, fill=0)
    page.drawImage(str(wordmark), (panel_width - 145) / 2, 458, width=145, height=51.25, mask="auto")
    _seal(page, panel_width / 2, 87, score)
    page.restoreState()

    _label(page, "NAC CONNECT  /  EMPLOYEE ONBOARDING", left, 525)
    page.setFillColor(INK)
    page.setFont(SERIF, 52)
    page.drawString(left - 2, 449, "Certificate of")
    page.drawString(left - 2, 393, "Completion")
    page.setStrokeColor(COPPER)
    page.setLineWidth(1.15)
    page.line(left, 362, left + 54, 362)

    _recipient(page, learner, left, split - left - 34)
    _label(page, "FOR PERFECT COMPLETION OF", left, 196)
    page.setFillColor(INK)
    page.setFont(SERIF, 27)
    page.drawString(left, 161, title)

    page.setStrokeColor(RULE)
    page.setLineWidth(0.6)
    page.line(left, 126, split - 34, 126)
    _label(page, "AWARDED", left, 104)
    _label(page, "FULL ATTEMPT", 342, 104)
    page.setFillColor(INK)
    page.setFont(SANS, 11)
    page.drawString(left, 83, awarded)
    page.drawString(342, 83, str(attempt_number))
    page.showPage()
    page.save()
    return buffer.getvalue()
