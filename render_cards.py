#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Gnarl – Card PDF Renderer (beta)
- Reads cards from XML
- Generates A4 PDF with 3x3 grid of poker-sized cards (63x88 mm)
- Text-only design, icons by unicode
"""

from __future__ import annotations

import os
import math
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple
import glob
import argparse

from reportlab.lib import colors

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader

# Optional XSD for XML validation
INPUT_XSD = "cards.xsd"


# -----------------------------
# Configuration
# -----------------------------
INPUT_XML = "cards.xml"
OUTPUT_PDF = os.path.join("out", "gnarl_cards.pdf")

PAGE_SIZE = A4

# Poker card size (common): 63 x 88 mm
CARD_W = 62 * mm
CARD_H = 87 * mm

# Grid layout: 3x3 on A4
GRID_COLS = 3
GRID_ROWS = 3

# Page margins + spacing
# Use asymmetric left/right margins so the right safe-print margin can be larger.
PAGE_MARGIN_LEFT = 10 * mm
# Increased right margin for safe printing
PAGE_MARGIN_RIGHT = 10 * mm
PAGE_MARGIN_Y = 10 * mm
GAP_X = 4 * mm
GAP_Y = 4 * mm

# Visual constants
BORDER_RADIUS = 3 * mm  # "fake" radius (drawn as normal rect for simplicity)
PADDING = 3.5 * mm
HEADER_H = 12 * mm
FOOTER_H = 8 * mm

# Typography
FONT_REG = "DejaVuSans"
FONT_BOLD = "DejaVuSans-Bold"

FONT_PATH_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_PATH_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

TITLE_SIZE = 12
SUBTITLE_SIZE = 8
BODY_SIZE = 9
COST_SIZE = 18
META_SIZE = 7

# Icons (unicode)
ICONS = {
    "attack": "⚔",
    "defense": "🛡",
    "spell": "✦",
    "utility": "⚙",
    # Many emoji (like 🎒), "utility": "🧰", are not present in common TTF fonts like DejaVuSans
    # and therefore won't render in PDF. Use a monochrome symbol as fallback.
    "item": "⚒",
    "coin": "◈",
}

# Optional image icon size (will use icons/<type>.png if present)
ICON_SIZE = 10 * mm


@dataclass
class Card:
    id: str
    type: str                 # item | ability | coin
    cost: int
    name: str
    subtitle: str
    effect: str
    school: Optional[str] = None   # attack | defense | spell | utility
    slot: Optional[str] = None
    klass: Optional[str] = None
    count: int = 1
    tags: List[str] = None


def ensure_fonts() -> None:
    # Register fonts for Unicode support
    if os.path.exists(FONT_PATH_REG):
        pdfmetrics.registerFont(TTFont(FONT_REG, FONT_PATH_REG))
    else:
        raise FileNotFoundError(f"Font not found: {FONT_PATH_REG}")

        parser = argparse.ArgumentParser(description="Render Gnarl cards from XML to PDF")
        parser.add_argument("-i", "--input", default=INPUT_XML,
                            help="Input XML file or directory containing *.xml files")
        parser.add_argument("-x", "--xsd", default=None,
                            help="Optional XSD file to validate XML against (if omitted, looks for cards.xsd)")
        parser.add_argument("--color", dest="color", action="store_true", default=False,
                            help="Render in color (default: black & white)")
        parser.add_argument("-o", "--outdir", default=os.path.dirname(OUTPUT_PDF) or "out",
                            help="Output directory for generated PDFs")
    if os.path.exists(FONT_PATH_BOLD):
        pdfmetrics.registerFont(TTFont(FONT_BOLD, FONT_PATH_BOLD))
    else:
        raise FileNotFoundError(f"Font not found: {FONT_PATH_BOLD}")


def validate_xml(xml_path: str, xsd_path: str) -> None:
    """Validate `xml_path` against `xsd_path` using lxml.etree.

    Raises ValueError with error log if validation fails.
    """
    try:
        from lxml import etree
    except Exception as e:
        raise RuntimeError(
            "lxml is required for XML validation (install with 'pip install lxml')"
        ) from e

    xml_doc = etree.parse(xml_path)
    xsd_doc = etree.parse(xsd_path)
    schema = etree.XMLSchema(xsd_doc)
    if not schema.validate(xml_doc):
        errors = "\n".join(str(e) for e in schema.error_log)
        raise ValueError(f"XML validation failed:\n{errors}")


def parse_cards(xml_path: str) -> List[Card]:
    tree = ET.parse(xml_path)
    root = tree.getroot()
    cards: List[Card] = []

    for node in root.findall("card"):
        cid = node.attrib.get("id", "").strip()
        ctype = node.attrib.get("type", "ability").strip()
        cost_str = node.attrib.get("cost", "0").strip()
        school = node.attrib.get("school", None)
        slot = node.attrib.get("slot", None)
        klass = node.attrib.get("class", None)
        tags_raw = node.attrib.get("tags", "")
        tags = [t.strip() for t in tags_raw.split(",") if t.strip()]

        name = (node.findtext("name") or "").strip()
        subtitle = (node.findtext("subtitle") or "").strip()
        effect = (node.findtext("effect") or "").strip()

        try:
            cost = int(cost_str)
        except ValueError:
            cost = 0

        count_str = node.attrib.get("count", "1").strip()
        try:
            count = int(count_str)
            if count < 1:
                count = 1
        except ValueError:
            count = 1

        if not cid:
            cid = f"{ctype}_{len(cards)+1}"

        # Append `count` copies of the card into the result list.
        for _ in range(count):
            cards.append(Card(
                id=cid,
                type=ctype,
                cost=cost,
                name=name,
                subtitle=subtitle,
                effect=effect,
                school=school,
                slot=slot,
                klass=klass,
                count=count,
                tags=tags,
            ))

    return cards


def wrap_text(c: canvas.Canvas, text: str, max_width: float, font_name: str, font_size: int) -> List[str]:
    # Simple word-wrapping for canvas.drawString
    words = text.replace("\n", " ").split()
    lines: List[str] = []
    cur: List[str] = []

    c.setFont(font_name, font_size)

    for w in words:
        trial = (" ".join(cur + [w])).strip()
        if not trial:
            continue
        if c.stringWidth(trial, font_name, font_size) <= max_width:
            cur.append(w)
        else:
            if cur:
                lines.append(" ".join(cur))
                cur = [w]
            else:
                # If one word is too long, hard-split (rare for CZ)
                lines.append(w)

    if cur:
        lines.append(" ".join(cur))

    return lines


def icon_for(card: Card) -> str:
    if card.type in ICONS:
        return ICONS[card.type]
    if card.school and card.school in ICONS:
        return ICONS[card.school]
    return "•"


def draw_cut_marks(c: canvas.Canvas, x: float, y: float, w: float, h: float, size: float = 2.5 * mm) -> None:
    # Minimal corner cut marks around a card rectangle
    # Top-left
    c.line(x - size, y + h, x, y + h)
    c.line(x, y + h, x, y + h + size)
    # Top-right
    c.line(x + w, y + h, x + w + size, y + h)
    c.line(x + w, y + h, x + w, y + h + size)
    # Bottom-left
    c.line(x - size, y, x, y)
    c.line(x, y - size, x, y)
    # Bottom-right
    c.line(x + w, y, x + w + size, y)
    c.line(x + w, y - size, x + w, y)


def draw_card(c: canvas.Canvas, card: Card, x: float, y: float, w: float, h: float, color: bool = False) -> None:
    # Card border
    c.setLineWidth(1)
    c.rect(x, y, w, h, stroke=1, fill=0)

    # Optional colored header background
    if color:
        c.setFillColor(colors.whitesmoke)
        c.rect(x + 0.5, y + h - HEADER_H - 0.5, w - 1, HEADER_H, stroke=0, fill=1)
        c.setFillColor(colors.black)

    # Cut marks (optional; keep them light)
    c.setLineWidth(0.4)
    draw_cut_marks(c, x, y, w, h)

    # Inner frame
    ix = x + PADDING
    iy = y + PADDING
    iw = w - 2 * PADDING
    ih = h - 2 * PADDING

    # Header area
    header_y_top = y + h - PADDING
    header_y_bottom = y + h - PADDING - HEADER_H

    # Icon + meta line (type/school/slot/class)
    ic = icon_for(card)
    meta_parts = []
    if card.school:
        meta_parts.append(card.school)
    if card.type:
        meta_parts.append(card.type)
    if card.slot:
        meta_parts.append(card.slot)
    if card.klass:
        meta_parts.append(card.klass)
    meta = " • ".join(meta_parts)

    # Cost (top-right)
    c.setFont(FONT_BOLD, COST_SIZE)
    # Prepend coin symbol and nudge the price downward so it doesn't touch the card's top edge
    coin_sym = ICONS.get("coin", "◈")
    cost_text = f"{coin_sym} {card.cost}"
    cost_y = header_y_top - (COST_SIZE / 2) - 2
    c.drawRightString(x + w - PADDING, cost_y, cost_text)

    # Icon (top-left) – prefer image file icons/<type>.png, fallback to unicode char
    icon_img_path = os.path.join("icons", f"{card.type}.png")
    if os.path.exists(icon_img_path):
        try:
            c.drawImage(icon_img_path, ix, header_y_top - ICON_SIZE, width=ICON_SIZE, height=ICON_SIZE, mask='auto')
        except Exception:
            c.setFont(FONT_REG, 12)
            c.drawString(ix, header_y_top - 12, ic)
    else:
        c.setFont(FONT_REG, 12)
        c.drawString(ix, header_y_top - 12, ic)

    # Title
    c.setFont(FONT_BOLD, TITLE_SIZE)
    title_x = ix + 14
    title_y = header_y_top - 12
    c.drawString(title_x, title_y, card.name[:40])

    # Subtitle
    c.setFont(FONT_REG, SUBTITLE_SIZE)
    c.drawString(title_x, title_y - 10, card.subtitle[:55])

    # Meta
    c.setFont(FONT_REG, META_SIZE)
    c.drawString(ix, header_y_bottom + 2, meta[:80])

    # Body / effect text
    body_top = header_y_bottom - 4
    body_bottom = y + PADDING + FOOTER_H
    body_h = body_top - body_bottom
    max_lines = max(1, int(body_h / (BODY_SIZE + 2)))

    c.setFont(FONT_REG, BODY_SIZE)
    lines = wrap_text(c, card.effect, iw, FONT_REG, BODY_SIZE)[:max_lines]
    line_y = body_top - (BODY_SIZE + 2)
    for ln in lines:
        c.drawString(ix, line_y, ln)
        line_y -= (BODY_SIZE + 2)

    # Footer: ID + tags (tiny)
    footer_y = y + PADDING + 2
    c.setFont(FONT_REG, META_SIZE)
    tags = ", ".join(card.tags or [])
    footer = f"{card.id}"
    if tags:
        footer += f" | {tags}"
    c.drawString(ix, footer_y, footer[:95])


def draw_back(c: canvas.Canvas, card: Optional[Card], x: float, y: float, w: float, h: float, color: bool = False) -> None:
    """Draw the back side of a card into the same rectangle.
    If `card` is None, draw a generic back pattern with "Gnarl".
    """
    # Card border
    c.setLineWidth(1)
    c.rect(x, y, w, h, stroke=1, fill=0)

    # Center positions
    cx = x + w / 2
    cy = y + h / 2

    # Icon (prefer image file icons/<type>.png if available)
    icon_text = ICONS.get("coin", "◈")
    icon_img_path = None
    if card is not None:
        icon_text = icon_for(card)
        potential = os.path.join("icons", f"{card.type}.png")
        if os.path.exists(potential):
            icon_img_path = potential

    if icon_img_path:
        try:
            # draw image centered above the cost
            img_w = ICON_SIZE
            img_h = ICON_SIZE
            c.drawImage(icon_img_path, cx - img_w / 2, cy + 10 * mm, width=img_w, height=img_h, mask='auto')
        except Exception:
            c.setFont(FONT_REG, 28)
            c.drawCentredString(cx, cy + 10 * mm + 6, icon_text)
    else:
        c.setFont(FONT_REG, 28)
        c.drawCentredString(cx, cy + 10 * mm + 6, icon_text)

    # Optional colored back background
    if color:
        c.setFillColor(colors.lightblue)
        c.rect(x + 1, y + 1, w - 2, h - 2, stroke=0, fill=1)
        c.setFillColor(colors.black)

    # Large cost in center
    back_cost_size = int(COST_SIZE * 1.8)
    c.setFont(FONT_BOLD, back_cost_size)
    cost_str = str(card.cost) if card is not None else ""
    c.drawCentredString(cx, cy - (back_cost_size / 2) + 4, cost_str)

    # Small label at bottom
    c.setFont(FONT_BOLD, META_SIZE)
    label = "Gnarl"
    c.drawCentredString(cx, y + PADDING + 2, label)

    # (no per-card numbering — page numbering handled globally)


def render_pdf(cards: List[Card], out_path: str, color: bool = False) -> None:
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    c = canvas.Canvas(out_path, pagesize=PAGE_SIZE)
    ensure_fonts()

    page_w, page_h = PAGE_SIZE

    # color mode
    use_color = bool(color)

    # Compute grid total size
    grid_w = GRID_COLS * CARD_W + (GRID_COLS - 1) * GAP_X
    grid_h = GRID_ROWS * CARD_H + (GRID_ROWS - 1) * GAP_Y

    # Center grid horizontally so left and right margins are equal (ideal case).
    start_x = (page_w - grid_w) / 2
    actual_left = start_x
    actual_right = page_w - (start_x + grid_w)

    # If the centered position would violate requested minimal margins, inform the user.
    if actual_left < PAGE_MARGIN_LEFT or actual_right < PAGE_MARGIN_RIGHT:
        print(
            f"Warning: requested margins L={PAGE_MARGIN_LEFT/mm:.1f} mm, R={PAGE_MARGIN_RIGHT/mm:.1f} mm cannot both be maintained when centering."
        )
        print(
            f"Actual margins will be L={actual_left/mm:.1f} mm, R={actual_right/mm:.1f} mm."
            " Consider increasing margins or reducing card/gap sizes."
        )

    start_y = page_h - PAGE_MARGIN_Y - grid_h

    if start_y < 0:
        raise ValueError("Grid doesn't fit on page vertically with current settings. Adjust margins/gaps or card size.")

    cards_per_page = GRID_COLS * GRID_ROWS
    total_pages = max(1, math.ceil(len(cards) / cards_per_page))

    for page in range(total_pages):
        # draw front page label
        c.setFont(FONT_BOLD, 10)
        c.drawString(PAGE_MARGIN_LEFT, page_h - 6 * mm, "Gnarl – beta cards")

        start_idx = page * cards_per_page
        end_idx = min(len(cards), start_idx + cards_per_page)

        # Draw fronts
        for pos in range(cards_per_page):
            card_idx = start_idx + pos
            col = pos % GRID_COLS
            r = pos // GRID_COLS
            x = start_x + col * (CARD_W + GAP_X)
            y = start_y + (GRID_ROWS - 1 - r) * (CARD_H + GAP_Y)
            if card_idx < end_idx:
                draw_card(c, cards[card_idx], x, y, CARD_W, CARD_H, color=use_color)

        # Page-level footer: number this page as "N. front"
        c.setFont(FONT_REG, META_SIZE)
        front_label = f"{page+1}. front"
        c.drawCentredString(page_w / 2.0, PAGE_MARGIN_Y / 2.0, front_label)

        c.showPage()

        # Draw backs in same layout (so that double-sided printing lines up)
        for pos in range(cards_per_page):
            card_idx = start_idx + pos
            col = pos % GRID_COLS
            r = pos // GRID_COLS
            x = start_x + col * (CARD_W + GAP_X)
            y = start_y + (GRID_ROWS - 1 - r) * (CARD_H + GAP_Y)
            if card_idx < len(cards):
                draw_back(c, cards[card_idx], x, y, CARD_W, CARD_H, color=use_color)
            else:
                # empty slot -> generic back
                draw_back(c, None, x, y, CARD_W, CARD_H, color=use_color)

        # Page-level footer: number this page as "N. back"
        c.setFont(FONT_REG, META_SIZE)
        back_label = f"{page+1}. back"
        c.drawCentredString(page_w / 2.0, PAGE_MARGIN_Y / 2.0, back_label)

        c.showPage()

    c.save()


def main() -> None:
    parser = argparse.ArgumentParser(description="Render Gnarl cards from XML to PDF")
    parser.add_argument("-i", "--input", default=INPUT_XML,
                        help="Input XML file or directory containing *.xml files")
    parser.add_argument("-x", "--xsd", default=None,
                        help="Optional XSD file to validate XML against (if omitted, looks for cards.xsd)")
    parser.add_argument("--color", dest="color", action="store_true", default=False,
                        help="Render in color (default: black & white)")
    parser.add_argument("-o", "--outdir", default=os.path.dirname(OUTPUT_PDF) or "out",
                        help="Output directory for generated PDFs")

    args = parser.parse_args()

    inpath = args.input
    xsd_path = args.xsd or (INPUT_XSD if os.path.exists(INPUT_XSD) else None)
    use_color = args.color

    # Collect xml files
    xml_files: List[str] = []
    if os.path.isdir(inpath):
        xml_files = sorted(glob.glob(os.path.join(inpath, "*.xml")))
        if not xml_files:
            raise RuntimeError(f"No .xml files found in directory: {inpath}")
    elif os.path.isfile(inpath):
        xml_files = [inpath]
    else:
        raise RuntimeError(f"Input path not found: {inpath}")

    os.makedirs(args.outdir, exist_ok=True)

    for xml_path in xml_files:
        # validate if xsd provided
        if xsd_path and os.path.exists(xsd_path):
            validate_xml(xml_path, xsd_path)
            print(f"XML {xml_path} validated against {xsd_path}")

        cards = parse_cards(xml_path)
        if not cards:
            print(f"No cards found in {xml_path}, skipping")
            continue

        base = os.path.splitext(os.path.basename(xml_path))[0]
        out_pdf = os.path.join(args.outdir, f"{base}_gnarl_cards.pdf")
        render_pdf(cards, out_pdf, color=use_color)
        print(f"OK: rendered {len(cards)} cards -> {out_pdf}")


if __name__ == "__main__":
    main()
