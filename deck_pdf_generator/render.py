import os
import math
import logging
from typing import List, Optional
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import mm
from .types import Card
from . import config
from . import fonts


def wrap_text(c: canvas.Canvas, text: str, max_width: float, font_name: str, font_size: int) -> List[str]:
    """Wrap `text` to fit into `max_width` using canvas font metrics.

    Normalizes literal "\\n" sequences into real newlines and preserves
    paragraph breaks. Returns a list of output lines that will fit within
    the provided `max_width` when rendered with `font_name`/`font_size`.
    """
    c.setFont(font_name, font_size)
    lines: List[str] = []

    # Normalize literal "\\n" sequences into real newlines, then split into paragraphs
    if text is None:
        paragraphs = ['']
    else:
        normalized = text.replace('\\n', '\n')
        paragraphs = normalized.split('\n')
    for p_idx, para in enumerate(paragraphs):
        if para.strip() == '':
            # empty paragraph -> produce an empty line
            lines.append('')
            continue

        words = para.split()
        cur: List[str] = []
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
                    lines.append(w)

        if cur:
            lines.append(" ".join(cur))

    return lines


def icon_for(card: Card) -> str:
    """Return an icon glyph for `card` using configured mappings.

    Checks `card.type`, then `card.school`, and falls back to a bullet.
    """
    if card.type in config.TYPE_ICONS:
        return config.TYPE_ICONS[card.type]
    if card.school and card.school in config.TYPE_ICONS:
        return config.TYPE_ICONS[card.school]
    return "•"


def draw_cut_marks(c: canvas.Canvas, x: float, y: float, w: float, h: float, size: float = 2.5 * mm) -> None:
    """Draw crop/cut marks around the rectangle at (x, y, w, h).

    `size` controls the length of the crop marks (default in millimeters).
    """
    c.line(x - size, y + h, x, y + h)
    c.line(x, y + h, x, y + h + size)
    c.line(x + w, y + h, x + w + size, y + h)
    c.line(x + w, y + h, x + w, y + h + size)
    c.line(x - size, y, x, y)
    c.line(x, y - size, x, y)
    c.line(x + w, y, x + w + size, y)
    c.line(x + w, y - size, x + w, y)


def draw_card(c: canvas.Canvas, card: Card, x: float, y: float, w: float, h: float, color: bool = False) -> None:
    """Draw the front side of a single `card` onto the canvas `c`.

    Parameters:
    - `c`: reportlab canvas to draw onto.
    - `card`: Card data structure with fields used for rendering.
    - `x`, `y`: lower-left coordinates of the card box.
    - `w`, `h`: width and height of the card box.
    - `color`: when True, use deck color fill for the header.
    """
    c.setLineWidth(1)
    c.rect(x, y, w, h, stroke=1, fill=0)

    if color:
        deck_name = card.deck or "loot"
        header_color = config.DECK_COLORS.get(deck_name, colors.whitesmoke)
        # always use black text for colored cards
        text_color = colors.black
        c.setFillColor(header_color)
        c.rect(x + 0.5, y + h - config.HEADER_H - 0.5, w - 1, config.HEADER_H, stroke=0, fill=1)
        c.setFillColor(text_color)

    c.setLineWidth(0.4)
    draw_cut_marks(c, x, y, w, h)

    ix = x + config.PADDING
    iy = y + config.PADDING
    iw = w - 2 * config.PADDING
    ih = h - 2 * config.PADDING

    header_y_top = y + h - config.PADDING
    header_y_bottom = y + h - config.PADDING - config.HEADER_H

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

    # draw cost (or monster lootBudget) only when non-zero
    display_cost = None
    if getattr(card, 'type', None) == 'monster' and getattr(card, 'lootBudget', None) is not None:
        display_cost = getattr(card, 'lootBudget', 0)
    else:
        display_cost = getattr(card, 'cost', 0)

    coin_sym = config.TYPE_ICONS.get("coin", "◈")
    if display_cost:
        c.setFont(fonts.FONT_BOLD, config.COST_SIZE)
        cost_text = f"{coin_sym} {display_cost}"
        cost_y = header_y_top - (config.COST_SIZE / 2) - 2
        c.drawRightString(x + w - config.PADDING, cost_y, cost_text)

    cx = x + w / 2

    # determine left/top icon text: for monsters prefer biome-specific icon
    left_icon_text = None
    if getattr(card, 'type', None) == 'monster' and getattr(card, 'biome', None):
        left_icon_text = config.FRONT_BIOME_ICONS.get(card.biome)
    if not left_icon_text:
        left_icon_text = config.TYPE_ICONS.get(card.type) or ic

    if card.front_icon:
        icon_img_path = os.path.join("icons", f"{card.front_icon}.png")
        icon_text = config.TYPE_ICONS.get(card.front_icon) or card.front_icon or ic
        large_size = min(w * 0.5, h * 0.35)
        content_top = header_y_bottom - 4
        content_bottom = y + config.PADDING + config.FOOTER_H
        icon_center_y = content_bottom + (content_top - content_bottom) * 0.66
        try:
            if os.path.exists(icon_img_path):
                c.drawImage(icon_img_path, cx - large_size / 2, icon_center_y - large_size / 2,
                            width=large_size, height=large_size, mask='auto')
            else:
                logging.info("Icon image not found for front icon '%s' (expected %s); falling back to glyph", icon_text, icon_img_path)
                icon_font_name = fonts.ICON_FONT if fonts.ICON_FONT_PATH else fonts.FONT_REG
                c.setFont(icon_font_name, int(min(48, large_size / mm * 4)))
                c.drawCentredString(cx, icon_center_y, icon_text)
        except Exception:
            logging.warning("Failed to draw front icon image '%s' or glyph '%s' for card %s", icon_img_path, icon_text, getattr(card, 'id', '<unknown>'))
            icon_font_name = fonts.ICON_FONT if fonts.ICON_FONT_PATH else fonts.FONT_REG
            c.setFont(icon_font_name, 28)
            try:
                c.drawCentredString(cx, icon_center_y + 6, icon_text)
            except Exception:
                logging.error("Failed to fallback-draw front glyph '%s' for card %s", icon_text, getattr(card, 'id', '<unknown>'))

        # small header icon (biome/type)
        small_icon_path = os.path.join("icons", f"{card.type}.png")
        if os.path.exists(small_icon_path):
            try:
                c.drawImage(small_icon_path, ix, header_y_top - config.ICON_SIZE, width=config.ICON_SIZE, height=config.ICON_SIZE, mask='auto')
            except Exception:
                logging.warning("Failed to draw small icon image %s for card %s; using glyph '%s'", small_icon_path, getattr(card, 'id', '<unknown>'), left_icon_text)
                icon_font_name = fonts.ICON_FONT if fonts.ICON_FONT_PATH else fonts.FONT_REG
                c.setFont(icon_font_name, 12)
                c.drawString(ix, header_y_top - 12, left_icon_text)
        else:
            logging.debug("Small icon image not found: %s; using glyph '%s'", small_icon_path, left_icon_text)
            icon_font_name = fonts.ICON_FONT if fonts.ICON_FONT_PATH else fonts.FONT_REG
            c.setFont(icon_font_name, 12)
            c.drawString(ix, header_y_top - 12, left_icon_text)

        body_top = icon_center_y - (large_size / 2) - 4
    else:
        # no large front icon: draw small top-left icon and set body area under header
        small_icon_path = os.path.join("icons", f"{card.type}.png")
        if os.path.exists(small_icon_path):
            try:
                c.drawImage(small_icon_path, ix, header_y_top - config.ICON_SIZE, width=config.ICON_SIZE, height=config.ICON_SIZE, mask='auto')
            except Exception:
                logging.warning("Failed to draw small icon image %s for card %s; using glyph '%s'", small_icon_path, getattr(card, 'id', '<unknown>'), left_icon_text)
                icon_font_name = fonts.ICON_FONT if fonts.ICON_FONT_PATH else fonts.FONT_REG
                c.setFont(icon_font_name, 12)
                c.drawString(ix, header_y_top - 12, left_icon_text)
        else:
            logging.debug("Small icon image not found: %s; using glyph '%s'", small_icon_path, left_icon_text)
            icon_font_name = fonts.ICON_FONT if fonts.ICON_FONT_PATH else fonts.FONT_REG
            c.setFont(icon_font_name, 12)
            c.drawString(ix, header_y_top - 12, left_icon_text)

        body_top = header_y_bottom - 4

    # Title and subtitle next to the small icon
    title_x = ix + config.ICON_SIZE / 2 + 1
    c.setFont(fonts.FONT_BOLD, config.TITLE_SIZE)
    title_y = header_y_top - 12
    c.drawString(title_x, title_y, (card.name or '')[:40])

    c.setFont(fonts.FONT_REG, config.SUBTITLE_SIZE)
    c.drawString(title_x, title_y - 10, (card.subtitle or '')[:55])

    c.setFont(fonts.FONT_REG, config.META_SIZE)
    c.drawString(ix, header_y_bottom + 2, meta[:80])

    body_bottom = y + config.PADDING + config.FOOTER_H
    body_h = body_top - body_bottom
    max_lines = int(body_h / (config.BODY_SIZE + 2)) if body_h > 0 else 1
    line_y = body_top - config.BODY_SIZE

    c.setFont(fonts.FONT_REG, config.BODY_SIZE)
    lines = wrap_text(c, card.effect, iw, fonts.FONT_REG, config.BODY_SIZE)[:max_lines]
    for ln in lines:
        c.drawString(ix, line_y, ln)
        line_y -= (config.BODY_SIZE + 2)

    # Draw monster stats row just above footer area
    body_bottom = y + config.PADDING + config.FOOTER_H  + (config.STAT_SIZE + 4)
    stats_y = body_bottom - (config.STAT_SIZE + 2)
    if getattr(card, 'type', None) == 'monster':
        stat_parts = []
        if getattr(card, 'hp', None) is not None:
            stat_parts.append(f"❤️ {card.hp}")
        if getattr(card, 'atk', None) is not None:
            stat_parts.append(f"⚔ {card.atk}")
        lb = getattr(card, 'lootBudget', None)
        if lb is not None:
            coin_sym = config.TYPE_ICONS.get("coin", "◈")
            stat_parts.append(f"{coin_sym} {lb}")
        if stat_parts:
            c.setFont(fonts.FONT_REG, config.STAT_SIZE)
            stats_text = "   ".join(stat_parts)
            c.drawString(ix, stats_y, stats_text)

    footer_y = y + config.PADDING + 2
    c.setFont(fonts.FONT_REG, config.META_SIZE)
    tags = ", ".join(card.tags or [])
    footer = f"{card.id}"
    if tags:
        footer += f" | {tags}"
    c.drawString(ix, footer_y, footer[:95])


def draw_back(c: canvas.Canvas, card: Optional[Card], x: float, y: float, w: float, h: float, color: bool = False) -> None:
    """Draw the back side (reverse) of a card or an empty back.

    If `card` is None a generic back is drawn. Parameters mirror
    `draw_card` (canvas, position/size, color flag).
    """
    c.setLineWidth(1)
    c.rect(x, y, w, h, stroke=1, fill=0)

    cx = x + w / 2
    cy = y + h / 2

    icon_text = config.BACK_DECK_ICONS.get("loot", config.TYPE_ICONS.get("coin", "◈"))
    icon_img_path = None
    deck_name = (card.deck if card is not None else None) or "loot"
    if card is not None:
        # prefer explicit back_icon on the card (from loot/back_icon attribute)
        back_icon_attr = getattr(card, 'back_icon', None)
        back_icon_provided = False
        if back_icon_attr:
            back_icon_provided = True
            icon_text = back_icon_attr
            # use only the first character/glyph for back rendering
            if icon_text:
                icon_text = icon_text[0]
            back_img = os.path.join("icons", f"{back_icon_attr}.png")
            if os.path.exists(back_img):
                icon_img_path = back_img

        # if no explicit back icon image was found, fall back to deck/type defaults
        if not icon_img_path and not back_icon_provided:
            if card.deck and card.deck in config.BACK_DECK_ICONS:
                icon_text = config.BACK_DECK_ICONS.get(card.deck, icon_text)
                if icon_text:
                    icon_text = icon_text[0]
            else:
                if card.type in config.LOOT_FRONT_DEFAULTS:
                    icon_text = config.BACK_DECK_ICONS.get("loot", icon_text)
                    if icon_text:
                        icon_text = icon_text[0]
                else:
                    icon_text = icon_for(card)
                    if icon_text:
                        icon_text = icon_text[0]
            potential = os.path.join("icons", f"{card.type}.png")
            if os.path.exists(potential):
                icon_img_path = potential
            else:
                logging.debug("No specific back image found for card type '%s' at %s", card.type, potential)
    # color fill should be drawn before the icon so it doesn't cover it
    if color:
        back_color = config.DECK_COLORS.get(deck_name, colors.lightblue)
        # always use black text for colored cards
        text_color = colors.black
        c.setFillColor(back_color)
        c.rect(x + 1, y + 1, w - 2, h - 2, stroke=0, fill=1)
        c.setFillColor(text_color)

    if icon_img_path:
        try:
            img_w = config.ICON_SIZE * 4
            img_h = config.ICON_SIZE * 4
            c.drawImage(icon_img_path, cx - img_w / 2, cy - 15 * mm, width=img_w, height=img_h, mask='auto')
        except Exception:
            logging.warning("Failed to draw back image %s for card %s; falling back to glyph '%s'", icon_img_path, getattr(card, 'id', '<unknown>'), icon_text)
            icon_font_name = fonts.ICON_FONT if fonts.ICON_FONT_PATH else fonts.FONT_REG
            # font size in points ~ image height
            font_size = int(img_h)
            c.setFont(icon_font_name, font_size)
            try:
                c.drawCentredString(cx, cy - 15 * mm + int(img_h / 4), (icon_text or '')[:1])
            except Exception:
                logging.error("Failed to draw back glyph '%s' for card %s", icon_text, getattr(card, 'id', '<unknown>'))
    else:
        logging.debug("No back image available; using glyph '%s' for card %s", icon_text, getattr(card, 'id', '<unknown>'))
        icon_font_name = fonts.ICON_FONT if fonts.ICON_FONT_PATH else fonts.FONT_REG
        # draw larger emoji when no image is available
        font_size = int(config.ICON_SIZE * 4)
        c.setFont(icon_font_name, font_size)
        c.drawCentredString(cx, cy - 15 * mm + int((config.ICON_SIZE * 4) / 4), (icon_text or '')[:1])

    # draw back cost only when card present and cost > 0
    if card is not None and getattr(card, 'cost', 0):
        back_cost_size = int(config.COST_SIZE * 1.8)
        c.setFont(fonts.FONT_BOLD, back_cost_size)
        cost_str = str(card.cost)
        c.drawCentredString(cx, cy - (back_cost_size / 2) - 14 * mm, cost_str)
    
    # pokud je karta monster.
    if card is not None and getattr(card, 'type', None) == 'monster':
        # If this is a monster with a biome-specific icon, draw the biome icon
        # in the middle of the back card under the big icon
        back_cost_size = int(config.COST_SIZE * 1.8)
        c.setFont(fonts.FONT_BOLD, back_cost_size)
        biome_icon = None
        if getattr(card, 'biome', None):
            biome_icon = config.FRONT_BIOME_ICONS.get(card.biome)

        icon_font_name = fonts.ICON_FONT if fonts.ICON_FONT_PATH else fonts.FONT_REG
        back_y = cy - (back_cost_size / 2) - 14 * mm
        if biome_icon:
            # draw icon slightly left of center (use only the first character)
            biome_glyph = (biome_icon or '')[:1]
            c.setFont(icon_font_name, back_cost_size)
            c.drawCentredString(cx, back_y, biome_glyph)

    c.setFont(fonts.FONT_BOLD, config.META_SIZE)
    # include deck type next to the "Gnarl" label on the back
    deck_label = (card.deck if card is not None else None) or "loot"
    label = f"Gnarl — {deck_label}"
    c.drawCentredString(cx, y + config.PADDING + 2, label)


def render_pdf(cards: List[Card], out_path: str, color: bool = False, zero_gaps: bool = False) -> None:
    """Render `cards` into a multi-page PDF saved to `out_path`.

    Layout is determined by configuration in `config`. When `color` is
    True, card backs and headers are drawn using deck colors.
    """
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    c = canvas.Canvas(out_path, pagesize=config.PAGE_SIZE)
    fonts.ensure_fonts()

    page_w, page_h = config.PAGE_SIZE
    use_color = bool(color)

    gap_x = 0 if zero_gaps else config.GAP_X
    gap_y = 0 if zero_gaps else config.GAP_Y

    grid_w = config.GRID_COLS * config.CARD_W + (config.GRID_COLS - 1) * gap_x
    grid_h = config.GRID_ROWS * config.CARD_H + (config.GRID_ROWS - 1) * gap_y

    start_x = (page_w - grid_w) / 2
    actual_left = start_x
    actual_right = page_w - (start_x + grid_w)

    if actual_left < config.PAGE_MARGIN_LEFT or actual_right < config.PAGE_MARGIN_RIGHT:
        print(
            f"Warning: requested margins L={config.PAGE_MARGIN_LEFT/mm:.1f} mm, R={config.PAGE_MARGIN_RIGHT/mm:.1f} mm cannot both be maintained when centering."
        )
        print(
            f"Actual margins will be L={actual_left/mm:.1f} mm, R={actual_right/mm:.1f} mm."
            " Consider increasing margins or reducing card/gap sizes."
        )

    start_y = page_h - config.PAGE_MARGIN_Y - grid_h

    if start_y < 0:
        raise ValueError("Grid doesn't fit on page vertically with current settings. Adjust margins/gaps or card size.")

    cards_per_page = config.GRID_COLS * config.GRID_ROWS
    total_pages = max(1, math.ceil(len(cards) / cards_per_page))

    for page in range(total_pages):
        c.setFont(fonts.FONT_BOLD, 10)
        c.drawString(config.PAGE_MARGIN_LEFT, page_h - 6 * mm, "Gnarl – beta cards")

        start_idx = page * cards_per_page
        end_idx = min(len(cards), start_idx + cards_per_page)

        for pos in range(cards_per_page):
            card_idx = start_idx + pos
            col = pos % config.GRID_COLS
            r = pos // config.GRID_COLS
            x = start_x + col * (config.CARD_W + gap_x)
            y = start_y + (config.GRID_ROWS - 1 - r) * (config.CARD_H + gap_y)
            if card_idx < end_idx:
                draw_card(c, cards[card_idx], x, y, config.CARD_W, config.CARD_H, color=use_color)

        c.setFont(fonts.FONT_REG, config.META_SIZE)
        front_label = f"{page+1}. front"
        c.drawCentredString(page_w / 2.0, config.PAGE_MARGIN_Y / 2.0, front_label)

        c.showPage()

        for pos in range(cards_per_page):
            card_idx = start_idx + pos
            col = pos % config.GRID_COLS
            r = pos // config.GRID_COLS
            # Mirror columns left<->right so backs align right-to-left for duplex printing
            mirror_col = (config.GRID_COLS - 1 - col)
            x = start_x + mirror_col * (config.CARD_W + gap_x)
            y = start_y + (config.GRID_ROWS - 1 - r) * (config.CARD_H + gap_y)
            if card_idx < len(cards):
                draw_back(c, cards[card_idx], x, y, config.CARD_W, config.CARD_H, color=use_color)
            else:
                draw_back(c, None, x, y, config.CARD_W, config.CARD_H, color=use_color)

        # Page-level footer: number this page as "N. back" and finish the back page
        c.setFont(fonts.FONT_REG, config.META_SIZE)
        back_label = f"{page+1}. back"
        c.drawCentredString(page_w / 2.0, config.PAGE_MARGIN_Y / 2.0, back_label)

        c.showPage()

    c.save()
