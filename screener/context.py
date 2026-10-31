"""Flux de l'unité supérieure (FRTM / RP) : H1 pour un signal M15, journalier pour H1/H4, hebdo pour le journalier."""

import pandas as pd

from . import config
from .indicators import atr, ema


def flux_label(close: pd.Series) -> pd.Series:
    fast, slow = ema(close, config.FLUX_FAST), ema(close, config.FLUX_SLOW)
    lab = pd.Series("neutre", index=close.index)
    lab[(close > fast) & (fast > slow)] = "haussier"
    lab[(close < fast) & (fast < slow)] = "baissier"
    return lab


def higher_flux(df: pd.DataFrame, tf: str, daily: pd.DataFrame, h1: pd.DataFrame | None = None) -> pd.Series:
    """Flux de l'unité supérieure connu à chaque bougie de df (seules les bougies supérieures clôturées comptent).

    15M -> flux H1 (référence de Romain pour l'intraday), 1H et 4H -> journalier, 1D -> hebdo.
    """
    if tf == "15M":
        lab = flux_label(h1["close"]).shift(1)  # heure précédente, déjà clôturée
        return pd.Series(lab.reindex(df.index.floor("h")).to_numpy(), index=df.index).fillna("neutre")
    if tf in ("1H", "4H"):
        return _by_session(flux_label(daily["close"]), df).fillna("neutre")
    weekly = daily["close"].resample("W-FRI").last()
    lab = flux_label(weekly).shift(1)  # semaine précédente, clôturée
    week = df.index.to_period("W-FRI").end_time.normalize()
    lab.index = lab.index.normalize()
    return pd.Series(lab.reindex(week).to_numpy(), index=df.index).fillna("neutre")


def _by_session(daily_values: pd.Series, df: pd.DataFrame) -> pd.Series:
    """Valeur de la séance précédente (déjà clôturée) pour chaque bougie intraday de df."""
    v = daily_values.shift(1)
    v.index = pd.to_datetime(v.index).date
    # Séance CME : ouvre à 18 h New York la veille de sa date.
    session = (df.index.tz_convert("America/New_York") + pd.Timedelta(hours=6)).date
    return pd.Series(v.reindex(session).to_numpy(), index=df.index)


def stop_vol(df: pd.DataFrame, daily: pd.DataFrame) -> pd.Series:
    """Stop minimum de Romain (2026) : 20 % de l'expected move du jour.

    shortcut: l'expected move (volatilité implicite VIX1D/VXN/VXD, ajustée sur 60 séances) est approché
    par l'ATR 14 journalier de la veille ; brancher les indices de volatilité si les stops paraissent décalés.
    """
    return _by_session(config.STOP_VOL_FRACTION * atr(daily), df)
