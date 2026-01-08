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
import logging

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

# Icon font (emoji) — registered separately so text stays in the regular font
ICON_FONT = "Symbola"
ICON_FONT_PATH: Optional[str] = None

TITLE_SIZE = 12
SUBTITLE_SIZE = 8
BODY_SIZE = 9
COST_SIZE = 18
META_SIZE = 7

# Load icons (unicode) from config/types.xml. Fallback to a small built-in set for schools.
def load_type_icons(path: str = os.path.join("config", "types.xml")) -> Dict[str, str]:
    icons: Dict[str, str] = {}
    try:
        tree = ET.parse(path)
        root = tree.getroot()
        for t in root.findall("type"):
            name = t.attrib.get("name")
            icon = t.attrib.get("icon")
            if name and icon:
                icons[name] = icon
    except Exception:
        # If config missing or invalid, continue with empty mapping and rely on defaults below
        pass
    return icons

# Global mapping loaded once
TYPE_ICONS = load_type_icons()


def load_front_icons(path: str = os.path.join("config", "front_icons.xml")) -> Tuple[Dict[str, str], Dict[str, str], Dict[str, str]]:
    """Load icon mappings: deck -> front char, deck -> back char, and lootType -> front char."""
    deck_front_map: Dict[str, str] = {}
    deck_back_map: Dict[str, str] = {}
    loot_map: Dict[str, str] = {}
    try:
        tree = ET.parse(path)
        root = tree.getroot()
        for d in root.findall("deck"):
            name = d.attrib.get("name")
            front = d.attrib.get("front")
            back = d.attrib.get("back")
            if name and front:
                deck_front_map[name] = front
            if name and back:
                deck_back_map[name] = back
        ld = root.find("lootDefaults")
        if ld is not None:
            for lt in ld.findall("lootType"):
                name = lt.attrib.get("name")
                front = lt.attrib.get("front")
                if name and front:
                    loot_map[name] = front
    except Exception:
        pass

    return deck_front_map, deck_back_map, loot_map


# Global front icon mappings
FRONT_DECK_ICONS, BACK_DECK_ICONS, LOOT_FRONT_DEFAULTS = load_front_icons()

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
    front_icon: Optional[str] = None
    deck: Optional[str] = None
    count: int = 1
    tags: List[str] = None


def ensure_fonts() -> None:
    global FONT_REG, FONT_BOLD, FONT_PATH_REG, FONT_PATH_BOLD
    global ICON_FONT, ICON_FONT_PATH

    # Prefer Symbola for emoji if available (common locations)
    symbola_candidates = [
        "/usr/share/fonts/truetype/Symbola/Symbola.ttf",
        "/usr/share/fonts/truetype/symbola/Symbola.ttf",
        "/usr/share/fonts/truetype/ancient-scripts/Symbola_hint.ttf",
        "/usr/local/share/fonts/Symbola.ttf",
        os.path.expanduser("~/.local/share/fonts/Symbola.ttf"),
    ]
    for p in symbola_candidates:
        if p and os.path.exists(p):
            try:
                # Register Symbola (or similar) as the icon font; keep text font as-is.
                ICON_FONT = "Symbola"
                ICON_FONT_PATH = p
                pdfmetrics.registerFont(TTFont(ICON_FONT, ICON_FONT_PATH))
                logging.info("Registered icon font %s for emoji: %s", ICON_FONT, p)
                break
            except Exception:
                # continue to fallback behaviour
                ICON_FONT_PATH = None
                continue

    # Register fonts for Unicode support. Try multiple candidates and fall back
    # to built-in PDF fonts when TTFs are not available to avoid crashing.
    candidates_reg = [
        FONT_PATH_REG,
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ]
    candidates_bold = [
        FONT_PATH_BOLD,
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ]

    reg_registered = False
    for p in candidates_reg:
        if p and os.path.exists(p):
            try:
                FONT_PATH_REG = p
                pdfmetrics.registerFont(TTFont(FONT_REG, p))
                reg_registered = True
                break
            except Exception:
                continue

    bold_registered = False
    for p in candidates_bold:
        if p and os.path.exists(p):
            try:
                FONT_PATH_BOLD = p
                pdfmetrics.registerFont(TTFont(FONT_BOLD, p))
                bold_registered = True
                break
            except Exception:
                continue

    if not reg_registered or not bold_registered:
        logging.warning(
            "Could not register configured TTF fonts (%s / %s). Falling back to built-in fonts which may lack Unicode emoji support.",
            FONT_PATH_REG,
            FONT_PATH_BOLD,
        )
        # Use PDF base fonts as fallback (limited glyph coverage)
        FONT_REG = "Helvetica"
        FONT_BOLD = "Helvetica-Bold"


def check_icon_glyphs(font_path: Optional[str] = None) -> None:
    """Check whether configured icon glyphs are present in the TTF font.

    Uses fontTools if available. Prints warnings for missing glyphs and
    suggests installing `fonttools` when not available.
    """
    icons: List[str] = []
    # collect icon glyphs from known mappings
    icons.extend(FRONT_DECK_ICONS.values())
    icons.extend(BACK_DECK_ICONS.values())
    icons.extend(LOOT_FRONT_DEFAULTS.values())
    icons.extend(TYPE_ICONS.values())

    # normalize and keep unique single characters only
    chars = set()
    for ic in icons:
        if not ic:
            continue
        # consider only first codepoint of multi-char strings
        chars.add(ic[0])

    try:
        from fontTools.ttLib import TTFont  # type: ignore
    except Exception:
        logging.warning("fontTools not installed; cannot check icon glyph coverage. Install with 'pip install fonttools' to enable checks.")
        return

    if font_path is None:
        # Ensure fonts are registered and globals updated so we inspect
        # the same font that will be used for rendering.
        try:
            ensure_fonts()
        except Exception:
            pass
        # Prefer to check the icon font if available
        font_path = ICON_FONT_PATH or FONT_PATH_REG

    try:
        tt = TTFont(font_path)
    except Exception as e:
        logging.warning(f"Unable to load font for glyph check: %s", e)
        return

    cmap = {}
    for table in tt['cmap'].tables:
        cmap.update(table.cmap)

    missing = []
    for ch in sorted(chars):
        if ord(ch) not in cmap:
            missing.append((ch, ord(ch)))

    if missing:
        logging.warning("The following icon characters are NOT present in font %s:", font_path)
        for ch, code in missing:
            logging.warning("  U+%04X  %r", code, ch)
        logging.warning("These will render as fallback rectangles in the PDF. Consider using a font with broader emoji/glyph coverage or replace icons in config/front_icons.xml.")
    else:
        logging.info("All configured icon glyphs are present in %s", font_path)


def parse_cards(xml_path: str) -> List[Card]:
    # Prefer lxml for parsing so we can support XInclude; fall back to ElementTree.
    try:
        from lxml import etree as LET  # type: ignore
    except Exception:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    else:
        # Parse with lxml so xi:include can be expanded via .xinclude()
        ltree = LET.parse(xml_path)
        try:
            ltree.xinclude()
        except Exception:
            # If xinclude fails for any reason, continue with the collapsed tree anyway
            pass
        xml_bytes = LET.tostring(ltree)
        root = ET.fromstring(xml_bytes)

    cards: List[Card] = []

    for node in root.findall("card"):
        cid = node.attrib.get("id", "").strip()
        # Tags remain as card attributes
        tags_raw = node.attrib.get("tags", "")
        tags = [t.strip() for t in tags_raw.split(",") if t.strip()]

        name = (node.findtext("name") or "").strip()
        subtitle = (node.findtext("subtitle") or "").strip()
        effect = (node.findtext("text") or "").strip()

        # Default values
        ctype = "ability"
        cost = 0
        school = None
        slot = None
        klass = None
        front_icon = None
        deck = None

        # Read nested <loot> block if present (new format)
        loot = node.find("loot")
        if loot is not None:
            ctype = loot.attrib.get("lootType", ctype)
            cost_str = loot.attrib.get("cost", None)
            if cost_str is not None:
                try:
                    cost = int(cost_str)
                except ValueError:
                    cost = 0
            school = loot.attrib.get("school", None)
            slot = loot.attrib.get("slot", None)
            klass = loot.attrib.get("class", None)
            front_icon = loot.attrib.get("front_icon", None)
            # if not explicitly provided, use loot defaults from config/front_icons.xml
            if not front_icon:
                front_icon = LOOT_FRONT_DEFAULTS.get(ctype)
            # mark as loot deck
            deck = "loot"
        else:
            # Backwards compat: read attributes from card element
            ctype = node.attrib.get("type", ctype).strip()
            cost_str = node.attrib.get("cost", "0").strip()
            try:
                cost = int(cost_str)
            except ValueError:
                cost = 0
            school = node.attrib.get("school", None)
            slot = node.attrib.get("slot", None)
            klass = node.attrib.get("class", None)
            front_icon = node.attrib.get("front_icon", None)
            # for non-loot variants, try deck-level default icons (monster/biome/etc.)
            if not front_icon:
                # determine variant type from child elements
                for v in ("monster", "biome", "npc", "quest", "curse", "health"):
                    if node.find(v) is not None:
                        front_icon = FRONT_DECK_ICONS.get(v)
                        deck = v
                        break

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
                front_icon=front_icon,
                deck=deck,
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
    if card.type in TYPE_ICONS:
        return TYPE_ICONS[card.type]
    if card.school and card.school in TYPE_ICONS:
        return TYPE_ICONS[card.school]
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
    coin_sym = TYPE_ICONS.get("coin", "◈")
    cost_text = f"{coin_sym} {card.cost}"
    cost_y = header_y_top - (COST_SIZE / 2) - 2
    c.drawRightString(x + w - PADDING, cost_y, cost_text)

    # Icon (top-left) – prefer image file icons/<type>.png, fallback to unicode char
    # If a front_icon is provided, draw it centered as a large mark and reserve lower half for text
    cx = x + w / 2
    if card.front_icon:
        # prefer image icons/<front_icon>.png, fallback to unicode mapping
        icon_img_path = os.path.join("icons", f"{card.front_icon}.png")
        # Prefer any configured mapping; if front_icon is an explicit symbol, use it
        icon_text = TYPE_ICONS.get(card.front_icon) or card.front_icon or ic
        # large icon size (proportional)
        large_size = min(w * 0.5, h * 0.35)
        # compute vertical position in upper half
        content_top = header_y_bottom - 4
        content_bottom = y + PADDING + FOOTER_H
        icon_center_y = content_bottom + (content_top - content_bottom) * 0.66
        try:
            if os.path.exists(icon_img_path):
                c.drawImage(icon_img_path, cx - large_size / 2, icon_center_y - large_size / 2,
                            width=large_size, height=large_size, mask='auto')
            else:
                icon_font_name = ICON_FONT if ICON_FONT_PATH else FONT_REG
                c.setFont(icon_font_name, int(min(48, large_size / mm * 4)))
                c.drawCentredString(cx, icon_center_y - (FONT_REG and 0), icon_text)
        except Exception:
            icon_font_name = ICON_FONT if ICON_FONT_PATH else FONT_REG
            c.setFont(icon_font_name, 28)
            c.drawCentredString(cx, icon_center_y + 6, icon_text)
        # draw a small meta/icon in top-left as well
        small_icon_path = os.path.join("icons", f"{card.type}.png")
        if os.path.exists(small_icon_path):
            try:
                c.drawImage(small_icon_path, ix, header_y_top - ICON_SIZE, width=ICON_SIZE, height=ICON_SIZE, mask='auto')
            except Exception:
                    icon_font_name = ICON_FONT if ICON_FONT_PATH else FONT_REG
                    c.setFont(icon_font_name, 12)
                    c.drawString(ix, header_y_top - 12, ic)
        else:
            icon_font_name = ICON_FONT if ICON_FONT_PATH else FONT_REG
            c.setFont(icon_font_name, 12)
            c.drawString(ix, header_y_top - 12, ic)
        # adjust body_top to be below the large icon
        body_top = icon_center_y - (large_size / 2) - 4
    else:
        # Icon (top-left) – prefer image file icons/<type>.png, fallback to unicode char
        icon_img_path = os.path.join("icons", f"{card.type}.png")
        if os.path.exists(icon_img_path):
            try:
                c.drawImage(icon_img_path, ix, header_y_top - ICON_SIZE, width=ICON_SIZE, height=ICON_SIZE, mask='auto')
            except Exception:
                icon_font_name = ICON_FONT if ICON_FONT_PATH else FONT_REG
                c.setFont(icon_font_name, 12)
                c.drawString(ix, header_y_top - 12, ic)
        else:
            icon_font_name = ICON_FONT if ICON_FONT_PATH else FONT_REG
            c.setFont(icon_font_name, 12)
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
    if not card.front_icon:
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
    # Default back icon: prefer deck-level 'loot' back icon, fallback to coin/type icon
    icon_text = BACK_DECK_ICONS.get("loot", TYPE_ICONS.get("coin", "◈"))
    icon_img_path = None
    if card is not None:
        # Prefer explicit deck back icon when available (e.g. biome -> ⛰)
        if card.deck and card.deck in BACK_DECK_ICONS:
            icon_text = BACK_DECK_ICONS.get(card.deck, icon_text)
        else:
            # For loot-type cards, use the loot deck back icon
            if card.type in LOOT_FRONT_DEFAULTS:
                icon_text = BACK_DECK_ICONS.get("loot", icon_text)
            else:
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
            icon_font_name = ICON_FONT if ICON_FONT_PATH else FONT_REG
            c.setFont(icon_font_name, 28)
            c.drawCentredString(cx, cy + 10 * mm + 6, icon_text)
    else:
        icon_font_name = ICON_FONT if ICON_FONT_PATH else FONT_REG
        c.setFont(icon_font_name, 28)
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
    parser.add_argument("--check-icons", dest="check_icons", action="store_true", default=False,
                        help="Check whether configured icon glyphs are present in the font and print a log")

    args = parser.parse_args()

    inpath = args.input
    xsd_path = args.xsd or (INPUT_XSD if os.path.exists(INPUT_XSD) else None)
    use_color = args.color
    if args.check_icons:
        check_icon_glyphs()
        return

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
