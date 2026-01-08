import os
import math
from typing import List, Optional
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import mm
from .types import Card
from . import config
from . import fonts


def wrap_text(c: canvas.Canvas, text: str, max_width: float, font_name: str, font_size: int) -> List[str]:
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
                lines.append(w)

    if cur:
        lines.append(" ".join(cur))

    return lines


def icon_for(card: Card) -> str:
    if card.type in config.TYPE_ICONS:
        return config.TYPE_ICONS[card.type]
    if card.school and card.school in config.TYPE_ICONS:
        return config.TYPE_ICONS[card.school]
    return "•"


def draw_cut_marks(c: canvas.Canvas, x: float, y: float, w: float, h: float, size: float = 2.5 * mm) -> None:
    c.line(x - size, y + h, x, y + h)
    c.line(x, y + h, x, y + h + size)
    c.line(x + w, y + h, x + w + size, y + h)
    c.line(x + w, y + h, x + w, y + h + size)
    c.line(x - size, y, x, y)
    c.line(x, y - size, x, y)
    c.line(x + w, y, x + w + size, y)
    c.line(x + w, y - size, x + w, y)


def draw_card(c: canvas.Canvas, card: Card, x: float, y: float, w: float, h: float, color: bool = False) -> None:
    c.setLineWidth(1)
    c.rect(x, y, w, h, stroke=1, fill=0)

    if color:
        c.setFillColor(colors.whitesmoke)
        c.rect(x + 0.5, y + h - config.HEADER_H - 0.5, w - 1, config.HEADER_H, stroke=0, fill=1)
        c.setFillColor(colors.black)

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

    # draw cost only when non-zero
    if getattr(card, 'cost', 0):
        c.setFont(fonts.FONT_BOLD, config.COST_SIZE)
        coin_sym = config.TYPE_ICONS.get("coin", "◈")
        cost_text = f"{coin_sym} {card.cost}"
        cost_y = header_y_top - (config.COST_SIZE / 2) - 2
        c.drawRightString(x + w - config.PADDING, cost_y, cost_text)

    cx = x + w / 2
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
                icon_font_name = fonts.ICON_FONT if fonts.ICON_FONT_PATH else fonts.FONT_REG
                c.setFont(icon_font_name, int(min(48, large_size / mm * 4)))
                c.drawCentredString(cx, icon_center_y - (fonts.FONT_REG and 0), icon_text)
        except Exception:
            icon_font_name = fonts.ICON_FONT if fonts.ICON_FONT_PATH else fonts.FONT_REG
            c.setFont(icon_font_name, 28)
            c.drawCentredString(cx, icon_center_y + 6, icon_text)

        small_icon_path = os.path.join("icons", f"{card.type}.png")
        if os.path.exists(small_icon_path):
            try:
                c.drawImage(small_icon_path, ix, header_y_top - config.ICON_SIZE, width=config.ICON_SIZE, height=config.ICON_SIZE, mask='auto')
            except Exception:
                icon_font_name = fonts.ICON_FONT if fonts.ICON_FONT_PATH else fonts.FONT_REG
                c.setFont(icon_font_name, 12)
                c.drawString(ix, header_y_top - 12, ic)
        else:
            icon_font_name = fonts.ICON_FONT if fonts.ICON_FONT_PATH else fonts.FONT_REG
            c.setFont(icon_font_name, 12)
            c.drawString(ix, header_y_top - 12, ic)

        body_top = icon_center_y - (large_size / 2) - 4
    else:
        icon_img_path = os.path.join("icons", f"{card.type}.png")
        if os.path.exists(icon_img_path):
            try:
                c.drawImage(icon_img_path, ix, header_y_top - config.ICON_SIZE, width=config.ICON_SIZE, height=config.ICON_SIZE, mask='auto')
            except Exception:
                icon_font_name = fonts.ICON_FONT if fonts.ICON_FONT_PATH else fonts.FONT_REG
                c.setFont(icon_font_name, 12)
                c.drawString(ix, header_y_top - 12, ic)
        else:
            icon_font_name = fonts.ICON_FONT if fonts.ICON_FONT_PATH else fonts.FONT_REG
            c.setFont(icon_font_name, 12)
            c.drawString(ix, header_y_top - 12, ic)

    c.setFont(fonts.FONT_BOLD, config.TITLE_SIZE)
    title_x = ix + 14
    title_y = header_y_top - 12
    c.drawString(title_x, title_y, card.name[:40])

    c.setFont(fonts.FONT_REG, config.SUBTITLE_SIZE)
    c.drawString(title_x, title_y - 10, card.subtitle[:55])

    c.setFont(fonts.FONT_REG, config.META_SIZE)
    c.drawString(ix, header_y_bottom + 2, meta[:80])

    if not card.front_icon:
        body_top = header_y_bottom - 4
    body_bottom = y + config.PADDING + config.FOOTER_H
    body_h = body_top - body_bottom
    max_lines = max(1, int(body_h / (config.BODY_SIZE + 2)))

    c.setFont(fonts.FONT_REG, config.BODY_SIZE)
    lines = wrap_text(c, card.effect, iw, fonts.FONT_REG, config.BODY_SIZE)[:max_lines]
    line_y = body_top - (config.BODY_SIZE + 2)
    for ln in lines:
        c.drawString(ix, line_y, ln)
        line_y -= (config.BODY_SIZE + 2)

    footer_y = y + config.PADDING + 2
    c.setFont(fonts.FONT_REG, config.META_SIZE)
    tags = ", ".join(card.tags or [])
    footer = f"{card.id}"
    if tags:
        footer += f" | {tags}"
    c.drawString(ix, footer_y, footer[:95])


def draw_back(c: canvas.Canvas, card: Optional[Card], x: float, y: float, w: float, h: float, color: bool = False) -> None:
    c.setLineWidth(1)
    c.rect(x, y, w, h, stroke=1, fill=0)

    cx = x + w / 2
    cy = y + h / 2

    icon_text = config.BACK_DECK_ICONS.get("loot", config.TYPE_ICONS.get("coin", "◈"))
    icon_img_path = None
    if card is not None:
        if card.deck and card.deck in config.BACK_DECK_ICONS:
            icon_text = config.BACK_DECK_ICONS.get(card.deck, icon_text)
        else:
            if card.type in config.LOOT_FRONT_DEFAULTS:
                icon_text = config.BACK_DECK_ICONS.get("loot", icon_text)
            else:
                icon_text = icon_for(card)
        potential = os.path.join("icons", f"{card.type}.png")
        if os.path.exists(potential):
            icon_img_path = potential

    if icon_img_path:
        try:
            img_w = config.ICON_SIZE * 4
            img_h = config.ICON_SIZE * 4
            c.drawImage(icon_img_path, cx - img_w / 2, cy - 15 * mm, width=img_w, height=img_h, mask='auto')
        except Exception:
            icon_font_name = fonts.ICON_FONT if fonts.ICON_FONT_PATH else fonts.FONT_REG
            # font size in points ~ image height
            font_size = int(img_h)
            c.setFont(icon_font_name, font_size)
            c.drawCentredString(cx, cy - 15 * mm + int(img_h / 4), icon_text)
    else:
        icon_font_name = fonts.ICON_FONT if fonts.ICON_FONT_PATH else fonts.FONT_REG
        # draw larger emoji when no image is available
        font_size = int(config.ICON_SIZE * 4)
        c.setFont(icon_font_name, font_size)
        c.drawCentredString(cx, cy - 15 * mm + int((config.ICON_SIZE * 4) / 4), icon_text)

    if color:
        c.setFillColor(colors.lightblue)
        c.rect(x + 1, y + 1, w - 2, h - 2, stroke=0, fill=1)
        c.setFillColor(colors.black)

    # draw back cost only when card present and cost > 0
    if card is not None and getattr(card, 'cost', 0):
        back_cost_size = int(config.COST_SIZE * 1.8)
        c.setFont(fonts.FONT_BOLD, back_cost_size)
        cost_str = str(card.cost)
        c.drawCentredString(cx, cy - (back_cost_size / 2) - 14 * mm, cost_str)

    c.setFont(fonts.FONT_BOLD, config.META_SIZE)
    label = "Gnarl"
    c.drawCentredString(cx, y + config.PADDING + 2, label)


def render_pdf(cards: List[Card], out_path: str, color: bool = False) -> None:
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    c = canvas.Canvas(out_path, pagesize=config.PAGE_SIZE)
    fonts.ensure_fonts()

    page_w, page_h = config.PAGE_SIZE
    use_color = bool(color)

    grid_w = config.GRID_COLS * config.CARD_W + (config.GRID_COLS - 1) * config.GAP_X
    grid_h = config.GRID_ROWS * config.CARD_H + (config.GRID_ROWS - 1) * config.GAP_Y

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
            x = start_x + col * (config.CARD_W + config.GAP_X)
            y = start_y + (config.GRID_ROWS - 1 - r) * (config.CARD_H + config.GAP_Y)
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
            x = start_x + col * (config.CARD_W + config.GAP_X)
            y = start_y + (config.GRID_ROWS - 1 - r) * (config.CARD_H + config.GAP_Y)
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
