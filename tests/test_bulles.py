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


def test_apesanteur_basse_donne_un_achat():
    rows = _flat() + [(97.0, 97.2, 96.3, 96.5)]
    sig = bulles.detect(_df(rows), "TEST", "1D")
    assert sig, "aucune bulle détectée"
    last = sig[-1]
    assert last.pattern == "Bulle apesanteur" and last.direction == "achat"
    assert last.stop < 96.3 < last.entry < last.target


def test_classique_attend_la_reintegration_verte():
    # Bulle : corps sous la bande basse mais la mèche haute la touche ; puis bougie verte qui réintègre.
    bubble = (97.6, 98.7, 97.4, 97.5)
    rows = _flat() + [bubble]
    assert not [s for s in bulles.detect(_df(rows), "T", "1D") if s.pattern == "Bulle classique"]
    rows = rows + [(97.6, 98.5, 97.45, 98.4)]
    sig = [s for s in bulles.detect(_df(rows), "T", "1D") if s.pattern == "Bulle classique"]
    assert sig and sig[-1].direction == "achat" and sig[-1].stop < 97.4 and sig[-1].rr >= 1.2


def test_reintegration_rouge_ignoree():
    rows = _flat() + [(97.6, 99.9, 97.0, 97.2), (98.9, 99.0, 97.1, 98.0)]
    assert not [s for s in bulles.detect(_df(rows), "T", "1D") if s.pattern == "Bulle classique"]


def test_serie_de_bulles_ignoree():
    rows = _flat()
    price = 100.0
    for _ in range(6):  # six bulles d'affilée à la baisse
        price -= 3
        rows.append((price + 0.5, price + 0.6, price - 0.1, price))
    sig = bulles.detect(_df(rows), "T", "1D")
    assert all(s.time != _df(rows).index[-1] for s in sig)
