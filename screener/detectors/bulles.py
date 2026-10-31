"""Bulles de Bollinger (fiche Notion « Bulles (bulle apesanteur) », mémo + leçon 16).

- Bulle : le corps (ouverture ET clôture) est entièrement hors d'une bande de Bollinger (20, 2).
- Apesanteur : toute la bougie, mèches comprises, est hors de la bande -> signal dès sa clôture.
- Classique : la mèche touche la bande -> signal à la clôture de la bougie suivante si elle
  réintègre la bande et est de la couleur du trade.
- Pas de signal après une série de plus de MAX_CONSECUTIVE_BUBBLES bulles (marché en accélération).
- Stop au-delà de la mèche, objectif la MM20, TP1 la MM7 pour l'apesanteur.
"""

import pandas as pd

from .. import config
from ..indicators import bollinger, sma
from ..signal import Signal


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    out = df.join(bollinger(df["close"], config.BB_PERIOD, config.BB_STD))
    out["mm7"] = sma(df["close"], 7)
    body_lo = out[["open", "close"]].min(axis=1)
    body_hi = out[["open", "close"]].max(axis=1)
    out["bubble_up"] = body_lo > out["bb_up"]     # bulle au-dessus de la bande haute -> vente
    out["bubble_down"] = body_hi < out["bb_low"]  # bulle sous la bande basse -> achat
    out["zero_g_up"] = out["low"] > out["bb_up"]
    out["zero_g_down"] = out["high"] < out["bb_low"]
    return out


def _streak(flags: pd.Series) -> pd.Series:
    """Nombre de bulles consécutives se terminant sur chaque bougie."""
    groups = (~flags).cumsum()
    return flags.astype(int).groupby(groups).cumsum()


HIGHER = {"4H": "journalier", "1D": "hebdo"}


def _build(asset, tf, pattern, direction, flux, time, entry, stop, target, notes):
    risk = abs(entry - stop)
    reward = (target - entry) if direction == "achat" else (entry - target)
    if risk <= 0 or reward <= 0:
        return None
    rr = reward / risk
    if rr < config.MIN_RR:
        return None
    in_flux = (direction == "achat" and flux == "haussier") or (direction == "vente" and flux == "baissier")
    context = "FRTM" if in_flux else "RP"
    notes = notes + [f"Flux {HIGHER.get(tf, tf)} {flux} (EMA{config.FLUX_FAST}/{config.FLUX_SLOW})",
                     "Risque conseillé : 1 %" if in_flux else "Risque conseillé : 0,5 %"]
    return Signal(asset, tf, pattern, direction, time, round(entry, 2), round(stop, 2),
                  round(target, 2), round(rr, 2), context, notes)


def detect(df: pd.DataFrame, asset: str, tf: str, flux: pd.Series | None = None) -> list[Signal]:
    """Toutes les bulles de l'historique (la dernière bougie = la plus récente clôturée).

    flux : flux de l'unité supérieure aligné sur df (voir context.higher_flux) ; à défaut, neutre.
    """
    d = prepare(df)
    flux = flux if flux is not None else pd.Series("neutre", index=df.index)
    up_streak = _streak(d["bubble_up"])
    down_streak = _streak(d["bubble_down"])
    signals = []
    idx = d.index
    for i in range(config.BB_PERIOD, len(d)):
        row = d.iloc[i]
        rng = row.high - row.low

        # Apesanteur : signal à la clôture de la bulle elle-même.
        for flag, streak, direction in (("zero_g_up", up_streak, "vente"), ("zero_g_down", down_streak, "achat")):
            if row[flag] and streak.iloc[i] <= config.MAX_CONSECUTIVE_BUBBLES:
                if direction == "vente":
                    stop = row.high + config.STOP_BUFFER * rng
                else:
                    stop = row.low - config.STOP_BUFFER * rng
                s = _build(asset, tf, "Bulle apesanteur", direction, flux.iloc[i], idx[i], row.close, stop,
                           row.bb_mid, [f"TP1 MM7 : {row.mm7:.2f} (puis stop au point d'entrée)", "TP2 MM20"])
                if s:
                    signals.append(s)

        # Classique : la bougie précédente est une bulle (non apesanteur), celle-ci réintègre.
        prev = d.iloc[i - 1]
        if prev.bubble_up and not prev.zero_g_up and up_streak.iloc[i - 1] <= config.MAX_CONSECUTIVE_BUBBLES:
            if row.close < row.bb_up and row.close < row.open:
                stop = max(prev.high, row.high) + config.STOP_BUFFER * (prev.high - prev.low)
                s = _build(asset, tf, "Bulle classique", "vente", flux.iloc[i], idx[i], row.close, stop, row.bb_mid,
                           ["Bougie rouge de réintégration"])
                if s:
                    signals.append(s)
        if prev.bubble_down and not prev.zero_g_down and down_streak.iloc[i - 1] <= config.MAX_CONSECUTIVE_BUBBLES:
            if row.close > row.bb_low and row.close > row.open:
                stop = min(prev.low, row.low) - config.STOP_BUFFER * (prev.high - prev.low)
                s = _build(asset, tf, "Bulle classique", "achat", flux.iloc[i], idx[i], row.close, stop, row.bb_mid,
                           ["Bougie verte de réintégration"])
                if s:
                    signals.append(s)
    return signals
