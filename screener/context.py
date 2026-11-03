"""Flux de l'unité supérieure (FRTM / RP) : H1 pour un signal M15, journalier pour H1/H4, hebdo pour le journalier."""

from math import sqrt

import pandas as pd

from . import config
from .indicators import atr, ema, value_area


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
        return _last_closed_hour(flux_label(h1["close"]), df).fillna("neutre")
    if tf in ("1H", "4H"):
        return _by_session(flux_label(daily["close"]), df).fillna("neutre")
    weekly = daily["close"].resample("W-FRI").last()
    lab = flux_label(weekly).shift(1)  # semaine précédente, clôturée
    week = df.index.to_period("W-FRI").end_time.normalize()
    lab.index = lab.index.normalize()
    return pd.Series(lab.reindex(week).to_numpy(), index=df.index).fillna("neutre")


def _last_closed_hour(hourly_values: pd.Series, df: pd.DataFrame) -> pd.Series:
    """Valeur de la dernière bougie H1 clôturée avant l'heure de chaque bougie de df.

    En ligne, l'heure en cours n'existe pas dans les données : la valeur d'une heure n'est donc connue qu'à sa clôture.
    """
    known = hourly_values.copy()
    known.index = known.index + pd.Timedelta(hours=1)
    return pd.Series(known.reindex(df.index.floor("h"), method="ffill").to_numpy(), index=df.index)


def _by_session(daily_values: pd.Series, df: pd.DataFrame) -> pd.Series:
    """Valeur de la dernière séance clôturée avant celle de chaque bougie intraday de df.

    En ligne, la séance en cours n'existe pas dans les données journalières : on cherche la séance précédente par date.
    """
    dates = pd.DatetimeIndex(pd.to_datetime(daily_values.index).date)
    # Séance CME : ouvre à 18 h New York la veille de sa date.
    session = pd.DatetimeIndex((df.index.tz_convert("America/New_York") + pd.Timedelta(hours=6)).date)
    pos = dates.searchsorted(session, side="left") - 1
    values = pd.Series(daily_values.to_numpy()[pos.clip(0)], index=df.index)
    return values.where(pos >= 0)


def stop_vol(df: pd.DataFrame, daily: pd.DataFrame, h1: pd.DataFrame | None = None, iv: pd.Series | None = None,
             vix: pd.Series | None = None) -> pd.Series:
    """Stop minimum de Romain (2026) : 20 % de l'expected move du jour, calculé sur les valeurs de la veille.

    iv : indice de volatilité de l'actif ; sans lui, l'ATR 14 journalier en tient lieu.
    vix + h1 : au-dessus de VIX_STRESS, le stop se rapproche de l'ATR H1, atteint à VIX_FULL_ATR.
    shortcut: expected move théorique, sans l'ajustement sur 60 séances de l'indicateur de Romain ; progression linéaire
    du VIX (Romain dit seulement « davantage d'ATR ») ; à revoir si les stops paraissent décalés.
    """
    proxy = atr(daily)
    move = proxy if iv is None else (daily["close"] * iv.reindex(daily.index).ffill() / 100 / sqrt(252)).fillna(proxy)
    base = _by_session(config.STOP_VOL_FRACTION * move, df)
    if vix is None or h1 is None:
        return base
    stress = (vix.reindex(daily.index).ffill() - config.VIX_STRESS) / (config.VIX_FULL_ATR - config.VIX_STRESS)
    weight = _by_session(stress.clip(0, 1), df).fillna(0.0)
    return base + weight * (_last_closed_hour(atr(h1), df) - base).clip(lower=0)


def _session_dates(index: pd.DatetimeIndex) -> pd.Index:
    """Date de séance CME de chaque bougie (le journalier Yahoo est déjà daté par séance)."""
    if index.tz is None:
        return pd.Index(index.date)
    return pd.Index((index.tz_convert("America/New_York") + pd.Timedelta(hours=6)).date)


def _week(dates: pd.Index) -> pd.Index:
    return pd.Index(pd.to_datetime(dates).to_period("W-FRI"))


def levels(df: pd.DataFrame, tf: str, daily: pd.DataFrame, h1: pd.DataFrame) -> pd.DataFrame:
    """Zones connues à chaque bougie de df : plus haut / bas de la veille (intraday seulement), de la semaine
    précédente, et VAH / VAL du volume profile de la semaine précédente (bougies H1)."""
    out = pd.DataFrame(index=df.index)
    if tf != "1D":
        out["plus haut de la veille"] = _by_session(daily["high"], df)
        out["plus bas de la veille"] = _by_session(daily["low"], df)
    weeks = _week(_session_dates(df.index))
    wk = daily.groupby(_week(pd.Index(daily.index.date))).agg(high=("high", "max"), low=("low", "min"))
    va = {w: value_area(g) for w, g in h1.groupby(_week(_session_dates(h1.index)))}
    va = pd.DataFrame(va, index=["val", "poc", "vah"]).T.sort_index()
    for name, col, src in (("plus haut de la semaine passée", "high", wk), ("plus bas de la semaine passée", "low", wk),
                           ("VAH hebdo", "vah", va), ("VAL hebdo", "val", va)):
        prev = src[col].shift(1)  # semaine précédente, terminée
        out[name] = prev.reindex(weeks).to_numpy()
    return out
