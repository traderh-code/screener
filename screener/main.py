"""Passage du screener : lancé tous les quarts d'heure par GitHub Actions (bulles H1/M15, OPR M15, divergences D/H4, sweeps D).

Chaque passage n'envoie que les signaux des bougies clôturées depuis moins de --hours
(le quart d'heure écoulé), pour ne pas renvoyer deux fois le même signal.

Usage : python -m screener.main [--hours N]   (N plus grand pour rejouer les dernières heures en essai)
"""

import argparse
import html

import pandas as pd

from . import config
from .charts import render
from .context import higher_flux, levels, stop_vol
from .data import DURATION, get_candles
from .detectors import bulles, divergences, opr, sweeps
from .telegram import send_photo

# Chaque détecteur et ses unités de temps.
DETECTORS = [(bulles.detect, config.BUBBLE_TIMEFRAMES), (opr.detect, config.OPR_TIMEFRAMES),
             (divergences.detect, config.DIV_TIMEFRAMES), (sweeps.detect, config.SWEEP_TIMEFRAMES)]
NY = "America/New_York"
ICONS = {"Bulle apesanteur": "🫧", "OPR - sortie": "📐", "Divergence RSI": "〰️", "Sweep": "🧹"}


def extras(detect, df: pd.DataFrame, tf: str, candles: dict) -> dict:
    """Données propres à un détecteur."""
    if detect is sweeps.detect:
        return {"zones": levels(df, tf, candles["1D"], candles["1H"])}
    if detect is opr.detect:
        return {"h4": candles["4H"]}
    return {}


def close_time(t: pd.Timestamp, tf: str) -> pd.Timestamp:
    if tf in DURATION:
        return t.tz_convert(NY) + DURATION[tf]
    return pd.Timestamp(t.date(), tz=NY) + pd.Timedelta(hours=17)  # clôture de séance CME


def caption(s) -> str:
    arrow = "🟢 ACHAT" if s.direction == "achat" else "🔴 VENTE"
    tv = config.TRADINGVIEW[s.asset]
    when = close_time(s.time, s.tf).tz_convert("Europe/Paris").strftime("%d/%m %H:%M")
    lines = [
        f"<b>{arrow} · {s.asset} · {s.tf}</b>",
        f"{ICONS.get(s.pattern, '📐')} {html.escape(s.pattern, quote=False)} · <b>{s.context}</b>",
        f"Clôture {when} (Paris)",
        "",
        f"Entrée {s.entry} · Stop {s.stop} · Objectif {s.target}",
        f"R/R {s.rr}",
        *[f"• {html.escape(n, quote=False)}" for n in s.notes],
        "",
        f'<a href="https://www.tradingview.com/chart/?symbol={tv}">Graphique TradingView</a> · '
        f'<a href="{config.NOTION[s.pattern]}">Fiche</a>',
    ]
    return "\n".join(lines)


def run(window_hours: float = 0.25) -> int:
    now = pd.Timestamp.now(tz=NY)
    sent = 0
    for asset, ticker in config.ASSETS.items():
        candles = {"1D": get_candles(ticker, "1D")}
        for detect, tfs in DETECTORS:
            for tf in tfs:
                for need in (tf, "1H", "4H"):  # H1 : flux du M15 ; H4 : contre-argument de l'OPR
                    if need not in candles:
                        candles[need] = get_candles(ticker, need)
                df = candles[tf]
                flux = higher_flux(df, tf, candles["1D"], candles["1H"])
                vol = stop_vol(df, candles["1D"]) if tf != "1D" else None
                for s in detect(df, asset, tf, flux, vol, **extras(detect, df, tf, candles)):
                    if now - close_time(s.time, tf) > pd.Timedelta(hours=window_hours):
                        continue
                    name = f"{asset}_{tf}_{s.time:%Y%m%d%H%M}_{s.direction}"
                    send_photo(caption(s), render(df, s), name)
                    sent += 1
    print(f"{sent} signal(s) envoyé(s)")
    return sent


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    # shortcut: fenêtre glissante d'un quart d'heure ; un passage GitHub très en retard peut doubler ou rater un signal, ajouter un état mémorisé si ça arrive.
    p.add_argument("--hours", type=float, default=0.25)
    run(p.parse_args().hours)
