"""Vague de Wolfe (formation, modules 52 et 53), en M15 et H1.

- Haussière : creux 1, sommet 2, creux 3, sommet 4, creux 5, sur les clôtures (« tracé sur les corps »), sans autre
  pivot entre eux. 1, 3, 5 sur une droite baissière ; le point 4 entre les points 1 et 2 ; une baisse avant le point 1
  (sommet précédent au-dessus du point 2) ; le point 5 ne dépasse pas la parallèle à 2-4 posée sur le point 1.
- Le point 5 dépasse la droite 1-3 ; signal à la première clôture qui la réintègre, sans nouveau plus bas.
- Stop au-delà de la mèche du point 5 (au moins le stop vol) ; objectif TP1 = niveau du point 4 ; R/R >= WOLFE_MIN_RR.
  Baissière : le miroir. Romain la juge non prioritaire en 2026 : simple information (config.INFO_ONLY), un seul
  signal en 2 ans sur les 5 actifs au backtest du 13/11/2026.
"""

import pandas as pd

from .. import config
from ..indicators import atr
from ..signal import Signal
from .bulles import HIGHER
from .divergences import _pivots

NAME = "Vague de Wolfe"


def _line(p, q, x):
    """Valeur en x de la droite qui passe par les points p et q, donnés en (indice, prix)."""
    return p[1] + (q[1] - p[1]) * (x - p[0]) / (q[0] - p[0])


def _zigzag(close: pd.Series) -> list[tuple[int, str]]:
    """Pivots alternés : deux creux (sommets) de suite sans sommet (creux) entre eux, on garde le plus extrême."""
    piv = []
    for i, kind in sorted([(i, "bas") for i in _pivots(close, low=True)] + [(i, "haut") for i in _pivots(close, low=False)]):
        if piv and piv[-1][1] == kind:
            if (close.iloc[i] < close.iloc[piv[-1][0]]) == (kind == "bas"):
                piv[-1] = (i, kind)
            continue
        piv.append((i, kind))
    return piv


def detect(df: pd.DataFrame, asset: str, tf: str, flux: pd.Series | None = None,
           min_stop: pd.Series | None = None) -> list[Signal]:
    flux = flux if flux is not None else pd.Series("neutre", index=df.index)
    min_stop = (min_stop if min_stop is not None else pd.Series(0.0, index=df.index)).fillna(0.0)
    close, a = df["close"], atr(df)
    piv = _zigzag(close)
    signals = []
    for k in range(5, len(piv)):
        kinds = [kind for _, kind in piv[k - 5:k + 1]]
        if kinds not in (["haut", "bas", "haut", "bas", "haut", "bas"], ["bas", "haut", "bas", "haut", "bas", "haut"]):
            continue  # pivots qui n'alternent pas : plus de deux sommets (creux) entre 1 et 5
        buy = kinds[-1] == "bas"
        sign = 1 if buy else -1  # achat : les creux 1, 3, 5 descendent
        prior, *five = [(i, close.iloc[i]) for i, _ in piv[k - 5:k + 1]]
        p1, p2, p3, p4, p5 = five
        if not (p3[1] * sign < p1[1] * sign and p5[1] * sign < p3[1] * sign
                and p1[1] * sign < p4[1] * sign < p2[1] * sign and prior[1] * sign > p2[1] * sign):
            continue
        if (p2[1] - p1[1]) * sign < config.WOLFE_MIN_ATR * a.iloc[p2[0]]:
            continue
        if p5[1] * sign >= _line(p1, p3, p5[0]) * sign:
            continue  # le point 5 doit dépasser la droite 1-3
        guard = p1[1] + (p4[1] - p2[1]) * (p5[0] - p1[0]) / (p4[0] - p2[0])  # parallèle à 2-4 posée sur 1
        if p5[1] * sign < guard * sign:
            continue
        for t in range(p5[0] + config.DIV_PIVOT, min(p5[0] + config.WOLFE_MAX_WAIT + 1, len(df))):
            if (close.iloc[p5[0] + 1:t + 1] * sign).min() < p5[1] * sign:
                break  # nouvel extrême au-delà du point 5 : invalidation
            if close.iloc[t] * sign > _line(p1, p3, t) * sign:
                built = _build(df, asset, tf, buy, t, p2, p4, p5, flux.iloc[t], min_stop.iloc[t])
                if built:
                    signals.append(built)
                break
    return sorted(signals, key=lambda s: s.time)


def _build(df, asset, tf, buy, t, p2, p4, p5, flux, vol):
    entry, sign = df["close"].iloc[t], 1 if buy else -1
    bar = df.iloc[p5[0]]
    wick = bar.low if buy else bar.high
    risk = max((entry - wick) * sign + config.STOP_BUFFER * (bar.high - bar.low), vol)
    stop, target = entry - risk * sign, p4[1]
    rr = (target - entry) * sign / risk if risk > 0 else 0.0
    if rr < config.WOLFE_MIN_RR:
        return None
    direction = "achat" if buy else "vente"
    in_flux = flux == ("haussier" if buy else "baissier")
    notes = ["Entrée à la clôture qui réintègre la droite 1-3-5",
             f"TP1 point 4 ({p4[1]:.2f}), TP2 point 2 ({p2[1]:.2f}), TP3 la droite 1-4",
             f"Flux {HIGHER.get(tf, tf)} {flux} (EMA{config.FLUX_FAST}/{config.FLUX_SLOW})",
             "Setup non prioritaire chez Romain en 2026 : seulement s'il est propre et sur une zone",
             "Risque conseillé : 1 %" if in_flux else "Risque conseillé : 0,5 %"]
    text = f"réintégration de la droite 1-3-5, retour possible vers le point 4 ({p4[1]:.2f})"
    return Signal(asset, tf, NAME, direction, df.index[t], round(float(entry), 2), round(float(stop), 2),
                  round(float(target), 2), round(rr, 2), text, notes)
