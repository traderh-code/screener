import pandas as pd

from screener import config
from screener.detectors import divergences


def _df(closes):
    rows = [(c + 0.1, c + 0.4, c - 0.4, c) for c in closes]
    idx = pd.date_range("2025-01-01", periods=len(rows), freq="D")
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx).assign(volume=0)


def _path(start, moves):
    out = [start]
    for m in moves:
        out.append(out[-1] + m)
    return out


# Forte baisse jusqu'au creux A (bougie 40), petit rebond, creux B plus bas (bougie 48) avec un RSI plus haut,
# puis remontée qui casse le bruit.
DOWN = [-1.5] * 40
SECOND_LOW = [0.6, 0.4, -0.3, -0.4, -0.3, -0.2, -0.2, -0.1]
UP = [0.8, 1.2, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5]


def test_divergence_haussiere():
    df = _df(_path(100, DOWN + SECOND_LOW + UP))
    sig = divergences.detect(df, "T", "1D")
    assert len(sig) == 1
    s = sig[0]
    assert s.direction == "achat" and s.time == df.index[50]  # pivot B confirmé, RSI au-dessus du bruit
    assert s.stop < df.low.iloc[48] < s.entry < s.target and s.rr >= 3


def test_divergence_baissiere_symetrique():
    df = _df(_path(100, [-m for m in DOWN + SECOND_LOW + UP]))
    sig = divergences.detect(df, "T", "1D")
    assert len(sig) == 1 and sig[0].direction == "vente" and sig[0].stop > df.high.iloc[48]


def test_trop_de_bougies_entre_les_creux():
    df = _df(_path(100, DOWN + [0.6, 0.4] + [-0.1] * 20 + UP))  # B à plus de 18 bougies de A
    assert not [s for s in divergences.detect(df, "T", "1D") if s.direction == "achat"]


def test_bruit_au_dessus_du_seuil(monkeypatch):
    df = _df(_path(100, DOWN + SECOND_LOW + UP))  # bruit RSI ≈ 7
    monkeypatch.setattr(config, "DIV_NOISE", 5)
    assert not divergences.detect(df, "T", "1D")
