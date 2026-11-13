import pandas as pd

from screener import main
from screener.detectors import wolfe


def _df(points, step=5):
    """Clôtures interpolées entre les points donnés, `step` bougies entre deux points."""
    closes = []
    for a, b in zip(points, points[1:]):
        closes += [a + (b - a) * i / step for i in range(step)]
    closes.append(points[-1])
    rows = [(c, c + 3, c - 3, c) for c in closes]
    idx = pd.date_range("2026-01-05", periods=len(rows), freq="h", tz="America/New_York")
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx).assign(volume=1)


# Exemple du module 52, avec une baisse avant le point 1 : 1 = 25 000, 2 = 25 300, 3 = 24 900, 4 = 25 150,
# 5 = 24 750 (au-delà de la droite 1-3, à 24 800), puis réintégration.
SHAPE = [25300, 25600, 25000, 25300, 24900, 25150, 24750, 24900, 25000]


def test_exemple_du_module_en_achat():
    sig = wolfe.detect(_df(SHAPE), "NQ", "1H")
    assert len(sig) == 1
    s = sig[0]
    assert s.direction == "achat" and s.pattern == "Vague de Wolfe"
    assert s.target == 25150 and s.stop < 24750 - 3 and s.rr >= 2


def test_baissiere_symetrique():
    sig = wolfe.detect(_df([50000 - p for p in SHAPE]), "NQ", "1H")
    assert len(sig) == 1 and sig[0].direction == "vente" and sig[0].target == 50000 - 25150


def test_point_4_hors_de_1_2_pas_de_wolfe():
    shape = SHAPE.copy()
    shape[5] = 25350  # au-dessus du point 2
    assert not wolfe.detect(_df(shape), "NQ", "1H")


def test_point_5_qui_ne_depasse_pas_la_droite_1_3():
    shape = SHAPE.copy()
    shape[6] = 24850  # au-dessus de la droite 1-3 (24 800)
    assert not wolfe.detect(_df(shape), "NQ", "1H")


def test_sans_baisse_prealable_pas_de_wolfe():
    shape = SHAPE.copy()
    shape[1] = 25200  # sommet précédent sous le point 2
    assert not wolfe.detect(_df(shape), "NQ", "1H")


def test_point_5_trop_loin_au_dela_de_la_parallele_2_4():
    shape = SHAPE.copy()
    shape[6] = 24500  # sous la parallèle à 2-4 posée sur 1 (24 700 au point 5)
    assert not wolfe.detect(_df(shape), "NQ", "1H")


def test_stop_vol_trop_large_on_passe():
    df = _df(SHAPE)
    assert not wolfe.detect(df, "NQ", "1H", min_stop=pd.Series(400.0, index=df.index))


def test_meme_signal_en_ligne_que_sur_lhistorique():
    df = _df(SHAPE)
    full = wolfe.detect(df, "NQ", "1H")[0]
    live = wolfe.detect(df.loc[:full.time], "NQ", "1H")
    assert len(live) == 1 and live[0].time == full.time and live[0].entry == full.entry



def test_zigzag_deux_creux_de_suite_garde_le_plus_bas():
    close = pd.Series([10, 9, 8, 7, 6, 6.8, 6.5, 6.2, 5, 6, 7, 8, 9], dtype=float)  # creux 6 puis 5, sans vrai sommet entre
    assert wolfe._zigzag(close) == [(8, "bas")]


def test_envoyee_en_simple_information():
    df = _df(SHAPE)
    s = wolfe.detect(df, "NQ", "1H")[0]
    text = main.caption(s)
    assert "INFO" in text and "contexte seulement" in text and "réintégration de la droite 1-3-5" in text
    for mot in ("ACHAT", "Entrée", "Stop", "R/R", "Risque"):
        assert mot not in text
    assert main.render(df, s).startswith(b"\x89PNG")
