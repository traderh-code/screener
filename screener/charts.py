"""Image d'un signal, style sombre façon TradingView : bougies, entrée, stop, objectif (+ Bollinger et MM7 pour les bulles)."""

import io

import matplotlib

matplotlib.use("Agg")
import mplfinance as mpf  # noqa: E402
import pandas as pd  # noqa: E402

from .detectors import bulles  # noqa: E402

STYLE = mpf.make_mpf_style(
    base_mpf_style="nightclouds",
    marketcolors=mpf.make_marketcolors(up="#26a69a", down="#ef5350", edge="inherit", wick="inherit"),
    facecolor="#131722", figcolor="#131722", gridcolor="#2a2e39", gridstyle="-",
    rc={"axes.labelcolor": "#d1d4dc", "xtick.color": "#d1d4dc", "ytick.color": "#d1d4dc"},
)


def render(df: pd.DataFrame, s, bars: int = 80) -> bytes:
    d = bulles.prepare(df)
    pos = d.index.get_loc(s.time)
    win = d.iloc[max(0, pos - bars + 1): pos + 1]
    if getattr(win.index, "tz", None) is not None:
        win = win.tz_localize(None)  # mplfinance n'accepte pas les dates avec fuseau
    buy = s.direction == "achat"
    marker = pd.Series(float("nan"), index=win.index)
    marker.iloc[-1] = s.entry
    plots = [mpf.make_addplot(marker, type="scatter", markersize=160, marker="^" if buy else "v",
                              color="#26a69a" if buy else "#ef5350")]
    if s.pattern.startswith("Bulle"):
        plots += [mpf.make_addplot(win[["bb_up", "bb_low"]], color="#2962ff", width=0.8),
                  mpf.make_addplot(win["bb_mid"], color="#ff9800", width=1.0),
                  mpf.make_addplot(win["mm7"], color="#d1d4dc", width=0.6, linestyle=":")]
    buf = io.BytesIO()
    mpf.plot(win[["open", "high", "low", "close", "volume"]], type="candle", style=STYLE, addplot=plots,
             title=f"{s.asset} {s.tf} - {s.pattern} ({s.direction})", figsize=(11, 6), tight_layout=True,
             datetime_format="%d/%m" if s.tf == "1D" else "%d/%m %H:%M",
             hlines=dict(hlines=[s.entry, s.stop, s.target], colors=["#d1d4dc", "#ef5350", "#26a69a"],
                         linestyle="--", linewidths=0.9),
             savefig=dict(fname=buf, dpi=110, format="png"))
    return buf.getvalue()
