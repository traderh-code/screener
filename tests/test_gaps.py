import pandas as pd

from screener import main
from screener.detectors import gaps
from screener.signal import Signal


def _df(rows, start="2026-01-05"):
    idx = pd.date_range(start, periods=len(rows), freq="B")
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx).assign(volume=1)


CALM = [(100, 101, 99, 100)] * 20
UP = [(105, 107, 104, 106)]      # plus bas 104 au-dessus du plus haut 101 de la veille
DOWN = [(95, 96, 93, 94)]        # plus haut 96 sous le plus bas 99 de la veille


def test_gap_haussier_en_information():
    df = _df(CALM + UP)
    s = gaps.detect(df, "ES", "1D")
    assert len(s) == 1 and s[0].pattern == "Gap" and s[0].time == df.index[-1]
    assert s[0].stop == 104 and s[0].target == 101 and "101.00 - 104.00" in s[0].context
    text = main.caption(s[0])
    assert "INFO" in text and "contexte seulement" in text and "comblement à 101.00" in text
    for mot in ("ACHAT", "Entrée", "Stop", "R/R", "retournement"):
        assert mot not in text
    assert main.render(df, s[0]).startswith(b"\x89PNG")


def test_gap_baissier():
    s = gaps.detect(_df(CALM + DOWN), "NQ", "1D")
    assert len(s) == 1 and s[0].direction == "vente" and s[0].target == 99


def test_seulement_les_indices_en_journalier():
    df = _df(CALM + UP)
    assert not gaps.detect(df, "GOLD", "1D") and not gaps.detect(df, "ES", "4H")


def test_gap_minuscule_ignore():
    assert not gaps.detect(_df(CALM + [(101.2, 102, 101.05, 101.5)]), "ES", "1D")


def test_changement_de_contrat_ecarte():
    assert gaps._near_roll(pd.Timestamp("2026-09-21")) and gaps._near_roll(pd.Timestamp("2026-06-15"))
    assert not gaps._near_roll(pd.Timestamp("2026-08-03")) and not gaps._near_roll(pd.Timestamp("2026-09-30"))
    assert not gaps.detect(_df(CALM + UP, start="2026-08-25"), "ES", "1D")  # le gap tombe le 22/09


def _trade(day, direction, entry):
    return Signal("ES", "15M", "OPR - sortie", direction, pd.Timestamp(day, tz="America/New_York"), entry, 0, 0, 2, "FRTM", [])


def test_note_gap_ouvert_sur_le_chemin_du_trade():
    daily = _df(CALM + DOWN + [(94, 95, 93, 94)] * 3)
    note = gaps.note_for(_trade("2026-03-02", "achat", 94), daily)
    assert note and "commence à 96.00" in note and "comblé à 99.00" in note
    assert gaps.note_for(_trade("2026-03-02", "vente", 94), daily) is None  # le gap est derrière ce trade


def test_gap_trop_loin_sans_note():
    drift = [(p + 1, p + 1.5, p - 1.5, p) for p in range(92, 58, -2)]  # baisse sans nouveau gap, jusqu'à 60
    daily = _df(CALM + DOWN + drift)
    assert gaps.note_for(_trade("2026-03-02", "achat", 60), daily) is None  # gap à partir de 96, trop loin
    assert gaps.note_for(_trade("2026-03-02", "achat", 94), _df(CALM + DOWN + drift[:1]))  # le même gap, tout près


def test_gap_comble_ou_futur_sans_note():
    filled = _df(CALM + DOWN + [(95, 100, 94, 99)])
    assert gaps.note_for(_trade("2026-03-02", "achat", 94), filled) is None
    daily = _df(CALM + DOWN)
    assert gaps.note_for(_trade(str(daily.index[-1].date()), "achat", 94), daily) is None  # pas encore connu ce jour-là
