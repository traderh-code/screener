import pandas as pd

from screener import data


def _h1():
    idx = pd.DatetimeIndex(["2026-10-29 18:00", "2026-10-30 09:00", "2026-10-30 16:00", "2026-11-01 18:00"], tz="America/New_York")
    return pd.DataFrame({"open": [1.0, 2.0, 3.0, 4.0], "high": [5.0, 9.0, 6.0, 7.0], "low": [0.5, 2.0, 1.0, 3.0],
                         "close": [2.0, 3.0, 4.0, 5.0], "volume": [10, 20, 30, 40]}, index=idx)


def test_journalier_par_seance_cme():
    day = data.daily_from_h1(_h1())
    # 18 h la veille appartient à la séance du lendemain ; dimanche 18 h à celle du lundi.
    assert list(day.index) == [pd.Timestamp("2026-10-30"), pd.Timestamp("2026-11-02")]
    assert day.iloc[0].to_dict() == {"open": 1.0, "high": 9.0, "low": 0.5, "close": 4.0, "volume": 60}


def test_seance_en_cours_retiree():
    day = data.daily_from_h1(_h1())
    now = pd.Timestamp("2026-11-02 10:00", tz="America/New_York")
    assert list(data.drop_unclosed(day, "1D", now).index) == [pd.Timestamp("2026-10-30")]


def _h1_days():
    """H1 du 28/10 18 h au 02/11 16 h (New York), une bougie par heure, plus haut = 100 + numéro de séance."""
    idx = pd.date_range("2026-10-28 18:00", "2026-11-02 16:00", freq="h", tz="America/New_York")
    session = (idx + pd.Timedelta(hours=6)).day
    return pd.DataFrame({"open": 1.0, "high": 100.0 + session, "low": 1.0, "close": 2.0, "volume": 1}, index=idx)


def test_journalier_recent_reconstruit_depuis_le_h1(monkeypatch):
    old = pd.DataFrame({"open": 1.0, "high": 999.0, "low": 1.0, "close": 2.0, "volume": 1},
                       index=pd.DatetimeIndex(pd.date_range("2026-10-20", "2026-11-02", freq="B"), name="Date"))

    def fake(ticker, period, interval):
        return _h1_days() if interval == "1h" else old

    monkeypatch.setattr(data, "_download", fake)
    day = data.get_candles("ES=F", "1D")
    assert (day.loc[:"2026-10-31", "high"] == 999).all()  # l'historique reste celui du journalier Yahoo
    # Les 2 dernières séances viennent du H1 (le H1 factice tourne aussi le week-end), pas du journalier.
    assert list(day.loc["2026-11-01":, "high"]) == [101.0, 102.0] and day.index.is_unique


def test_largent_entierement_depuis_le_h1(monkeypatch):
    calls = []

    def fake(ticker, period, interval):
        calls.append(interval)
        return _h1_days()

    monkeypatch.setattr(data, "_download", fake)
    day = data.get_candles("SI=F", "1D")
    assert calls == ["1h"] and day.index[0] == pd.Timestamp("2026-10-30")
