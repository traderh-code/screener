import pandas as pd

from screener import main
from screener.detectors import rsi_zone


def _df(moves):
    closes = [100.0]
    for m in moves:
        closes.append(closes[-1] + m)
    rows = [(c, c + 0.4, c - 0.4, c) for c in closes]
    idx = pd.date_range("2025-01-01", periods=len(rows), freq="D")
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx).assign(volume=1)


FALL = [-1.0] * 30
RISE = [1.0] * 8


def test_sortie_de_survente_en_information():
    df = _df(FALL + RISE)
    s = rsi_zone.detect(df, "ES", "1D")
    assert len(s) == 1 and s[0].direction == "achat" and s[0].pattern == "RSI" and s[0].rr == 0
    text = main.caption(s[0])
    assert "INFO" in text and "ressort de la survente" in text and "contexte seulement" in text
    for mot in ("ACHAT", "Entrée", "Stop", "R/R", "retournement"):
        assert mot not in text
    assert main.render(df, s[0]).startswith(b"\x89PNG")


def test_sortie_de_surachat_symetrique():
    s = rsi_zone.detect(_df([-m for m in FALL + RISE]), "ES", "1D")
    assert len(s) == 1 and s[0].direction == "vente" and "surachat" in s[0].context


def test_rester_dans_la_zone_ne_donne_rien():
    assert not rsi_zone.detect(_df(FALL), "ES", "1D")


def test_pas_de_signal_contre_la_tendance_de_fond():
    df = _df(FALL + RISE)
    assert not rsi_zone.detect(df, "ES", "1D", pd.Series("baissier", index=df.index))
    assert rsi_zone.detect(df, "ES", "1D", pd.Series("haussier", index=df.index))


def test_journalier_seulement():
    assert not rsi_zone.detect(_df(FALL + RISE), "ES", "4H")


def test_meme_signal_en_ligne_que_sur_lhistorique():
    full = _df(FALL + RISE)
    signal = rsi_zone.detect(full, "ES", "1D")[0]
    live = rsi_zone.detect(full.loc[:signal.time], "ES", "1D")
    assert len(live) == 1 and live[0].time == signal.time and live[0].entry == signal.entry
