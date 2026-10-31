"""Récupération des bougies (Yahoo Finance) et construction du H4."""

import warnings

import pandas as pd
import yfinance as yf

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


def resample_h4(h1: pd.DataFrame) -> pd.DataFrame:
    """H4 calé sur la session CME (ouverture 18 h New York) : 18-22, 22-02, 02-06, 06-10, 10-14, 14-18."""
    h1 = h1.tz_convert("America/New_York")
    h4 = h1.resample("4h", offset="2h", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
    return h4.dropna(subset=["open", "close"])


def drop_unclosed(df: pd.DataFrame, tf: str, now: pd.Timestamp | None = None) -> pd.DataFrame:
    """Retire la dernière bougie si elle n'est pas encore clôturée."""
    if df.empty:
        return df
    now = now or pd.Timestamp.now(tz="America/New_York")
    if tf == "4H":
        closed = df.index[-1] + pd.Timedelta(hours=4) <= now
    else:
        # Bougie journalière Yahoo = date de séance ; la séance CME clôture à 17 h New York.
        session_close = pd.Timestamp(df.index[-1].date(), tz="America/New_York") + pd.Timedelta(hours=17)
        closed = session_close <= now
    return df if closed else df.iloc[:-1]


def get_candles(ticker: str, tf: str) -> pd.DataFrame:
    if tf == "1D":
        return drop_unclosed(_download(ticker, "5y", "1d"), "1D")
    if tf == "4H":
        # Yahoo limite l'horaire à 730 jours.
        return drop_unclosed(resample_h4(_download(ticker, "729d", "1h")), "4H")
    raise ValueError(f"Unité de temps inconnue : {tf}")
