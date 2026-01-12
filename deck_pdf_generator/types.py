from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Card:
    id: str
    type: str
    cost: int
    name: str
    subtitle: str
    effect: str
    hp: int = None
    atk: int = None
    lootBudget: int = None
    biome: Optional[str] = None
    back_icon: Optional[str] = None
    school: Optional[str] = None
    slot: Optional[str] = None
    klass: Optional[str] = None
    front_icon: Optional[str] = None
    deck: Optional[str] = None
    count: int = 1
    tags: List[str] = None
