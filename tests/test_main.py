import json

import pandas as pd
import pytest

from screener import config, main
from screener.detectors import bulles
from screener.signal import Signal


@pytest.fixture
def scan(monkeypatch):
    """Un seul actif, un détecteur factice : renvoie les signaux demandés, compte les envois."""
    df = pd.DataFrame({"close": [1.0]}, index=pd.DatetimeIndex(["2026-01-01"], tz=main.NY))
    state = {"signals": [], "sent": []}
    monkeypatch.setattr(config, "ASSETS", {"ES": "ES=F"})
    monkeypatch.setitem(config.TRADINGVIEW, "ES", "X")
    monkeypatch.setattr(main, "get_candles", lambda t, tf: df)
    monkeypatch.setattr(main, "get_index", lambda t: None)
    monkeypatch.setattr(main, "higher_flux", lambda *a: None)
    monkeypatch.setattr(main, "stop_vol", lambda *a, **k: None)
    monkeypatch.setattr(main, "render", lambda df, s: b"")
    monkeypatch.setattr(main, "send_photo", lambda cap, img, name: state["sent"].append(cap))
    monkeypatch.setattr(main, "DETECTORS", [(lambda *a, **k: list(state["signals"]), ["15M"])])
    return state


def _signal(minutes_ago, pattern="Sweep"):
    closed = pd.Timestamp.now(tz=main.NY) - pd.Timedelta(minutes=minutes_ago)
    return Signal("ES", "15M", pattern, "achat", closed - pd.Timedelta(minutes=15), 1, 0, 3, 2, "FRTM", [])


def test_sans_fichier_detat_seule_la_fenetre_part_et_le_reste_est_note(scan, tmp_path):
    path = str(tmp_path / "state" / "sent.json")
    scan["signals"] = [_signal(5), _signal(60)]
    assert main.run(0.25, path) == 1  # le signal d'il y a 60 min est peut-être déjà parti avant cette version
    assert main.run(0.25, path) == 0  # et il ne part pas au passage suivant
    assert len(json.loads(open(path, encoding="utf-8").read())) == 2


def test_passage_en_retard_rattrape_le_signal_une_seule_fois_avec_son_retard(scan, tmp_path):
    path = str(tmp_path / "sent.json")
    main.run(0.25, path)  # premier passage, aucun signal
    scan["signals"] = [_signal(70)]
    assert main.run(0.25, path) == 1
    assert "retard de 70 min" in scan["sent"][-1]
    assert main.run(0.25, path) == 0


def test_trop_vieux_pas_de_rattrapage(scan, tmp_path):
    path = str(tmp_path / "sent.json")
    main.run(0.25, path)
    scan["signals"] = [_signal(config.CATCHUP_HOURS * 60 + 5)]
    assert main.run(0.25, path) == 0


def test_deux_setups_sur_la_meme_bougie_partent_tous_les_deux(scan, tmp_path):
    path = str(tmp_path / "sent.json")
    main.run(0.25, path)
    first = _signal(5, "Sweep")
    other = Signal("ES", "15M", "OPR - sortie", "achat", first.time, 1, 0, 3, 2, "FRTM", [])
    scan["signals"] = [first, other]
    assert main.run(0.25, path) == 2


def test_echec_denvoi_garde_ce_qui_est_parti_et_retente_le_reste(scan, tmp_path, monkeypatch):
    path = str(tmp_path / "sent.json")
    main.run(0.25, path)
    scan["signals"] = [_signal(5, "Sweep"), _signal(5, "OPR - sortie")]
    calls = []

    def flaky(cap, img, name):
        calls.append(cap)
        if len(calls) == 2:
            raise RuntimeError("Telegram")

    monkeypatch.setattr(main, "send_photo", flaky)
    with pytest.raises(RuntimeError):
        main.run(0.25, path)
    assert len(json.loads(open(path, encoding="utf-8").read())) == 1
    monkeypatch.setattr(main, "send_photo", lambda cap, img, name: None)
    assert main.run(0.25, path) == 1


def test_erreur_sur_un_actif_nempeche_pas_les_autres(scan, tmp_path, monkeypatch):
    path = str(tmp_path / "sent.json")
    main.run(0.25, path)
    monkeypatch.setattr(config, "ASSETS", {"GOLD": "GC=F", "ES": "ES=F"})
    good = main.get_candles

    def flaky(ticker, tf):
        if ticker == "GC=F":
            raise RuntimeError("Aucune donnée Yahoo")
        return good(ticker, tf)

    monkeypatch.setattr(main, "get_candles", flaky)
    scan["signals"] = [_signal(5)]
    with pytest.raises(RuntimeError, match="GOLD"):
        main.run(0.25, path)
    assert len(scan["sent"]) == 1  # ES est parti malgré GOLD
    assert len(json.loads(open(path, encoding="utf-8").read())) == 1  # et ne repartira pas


def _bars():
    rows = [(100, 100.8, 99.2, 100 + (0.5 if i % 2 else -0.5)) for i in range(30)] + [(96.4, 96.9, 96.3, 96.8)]
    idx = pd.date_range("2026-10-01 10:00", periods=len(rows), freq="15min", tz=main.NY)
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx).assign(volume=0)


def test_bulle_en_simple_information_sans_plan_de_trade():
    df = _bars()
    s = bulles.detect(df, "ES", "15M")[-1]
    text = main.caption(s)
    assert "INFO" in text and "contexte seulement" in text and "hausse" in text
    for mot in ("ACHAT", "Entrée", "Stop", "Objectif", "R/R", "Risque"):
        assert mot not in text
    assert main.render(df, s).startswith(b"\x89PNG")


def test_les_autres_setups_gardent_leur_plan_de_trade():
    df = _bars()
    s = Signal("ES", "15M", "OPR - sortie", "achat", df.index[-1], 96.8, 96, 98, 2, "FRTM", ["Risque conseillé : 1 %"])
    text = main.caption(s)
    assert "ACHAT" in text and "Entrée 96.8" in text and "Risque" in text and "INFO" not in text
    assert main.render(df, s).startswith(b"\x89PNG")


def test_sans_state_le_comportement_dessai_ne_change_pas(scan):
    scan["signals"] = [_signal(5), _signal(60)]
    assert main.run(0.25) == 1
    assert main.run(2) == 2
