import pandas as pd

from screener.detectors import opr


def _day(bars, date="2026-10-28"):
    """bars : [(heure New York, open, high, low, close)] ; la veille est un jour plat autour de 100."""
    prev = [(f"{date[:-2]}{int(date[-2:]) - 1:02d} {h:02d}:00", 100, 100.5, 99.5, 100) for h in range(9, 16)]
    rows = prev + [(f"{date} {t}", o, h, l, c) for t, o, h, l, c in bars]
    idx = pd.DatetimeIndex([r[0] for r in rows]).tz_localize("America/New_York")
    return pd.DataFrame([r[1:] for r in rows], columns=["open", "high", "low", "close"], index=idx).assign(volume=0)


def _flux(df, label):
    return pd.Series(label, index=df.index)


BARS = [("09:30", 100, 101, 99, 100.5),     # OPR 99 - 101
        ("09:45", 100.5, 101.2, 100.2, 101),  # pas de clôture dehors
        ("10:00", 101, 103.6, 100.8, 103.5)]  # sortie par le haut, clôture 2,5 au-dessus


def test_sortie_par_le_haut_en_flux_haussier():
    df = _day(BARS)
    sig = opr.detect(df, "ES", "15M", _flux(df, "haussier"))
    assert len(sig) == 1
    s = sig[0]
    assert s.direction == "achat" and s.entry == 101 and s.stop < 100.8 and s.target == round(101 + 2 * (101 - s.stop), 2)
    assert s.time == df.index[-1]


def test_flux_contraire_ou_neutre_pas_de_signal():
    df = _day(BARS)
    assert not opr.detect(df, "ES", "15M", _flux(df, "baissier"))
    assert not opr.detect(df, "ES", "15M", _flux(df, "neutre"))


def test_trop_loin_de_la_borne():
    df = _day(BARS[:2] + [("10:00", 101, 120, 100.8, 117)])  # 16 pts > 15 pts sur le S&P
    assert not opr.detect(df, "ES", "15M", _flux(df, "haussier"))


def test_obstacle_de_la_veille_avant_r1():
    df = _day(BARS)
    df.iloc[3, df.columns.get_loc("high")] = 101.3  # plus haut de la veille juste au-dessus de la borne
    assert not opr.detect(df, "ES", "15M", _flux(df, "haussier"))


def test_actifs_hors_indices_ignores():
    df = _day(BARS)
    assert not opr.detect(df, "GOLD", "15M", _flux(df, "haussier"))
