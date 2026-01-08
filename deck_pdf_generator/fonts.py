import os
import logging
from typing import Optional, List
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Defaults (may be overridden)
FONT_REG = "DejaVuSans"
FONT_BOLD = "DejaVuSans-Bold"
FONT_PATH_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_PATH_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# Icon font (emoji)
ICON_FONT = "Symbola"
ICON_FONT_PATH: Optional[str] = None


def ensure_fonts() -> None:
    global FONT_REG, FONT_BOLD, FONT_PATH_REG, FONT_PATH_BOLD, ICON_FONT, ICON_FONT_PATH

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
                ICON_FONT_PATH = p
                pdfmetrics.registerFont(TTFont(ICON_FONT, ICON_FONT_PATH))
                logging.info("Registered icon font %s: %s", ICON_FONT, p)
                break
            except Exception:
                ICON_FONT_PATH = None
                continue

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
        FONT_REG = "Helvetica"
        FONT_BOLD = "Helvetica-Bold"


def check_icon_glyphs(font_path: Optional[str] = None) -> None:
    try:
        from fontTools.ttLib import TTFont  # type: ignore
    except Exception:
        logging.warning("fontTools not installed; cannot check icon glyph coverage. Install with 'pip install fonttools' to enable checks.")
        return

    if font_path is None:
        # Prefer icon font when available
        font_path = ICON_FONT_PATH or FONT_PATH_REG

    try:
        tt = TTFont(font_path)
    except Exception as e:
        logging.warning("Unable to load font for glyph check: %s", e)
        return

    cmap = {}
    for table in tt['cmap'].tables:
        cmap.update(table.cmap)

    # collect configured icons lazily to avoid circular imports
    from . import config
    icons = []
    icons.extend(config.TYPE_ICONS.values())
    icons.extend(config.FRONT_DECK_ICONS.values())
    icons.extend(config.BACK_DECK_ICONS.values())
    icons.extend(config.LOOT_FRONT_DEFAULTS.values())

    chars = set()
    for ic in icons:
        if not ic:
            continue
        chars.add(ic[0])

    missing = []
    for ch in sorted(chars):
        if ord(ch) not in cmap:
            missing.append((ch, ord(ch)))

    if missing:
        logging.warning("The following icon characters are NOT present in font %s:", font_path)
        for ch, code in missing:
            logging.warning("  U+%04X  %r", code, ch)
    else:
        logging.info("All configured icon glyphs are present in %s", font_path)
