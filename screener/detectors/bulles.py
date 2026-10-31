"""Bulles apesanteur (fiche Notion « Bulles (bulle apesanteur) », règles du coaching du 22 oct. 2026).

- Bulle apesanteur : toute la bougie, mèches comprises, est hors d'une bande de Bollinger (20, 2),
  avec le corps de la couleur du retournement (vert pour un achat, rouge pour une vente).
  Les bulles classiques (mèche qui touche la bande) ne font plus partie de la méthode depuis 2026.
- Signal à la clôture de la bulle ; stop au-delà de la mèche ; objectif la MM20 au moment de la bulle.
- R/R : le screener ne connaît pas le plan du matin, il applique la règle « hors plan » (MIN_RR).
  Si le R/R à la clôture n'atteint que PLAN_RR, on tente l'entrée optimisée : ordre limite au 50 %
  de la bulle, même stop ; le signal n'est envoyé que si ce R/R optimisé atteint MIN_RR.
- Pas de signal après une série de plus de MAX_CONSECUTIVE_BUBBLES bulles (marché en accélération).
"""

import pandas as pd

from .. import config
from ..indicators import bollinger, sma
from ..signal import Signal


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    out = df.join(bollinger(df["close"], config.BB_PERIOD, config.BB_STD))
    out["mm7"] = sma(df["close"], 7)  # affichée sur le graphique
    body_lo = out[["open", "close"]].min(axis=1)
    body_hi = out[["open", "close"]].max(axis=1)
    out["bubble_up"] = body_lo > out["bb_up"]     # corps au-dessus de la bande haute
    out["bubble_down"] = body_hi < out["bb_low"]  # corps sous la bande basse
    out["zero_g_up"] = out["low"] > out["bb_up"]
    out["zero_g_down"] = out["high"] < out["bb_low"]
    return out


def _streak(flags: pd.Series) -> pd.Series:
    """Nombre de bulles consécutives se terminant sur chaque bougie."""
    groups = (~flags).cumsum()
    return flags.astype(int).groupby(groups).cumsum()


HIGHER = {"4H": "journalier", "1D": "hebdo"}


def _rr(direction, entry, stop, target):
    risk = abs(entry - stop)
    reward = (target - entry) if direction == "achat" else (entry - target)
    return reward / risk if risk > 0 and reward > 0 else 0.0


def _build(asset, tf, direction, flux, time, row, stop):
    target = row.bb_mid
    entry, notes = row.close, ["Entrée à la clôture de la bulle"]
    rr = _rr(direction, entry, stop, target)
    if config.PLAN_RR <= rr < config.MIN_RR:
        entry = (row.high + row.low) / 2
        rr = _rr(direction, entry, stop, target)
        notes = ["Ordre limite au 50 % de la bulle (entrée optimisée, peut ne pas être exécuté)"]
    if rr < config.MIN_RR:
        return None
    in_flux = (direction == "achat" and flux == "haussier") or (direction == "vente" and flux == "baissier")
    context = "FRTM" if in_flux else "RP"
    notes = notes + [f"Objectif MM20 : {target:.2f}",
                     f"Flux {HIGHER.get(tf, tf)} {flux} (EMA{config.FLUX_FAST}/{config.FLUX_SLOW})",
                     "Risque conseillé : 1 %" if in_flux else "Risque conseillé : 0,5 %"]
    return Signal(asset, tf, "Bulle apesanteur", direction, time, round(entry, 2), round(stop, 2),
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
        if row.zero_g_up and row.close < row.open and up_streak.iloc[i] <= config.MAX_CONSECUTIVE_BUBBLES:
            s = _build(asset, tf, "vente", flux.iloc[i], idx[i], row, row.high + config.STOP_BUFFER * rng)
        elif row.zero_g_down and row.close > row.open and down_streak.iloc[i] <= config.MAX_CONSECUTIVE_BUBBLES:
            s = _build(asset, tf, "achat", flux.iloc[i], idx[i], row, row.low - config.STOP_BUFFER * rng)
        else:
            continue
        if s:
            signals.append(s)
    return signals
