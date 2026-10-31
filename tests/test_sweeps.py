import pandas as pd

from screener.detectors import sweeps
from screener.indicators import value_area


def _df(rows):
    idx = pd.date_range("2025-01-01", periods=len(rows), freq="D")
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx).assign(volume=1)


# Marché calme autour de 102 (étendue 1), un sommet à 106 (bougie 8), puis un balayage de la zone 100.
CALM = [(102, 102.5, 101.5, 102)] * 6 + [(102, 104, 101.8, 103.8), (103.8, 105, 103.5, 104.8),
                                         (104.8, 106, 104.5, 105.2), (105.2, 105.4, 103, 103.2),
                                         (103.2, 103.4, 101.6, 101.8), (101.8, 102.2, 101.2, 101.5)]
SWEEP = [(101.5, 101.8, 98.5, 99.0), (99.0, 101.2, 98.8, 101.0)]  # casse 100 puis clôture au-dessus


def _zones(df, level=100.0):
    return pd.DataFrame({"VAL hebdo": level}, index=df.index)


def _flux(df, label="haussier"):
    return pd.Series(label, index=df.index)


def test_sweep_acheteur_reintegre_en_deux_bougies():
    df = _df(CALM + SWEEP)
    sig = sweeps.detect(df, "ES", "1D", _flux(df), zones=_zones(df))
    assert len(sig) == 1
    s = sig[0]
    assert s.direction == "achat" and s.time == df.index[-1] and s.entry == 100
    assert s.stop < 98.5 and s.target == 106 and s.rr >= 2 and "VAL hebdo" in s.notes[1]


def test_flux_contraire_pas_de_sweep():
    df = _df(CALM + SWEEP)
    assert not sweeps.detect(df, "ES", "1D", _flux(df, "baissier"), zones=_zones(df))


def test_pas_de_reintegration_pas_de_sweep():
    df = _df(CALM + [SWEEP[0], (99.0, 99.6, 98.6, 99.2), (99.2, 99.5, 98.9, 99.1), (99.1, 99.4, 98.8, 99.0)])
    assert not sweeps.detect(df, "ES", "1D", _flux(df), zones=_zones(df))


def test_value_area_autour_du_volume():
    bars = pd.DataFrame({"low": [100, 104, 104, 104, 108], "high": [101, 105, 105, 105, 109], "volume": [1, 10, 10, 10, 1]})
    val, poc, vah = value_area(bars)
    assert 104 <= poc <= 105 and val >= 103.5 and vah <= 105.5
