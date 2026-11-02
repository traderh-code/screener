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
- Vidéo OPR 3.0 : rien après 13h30 New York (19h30 Paris) ; la bougie qui clôture à 10h New York (news de 16h
  à Paris) est ignorée sans compter comme première sortie ; pas d'alerte si R1 est déjà atteint à la clôture, et
  ordre à annuler si R1 est atteint avant le pullback.
- Pas d'OPR contre une bulle apesanteur H4 clôturée pendant la séance (checklist _BuKVJt_uxQ).
- Le flux « bâtard » (clôture H1 du mauvais côté de la MM50) est déjà exclu : context.flux_label le classe neutre.
"""

import pandas as pd

from .. import config
from ..signal import Signal
from .bulles import zero_g_directions

OPEN = "09:30"
NEWS_BAR = "09:45"  # clôture à 10h New York


def detect(df: pd.DataFrame, asset: str, tf: str, flux: pd.Series | None = None,
           min_stop: pd.Series | None = None, h4: pd.DataFrame | None = None) -> list[Signal]:
    if asset not in config.OPR_MAX_DISTANCE or tf != "15M":
        return []
    flux = flux if flux is not None else pd.Series("neutre", index=df.index)
    min_stop = (min_stop if min_stop is not None else pd.Series(0.0, index=df.index)).fillna(0.0)
    max_dist = config.OPR_MAX_DISTANCE[asset]
    use_h4 = h4 is not None and config.OPR_H4_CONTRA
    contra = zero_g_directions(h4, pd.Timedelta(hours=4)) if use_h4 else None
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
        session = bars[(hm > OPEN) & (hm < config.OPR_LAST_ENTRY) & ~(config.OPR_SKIP_NEWS & (hm == NEWS_BAR))]
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
            # Bulles H4 de la séance CME (ouverte à 18 h New York la veille), clôturées à la fin de la bougie.
            if contra is not None:
                seen = contra[(contra.index > pd.Timestamp(day, tz="America/New_York") - pd.Timedelta(hours=6))
                              & (contra.index <= t + pd.Timedelta(minutes=15))]
                if (seen == ("vente" if direction == "achat" else "achat")).any():
                    break
            rng = bar.high - bar.low
            vol = min_stop.loc[t]
            if direction == "achat":
                stop = min(bar.low - config.STOP_BUFFER * rng, entry - vol)
                risk = entry - stop
                target = entry + config.OPR_RR * risk
                blocked = entry < prev_high < entry + risk  # NaN (pas de veille) -> False
                r1, reached = entry + risk, bar.high >= entry + risk
            else:
                stop = max(bar.high + config.STOP_BUFFER * rng, entry + vol)
                risk = stop - entry
                target = entry - config.OPR_RR * risk
                blocked = entry - risk < prev_low < entry
                r1, reached = entry - risk, bar.low <= entry - risk
            if risk > 0 and not blocked and not (config.OPR_CANCEL_R1 and reached):
                notes = [f"Ordre limite sur la borne {'haute' if direction == 'achat' else 'basse'} "
                         f"de l'OPR ({entry:.2f}), on attend le pullback",
                         f"Annuler l'ordre si {r1:.2f} (R1) est touché avant le pullback",
                         f"OPR {bottom:.2f} - {top:.2f}",
                         f"Objectif R/R {config.OPR_RR:g}, puis protéger et laisser courir",
                         "Flux H1 " + flux.loc[t] + f" (EMA{config.FLUX_FAST}/{config.FLUX_SLOW})",
                         "Risque conseillé : 1 %"]
                signals.append(Signal(asset, tf, "OPR - sortie", direction, t, round(entry, 2),
                                      round(stop, 2), round(target, 2), config.OPR_RR, "FRTM", notes))
            break
    return signals
