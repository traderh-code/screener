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


def test_seul_largent_passe_par_le_h1(monkeypatch):
    calls = []

    def fake(ticker, period, interval):
        calls.append((ticker, interval))
        return _h1() if interval == "1h" else data.daily_from_h1(_h1())

    monkeypatch.setattr(data, "_download", fake)
    data.get_candles("SI=F", "1D")
    data.get_candles("GC=F", "1D")
    assert calls == [("SI=F", "1h"), ("GC=F", "1d")]
