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
    school: Optional[str] = None
    slot: Optional[str] = None
    klass: Optional[str] = None
    front_icon: Optional[str] = None
    deck: Optional[str] = None
    count: int = 1
    tags: List[str] = None
