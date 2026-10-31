from dataclasses import dataclass, field

import pandas as pd


@dataclass
class Signal:
    asset: str
    tf: str
    pattern: str          # ex. "Bulle apesanteur"
    direction: str        # "achat" ou "vente"
    time: pd.Timestamp    # bougie qui déclenche le signal (clôturée)
    entry: float
    stop: float
    target: float
    rr: float
    context: str = ""     # "FRTM" ou "RP"
    notes: list[str] = field(default_factory=list)
