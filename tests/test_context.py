from math import sqrt

import pandas as pd
import pytest

from screener.context import flux_label, higher_flux, stop_vol
from screener.indicators import atr

NY = "America/New_York"


def _frames():
    days = pd.date_range("2026-09-01", periods=30, freq="B")
    daily = pd.DataFrame({"open": 1000.0, "high": 1010.0, "low": 990.0, "close": 1000.0}, index=days)
    hours = pd.date_range("2026-10-01 00:00", "2026-10-13 23:00", freq="h", tz=NY)
    h1 = pd.DataFrame({"open": 1000.0, "high": 1050.0, "low": 950.0, "close": 1000.0}, index=hours)
    # Une bougie à 10 h New York, le 12/10 : séance du 12/10, donc valeurs du 09/10.
    df = pd.DataFrame({"close": [1000.0]}, index=pd.DatetimeIndex(["2026-10-12 10:00"], tz=NY))
    return daily, h1, df


def _index(daily, value, last=None):
    s = pd.Series(float(value), index=daily.index)
    if last is not None:
        s.loc[pd.Timestamp("2026-10-12"):] = float(last)  # valeur du jour même : ne doit pas servir
    return s


def test_stop_vol_vaut_20_pour_cent_de_lexpected_move_de_la_veille():
    daily, h1, df = _frames()
    vol = stop_vol(df, daily, h1, iv=_index(daily, 16, last=90))
    assert vol.iloc[0] == pytest.approx(0.2 * 1000 * 0.16 / sqrt(252))


def test_sans_indice_lancien_calcul_atr_reste_en_place():
    daily, h1, df = _frames()
    assert stop_vol(df, daily, h1).iloc[0] == pytest.approx(0.2 * atr(daily).loc["2026-10-09"])


@pytest.mark.parametrize("level, share", [(15, 0.0), (20, 0.0), (30, 0.5), (40, 1.0), (60, 1.0)])
def test_le_vix_rapproche_le_stop_de_latr_h1(level, share):
    daily, h1, df = _frames()
    iv = _index(daily, 16)
    base = stop_vol(df, daily, h1, iv=iv).iloc[0]
    vol = stop_vol(df, daily, h1, iv=iv, vix=_index(daily, level)).iloc[0]
    assert vol == pytest.approx(base + share * (atr(h1).loc["2026-10-12 09:00"] - base))


def test_un_atr_h1_plus_petit_ne_raccourcit_pas_le_stop():
    daily, h1, df = _frames()
    h1[["high", "low"]] = [1000.5, 999.5]
    iv = _index(daily, 16)
    assert stop_vol(df, daily, h1, iv=iv, vix=_index(daily, 40)).iloc[0] == pytest.approx(stop_vol(df, daily, h1, iv=iv).iloc[0])


def test_en_ligne_la_seance_en_cours_absente_ne_vide_pas_le_stop_vol():
    daily, h1, df = _frames()
    iv = _index(daily, 16)
    live = stop_vol(df, daily.loc[:"2026-10-09"], h1, iv=iv)  # la séance du 12/10 n'est pas clôturée
    assert live.iloc[0] == pytest.approx(stop_vol(df, daily, h1, iv=iv).iloc[0]) and live.iloc[0] > 0


def test_en_ligne_lheure_en_cours_absente_ne_vide_pas_le_flux_m15():
    daily, _, _ = _frames()
    hours = pd.date_range("2026-10-01 00:00", "2026-10-12 10:00", freq="h", tz=NY)
    closes = [1000.0 + i for i in range(len(hours))]
    h1 = pd.DataFrame({"open": closes, "high": closes, "low": closes, "close": closes}, index=hours)
    df = pd.DataFrame({"close": [1.0]}, index=pd.DatetimeIndex(["2026-10-12 10:15"], tz=NY))
    live = higher_flux(df, "15M", daily, h1.iloc[:-1])  # à 10h30, la bougie H1 de 10h n'est pas clôturée
    assert live.iloc[0] == "haussier" == higher_flux(df, "15M", daily, h1).iloc[0]
    assert flux_label(h1["close"]).iloc[-2] == "haussier"
