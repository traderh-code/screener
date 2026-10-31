"""Passage du screener : lancé toutes les heures par GitHub Actions.

Chaque passage n'envoie que les signaux des bougies clôturées depuis moins de WINDOW
(l'heure écoulée), pour ne pas renvoyer deux fois le même signal.

Usage : python -m screener.main [--hours N]   (N > 1 pour rejouer les dernières heures en essai)
"""

import argparse
import html

import pandas as pd

from . import config
from .charts import render
from .context import higher_flux
from .data import get_candles
from .detectors import bulles
from .telegram import send_photo

DETECTORS = [bulles.detect]
NY = "America/New_York"


def close_time(t: pd.Timestamp, tf: str) -> pd.Timestamp:
    if tf == "4H":
        return t.tz_convert(NY) + pd.Timedelta(hours=4)
    return pd.Timestamp(t.date(), tz=NY) + pd.Timedelta(hours=17)  # clôture de séance CME


def caption(s) -> str:
    arrow = "🟢 ACHAT" if s.direction == "achat" else "🔴 VENTE"
    tv = config.TRADINGVIEW[s.asset]
    when = close_time(s.time, s.tf).tz_convert("Europe/Paris").strftime("%d/%m %H:%M")
    lines = [
        f"<b>{arrow} · {s.asset} · {s.tf}</b>",
        f"🫧 {html.escape(s.pattern, quote=False)} · <b>{s.context}</b>",
        f"Clôture {when} (Paris)",
        "",
        f"Entrée {s.entry} · Stop {s.stop} · Objectif {s.target} (MM20)",
        f"R/R {s.rr}",
        *[f"• {html.escape(n, quote=False)}" for n in s.notes],
        "",
        f'<a href="https://www.tradingview.com/chart/?symbol={tv}">Graphique TradingView</a> · '
        f'<a href="{config.NOTION[s.pattern]}">Fiche</a>',
    ]
    return "\n".join(lines)


def run(window_hours: float = 1.0) -> int:
    now = pd.Timestamp.now(tz=NY)
    sent = 0
    for asset, ticker in config.ASSETS.items():
        daily = get_candles(ticker, "1D")
        for tf in config.TIMEFRAMES:
            df = daily if tf == "1D" else get_candles(ticker, tf)
            flux = higher_flux(df, tf, daily)
            for detect in DETECTORS:
                for s in detect(df, asset, tf, flux):
                    if now - close_time(s.time, tf) > pd.Timedelta(hours=window_hours):
                        continue
                    name = f"{asset}_{tf}_{s.time:%Y%m%d%H%M}_{s.direction}"
                    send_photo(caption(s), render(df, s), name)
                    sent += 1
    print(f"{sent} signal(s) envoyé(s)")
    return sent


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    # shortcut: fenêtre glissante d'une heure ; un passage GitHub très en retard peut doubler ou rater un signal, ajouter un état mémorisé si ça arrive.
    p.add_argument("--hours", type=float, default=1.0)
    run(p.parse_args().hours)
