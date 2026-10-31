"""OPR - Open Price Range (fiche Notion « OPR – Open Price Range » : mémo + coachings 2026).

- OPR = plus haut / plus bas de la première bougie M15 de la séance US (9h30 New York).
- Sortie : une bougie M15 clôture hors de l'OPR, dans le sens du flux H1 (flux neutre : pas d'OPR).
  Seule la première sortie de la séance compte. Le signal part à sa clôture : ordre limite sur la borne
  cassée (on attend le pullback).
- Pas d'alerte si la clôture est déjà trop loin de la borne (mémo : 100 pts Dow, 50 Nasdaq, 15 S&P).
- Stop au-delà de la bougie de cassure, au moins égal au stop vol ; objectif R/R 2 (le mémo dit
  « R/R 2 jusqu'au prochain niveau, puis on laisse courir ») ; pas de trade si le plus haut / plus bas
  de la veille fait obstacle avant R1 (règle 2026 « obstacle avant le break-even »).
- Réintégrations : non alertées (décision du 2026-10-30).
"""

import pandas as pd

from .. import config
from ..signal import Signal

OPEN = "09:30"
LAST_ENTRY = "16:00"  # une sortie après la clôture des actions ne compte plus


def detect(df: pd.DataFrame, asset: str, tf: str, flux: pd.Series | None = None,
           min_stop: pd.Series | None = None) -> list[Signal]:
    if asset not in config.OPR_MAX_DISTANCE or tf != "15M":
        return []
    flux = flux if flux is not None else pd.Series("neutre", index=df.index)
    min_stop = (min_stop if min_stop is not None else pd.Series(0.0, index=df.index)).fillna(0.0)
    max_dist = config.OPR_MAX_DISTANCE[asset]
    ny = df.index.tz_convert("America/New_York")
    days = df.groupby(ny.date).agg(high=("high", "max"), low=("low", "min"))
    prev_hl = days.shift(1)  # plus haut / plus bas de la journée précédente (New York)
    signals = []
    for day, bars in df.groupby(ny.date):
        hm = bars.index.tz_convert("America/New_York").strftime("%H:%M")
        if OPEN not in hm:
            continue
        first = bars[hm == OPEN].iloc[0]
        top, bottom = first.high, first.low
        session = bars[(hm > OPEN) & (hm < LAST_ENTRY)]
        prev_high, prev_low = prev_hl.loc[day, "high"], prev_hl.loc[day, "low"]
        for t, bar in session.iterrows():
            if bar.close > top:
                direction, entry = "achat", top
            elif bar.close < bottom:
                direction, entry = "vente", bottom
            else:
                continue
            # première sortie de la séance : on s'arrête ici, qu'elle soit alertée ou non
            if flux.loc[t] != ("haussier" if direction == "achat" else "baissier"):
                break
            if abs(bar.close - entry) > max_dist:
                break
            rng = bar.high - bar.low
            vol = min_stop.loc[t]
            if direction == "achat":
                stop = min(bar.low - config.STOP_BUFFER * rng, entry - vol)
                risk = entry - stop
                target = entry + config.OPR_RR * risk
                blocked = entry < prev_high < entry + risk  # NaN (pas de veille) -> False
            else:
                stop = max(bar.high + config.STOP_BUFFER * rng, entry + vol)
                risk = stop - entry
                target = entry - config.OPR_RR * risk
                blocked = entry - risk < prev_low < entry
            if risk > 0 and not blocked:
                notes = [f"Ordre limite sur la borne {'haute' if direction == 'achat' else 'basse'} "
                         f"de l'OPR ({entry:.2f}), on attend le pullback",
                         f"OPR {bottom:.2f} - {top:.2f}",
                         f"Objectif R/R {config.OPR_RR:g}, puis protéger et laisser courir",
                         "Flux H1 " + flux.loc[t] + f" (EMA{config.FLUX_FAST}/{config.FLUX_SLOW})",
                         "Risque conseillé : 1 %"]
                signals.append(Signal(asset, tf, "OPR - sortie", direction, t, round(entry, 2),
                                      round(stop, 2), round(target, 2), config.OPR_RR, "FRTM", notes))
            break
    return signals
