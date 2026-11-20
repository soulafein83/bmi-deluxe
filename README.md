# BMI Deluxe

Zaawansowany kalkulator BMI (CLI + GUI webowe).

## Uruchomienie

```bash
python bmi.py
python bmi.py -w 70 -z 1.75 --wiek 30 --plec M --tdee
python bmi_web.py        # GUI w przeglądarce
python bmi_desktop.py    # GUI desktop (wymaga PySide6)
```

Instalacja desktop GUI:
```bash
python -m pip install PySide6 matplotlib
```

## Testy

```bash
python -m pytest -q
```