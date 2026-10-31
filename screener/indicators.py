"""Indicateurs calculés comme sur TradingView / ProRealTime."""

import pandas as pd


def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n).mean()


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def bollinger(close: pd.Series, n: int = 20, k: float = 2.0) -> pd.DataFrame:
    mid = sma(close, n)
    std = close.rolling(n).std(ddof=0)  # écart-type de population, comme TradingView
    return pd.DataFrame({"bb_mid": mid, "bb_up": mid + k * std, "bb_low": mid - k * std})


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + gain / loss)


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    prev = df["close"].shift(1)
    tr = pd.concat([df["high"] - df["low"], (df["high"] - prev).abs(), (df["low"] - prev).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()  # lissage de Wilder, comme TradingView


def value_area(bars: pd.DataFrame, bins: int = 200, share: float = 0.70) -> tuple[float, float, float]:
    """(VAL, POC, VAH) du volume profile des bougies : le volume de chaque bougie est réparti uniformément
    entre son plus bas et son plus haut ; value area = 70 % du volume, étendue depuis le POC."""
    import numpy as np
    lo, hi = bars["low"].min(), bars["high"].max()
    edges = np.linspace(lo, hi, bins + 1)
    mids = (edges[:-1] + edges[1:]) / 2
    vol = np.zeros(bins)
    for low, high, v in zip(bars["low"], bars["high"], bars["volume"]):
        inside = (mids >= low) & (mids <= high)
        if inside.any() and v > 0:
            vol[inside] += v / inside.sum()
    poc = int(vol.argmax())
    a = b = poc
    total, acc = vol.sum(), vol[poc]
    while acc < share * total and (a > 0 or b < bins - 1):
        below = vol[a - 1] if a > 0 else -1
        above = vol[b + 1] if b < bins - 1 else -1
        if above >= below:
            b += 1
            acc += vol[b]
        else:
            a -= 1
            acc += vol[a]
    return float(edges[a]), float(mids[poc]), float(edges[b + 1])
