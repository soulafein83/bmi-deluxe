"""Testy warstwy historii."""

import pytest

import bmi


def test_edytuj_przelicza_bmi(tmp_path):
    h = bmi.Historia(str(tmp_path / "h.json"))
    h.dodaj(bmi.Pomiar("2026-01-01", 70.0, 1.75, 22.857142857142858))
    assert h.edytuj(0, waga=80.0) is True
    wpisy = h.wczytaj()
    assert len(wpisy) == 1
    assert wpisy[0].waga == 80.0
    assert wpisy[0].bmi == pytest.approx(80.0 / (1.75 ** 2), rel=1e-6)


def test_edytuj_nieistniejacy_indeks(tmp_path):
    h = bmi.Historia(str(tmp_path / "h.json"))
    assert h.edytuj(5, waga=80.0) is False


def test_usun_dziala(tmp_path):
    h = bmi.Historia(str(tmp_path / "h.json"))
    h.dodaj(bmi.Pomiar("2026-01-01", 70.0, 1.75, 22.857142857142858))
    assert h.usun(0) is True
    assert h.wczytaj() == []


def test_usun_nieistniejacy_indeks(tmp_path):
    h = bmi.Historia(str(tmp_path / "h.json"))
    assert h.usun(0) is False