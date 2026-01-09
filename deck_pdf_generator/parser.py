from typing import List
import xml.etree.ElementTree as ET
from .types import Card
from . import config


def parse_cards(xml_path: str) -> List[Card]:
    try:
        from lxml import etree as LET  # type: ignore
    except Exception:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    else:
        ltree = LET.parse(xml_path)
        try:
            ltree.xinclude()
        except Exception:
            pass
        xml_bytes = LET.tostring(ltree)
        root = ET.fromstring(xml_bytes)

    cards: List[Card] = []

    for node in root.findall("card"):
        cid = node.attrib.get("id", "").strip()
        tags_raw = node.attrib.get("tags", "")
        tags = [t.strip() for t in tags_raw.split(",") if t.strip()]

        name = (node.findtext("name") or "").strip()
        subtitle = (node.findtext("subtitle") or "").strip()
        effect = (node.findtext("text") or "").strip()

        ctype = "ability"
        cost = 0
        school = None
        slot = None
        klass = None
        front_icon = None
        deck = None

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
            if not front_icon:
                # prefer an icon based on school for abilities, then fallback to loot-type defaults
                school_icon_map = {
                    "attack": "⚔️",
                    "defense": "🛡️",
                    "spell": "✨",
                    "utility": "⚙️",
                }
                front_icon = None
                if school and school in school_icon_map:
                    front_icon = school_icon_map[school]
                if not front_icon:
                    front_icon = config.LOOT_FRONT_DEFAULTS.get(ctype)
            deck = "loot"
        else:
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
            # if card-level front_icon missing, try to read it from the variant child (e.g. <biome front_icon="…"/>)
            if not front_icon:
                for v in ("monster", "biome", "npc", "quest", "curse", "health"):
                    el = node.find(v)
                    if el is not None:
                        # prefer explicit attribute on the child element
                        front_icon = el.attrib.get("front_icon") or config.FRONT_DECK_ICONS.get(v)
                        deck = v
                        # if no explicit `type` attribute was provided on the card,
                        # use the variant name as the card type (e.g. npc, monster, biome)
                        if 'type' not in node.attrib:
                            ctype = v
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

        # parse monster-specific stats if present
        m = node.find('monster')
        hp = None
        atk = None
        lootBudget = None
        if m is not None:
            hp_str = m.attrib.get('hp')
            atk_str = m.attrib.get('atk')
            lb_str = m.attrib.get('lootBudget') or m.attrib.get('lootbudget')
            try:
                hp = int(hp_str) if hp_str is not None else None
            except Exception:
                hp = None
            try:
                atk = int(atk_str) if atk_str is not None else None
            except Exception:
                atk = None
            try:
                lootBudget = int(lb_str) if lb_str is not None else None
            except Exception:
                lootBudget = None

        for _ in range(count):
            cards.append(Card(
                id=cid,
                type=ctype,
                cost=cost,
                name=name,
                subtitle=subtitle,
                effect=effect,
                hp=hp,
                atk=atk,
                lootBudget=lootBudget,
                school=school,
                slot=slot,
                klass=klass,
                front_icon=front_icon,
                deck=deck,
                count=count,
                tags=tags,
            ))

    return cards
