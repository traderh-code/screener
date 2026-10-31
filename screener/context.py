"""Flux de l'unité supérieure (FRTM / RP) : journalier pour un signal H4, hebdo pour un signal journalier."""

import pandas as pd

from . import config
from .indicators import ema


def flux_label(close: pd.Series) -> pd.Series:
    fast, slow = ema(close, config.FLUX_FAST), ema(close, config.FLUX_SLOW)
    lab = pd.Series("neutre", index=close.index)
    lab[(close > fast) & (fast > slow)] = "haussier"
    lab[(close < fast) & (fast < slow)] = "baissier"
    return lab


def higher_flux(df: pd.DataFrame, tf: str, daily: pd.DataFrame) -> pd.Series:
    """Flux de l'unité supérieure connu à chaque bougie de df (seules les bougies supérieures clôturées comptent)."""
    if tf == "4H":
        lab = flux_label(daily["close"]).shift(1)  # flux de la séance précédente, déjà clôturée
        lab.index = pd.to_datetime(lab.index).date
        # Séance CME : ouvre à 18 h New York la veille de sa date.
        session = (df.index.tz_convert("America/New_York") + pd.Timedelta(hours=6)).date
        return pd.Series(lab.reindex(session).to_numpy(), index=df.index).fillna("neutre")
    weekly = daily["close"].resample("W-FRI").last()
    lab = flux_label(weekly).shift(1)  # semaine précédente, clôturée
    week = df.index.to_period("W-FRI").end_time.normalize()
    lab.index = lab.index.normalize()
    return pd.Series(lab.reindex(week).to_numpy(), index=df.index).fillna("neutre")
