"""Méthode du 61,8 de Romain (formation, module 26), en H1 et H4.

- Vague : dernier creux puis dernier sommet (pivots confirmés), d'au moins FIB_MIN_ATR ATR14. Vente : le prix clôture sous le
  61,8 % de la hausse, sans nouveau sommet entre-temps. Achat : l'inverse.
- Ordre limite sur le 61,8 %, on n'entre pas dans l'accélération ; stop derrière le 50 % (au moins le stop vol) ;
  objectif juste avant le 100 % ; R/R >= FIB_MIN_RR, sinon on passe.
- Envoyé en simple information (config.INFO_ONLY) : à l'équilibre au backtest (+4,1 R sur 294 trades, négatif depuis 2025).
- Romain ne joue pas le 61,8 seul : on exige le sens du flux, et aucun plus haut / bas de la veille avant R1.
  Le combo avec une borne d'OPR ou un pivot n'est pas vérifié. La golden zone (zone + signal de bougie) n'est pas codée.
"""

import pandas as pd

from .. import config
from ..indicators import atr
from ..signal import Signal
from .bulles import HIGHER
from .divergences import _pivots

NAME = "Fibonacci 61,8"


def detect(df: pd.DataFrame, asset: str, tf: str, flux: pd.Series | None = None,
           min_stop: pd.Series | None = None, zones: pd.DataFrame | None = None) -> list[Signal]:
    flux = flux if flux is not None else pd.Series("neutre", index=df.index)
    min_stop = (min_stop if min_stop is not None else pd.Series(0.0, index=df.index)).fillna(0.0)
    a = atr(df)
    tops, bottoms = _pivots(df["high"], low=False), _pivots(df["low"], low=True)
    signals = []
    for direction, ends, starts in (("vente", tops, bottoms), ("achat", bottoms, tops)):
        sign = 1 if direction == "vente" else -1  # sens de la vague qui précède le trade
        extreme, origin = (df["high"], df["low"]) if sign == 1 else (df["low"], df["high"])
        for e in ends:
            before = [s for s in starts if s < e]
            if not before:
                continue
            s = before[-1]
            start, end = origin.iloc[s], extreme.iloc[e]
            wave = (end - start) * sign
            if wave < config.FIB_MIN_ATR * a.iloc[e]:
                continue
            level = end - 0.618 * wave * sign
            for t in range(e + config.DIV_PIVOT, min(e + config.FIB_MAX_WAIT + 1, len(df))):
                if (extreme.iloc[e + 1:t + 1] * sign).max() > end * sign:
                    break  # nouvel extrême : la vague continue
                if df["close"].iloc[t] * sign < level * sign:
                    built = _build(df, asset, tf, direction, t, start, wave, level, flux.iloc[t], min_stop.iloc[t], zones)
                    if built:
                        signals.append(built)
                    break
    return sorted(signals, key=lambda x: x.time)


def _build(df, asset, tf, direction, t, start, wave, level, flux, vol, zones):
    if flux != ("baissier" if direction == "vente" else "haussier"):
        return None
    sign = 1 if direction == "vente" else -1
    target = start + config.FIB_TARGET_MARGIN * wave * sign
    if df["close"].iloc[t] * sign <= target * sign:
        return None  # déjà à l'objectif
    fifty = start + 0.5 * wave * sign
    risk = max((fifty + config.FIB_STOP_MARGIN * wave * sign - level) * sign, vol)
    stop = level + risk * sign
    rr = (level - target) * sign / risk
    if rr < config.FIB_MIN_RR:
        return None
    if zones is not None:
        known = zones.iloc[t].dropna()
        # Obstacle : plus haut / bas de la veille entre l'entrée et R1.
        if (((known - level) * -sign > 0) & ((known - level) * -sign < risk)).any():
            return None
    notes = [f"Ordre limite sur le 61,8 % ({level:.2f}), on attend le pullback",
             f"Annuler l'ordre si l'objectif est touché avant ({target:.2f})",
             f"Vague de {wave:.2f} points, stop derrière le 50 % ({fifty:.2f})",
             f"Flux {HIGHER.get(tf, tf)} {flux} (EMA{config.FLUX_FAST}/{config.FLUX_SLOW})",
             "Romain ne joue pas le 61,8 seul : vérifier le combo (borne d'OPR, pivot, rien devant)",
             "Risque conseillé : 1 %"]
    side, way = ("sous le", "de la hausse") if direction == "vente" else ("au-dessus du", "de la baisse")
    text = f"clôture {side} 61,8 % {way} ({level:.2f}), retour possible vers {target:.2f}"
    return Signal(asset, tf, NAME, direction, df.index[t], round(level, 2), round(stop, 2), round(target, 2),
                  round(rr, 2), text, notes)
