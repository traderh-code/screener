"""Récupération des bougies (Yahoo Finance) et construction du H4."""

import warnings

import pandas as pd
import yfinance as yf

from . import config

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", message=".*inplace.*")

COLUMNS = ["open", "high", "low", "close", "volume"]


def _download(ticker: str, period: str, interval: str) -> pd.DataFrame:
    df = yf.download(ticker, period=period, interval=interval, progress=False,
                     auto_adjust=False, multi_level_index=False)
    if df.empty:
        raise RuntimeError(f"Aucune donnée Yahoo pour {ticker} ({interval})")
    df = df.rename(columns=str.lower)[COLUMNS]
    return df.dropna(subset=["open", "high", "low", "close"])


def get_index(ticker: str | None) -> pd.Series | None:
    """Clôtures journalières d'un indice de volatilité ; None si Yahoo ne répond pas (le stop retombe sur l'ATR)."""
    if not ticker:
        return None
    try:
        return _download(ticker, "5y", "1d")["close"]
    except Exception as e:
        print(f"Indice {ticker} indisponible : {type(e).__name__}")
        return None


def daily_from_h1(h1: pd.DataFrame) -> pd.DataFrame:
    """Journalier par séance CME (ouverte à 18 h New York la veille de sa date), daté comme le journalier Yahoo."""
    ny = h1.tz_convert("America/New_York")
    session = pd.DatetimeIndex((ny.index + pd.Timedelta(hours=6)).date, name="Date")
    return ny.groupby(session).agg(open=("open", "first"), high=("high", "max"), low=("low", "min"),
                                   close=("close", "last"), volume=("volume", "sum"))


def resample_h4(h1: pd.DataFrame) -> pd.DataFrame:
    """H4 calé sur la session CME (ouverture 18 h New York) : 18-22, 22-02, 02-06, 06-10, 10-14, 14-18."""
    h1 = h1.tz_convert("America/New_York")
    h4 = h1.resample("4h", offset="2h", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
    return h4.dropna(subset=["open", "close"])


# Durée des bougies intraday (le journalier clôture à 17 h New York, voir drop_unclosed).
DURATION = {"15M": pd.Timedelta(minutes=15), "1H": pd.Timedelta(hours=1), "4H": pd.Timedelta(hours=4)}


def drop_unclosed(df: pd.DataFrame, tf: str, now: pd.Timestamp | None = None) -> pd.DataFrame:
    """Retire la dernière bougie si elle n'est pas encore clôturée."""
    if df.empty:
        return df
    now = now or pd.Timestamp.now(tz="America/New_York")
    if tf in DURATION:
        closed = df.index[-1] + DURATION[tf] <= now
    else:
        # Bougie journalière Yahoo = date de séance ; la séance CME clôture à 17 h New York.
        session_close = pd.Timestamp(df.index[-1].date(), tz="America/New_York") + pd.Timedelta(hours=17)
        closed = session_close <= now
    return df if closed else df.iloc[:-1]


def get_candles(ticker: str, tf: str) -> pd.DataFrame:
    if tf == "1D":
        if ticker in config.DAILY_FROM_H1:
            return drop_unclosed(daily_from_h1(_download(ticker, "729d", "1h")), "1D")
        return drop_unclosed(_download(ticker, "5y", "1d"), "1D")
    if tf == "4H":
        # Yahoo limite l'horaire à 730 jours.
        return drop_unclosed(resample_h4(_download(ticker, "729d", "1h")), "4H")
    if tf == "1H":
        return drop_unclosed(_download(ticker, "729d", "1h").tz_convert("America/New_York"), "1H")
    if tf == "15M":
        # Yahoo limite le 15 minutes à 60 jours.
        return drop_unclosed(_download(ticker, "59d", "15m").tz_convert("America/New_York"), "15M")
    raise ValueError(f"Unité de temps inconnue : {tf}")
