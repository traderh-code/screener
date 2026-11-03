import pandas as pd
import pytest

from screener import main
from screener.backtest import outcome
from screener.detectors import fibo


def _df(closes):
    rows = [(c, c + 2, c - 2, c) for c in closes]
    idx = pd.date_range("2026-01-05", periods=len(rows), freq="h", tz="America/New_York")
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx).assign(volume=1)


CALM = [1000.0] * 10
UP = [1000.0 + 25 * i for i in range(1, 33)]      # hausse jusqu'à 1800
PEAK = [1790.0, 1780.0]
FALL = [1700.0, 1600.0, 1500.0, 1450.0, 1400.0, 1350.0, 1300.0]  # clôture sous le 61,8 %


def _flux(df, label="baissier"):
    return pd.Series(label, index=df.index)


def _sell():
    return _df(CALM + UP + PEAK + FALL)


def test_exemple_du_module_clotures_et_niveaux():
    df = _sell()
    sig = fibo.detect(df, "DOW", "1H", _flux(df))
    assert len(sig) == 1
    s = sig[0]
    wave = 1802 - 998
    assert s.direction == "vente" and s.pattern == "Fibonacci 61,8" and s.entry == pytest.approx(1802 - 0.618 * wave, abs=0.01)
    assert s.stop > 998 + 0.5 * wave and s.target > 998 and s.rr == pytest.approx(2.68, abs=0.02)
    assert s.notes[0].startswith("Ordre limite") and df["close"][s.time] < s.entry
    assert df["close"].iloc[:df.index.get_loc(s.time)].iloc[-1] >= s.entry  # c'est bien la première clôture dessous


def test_envoye_en_simple_information():
    df = _sell()
    text = main.caption(fibo.detect(df, "DOW", "1H", _flux(df))[0])
    assert "INFO" in text and "contexte seulement" in text and "sous du 61,8" not in text and "61,8 % de la hausse" in text
    assert "Flux" in text
    for mot in ("VENTE", "Entrée", "Stop", "R/R", "Ordre limite", "Risque"):
        assert mot not in text
    assert main.render(df, fibo.detect(df, "DOW", "1H", _flux(df))[0]).startswith(b"\x89PNG")


def test_achat_symetrique():
    closes = [2000 - (c - 1000) for c in CALM + UP + PEAK + FALL]
    df = _df(closes)
    sig = fibo.detect(df, "DOW", "1H", _flux(df, "haussier"))
    assert len(sig) == 1 and sig[0].direction == "achat" and sig[0].stop < sig[0].entry < sig[0].target


def test_flux_contraire_ou_neutre_pas_de_signal():
    df = _sell()
    assert not fibo.detect(df, "DOW", "1H", _flux(df, "haussier"))
    assert not fibo.detect(df, "DOW", "1H", _flux(df, "neutre"))


def test_stop_vol_trop_large_on_passe():
    df = _sell()
    assert not fibo.detect(df, "DOW", "1H", _flux(df), pd.Series(200.0, index=df.index))  # R/R sous 2
    assert fibo.detect(df, "DOW", "1H", _flux(df), pd.Series(120.0, index=df.index))


def test_petite_vague_ignoree():
    small = [1000.0] * 40 + [1001.0, 1002.0, 1003.0, 1002.0, 1001.0, 999.0, 998.0, 997.0]
    df = _df(small)
    assert not fibo.detect(df, "DOW", "1H", _flux(df))


def test_nouveau_sommet_annule_la_vague():
    df = _df(CALM + UP + PEAK + [1810.0] + [1900.0, 1890.0, 1880.0])
    assert not fibo.detect(df, "DOW", "1H", _flux(df))


def test_obstacle_avant_r1():
    df = _sell()
    s = fibo.detect(df, "DOW", "1H", _flux(df))[0]
    below = s.entry - 20
    zones = pd.DataFrame({"plus bas de la veille": below}, index=df.index)
    assert not fibo.detect(df, "DOW", "1H", _flux(df), zones=zones)
    far = pd.DataFrame({"plus bas de la veille": s.entry - 500}, index=df.index)
    assert fibo.detect(df, "DOW", "1H", _flux(df), zones=far)


def test_meme_signal_en_ligne_que_sur_lhistorique():
    df = _sell()
    full = fibo.detect(df, "DOW", "1H", _flux(df))[0]
    cut = df.loc[:full.time]
    live = fibo.detect(cut, "DOW", "1H", _flux(cut))
    assert len(live) == 1 and live[0].time == full.time and live[0].entry == full.entry


def test_backtest_annule_si_objectif_touche_avant_lordre():
    df = _sell()
    s = fibo.detect(df, "DOW", "1H", _flux(df))[0]
    after = _df(CALM + UP + PEAK + FALL + [1200.0, 1100.0, 1000.0, 1400.0, 1600.0])
    assert outcome(after, s) == ("annulé", 0.0)
