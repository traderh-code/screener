"""LST Sweep (fiche Notion « LST Sweep (fausse cassure) » : mémo + coachings 2026).

- Zones : à défaut du plan du matin, des niveaux calculés (context.levels) : plus haut / bas de la veille,
  de la semaine passée, VAH / VAL du volume profile de la semaine passée.
- Achat : le prix était au-dessus du niveau, une bougie impulsive (étendue >= SWEEP_IMPULSE x ATR14)
  clôture dessous, puis une clôture revient au-dessus au plus SWEEP_MAX_BARS bougies après. Vente : l'inverse.
  (Avec SWEEP_CLOSE_BEYOND = False, une simple mèche suffit : backtest nettement moins bon.)
- Biais de l'unité supérieure dans le sens du trade, donc opposé à la cassure (flux neutre : pas de sweep).
- Ordre limite sur le niveau (retest), stop sous le plus bas du sweep (au moins le stop vol), objectif le
  dernier sommet (creux pour une vente) avant le sweep, R/R >= SWEEP_MIN_RR (zones de plan : R/R 2).
"""

import pandas as pd

from .. import config
from ..indicators import atr
from ..signal import Signal
from .bulles import HIGHER
from .divergences import _pivots


def detect(df: pd.DataFrame, asset: str, tf: str, flux: pd.Series | None = None,
           min_stop: pd.Series | None = None, zones: pd.DataFrame | None = None) -> list[Signal]:
    if zones is None or zones.empty:
        return []
    flux = flux if flux is not None else pd.Series("neutre", index=df.index)
    min_stop = (min_stop if min_stop is not None else pd.Series(0.0, index=df.index)).fillna(0.0)
    a = atr(df)
    tops, bottoms = _pivots(df["high"], low=False), _pivots(df["low"], low=True)
    signals, used = [], set()
    for i in range(1, len(df)):
        bar, prev_close = df.iloc[i], df["close"].iloc[i - 1]
        if bar.high - bar.low < config.SWEEP_IMPULSE * a.iloc[i]:
            continue
        for name, level in zones.iloc[i].dropna().items():
            if prev_close > level > bar.low:
                direction = "achat"
            elif prev_close < level < bar.high:
                direction = "vente"
            else:
                continue
            beyond = bar.close < level if direction == "achat" else bar.close > level
            if config.SWEEP_CLOSE_BEYOND and not beyond:
                continue  # la bougie de cassure doit clôturer de l'autre côté (« bien grasse »)
            for k in range(i + int(config.SWEEP_CLOSE_BEYOND), min(i + config.SWEEP_MAX_BARS + 1, len(df))):
                close = df["close"].iloc[k]
                if (direction == "achat" and close > level) or (direction == "vente" and close < level):
                    if (k, direction) not in used:
                        s = _build(df, asset, tf, direction, name, level, i, k, flux.iloc[k], min_stop.iloc[k],
                                   tops if direction == "achat" else bottoms)
                        if s:
                            signals.append(s)
                            used.add((k, direction))
                    break
    return sorted(signals, key=lambda s: s.time)


def _build(df, asset, tf, direction, zone, level, i, k, flux, vol, pivots):
    if flux != ("haussier" if direction == "achat" else "baissier"):
        return None
    # Dernier sommet (creux) confirmé avant la cassure : un pivot n'est connu que DIV_PIVOT bougies après.
    before = [p for p in pivots if p + config.DIV_PIVOT <= i]
    if not before:
        return None
    sweep = df.iloc[i:k + 1]
    rng = df["high"].iloc[i] - df["low"].iloc[i]
    if direction == "achat":
        target = df["high"].iloc[before[-1]]
        stop = min(sweep["low"].min() - config.STOP_BUFFER * rng, level - vol)
        risk, reward = level - stop, target - level
    else:
        target = df["low"].iloc[before[-1]]
        stop = max(sweep["high"].max() + config.STOP_BUFFER * rng, level + vol)
        risk, reward = stop - level, level - target
    if risk <= 0 or reward <= 0 or reward / risk < config.SWEEP_MIN_RR:
        return None
    notes = [f"Ordre limite sur le niveau balayé ({level:.2f}), on attend le retest",
             f"Zone : {zone}",
             f"Réintégration en {k - i + 1} bougie(s)",
             f"Flux {HIGHER.get(tf, tf)} {flux} (EMA{config.FLUX_FAST}/{config.FLUX_SLOW})",
             "Risque conseillé : 1 %"]
    return Signal(asset, tf, "Sweep", direction, df.index[k], round(level, 2), round(stop, 2), round(target, 2),
                  round(reward / risk, 2), "FRTM", notes)
