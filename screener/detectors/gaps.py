"""Gaps en journalier sur les indices US (formation, module 29).

- Gap haussier : le plus bas du jour reste au-dessus du plus haut de la veille. Baissier : l'inverse.
- Romain s'en sert comme objectif ou argument, « jamais seul » : une simple information (config.INFO_ONLY), et une note
  sur les autres signaux quand un gap ouvert se trouve sur leur chemin. Un gap comblé n'est plus pris en compte.
- Écartés : l'or et l'argent (données Yahoo : 16 gaps sur 16 haussiers sur l'or, journées plates sur l'argent), les
  gaps minuscules, et les jours autour du changement de contrat trimestriel, où le contrat continu saute sans vrai gap.
"""

import pandas as pd

from .. import config
from ..indicators import atr
from ..signal import Signal


def _near_roll(day: pd.Timestamp) -> bool:
    """Le contrat continu de Yahoo change entre 10 jours avant et 4 jours après le 3e vendredi du trimestre."""
    if day.month not in (3, 6, 9, 12):
        return False
    first = pd.Timestamp(day.year, day.month, 1)
    third_friday = first + pd.Timedelta(days=(4 - first.weekday()) % 7 + 14)
    return third_friday - pd.Timedelta(days=10) <= day <= third_friday + pd.Timedelta(days=4)


def find(daily: pd.DataFrame) -> pd.DataFrame:
    """Gaps de l'historique : date, sens (« haussier » ou « baissier »), near (bord du jour), far (bord de la veille)."""
    a, rows = atr(daily), []
    for i in range(1, len(daily)):
        bar, prev = daily.iloc[i], daily.iloc[i - 1]
        if bar.low > prev.high:
            sens, near, far = "haussier", bar.low, prev.high
        elif bar.high < prev.low:
            sens, near, far = "baissier", bar.high, prev.low
        else:
            continue
        day = pd.Timestamp(daily.index[i].date())
        if abs(near - far) >= config.GAP_MIN_ATR * a.iloc[i] and not _near_roll(day):
            rows.append(dict(i=i, sens=sens, near=near, far=far))
    return pd.DataFrame(rows, columns=["i", "sens", "near", "far"])


def detect(df: pd.DataFrame, asset: str, tf: str, flux: pd.Series | None = None,
           min_stop: pd.Series | None = None) -> list[Signal]:
    if asset not in config.OPR_MAX_DISTANCE or tf != "1D":
        return []
    signals = []
    for g in find(df).itertuples():
        low, high = sorted((g.near, g.far))
        text = f"{g.sens} {low:.2f} - {high:.2f}, objectif possible : comblement à {g.far:.2f}"
        signals.append(Signal(asset, tf, "Gap", "achat" if g.sens == "haussier" else "vente", df.index[g.i],
                              round(float(df["close"].iloc[g.i]), 2), round(float(g.near), 2), round(float(g.far), 2),
                              0.0, text))
    return signals


def note_for(s: Signal, daily: pd.DataFrame) -> str | None:
    """Gap ouvert le plus proche sur le chemin d'un signal, connu avant la séance du signal, s'il est assez près."""
    if s.asset not in config.OPR_MAX_DISTANCE:
        return None
    known = daily[pd.DatetimeIndex(pd.to_datetime(daily.index).date) < pd.Timestamp(s.time.date())]
    buy = s.direction == "achat"
    reach = config.GAP_NOTE_MAX_ATR * atr(known).iloc[-1] if len(known) else 0.0
    best = None
    for g in find(known).itertuples():
        after = known.iloc[g.i + 1:]
        filled = (after["low"] <= g.far).any() if g.sens == "haussier" else (after["high"] >= g.far).any()
        ahead = g.sens == "baissier" and g.near > s.entry if buy else g.sens == "haussier" and g.near < s.entry
        if not filled and ahead and abs(g.near - s.entry) <= reach and (best is None or abs(g.near - s.entry) < abs(best.near - s.entry)):
            best = g
    if best is None:
        return None
    return f"Gap {best.sens} ouvert sur le chemin : commence à {best.near:.2f}, comblé à {best.far:.2f}"
