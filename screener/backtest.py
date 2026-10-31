"""Rejoue un détecteur sur l'historique : objectif ou stop touché en premier ?

Usage : python -m screener.backtest [nb_graphiques]
"""

import sys
from pathlib import Path

import pandas as pd

from . import config
from .context import higher_flux, stop_vol
from .data import get_candles
from .detectors import bulles
from .main import DETECTORS

MAX_BARS = 20  # au-delà, le trade est classé « sans issue »
# Unités rejouées : celles des bulles, plus D/H4 pour comparer (python -m screener.backtest N 1H 15M 4H 1D).
TIMEFRAMES = sys.argv[2:] or config.BUBBLE_TIMEFRAMES + config.OPR_TIMEFRAMES


def outcome(df: pd.DataFrame, s) -> tuple[str, float]:
    after = df.loc[df.index > s.time].head(MAX_BARS)
    if s.notes and s.notes[0].startswith("Ordre limite"):  # entrée optimisée : il faut d'abord être exécuté
        filled = (after.low <= s.entry) if s.direction == "achat" else (after.high >= s.entry)
        if not filled.any():
            return "non exécuté", 0.0
        after = after.loc[filled.idxmax():]
    for _, bar in after.iterrows():
        if s.direction == "achat":
            hit_stop, hit_target = bar.low <= s.stop, bar.high >= s.target
        else:
            hit_stop, hit_target = bar.high >= s.stop, bar.low <= s.target
        if hit_stop:  # stop et objectif dans la même bougie : on compte la perte (prudent)
            return "stop", -1.0
        if hit_target:
            return "objectif", s.rr
    return "sans issue", 0.0


def chart(df: pd.DataFrame, s, path: Path):
    import matplotlib
    matplotlib.use("Agg")
    import mplfinance as mpf
    d = bulles.prepare(df)
    pos = d.index.get_loc(s.time)
    win = d.iloc[max(0, pos - 40): pos + 15]
    marker = pd.Series(float("nan"), index=win.index)
    marker[s.time] = s.entry
    plots = [mpf.make_addplot(win[["bb_up", "bb_mid", "bb_low"]], color="#888888", width=0.8),
             mpf.make_addplot(marker, type="scatter", markersize=120,
                              marker="^" if s.direction == "achat" else "v",
                              color="green" if s.direction == "achat" else "red")]
    title = f"{s.asset} {s.tf} {s.pattern} {s.direction} {s.time:%Y-%m-%d %H:%M}"
    mpf.plot(win, type="candle", style="yahoo", addplot=plots, title=title,
             hlines=dict(hlines=[s.stop, s.target], colors=["red", "green"], linestyle="--", linewidths=0.8),
             savefig=str(path))


def main(n_charts: int = 0):
    out = Path("backtest-out")
    out.mkdir(exist_ok=True)
    rows = []
    for asset, ticker in config.ASSETS.items():
        candles = {"1D": get_candles(ticker, "1D"), "1H": get_candles(ticker, "1H")}
        for detect, tf in [(d, tf) for d, tfs in DETECTORS for tf in tfs if tf in TIMEFRAMES]:
            if tf not in candles:
                candles[tf] = get_candles(ticker, tf)
            df, daily = candles[tf], candles["1D"]
            vol = stop_vol(df, daily) if tf != "1D" else None
            for s in detect(df, asset, tf, higher_flux(df, tf, daily, candles["1H"]), vol):
                res, r = outcome(df, s)
                rows.append(dict(asset=asset, tf=tf, pattern=s.pattern, direction=s.direction,
                                 context=s.context, time=s.time, rr=s.rr, result=res, r=r))
                if n_charts and len([x for x in rows if x["asset"] == asset and x["tf"] == tf]) <= n_charts:
                    chart(df, s, out / f"{asset}_{tf}_{s.time:%Y%m%d%H%M}.png")
    res = pd.DataFrame(rows)
    res.to_csv(out / "signaux.csv", index=False)
    done = res[res.result != "sans issue"]
    print(f"{len(res)} signaux, {len(done)} avec issue")
    summary = done.groupby(["pattern", "tf", "context"]).agg(
        signaux=("r", "size"), reussite=("result", lambda x: round((x == "objectif").mean() * 100)),
        R_moyen=("r", lambda x: round(x.mean(), 2)), R_total=("r", lambda x: round(x.sum(), 1)))
    print(summary.to_string())
    print("\nPar actif :")
    print(done.groupby(["asset", "tf"]).agg(signaux=("r", "size"),
          reussite=("result", lambda x: round((x == "objectif").mean() * 100)),
          R_total=("r", lambda x: round(x.sum(), 1))).to_string())


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 0)
