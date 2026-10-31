import pandas as pd

from screener.detectors import bulles


def _flat(n=30):
    rows = []
    for i in range(n):
        c = 100 + (0.5 if i % 2 else -0.5)
        rows.append((100, c + 0.3 if c > 100 else 100.3, c - 0.3 if c < 100 else 99.7, c))
    return rows


def _df(rows):
    idx = pd.date_range("2025-01-01", periods=len(rows), freq="D")
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx).assign(volume=0)


def test_apesanteur_verte_sous_la_bande_donne_un_achat():
    rows = _flat() + [(96.4, 96.9, 96.3, 96.8)]
    sig = bulles.detect(_df(rows), "TEST", "1D")
    assert sig, "aucune bulle détectée"
    last = sig[-1]
    assert last.pattern == "Bulle apesanteur" and last.direction == "achat"
    assert last.entry == 96.8 and last.stop < 96.3 and last.target > last.entry and last.rr >= 3


def test_apesanteur_de_la_mauvaise_couleur_ignoree():
    rows = _flat() + [(96.8, 96.9, 96.3, 96.4)]  # corps rouge sous la bande basse
    assert not bulles.detect(_df(rows), "T", "1D")


def test_rr_insuffisant_a_la_cloture_passe_en_entree_optimisee():
    rows = _flat() + [(95.9, 96.9, 95.8, 96.8)]  # R/R ≈ 2,7 à la clôture, ≥ 3 au 50 %
    sig = bulles.detect(_df(rows), "T", "1D")
    assert sig and sig[-1].entry == 96.35 and sig[-1].rr >= 3
    assert "50 %" in sig[-1].notes[0]


def test_serie_de_bulles_ignoree():
    rows = _flat()
    price = 100.0
    for _ in range(6):  # six bulles vertes d'affilée à la baisse
        price -= 3
        rows.append((price - 0.4, price + 0.1, price - 0.5, price))
    sig = bulles.detect(_df(rows), "T", "1D")
    assert all(s.time != _df(rows).index[-1] for s in sig)
