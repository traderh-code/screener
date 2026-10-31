"""Réglages du screener : actifs, unités de temps, seuils des détecteurs."""

# Contrats futures continus Yahoo Finance.
ASSETS = {
    "GOLD": "GC=F",
    "SILVER": "SI=F",
    "NQ": "NQ=F",
    "DOW": "YM=F",
    "ES": "ES=F",
}

TIMEFRAMES = ["1D", "4H"]

# Symbole TradingView correspondant (contrat le plus proche), pour le lien dans le message.
TRADINGVIEW = {
    "GOLD": "COMEX:GC1!",
    "SILVER": "COMEX:SI1!",
    "NQ": "CME_MINI:NQ1!",
    "DOW": "CBOT_MINI:YM1!",
    "ES": "CME_MINI:ES1!",
}

# Fiche Notion de chaque pattern (lien dans le message).
NOTION = {
    "Bulle apesanteur": "https://app.notion.com/p/4093dfd490b0815db170c0da9b1ec29d",
}

# Bollinger (20, 2) comme sur les graphiques de Romain.
BB_PERIOD = 20
BB_STD = 2.0

# Flux : EMA20 / EMA50 de l'unité du signal (FRTM si la bulle va dans le sens du flux, sinon RP).
FLUX_FAST = 20
FLUX_SLOW = 50

# Bulles
MAX_CONSECUTIVE_BUBBLES = 3   # au-delà, marché en pleine accélération : pas de signal
STOP_BUFFER = 0.10            # marge au-delà de la mèche, en fraction de la hauteur de la bougie bulle
# Coaching du 22 oct. 2026 : R/R ≥ 2 si le trade est dans le plan du matin, ≥ 3 sinon.
# Le screener ne connaît pas le plan : il applique « hors plan ».
MIN_RR = 3.0
PLAN_RR = 2.0   # à partir de ce R/R, on tente l'entrée optimisée au 50 % de la bulle
