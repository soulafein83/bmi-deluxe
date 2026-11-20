"""Testy core obliczen Kalkulatora."""

import math
import pytest

import bmi


def test_oblicz_bmi():
    assert bmi.BMICalculator.oblicz_bmi(70.0, 1.75) == pytest.approx(22.857, rel=1e-3)
    with pytest.raises(ValueError):
        bmi.BMICalculator.oblicz_bmi(0, 1.75)
    with pytest.raises(ValueError):
        bmi.BMICalculator.oblicz_bmi(70, 0)


def test_kategoria_who():
    assert bmi.BMICalculator.kategoria(22.86)[0] == "Prawidłowa masa"
    assert bmi.BMICalculator.kategoria(17.0)[0] == "Niedowaga"
    assert bmi.BMICalculator.kategoria(32.0)[0] == "Otyłość I stopnia"
    assert bmi.BMICalculator.kategoria(100.0)[0] == "Otyłość III stopnia"


def test_zdrowy_zakres():
    lo, hi = bmi.BMICalculator.zdrowy_zakres_kg(1.75)
    assert lo == pytest.approx(18.5 * 1.75 ** 2)
    assert hi == pytest.approx(25.0 * 1.75 ** 2)


def test_bmi_prime():
    assert bmi.BMICalculator.bmi_prime(25.0) == 1.0


def test_kategoria_tłuszczu():
    kat, _ = bmi.kategoria_tłuszczu(3.0, "M")
    assert kat == "Składnik (minimalny)"
    kat, _ = bmi.kategoria_tłuszczu(20.0, "K")
    assert kat == "Atletyczny"

