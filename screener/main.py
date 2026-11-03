"""Passage du screener : lancé tous les quarts d'heure par GitHub Actions (bulles H1/M15, OPR M15, divergences D/H4, sweeps D, Fibonacci H1/H4, gaps et RSI D).

GitHub retarde souvent les passages : avec --state, le fichier garde les signaux déjà traités, et chaque passage
envoie ceux des config.CATCHUP_HOURS dernières heures qui n'y sont pas encore. Sans fichier d'état (premier passage,
essai), seule la fenêtre --hours est envoyée ; avec --state, le reste est noté comme déjà traité, pas envoyé.

Usage : python -m screener.main [--hours N] [--state fichier.json]
"""

import argparse
import html
import json
import traceback
from pathlib import Path

import pandas as pd

from . import config
from .charts import render
from .context import higher_flux, levels, stop_vol
from .data import DURATION, get_candles, get_index
from .detectors import bulles, divergences, fibo, gaps, opr, rsi_zone, sweeps
from .telegram import send_photo

# Chaque détecteur et ses unités de temps.
DETECTORS = [(bulles.detect, config.BUBBLE_TIMEFRAMES), (opr.detect, config.OPR_TIMEFRAMES),
             (divergences.detect, config.DIV_TIMEFRAMES), (sweeps.detect, config.SWEEP_TIMEFRAMES),
             (fibo.detect, config.FIB_TIMEFRAMES),
             (gaps.detect, ["1D"]), (rsi_zone.detect, ["1D"])]
NY = "America/New_York"
ICONS = {"Bulle apesanteur": "🫧", "OPR - sortie": "📐", "Divergence RSI": "〰️", "Sweep": "🧹", "Gap": "🕳️", "RSI": "📉", "Fibonacci 61,8": "🌀"}


def extras(detect, df: pd.DataFrame, tf: str, candles: dict) -> dict:
    """Données propres à un détecteur."""
    if detect is sweeps.detect:
        return {"zones": levels(df, tf, candles["1D"], candles["1H"])}
    if detect is opr.detect:
        return {"h4": candles["4H"]}
    if detect is fibo.detect:
        zones = levels(df, tf, candles["1D"], candles["1H"])
        return {"zones": zones[["plus haut de la veille", "plus bas de la veille"]]}
    return {}


def volatility(asset: str) -> dict:
    """Indices de volatilité de l'actif, pour context.stop_vol. Le VIX ne règle que les indices US."""
    return {"iv": get_index(config.IV_INDEX.get(asset)),
            "vix": get_index(config.VIX_TICKER) if asset in config.OPR_MAX_DISTANCE else None}


def close_time(t: pd.Timestamp, tf: str) -> pd.Timestamp:
    if tf in DURATION:
        return t.tz_convert(NY) + DURATION[tf]
    return pd.Timestamp(t.date(), tz=NY) + pd.Timedelta(hours=17)  # clôture de séance CME


def caption(s) -> str:
    arrow = "🟢 ACHAT" if s.direction == "achat" else "🔴 VENTE"
    tv = config.TRADINGVIEW[s.asset]
    when = close_time(s.time, s.tf).tz_convert("Europe/Paris").strftime("%d/%m %H:%M")
    if s.pattern in config.INFO_ONLY:
        notes = [n for n in s.notes if n.startswith(("Flux", "Alerte en retard"))]
        return "\n".join([
            f"<b>ℹ️ INFO · {s.asset} · {s.tf}</b>",
            f"{ICONS.get(s.pattern, '📐')} {html.escape(s.pattern, quote=False)} · " + (
                f"retournement possible à la {'hausse' if s.direction == 'achat' else 'baisse'}"
                if s.pattern == "Bulle apesanteur" else s.context),
            "Pas un signal de trade : contexte seulement",
            f"Clôture {when} (Paris)",
            *[f"• {html.escape(n, quote=False)}" for n in notes],
            "",
            f'<a href="https://www.tradingview.com/chart/?symbol={tv}">Graphique TradingView</a> · '
            f'<a href="{config.NOTION[s.pattern]}">Fiche</a>',
        ])
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


def load_state(path: str | None) -> dict | None:
    return json.loads(Path(path).read_text(encoding="utf-8")) if path and Path(path).exists() else None


def save_state(path: str, seen: dict, now: pd.Timestamp) -> None:
    limit = now - pd.Timedelta(hours=config.CATCHUP_HOURS)
    kept = {k: v for k, v in seen.items() if pd.Timestamp(v) >= limit}
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(kept, indent=0), encoding="utf-8")


def run(window_hours: float = 0.25, state_path: str | None = None) -> int:
    now = pd.Timestamp.now(tz=NY)
    state = load_state(state_path)
    seen = state or {}
    window = pd.Timedelta(hours=window_hours if state is None else max(window_hours, config.CATCHUP_HOURS))
    catchup = pd.Timedelta(hours=max(window_hours, config.CATCHUP_HOURS))
    sent = 0
    try:
        sent = _scan(now, seen, window, catchup)
    finally:  # même après une erreur : ce qui est parti ne doit pas repartir
        if state_path:
            save_state(state_path, seen, now)
    print(f"{sent} signal(s) envoyé(s)")
    return sent


def _scan(now: pd.Timestamp, seen: dict, window: pd.Timedelta, catchup: pd.Timedelta) -> int:
    """Une erreur sur un actif n'empêche pas de traiter les autres ; le passage échoue à la fin pour la signaler."""
    sent, failed = 0, []
    for asset, ticker in config.ASSETS.items():
        try:
            sent += _scan_asset(asset, ticker, now, seen, window, catchup)
        except Exception:
            traceback.print_exc()
            failed.append(asset)
    if failed:
        print(f"{sent} signal(s) envoyé(s)")
        raise RuntimeError(f"Passage incomplet : {', '.join(failed)}")
    return sent


def _scan_asset(asset: str, ticker: str, now: pd.Timestamp, seen: dict, window: pd.Timedelta,
                catchup: pd.Timedelta) -> int:
    sent = 0
    candles = {"1D": get_candles(ticker, "1D")}
    implied = volatility(asset)
    for detect, tfs in DETECTORS:
        for tf in tfs:
            for need in (tf, "1H", "4H"):  # H1 : flux du M15 ; H4 : contre-argument de l'OPR
                if need not in candles:
                    candles[need] = get_candles(ticker, need)
            df = candles[tf]
            flux = higher_flux(df, tf, candles["1D"], candles["1H"])
            vol = stop_vol(df, candles["1D"], candles["1H"], **implied) if tf != "1D" else None
            for s in detect(df, asset, tf, flux, vol, **extras(detect, df, tf, candles)):
                closed = close_time(s.time, tf)
                age = now - closed
                name = f"{asset}_{tf}_{s.time:%Y%m%d%H%M}_{s.direction}"
                key = f"{name}_{s.pattern}"  # deux setups peuvent partir sur la même bougie
                if age > catchup or key in seen:
                    continue
                if age <= window:
                    if age > pd.Timedelta(minutes=config.LATE_MINUTES):
                        check = "" if s.pattern in config.INFO_ONLY else " : vérifier que l'entrée est encore valable"
                        s.notes.append(f"Alerte en retard de {int(age.total_seconds() // 60)} min{check}")
                    note = None if s.pattern in config.INFO_ONLY else gaps.note_for(s, candles["1D"])
                    if note:
                        s.notes.append(note)
                    send_photo(caption(s), render(df, s), name)
                    sent += 1
                seen[key] = closed.isoformat()
    return sent


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--hours", type=float, default=0.25)
    p.add_argument("--state", default=None)
    args = p.parse_args()
    run(args.hours, args.state)
