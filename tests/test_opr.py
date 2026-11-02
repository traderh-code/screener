import pandas as pd

from screener.backtest import outcome
from screener.context import flux_label
from screener.detectors import opr


def _day(bars, date="2026-10-28"):
    """bars : [(heure New York, open, high, low, close)] ; la veille est un jour plat autour de 100."""
    prev = [(f"{date[:-2]}{int(date[-2:]) - 1:02d} {h:02d}:00", 100, 100.5, 99.5, 100) for h in range(9, 16)]
    rows = prev + [(f"{date} {t}", o, h, l, c) for t, o, h, l, c in bars]
    idx = pd.DatetimeIndex([r[0] for r in rows]).tz_localize("America/New_York")
    return pd.DataFrame([r[1:] for r in rows], columns=["open", "high", "low", "close"], index=idx).assign(volume=0)


def _flux(df, label):
    return pd.Series(label, index=df.index)


def _vol(df, points=3.0):
    return pd.Series(points, index=df.index)  # stop assez large pour que la cassure n'atteigne pas R1


BARS = [("09:30", 100, 101, 99, 100.5),     # OPR 99 - 101
        ("09:45", 100.5, 101.2, 100.2, 101),  # pas de clôture dehors
        ("10:00", 101, 103.6, 100.8, 103.5)]  # sortie par le haut, clôture 2,5 au-dessus


def test_sortie_par_le_haut_en_flux_haussier():
    df = _day(BARS)
    sig = opr.detect(df, "ES", "15M", _flux(df, "haussier"), _vol(df))
    assert len(sig) == 1
    s = sig[0]
    assert s.direction == "achat" and s.entry == 101 and s.stop < 100.8 and s.target == round(101 + 2 * (101 - s.stop), 2)
    assert s.time == df.index[-1]


def test_flux_contraire_ou_neutre_pas_de_signal():
    df = _day(BARS)
    assert not opr.detect(df, "ES", "15M", _flux(df, "baissier"), _vol(df))
    assert not opr.detect(df, "ES", "15M", _flux(df, "neutre"), _vol(df))


def test_trop_loin_de_la_borne():
    df = _day(BARS[:2] + [("10:00", 101, 120, 100.8, 117)])  # 16 pts > 15 pts sur le S&P
    assert not opr.detect(df, "ES", "15M", _flux(df, "haussier"), _vol(df, 30))


def test_obstacle_de_la_veille_avant_r1():
    df = _day(BARS)
    df.iloc[3, df.columns.get_loc("high")] = 101.3  # plus haut de la veille juste au-dessus de la borne
    assert not opr.detect(df, "ES", "15M", _flux(df, "haussier"), _vol(df))


def test_actifs_hors_indices_ignores():
    df = _day(BARS)
    assert not opr.detect(df, "GOLD", "15M", _flux(df, "haussier"), _vol(df))


def test_r1_deja_atteint_par_la_cassure_pas_de_signal():
    df = _day(BARS)  # sans stop vol : risque 0,48, la bougie monte 2,6 au-dessus de la borne
    assert not opr.detect(df, "ES", "15M", _flux(df, "haussier"))


def test_note_annulation_r1_et_backtest_annule():
    df = _day(BARS)
    s = opr.detect(df, "ES", "15M", _flux(df, "haussier"), _vol(df))[0]
    assert any("R1" in n for n in s.notes)
    after = _day(BARS + [("10:15", 103.5, 104.5, 103.2, 104), ("10:30", 104, 104.2, 100.9, 101)])
    assert outcome(after, s) == ("annulé", 0.0)  # R1 (104) touché avant le retour sur la borne


def test_bougie_de_10h_ignoree_sans_compter_comme_premiere_sortie():
    bars = [BARS[0], ("09:45", 100.5, 103.6, 100.8, 103.5), ("10:00", 103.5, 103.7, 102.5, 103)]
    df = _day(bars)
    s = opr.detect(df, "ES", "15M", _flux(df, "haussier"), _vol(df))
    assert len(s) == 1 and s[0].time == df.index[-1]


def test_sortie_trop_tardive_ignoree():
    df = _day([BARS[0], ("13:30", 100.5, 103.6, 100.8, 103.5)])
    assert not opr.detect(df, "ES", "15M", _flux(df, "haussier"), _vol(df))
    df = _day([BARS[0], ("13:15", 100.5, 103.6, 100.8, 103.5)])
    assert opr.detect(df, "ES", "15M", _flux(df, "haussier"), _vol(df))


def _h4(row):
    """25 bougies H4 calmes autour de 100 jusqu'à la veille à 10 h, puis row = (heure New York, o, h, l, c)."""
    calm = [(t, 100, 100.5 + (i % 2) / 2, 99.5 - (i % 2) / 2, 100) for i, t in
            enumerate(pd.date_range(end="2026-10-27 10:00", periods=25, freq="4h"))]
    rows = calm + [(pd.Timestamp(row[0]), *row[1:])]
    idx = pd.DatetimeIndex([r[0] for r in rows]).tz_localize("America/New_York")
    return pd.DataFrame([r[1:] for r in rows], columns=["open", "high", "low", "close"], index=idx).assign(volume=0)


def test_bulle_h4_opposee_de_la_seance_bloque_l_opr():
    df = _day(BARS)
    vente = _h4(("2026-10-28 06:00", 110.2, 112, 109.8, 110))  # bulle rouge au-dessus des bandes
    assert not opr.detect(df, "ES", "15M", _flux(df, "haussier"), _vol(df), h4=vente)


def test_bulle_h4_dans_le_meme_sens_ou_de_la_veille_ne_bloque_pas():
    df = _day(BARS)
    achat = _h4(("2026-10-28 06:00", 90, 90.5, 88, 90.3))  # bulle verte sous les bandes
    assert opr.detect(df, "ES", "15M", _flux(df, "haussier"), _vol(df), h4=achat)
    veille = _h4(("2026-10-27 14:00", 110.2, 112, 109.8, 110))  # clôture à 18 h : séance précédente
    assert opr.detect(df, "ES", "15M", _flux(df, "haussier"), _vol(df), h4=veille)


def test_flux_batard_classe_neutre():
    close = pd.Series([100.0] * 60 + [120.0] * 40 + [95.0])  # EMA20 > EMA50 mais clôture sous la EMA50
    assert flux_label(close).iloc[-1] == "neutre"
