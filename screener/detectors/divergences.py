"""Divergences RSI (fiche Notion « Divergences RSI », règles du coaching du 22 oct. 2026).

- Haussière : deux creux de prix A puis B, B plus bas que A, mais RSI(14) plus haut en B qu'en A.
  Baissière : l'inverse sur deux sommets.
- Entre 5 et 18 bougies entre A et B.
- Bruit = point extrême du RSI entre A et B (plus haut pour une haussière) : <= 40 en haussière,
  >= 60 en baissière.
- Signal à la clôture de la bougie qui fait casser le bruit au RSI ; objectif 50 % du mouvement qui
  précède la divergence ; stop sous la mèche de B (au moins le stop vol) ; R/R >= MIN_RR (hors plan).
- Les creux / sommets sont des pivots de PIVOT bougies de chaque côté ; un pivot n'est connu que
  PIVOT bougies après, d'où un signal parfois un peu plus tardif que chez Romain.
"""

import pandas as pd

from .. import config
from ..indicators import rsi
from ..signal import Signal
from .bulles import HIGHER


def _pivots(s: pd.Series, low: bool) -> list[int]:
    p = config.DIV_PIVOT
    w = s.rolling(2 * p + 1, center=True)
    ext = w.min() if low else w.max()
    return [i for i in range(p, len(s) - p) if s.iloc[i] == ext.iloc[i]]


def detect(df: pd.DataFrame, asset: str, tf: str, flux: pd.Series | None = None,
           min_stop: pd.Series | None = None) -> list[Signal]:
    flux = flux if flux is not None else pd.Series("neutre", index=df.index)
    min_stop = (min_stop if min_stop is not None else pd.Series(0.0, index=df.index)).fillna(0.0)
    r = rsi(df["close"], config.RSI_PERIOD)
    signals = []
    for direction, low in (("achat", True), ("vente", False)):
        price = df["low"] if low else df["high"]
        piv = _pivots(price, low)
        for a, b in zip(piv, piv[1:]):
            if not config.DIV_MIN_BARS <= b - a <= config.DIV_MAX_BARS:
                continue
            new_extreme = price.iloc[b] < price.iloc[a] if low else price.iloc[b] > price.iloc[a]
            rsi_diverges = r.iloc[b] > r.iloc[a] if low else r.iloc[b] < r.iloc[a]
            if not (new_extreme and rsi_diverges):
                continue
            between = r.iloc[a:b + 1]
            noise = between.max() if low else between.min()
            if (low and noise > config.DIV_NOISE) or (not low and noise < 100 - config.DIV_NOISE):
                continue
            # Première clôture (pivot B confirmé) où le RSI casse le bruit, sans nouvel extrême sous / sur B.
            for t in range(b + config.DIV_PIVOT, min(b + config.DIV_PIVOT + config.DIV_MAX_WAIT, len(df))):
                if (low and df["low"].iloc[b + 1:t + 1].min() < price.iloc[b]) or \
                   (not low and df["high"].iloc[b + 1:t + 1].max() > price.iloc[b]):
                    break
                if (low and r.iloc[t] > noise) or (not low and r.iloc[t] < noise):
                    s = _build(df, asset, tf, direction, flux.iloc[t], t, a, b, noise, min_stop.iloc[t])
                    if s:
                        signals.append(s)
                    break
    return sorted(signals, key=lambda s: s.time)


def _build(df, asset, tf, direction, flux, t, a, b, noise, vol):
    entry = df["close"].iloc[t]
    start = max(0, a - config.DIV_MAX_BARS)
    if direction == "achat":
        extreme = df["low"].iloc[b]
        swing = df["high"].iloc[start:a + 1].max()  # départ du mouvement baissier qui précède la divergence
        target = extreme + 0.5 * (swing - extreme)
        stop = min(extreme - config.STOP_BUFFER * (df["high"].iloc[b] - extreme), entry - vol)
        risk, reward = entry - stop, target - entry
    else:
        extreme = df["high"].iloc[b]
        swing = df["low"].iloc[start:a + 1].min()
        target = extreme - 0.5 * (extreme - swing)
        stop = max(extreme + config.STOP_BUFFER * (extreme - df["low"].iloc[b]), entry + vol)
        risk, reward = stop - entry, entry - target
    if risk <= 0 or reward <= 0 or reward / risk < config.MIN_RR:
        return None
    in_flux = (direction == "achat" and flux == "haussier") or (direction == "vente" and flux == "baissier")
    notes = [f"Divergence de {b - a} bougies, bruit RSI {noise:.0f}",
             "Objectif : 50 % du mouvement précédent (la divergence peut aller à 100 %)",
             f"Flux {HIGHER.get(tf, tf)} {flux} (EMA{config.FLUX_FAST}/{config.FLUX_SLOW})",
             "Risque conseillé : 1 %" if in_flux else "Risque conseillé : 0,5 %"]
    return Signal(asset, tf, "Divergence RSI", direction, df.index[t], round(entry, 2), round(stop, 2),
                  round(target, 2), round(reward / risk, 2), "FRTM" if in_flux else "RP", notes)
