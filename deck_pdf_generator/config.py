import os
import xml.etree.ElementTree as ET
from typing import Dict, Tuple
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm

# Page / card sizes
PAGE_SIZE = A4
CARD_W = 62 * mm
CARD_H = 87 * mm
GRID_COLS = 3
GRID_ROWS = 3
PAGE_MARGIN_LEFT = 10 * mm
PAGE_MARGIN_RIGHT = 10 * mm
PAGE_MARGIN_Y = 10 * mm
GAP_X = 4 * mm
GAP_Y = 4 * mm

# Visual constants
BORDER_RADIUS = 3 * mm
PADDING = 3.5 * mm
HEADER_H = 12 * mm
FOOTER_H = 8 * mm
ICON_SIZE = 10 * mm

# Typography sizes
TITLE_SIZE = 12
SUBTITLE_SIZE = 8
BODY_SIZE = 9
COST_SIZE = 18
META_SIZE = 7

# Typography defaults (may be overridden by fonts.ensure_fonts)
FONT_REG = "DejaVuSans"
FONT_BOLD = "DejaVuSans-Bold"
FONT_PATH_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_PATH_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# Icon / type mappings loaded from config files

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
        pass
    return icons


def load_front_icons(path: str = os.path.join("config", "front_icons.xml")) -> Tuple[Dict[str, str], Dict[str, str], Dict[str, str]]:
    deck_front_map = {}
    deck_back_map = {}
    loot_map = {}
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

# Load globals
TYPE_ICONS = load_type_icons()
FRONT_DECK_ICONS, BACK_DECK_ICONS, LOOT_FRONT_DEFAULTS = load_front_icons()
