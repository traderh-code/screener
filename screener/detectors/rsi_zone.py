"""Sortie de zone du RSI en journalier (formation, module 16).

- Achat possible quand le RSI(14) repasse au-dessus de 30, vente possible quand il repasse sous 70 : on attend la sortie
  de la zone, pas l'entrée dedans. Pas de signal contre la tendance de fond (flux hebdomadaire contraire).
- Romain : « jamais seul, un argument en plus, pas un déclencheur » : une simple information (config.INFO_ONLY).
- Le passage de 50 en H1 n'est pas alerté : environ 18 fois par mois sur chaque actif, sans plus-value mesurée.
"""

import pandas as pd

from .. import config
from ..indicators import rsi
from ..signal import Signal


def detect(df: pd.DataFrame, asset: str, tf: str, flux: pd.Series | None = None,
           min_stop: pd.Series | None = None) -> list[Signal]:
    if tf != "1D":
        return []
    flux = flux if flux is not None else pd.Series("neutre", index=df.index)
    r = rsi(df["close"], config.RSI_PERIOD)
    signals = []
    for i in range(config.RSI_PERIOD + 1, len(df)):
        if r.iloc[i - 1] <= config.RSI_OVERSOLD < r.iloc[i] and flux.iloc[i] != "baissier":
            direction, text = "achat", f"le RSI ressort de la survente ({r.iloc[i]:.0f}), rebond possible"
        elif r.iloc[i] < config.RSI_OVERBOUGHT <= r.iloc[i - 1] and flux.iloc[i] != "haussier":
            direction, text = "vente", f"le RSI ressort du surachat ({r.iloc[i]:.0f}), repli possible"
        else:
            continue
        close = round(float(df["close"].iloc[i]), 2)
        signals.append(Signal(asset, tf, "RSI", direction, df.index[i], close, close, close, 0.0, text))
    return signals
