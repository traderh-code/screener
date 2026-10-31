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
# Les bulles (setup intraday chez Romain) se travaillent en H1 et M15, pas en D/H4.
BUBBLE_TIMEFRAMES = ["1H", "15M"]

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
    "OPR - sortie": "https://app.notion.com/p/4093dfd490b08162bbf5fc3826c6f41d",
    "Divergence RSI": "https://app.notion.com/p/4093dfd490b081d29898e1571695394a",
    "Sweep": "https://app.notion.com/p/4093dfd490b081cda995f664b4dc097c",
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
STOP_VOL_FRACTION = 0.20      # stop minimum = 20 % de l'expected move du jour (règle 2026, « stop vol »)
# Coaching du 22 oct. 2026 : R/R ≥ 2 si le trade est dans le plan du matin, ≥ 3 sinon.
# Le screener ne connaît pas le plan : il applique « hors plan ».
MIN_RR = 3.0
PLAN_RR = 2.0   # à partir de ce R/R, on tente l'entrée optimisée au 50 % de la bulle

# OPR (indices US seulement), signal en M15 (choix de l'utilisateur ; Romain prend le M5 en 2026).
OPR_TIMEFRAMES = ["15M"]
OPR_RR = 2.0
OPR_MAX_DISTANCE = {"DOW": 100, "NQ": 50, "ES": 15}  # écart max clôture / borne, en points (mémo)

# Divergences RSI (coaching du 22 oct. 2026), en journalier et H4.
DIV_TIMEFRAMES = ["1D", "4H"]
RSI_PERIOD = 14
DIV_MIN_BARS = 5     # bougies entre les deux points de la divergence
DIV_MAX_BARS = 18
DIV_NOISE = 40       # bruit <= 40 en haussière, >= 60 (100 - 40) en baissière
DIV_PIVOT = 2        # un creux / sommet = extrême sur 2 bougies de chaque côté
DIV_MAX_WAIT = 10    # bougies max entre B et la cassure du bruit

# Sweeps (LST Sweep) sur des zones calculées (context.levels).
SWEEP_TIMEFRAMES = ["1D"]  # backtest : H4 négatif (199 signaux, -13 R), journalier positif (56 signaux, +16 R)
SWEEP_IMPULSE = 1.0   # la bougie qui balaie le niveau fait au moins 1 ATR14 d'étendue
SWEEP_CLOSE_BEYOND = True  # la bougie de cassure clôture au-delà du niveau (pas une simple mèche)
SWEEP_MAX_BARS = 2    # réintégration au plus 2 bougies après la cassure (« 2-3 bougies max »)
SWEEP_MIN_RR = 2.0    # les zones tiennent lieu de plan : R/R 2 (Romain ne prend pas de sweep hors plan)
