#!/usr/bin/env python3
"""
Zaawansowany KALKULATOR BMI „Deluxe"
=====================================

Różnice względem bmi.py (wszystkie wprowadzone ulepszenia):

  * architektura w postaci klas (Historia, BMICalculator, Raport)
  * walidacja inputu z limity sensownymi i poleceniami q/quit
  * jednostki metryczne IMPERIALNE (-w/--unit), konwersja automatyczna
  * więcej metryków: BMI Prime, BMI dla dzieci (procentyl LMS CDC),
    błąd zaokrąglenia, masа beztłuszczowa (FFM), procent tłuszczu
    (Deurenberg, Ross), RMR/TDEE (Harris-Benedict, Mifflin-St Jeor)
  * cele wagowe (ile kg przyjąć/stracić dla zadanego BMI)
  * Historia: walidacja JSON, atomowy zapis, usuwanie/edycja wpisów,
    sort/filtr, eksport/import CSV
  * formaty wykresów: PNG, SVG, PDF (+ interaktywny Plotly jeśli dostępny)
  * paleta przyjazna odbiorcom z daltonizmem + pionowa legenda
  * kolorowy output przy TTY (--no-color), liczby wg lokalizacji (--pl)
  * maszynowy输出: --json ; link udostępnienia (--share-url)

UWAGA: Narzędzie ma charakter wyłącznie informacyjny i nie zastępuje
konsultacji medycznej.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
import tempfile
import urllib.parse
from dataclasses import dataclass, field, asdict
from datetime import date, datetime

DEFAULT_HISTORIA = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "bmi_historia_deluxe.json")

try:
    from locale import localeconv
except ImportError:  # bardzo eksotyczne środowisko
    localeconv = None

try:
    from statistics import NormalDist
except ImportError:
    NormalDist = None

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    HAS_MPL = True
except ImportError:
    plt = None
    HAS_MPL = False

try:
    import plotly.graph_objects as gobj  # type: ignore
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False

NORMAL_DIST = NormalDist() if NormalDist is not None else None

# ------------------------------------------------------------------ paleta
# Paleta przyjazna odbiorcom z daltonizmem (wzorowana na Okabe-Ito).
PALETA = [
    "#2166AC", "#D6604D", "#439A3D", "#E16D62",
    "#9B72AA", "#BFA587", "#5F9BD6", "#C67A5C",
]

KATEGORIE_WHO = [
    ("Niedowaga",                 0.0,  18.5, PALETA[0],
     "Rozważ konsultację z dietetykiem/lekarzem."),
    ("Prawidłowa masa",          18.5,  25.0, PALETA[2],
     "Bardzo dobrze! Podtrzymuj styl życia."),
    ("Nadwaga",                   25.0,  30.0, PALETA[1],
     "Warto wprowadzić aktywność i lekko ograniczyć kalorie."),
    ("Otyłość I stopnia",         30.0,  35.0, PALETA[3],
     "Zalecana konsultacja lekarska i plan odchudzania."),
    ("Otyłość II stopnia",        35.0,  40.0, PALETA[6],
     "Wysokie ryzyko zdrowotne — skontaktuj się z lekarzem."),
    ("Otyłość III stopnia",       40.0, 99.0, PALETA[1],
     "Otyłość skrajna — pilna opieka medyczna."),
]

# Dolny/ Górny brzeg strefy zdrowej zgodnie z KATEGORIE_WHO (spójne 25.0).
BMI_MIN_ZDROWY, BMI_MAX_ZDROWY = 18.5, 25.0

# Syntetyczna paleta kategorii (maks. 6 pasujących do KATEGORIE_WHO).
KOLORY_KATEGORII = {nazwa: kolor for nazwa, _, _, kolor, _ in KATEGORIE_WHO}

# ---------------------------------------------------------------- LMS CDC
# BMI-for-age LMS (L = skośność, M = mediana, S = log-sigma) dla dzieci
# wg wykresów wzrostu CDC. Wartości przybliżone — wyłącznie informacyjne.
_CHLOPCZY_LMS = {
    2: (12.606, 14.5, 0.0902),  3: (12.064, 15.3, 0.0932),
    4: (11.378, 16.2, 0.0982),  5: (10.721, 16.7, 0.1010),
    6: (10.2656, 17.1, 0.1025), 7: (9.5540, 17.6, 0.1048),
    8: (8.8799, 18.1, 0.1068),  9: (8.2832, 18.7, 0.1072),
    10: (7.7912, 19.4, 0.1076), 11: (7.3611, 20.2, 0.1079),
    12: (6.9876, 21.1, 0.1095), 13: (6.6551, 21.9, 0.1121),
    14: (6.3550, 22.7, 0.1156), 15: (6.0803, 23.4, 0.1199),
    16: (5.8254, 24.0, 0.1248), 17: (5.5887, 24.5, 0.1302),
    18: (5.3675, 25.0, 0.1360), 19: (5.1599, 25.5, 0.1416),
    20: (4.9652, 25.9, 0.1474),
}
_DZIEWCZTY_LMS = {
    2: (12.606, 14.3, 0.0873),  3: (12.074, 15.1, 0.0906),
    4: (11.159, 15.9, 0.0946),  5: (10.653, 16.3, 0.0979),
    6: (10.090, 16.7, 0.1012),  7: (9.5471, 17.0, 0.1042),
    8: (8.9987, 17.6, 0.1071),  9: (8.4417, 18.3, 0.1086),
    10: (7.9113, 19.0, 0.1092), 11: (7.4126, 19.8, 0.1089),
    12: (6.9595, 20.6, 0.1077), 13: (6.5520, 21.3, 0.1064),
    14: (6.1909, 22.0, 0.1068), 15: (5.8498, 22.6, 0.1085),
    16: (5.5194, 23.0, 0.1114), 17: (5.1964, 23.4, 0.1151),
    18: (4.8782, 23.9, 0.1192), 19: (4.5631, 24.5, 0.1237),
    20: (4.2503, 25.0, 0.1286),
}

# Aktywność fizyczna mnożnika RMR.
AKTYWNOSC = {
    "siedzący":   (1.20,  "praca przy biurku, brak ćwiczeń"),
    "lekkie":     (1.375, "1–3 dni ćwiczeń w tygodniu"),
    "umiarkowe":  (1.50,  "3–5 dni ćwiczeń w tygodniu"),
    "active":     (1.725, "6–7 dni ćwiczeń w tygodniu"),
    "bardzo":     (1.90,  "ciężka praca / 2x dziennie trening"),
}

# Limity walidacji (metryczne).
LIMITY = {"waga_kg": (2.0, 700.0), "wzrost_m": (0.40, 2.60), "wiek": (0, 120)}


# ------------------------------------------------------------------- kolory

class Kolory:
    """ANSI – włącza/koloruje output tylko, gdy terminal to TTY."""

    KOD = {
        "reset": "\033[0m", "bold": "\033[1m", "dim": "\033[2m",
        "red": "\033[31m", "green": "\033[32m", "yellow": "\033[33m",
        "blue": "\033[34m", "magenta": "\033[35m", "cyan": "\033[36m",
        "gray": "\033[90m",
    }

    def __init__(self, wlczone: bool = True):
        self.wlczone = wlczone

    def __call__(self, tekst: str, k: str) -> str:
        if not self.wlczone or k not in self.KOD:
            return tekst
        return f"{self.KOD[k]}{tekst}{self.KOD['reset']}"


# ----------------------------------------------------------------- formatowanie

def liczba(n: float, cyfry: int = 2, pl: bool = False) -> str:
    """Formatuje liczbę z separatorem tysięcy; dla --pl używa przecinka."""
    if n is None or (isinstance(n, float) and math.isnan(n)):
        return "—"
    s = f"{n:.{cyfry}f}"
    if not pl:
        return f"{n:,.{cyfry}f}"
    int_part, dec_part = s.split(".")
    grouped = "{:,}".format(int(int_part)).replace(",", ".")
    return f"{grouped},{dec_part}"


# ------------------------------------------------------------------- dane

@dataclass
class Pomiar:
    data: str
    waga: float
    wzrost: float
    bmi: float
    wiek: int | None = None
    plec: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def z_dict(cls, d: dict) -> "Pomiar":
        return cls(
            data=str(d.get("data", date.today().isoformat())),
            waga=float(d["waga"]), wzrost=float(d["wzrost"]),
            bmi=float(d["bmi"]),
            wiek=int(d["wiek"]) if d.get("wiek") is not None else None,
            plec=str(d["plec"]).upper() if d.get("plec") else None,
        )


class Historia:
    """Warstwa danych historii z atomowym zapisem i walidacją."""

    def __init__(self, sciezka: str | None = None):
        self.sciezka = sciezka or DEFAULT_HISTORIA

    # -- odczyt
    def wczytaj(self) -> list[Pomiar]:
        if not self.sciezka or not os.path.exists(self.sciezka):
            return []
        try:
            with open(self.sciezka, encoding="utf-8") as f:
                surowe = json.load(f)
        except (json.JSONDecodeError, OSError):
            return []
        if not isinstance(surowe, list):
            return []
        wynik = []
        for surow in surowe:
            if not isinstance(surow, dict) or "waga" not in surow or "bmi" not in surow:
                continue  # ignoruj uszkodzone/wpisy niepasujące do schematu
            try:
                wynik.append(Pomiar.z_dict(surow))
            except (ValueError, TypeError, KeyError):
                continue
        return wynik

    # -- zapis (atomowy)
    def _zapisz(self, wpisy: list[Pomiar]) -> None:
        danie = [p.to_dict() for p in wpisy]
        katalog = os.path.dirname(os.path.abspath(self.sciezka))
        os.makedirs(katalog, exist_ok=True)
        fd, tymczasowy = tempfile.mkstemp(dir=katalog, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(danie, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tymczasowy, self.sciezka)  # atomowa zamiana
        except OSError:
            if os.path.exists(tymczasowy):
                os.remove(tymczasowy)
            raise

    def dodaj(self, p: Pomiar) -> Pomiar:
        wpisy = self.wczytaj()
        wpisy.append(p)
        self._zapisz(wpisy)
        return p

    def usun(self, idx: int) -> bool:
        wpisy = self.wczytaj()
        if not 0 <= idx < len(wpisy):
            return False
        del wpisy[idx]
        self._zapisz(wpisy)
        return True

    def edytuj(self, idx: int, **pole) -> bool:
        wpisy = self.wczytaj()
        if not 0 <= idx < len(wpisy):
            return False
        for k, v in pole.items():
            if v is not None and hasattr(wpisy[idx], k):
                setattr(wpisy[idx], k, v)
        self._zapisz(wpisy)
        return True

    def lista(self, sortuj: str | None = None, od: str | None = None,
              od_daty: str | None = None, do_daty: str | None = None) -> list[Pomiar]:
        wpisy = self.wczytaj()
        if od_daty:
            wpisy = [p for p in wpisy if p.data >= od_daty]
        if do_daty:
            wpisy = [p for p in wpisy if p.data <= do_daty]
        order = 1 if od == "asc" else -1
        if sortuj == "data":
            wpisy.sort(key=lambda p: p.data, reverse=(order != 1))
        elif sortuj == "bmi":
            wpisy.sort(key=lambda p: p.bmi, reverse=(order != 1))
        elif sortuj == "waga":
            wpisy.sort(key=lambda p: p.waga, reverse=(order != 1))
        elif sortuj in ("asc", "desc"):
            wpisy.sort(key=lambda p: p.data, reverse=(sortuj == "desc"))
        return wpisy

    def czyszcza(self) -> None:
        if os.path.exists(self.sciezka):
            os.remove(self.sciezka)

    def eksport_csv(self, sciezka: str) -> int:
        wpisy = self.wczytaj()
        with open(sciezka, "w", newline="", encoding="utf-8") as f:
            n = csv.writer(f)
            n.writerow(["data", "waga_kg", "wzrost_m", "bmi", "wiek", "plec"])
            for p in wpisy:
                n.writerow([p.data, p.waga, p.wzrost, p.bmi,
                            p.wiek if p.wiek is not None else "",
                            p.plec if p.plec else ""])
        return len(wpisy)

    def import_csv(self, sciezka: str) -> int:
        wpisy = self.wczytaj()
        with open(sciezka, newline="", encoding="utf-8") as f:
            for rz in csv.DictReader(f):
                try:
                    wpisy.append(Pomiar(
                        data=rz["data"], waga=float(rz["waga_kg"]),
                        wzrost=float(rz["wzrost_m"]), bmi=float(rz["bmi"]),
                        wiek=int(rz["wiek"]) if rz.get("wiek") else None,
                        plec=(rz["plec"] or None),
                    ))
                except (ValueError, KeyError, TypeError):
                    continue
        self._zapisz(wpisy)
        return len(wpisy)


# ------------------------------------------------------------- kalkulacje

class BMICalculator:
    """Wzorce i obliczenia – bez stanu (stad łatwe do testowania)."""

    @staticmethod
    def walidacja(waga_kg: float, wzrost_m: float) -> None:
        lo_hi = (LIMITY["waga_kg"], LIMITY["wzrost_m"])
        if not lo_hi[0][0] <= waga_kg <= lo_hi[0][1]:
            raise ValueError(f"Waga {waga_kg:.1f} kg poza zakresem "
                             f"{lo_hi[0][0]:.0f}–{lo_hi[0][1]:.0f} kg.")
        if not lo_hi[1][0] <= wzrost_m <= lo_hi[1][1]:
            raise ValueError(f"Wzrost {wzrost_m:.2f} m poza zakresem "
                             f"{lo_hi[1][0]:.2f}–{lo_hi[1][1]:.2f} m.")

    @staticmethod
    def oblicz_bmi(waga_kg: float, wzrost_m: float) -> float:
        BMICalculator.walidacja(waga_kg, wzrost_m)
        return waga_kg / (wzrost_m ** 2)

    @staticmethod
    def kategoria(bmi: float):
        for nazwa, dol, gor, kolor, rada in KATEGORIE_WHO:
            if dol <= bmi < gor:
                return nazwa, kolor, rada
        n, _, _, k, r = KATEGORIE_WHO[-1]
        return n, k, r

    @staticmethod
    def bld_zaokrglenia(waga_kg: float, wzrost_m: float, krok: float = 0.05) -> tuple[float, float]:
        """Przedział BMI wynikający z zaokrąglenia wagi/wzrostu (±krok)."""
        lo = BMICalculator.oblicz_bmi(max(waga_kg - krok, 0.01), wzrost_m + krok)
        hi = BMICalculator.oblicz_bmi(waga_kg + krok, max(wzrost_m - krok, 0.01))
        return min(lo, hi), max(lo, hi)

    @staticmethod
    def zdrowy_zakres_kg(wzrost_m: float) -> tuple[float, float]:
        return BMI_MIN_ZDROWY * wzrost_m ** 2, BMI_MAX_ZDROWY * wzrost_m ** 2

    @staticmethod
    def bmi_prime(bmi: float) -> float:
        return bmi / 25.0

    # -- procent tłuszczu / FFM
    @staticmethod
    def tuk_deurenberg(bmi: float, wiek: int, plec: str) -> float:
        s = 1 if plec == "M" else 0
        return 1.20 * bmi + 0.23 * wiek - 10.8 * s - 5.4

    @staticmethod
    def tuk_ross(bmi: float, wiek: int, plec: str) -> float:
        if plec == "M":
            return 1.63 * bmi + 0.44 * wiek - 15.08 - 12.56
        return 1.62 * bmi + 0.24 * wiek - 12.38 * (1 if plec == "K" else 0) - 16.32

    @staticmethod
    def tuk_niezalezny(bmi: float) -> float:
        return 1.39 * bmi - 16.0  # wersja bez uwzględnienia płci

    @staticmethod
    def ffm(bmi: float, wiek: int, plec: str, waga_kg: float) -> float | None:
        t = BMICalculator.tuk_deurenberg(bmi, wiek, plec)
        if not (0 < t < 100):
            return None
        tuk_w = waga_kg * t / 100.0
        return max(waga_kg - tuk_w, 0.0)

    # -- TDEE / RMR
    @staticmethod
    def rmr_mifflin(waga_kg: float, wzrost_m: float, wiek: int, plec: str) -> float:
        s = 5 if plec == "M" else -161
        return 10 * waga_kg + 6.25 * wzrost_m * 100 - 5 * wiek + s

    @staticmethod
    def rmr_harris(waga_kg: float, wzrost_m: float, wiek: int, plec: str) -> float:
        if plec == "M":
            return 88.362 + 13.397 * waga_kg + 4.799 * wzrost_m * 100 - 5.677 * wiek
        return 447.593 + 9.247 * waga_kg + 3.098 * wzrost_m * 100 - 4.330 * wiek

    # -- procentyl BMI dla dzieci (LMS, CDC)
    @staticmethod
    def procentil_bmi(bmi: float, wiek: int, plec: str):
        if not (2 <= wiek <= 20):
            return None
        tabela = _CHLOPCZY_LMS if plec == "M" else _DZIEWCZTY_LMS
        if int(wiek) not in tabela:
            return None
        L, M, S = tabela[int(wiek)]
        if L != 0:
            z = ((bmi / M) ** L - 1.0) / (L * S)
        else:
            z = math.log(bmi / M) / S
        if NORMAL_DIST is None:
            # fallback: aproksymacja CDF przez math.erf
            procentil = 0.5 * (1 + math.erf(z / math.sqrt(2))) * 100.0
        else:
            procentil = NORMAL_DIST.cdf(z) * 100.0
        return {"scor": round(z, 2), "procentyl": round(procentil, 1)}

    # -- cel wagowy
    @staticmethod
    def cel_wagowy(waga_kg: float, wzrost_m: float, bmi_cel: float) -> dict:
        bmi = BMICalculator.oblicz_bmi(waga_kg, wzrost_m)
        waga_cel = bmi_cel * wzrost_m ** 2
        delta = waga_cel - waga_kg
        return {"bmi_cel": bmi_cel, "waga_cel": round(waga_cel, 1),
                "delta": round(delta, 1),
                "kierunek": "stracić" if delta < 0 else "przyjąć"}

    @staticmethod
    def share_url(waga_kg: float, wzrost_m: float, **extra) -> str:
        q = f"{waga_kg:g}/{wzrost_m*100:g}"
        for k, v in extra.items():
            if v not in (None, ""):
                q += f"-{urllib.parse.quote(str(v), safe='')}"
        return f"https://kalkulator-bmi.example/bmi/{urllib.parse.quote(q, safe='/')}"


def tdee(rmr: float, poziom: str) -> float:
    return rmr * AKTYWNOSC.get(poziom, AKTYWNOSC["siedzący"])[0]


def kategoria_tłuszczu(bf: float, plec: str) -> tuple[str, str]:
    """Kategoria tłuszczu cielesnego wg standardowych zakresów (ACSM)."""
    if plec == "M":
        ranges = [
            (5, "Składnik (minimalny)"), (14, "Atletyczny"), (18, "Fitness"),
            (25, "Przeciętny"), (31, "Nadwaga"), (100, "Otyłość"),
        ]
    else:
        ranges = [
            (13, "Składnik (minimalny)"), (21, "Atletyczny"), (25, "Fitness"),
            (32, "Przeciętny"), (39, "Nadwaga"), (100, "Otyłość"),
        ]
    for cutoff, label in ranges:
        if bf < cutoff:
            return label, f"{bf:.1f}% tłuszczu"
    return "Otyłość", f"{bf:.1f}% tłuszczu"


def _plural(n: int, forms: tuple[str, str, str]) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return forms[0]
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return forms[1]
    return forms[2]


def _format_duration(months: float) -> str:
    total = int(round(months))
    years, rem = divmod(total, 12)
    parts = []
    if years:
        parts.append(f"{years} {_plural(years, ('rok', 'lata', 'lat'))}")
    if rem or not parts:
        parts.append(f"{rem} {_plural(rem, ('miesiąc', 'miesiące', 'miesięcy'))}")
    return " ".join(parts)


# ------------------------------------------------------------------ raport

class Raport:
    def __init__(self, kol: Kolory, pl: bool = False):
        self.k = kol
        self.pl = pl

    def linia(self, tekst: str = "") -> str:
        return "=" * 52 if tekst == "" else tekst

    def raport(self, *, bmi, waga_kg, wzrost_m, wiek=None, plec=None,
                calornic=False, poziom_aktywnosci="siedzący",
                bmi_cel=None, bled=False, imperial=False) -> str:
        n, kol, rada = BMICalculator.kategoria(bmi)
        kolor = KOLORY_KATEGORII[n]
        lo, hi = BMICalculator.zdrowy_zakres_kg(wzrost_m)
        c = self.k
        L = self.linia
        w = []

        def l(v, d):
            return liczba(v, d, self.pl)

        def u(n):  # jednostki
            return "lbs" if imperial else "kg"

        waga_wysw = waga_kg * 2.20462 if imperial else waga_kg
        jedn_wagi = "lbs" if imperial else "kg"

        w.append(c(L(), "cyan"))
        w.append(c("          KALKULATOR BMI — WYNIK (Deluxe)", "bold"))
        w.append(c(L(), "cyan"))
        w.append(c(f"  Waga:              {l(waga_wysw,1)} {jedn_wagi:<3}", "white"))
        w.append(c(f"  Wzrost:            {l(wzrost_m*100,1)} cm", "white"))
        w.append(c(f"  BMI:               {l(bmi,2)}", "bold"))
        w.append(c(f"  Kategoria (WHO):   {c(n, 'yellow' if n in ('Niedowaga','Otyłość III stopnia') else 'green')}", "white"))
        w.append(c(f"  BMI Prime:         {l(BMICalculator.bmi_prime(bmi),2)}  (1.0 = 25)", "white"))
        if bled:
            blo, bhi = BMICalculator.bld_zaokrglenia(waga_kg, wzrost_m)
            w.append(c(f"  Zakres BMI (pog.): [{l(blo,2)} – {l(bhi,2)}]", "gray"))
        w.append(c(f"  Zdrowy zakres:     {l(lo,1)} – {l(hi,1)} kg", "white"))
        if bmi_cel is not None:
            cel = BMICalculator.cel_wagowy(waga_kg, wzrost_m, bmi_cel)
            w.append(c(f"  Cel ({bmi_cel} BMI): {l(cel['waga_cel'],1)} kg "
                       f"({'stracić' if cel['delta']<0 else 'przyjąć'} {l(abs(cel['delta']),1)} kg)", "cyan"))
        if wiek and plec:
            tf = BMICalculator.tuk_deurenberg(bmi, wiek, plec)
            r = BMICalculator.tuk_ross(bmi, wiek, plec)
            if 0 < tf < 70:
                w.append(c(f"  TŁUSZCZ (~{l(tf,1)}% Deurenberg)  |  {l(r,1)}% Ross", "white"))
                kat_tf, _ = kategoria_tłuszczu(tf, plec)
                w.append(c(f"  Kategoria tłuszczu: {kat_tf}", "gray"))
            ffm = BMICalculator.ffm(bmi, wiek, plec, waga_kg)
            if ffm:
                w.append(c(f"  Masa beztłuszczowa: ~{l(ffm,1)} kg", "white"))
            p = BMICalculator.procentil_bmi(bmi, wiek, plec)
            if p:
                w.append(c(f"  Procentyl BMI (dzieci): {l(p['procentyl'],0)}%  (z={l(p['scor'],2)})", "cyan"))
            if calornic:
                rmr_m = BMICalculator.rmr_mifflin(waga_kg, wzrost_m, wiek, plec)
                rmr_h = BMICalculator.rmr_harris(waga_kg, wzrost_m, wiek, plec)
                w.append(c(f"  RMR: {l(rmr_m,0)} kcal | TDEE: {l(tdee(rmr_m, poziom_aktywnosci),0)} kcal", "white"))
        w.append(c(L(), "cyan"))
        w.append(c(f"  Rada: {rada}", "gray"))
        w.append(c(L(), "cyan"))
        return "\n".join(w)

    def pasek(self, bmi: float, szerokosc: int = 60) -> str:
        min_v, max_v, poz = 12.0, 44.0, None
        pozycja = max(0, min(szerokosc - 1, int((bmi - min_v) / (max_v - min_v) * (szerokosc - 1))))
        linia = [" "] * szerokosc
        for nazwa, dol, gor, kolor, _ in KATEGORIE_WHO:
            a = int((max(dol, min_v) - min_v) / (max_v - min_v) * (szerokosc - 1))
            b = int((min(gor, max_v) - min_v) / (max_v - min_v) * (szerokosc - 1))
            for i in range(a, b):
                linia[i] = "█"
        linia[pozycja] = "▲"
        pasek = "".join(linia)
        buf, licznik = [], 0
        for idx, ch in enumerate(pasek):
            buf.append(ch)
            licznik += 1
            if idx > 0 and licznik % 10 == 0:
                buf.append("|")
        pasek = "".join(buf).rstrip()
        col = pasek.index("▲")
        znacznik = " " * (col + 1) + "└─ twoje BMI"
        return f"{pasek}\n{ znacznik}"


# ------------------------------------------------------------------ wykresy

def _potrzebny_mpl():
    if not HAS_MPL:
        raise RuntimeError("matplotlib jest niedostępny")
    assert plt is not None
    assert mpatches is not None


def rysuj_gauge(bmi, sciezka, waga_kg, wzrost_m, fmt: str = "png",
                  imperial: bool = False) -> str:
    _potrzebny_mpl()
    min_v, max_v = 12.0, 42.0
    fig, ax = plt.subplots(figsize=(9, 3.4), dpi=110)
    ax.set_xlim(min_v, max_v)
    ax.set_ylim(0, 10)
    ax.axis("off")
    ax.set_title("Twoje BMI na skali WHO", fontsize=14, fontweight="bold", pad=12)

    for nazwa, dol, gor, kolor, _ in KATEGORIE_WHO:
        a, b = max(dol, min_v), min(gor, max_v)
        ax.barh(5, b - a, left=a, height=2.2, color=kolor, alpha=0.85,
                edgecolor="white", linewidth=1.5)
        środek = (a + b) / 2
        if b - a > 2.5:
            ax.text(środek, 5, f"{a:g}–{b:g}", ha="center", va="center",
                    fontsize=8.5, color="white", fontweight="bold")

    strzalka_x = min(max(bmi, min_v), max_v)
    ax.add_patch(mpatches.Polygon(
        [(strzalka_x - 0.9, 8.4), (strzalka_x + 0.9, 8.4), (strzalka_x, 6.6)],
        color="#1d3557", zorder=5))
    ax.text(strzalka_x, 8.8, f"BMI {bmi:.1f}", ha="center", va="bottom",
            fontsize=11, fontweight="bold", color="#1d3557")

    lo, hi = BMICalculator.zdrowy_zakres_kg(wzrost_m)
    jednostka = "lbs" if imperial else "kg"
    ax.text((min_v + max_v) / 2, 3.0,
            f"Zdrowa waga dla {wzrost_m * 100:.0f} cm: {lo:.1f}–{hi:.1f} {jednostka}",
            ha="center", fontsize=9.5)
    ax.text((min_v + max_v) / 2, 1.4,
            f"Waga: {waga_kg:.1f} {jednostka}   Wzrost: {wzrost_m * 100:.1f} cm",
            ha="center", fontsize=9, color="#555")
    fig.savefig(sciezka, bbox_inches="tight")
    plt.close(fig)
    return sciezka


def rysuj_historia(sciezka, fmt: str = "png",
                     sciezka_historia: str | None = None) -> str | None:
    hist = Historia(sciezka_historia)
    wpisy = hist.wczytaj()
    if len(wpisy) < 2:
        return None
    _potrzebny_mpl()
    fig, ax = plt.subplots(figsize=(9, 4.5), dpi=110)
    ax.axhspan(BMI_MIN_ZDROWY, BMI_MAX_ZDROWY, color=KOLORY_KATEGORII["Prawidłowa masa"],
               alpha=0.25, label="Zdrowy zakres (18.5–25)")
    for dol, kolor in [(25, KOLORY_KATEGORII["Nadwaga"]),
                       (30, KOLORY_KATEGORII["Otyłość I stopnia"]),
                       (35, KOLORY_KATEGORII["Otyłość II stopnia"])]:
        ax.axhline(dol, color=kolor, linestyle="--", linewidth=1)

    dane = sorted(wpisy, key=lambda e: e.data)
    xs, ys, kolory = [], [], []
    for p in dane:
        xs.append(p.data); ys.append(p.bmi)
        kolory.append(KOLORY_KATEGORII[BMICalculator.kategoria(p.bmi)[0]])
    ax.plot(xs, ys, color="#1d3557", linewidth=2, marker="o", zorder=3, label="BMI")
    for x, y, c in zip(xs, ys, kolory):
        ax.scatter([x], [y], s=70, color=c, edgecolor="white", zorder=4)
        ax.annotate(f"{y:.1f}", (x, y), textcoords="offset points",
                    xytext=(0, 9), ha="center", fontsize=8)

    ax.set_title("Trend BMI w czasie", fontsize=13, fontweight="bold")
    ax.set_ylabel("BMI"); ax.set_xlabel("Data pomiaru")
    ax.legend(loc="best"); ax.grid(True, alpha=0.3)
    fig.autofmt_xdate(); fig.tight_layout()
    fig.savefig(sciezka, bbox_inches="tight")
    plt.close(fig)
    return sciezka


def rysuj_historia_interaktywna(wpisy) -> str | None:
    if not HAS_PLOTLY or len(wpisy) < 2:
        return None
    kol = [KOLORY_KATEGORII[BMICalculator.kategoria(p.bmi)[0]] for p in wpisy]
    fig = gobj.Figure(data=[
        gobj.Scatter(x=[p.data for p in wpisy], y=[p.bmi for p in wpisy],
                     mode="markers+lines", marker=dict(color=kol, size=9))
    ])
    fig.update_layout(title="Trend BMI (interaktywny)", xaxis_title="Data", yaxis_title="BMI")
    sciezka = "bmi_historia_interaktywna.html"
    fig.write_html(sciezka)
    return sciezka


# --------------------------------------------------------------- tryb inter

POMOC = """
Kalkulator BMI (Deluxe) — polecenia:
  waga            - waga w kg (lub 2.20462 lbs po --unit imperial)
  wzrost          - wzrost w metrach
  wiek            - lat (opcja)
  plec            - M lub K (opcja)
  tdee            - oblicz RMR/TDEE (wyma wiek i plec); nast. pytanie o aktywność
  cel <bmi>       - cele wagowe (np. cel 22)
  history         - pokaż historię
  clr             - wyczyść historię
  k               - koniec
"""


def czytaj(prompt, limity=None) -> float | None:
    while True:
        s = input(prompt).strip()
        try:
            v = float(s)
        except ValueError:
            if s.lower() in ("q", "quit", "x"):
                return None
            print("  Wpisz liczbę (lub k = wyjście).")
            continue
        if limity and not (limity[0] <= v <= limity[1]):
            print(f"  {v} poza zakresem {limity[0]}–{limity[1]}.")
            continue
        return v


def tryb_interaktywny(historia: Historia, kol: Kolory, pl: bool,
                      imperial: bool, format_wykresu: str) -> None:
    r = Raport(kol, pl)
    print(kol("=== KALKULATOR BMI (Deluxe) ===", "cyan"))
    print(kol(POMOC, "gray"))
    while True:
        waga = czytaj("Waga (kg/lbs, k = wyjście): ", LIMITY["waga_kg"])
        if waga is None:
            break
        wzrost = czytaj("Wzrost (m, k = wyjście): ", LIMITY["wzrost_m"])
        if wzrost is None:
            break
        try:
            wiek = int(input("Wiek (pusto = pominąć): ") or "0") or None
        except ValueError:
            print("  Wiek musi być liczbą — pomijam.")
            wiek = None
        plec_raw = (input("Płeć (M/K, pusto = pominąć): ") or "").strip().lower()
        plec = {"m": "M", "k": "K"}.get(plec_raw[:1])
        try:
            bmi = BMICalculator.oblicz_bmi(waga, wzrost)
        except ValueError as e:
            print(kol(f"Błąd: {e}", "red"))
            continue
        print()
        print(r.raport(bmi=bmi, waga_kg=waga, wzrost_m=wzrost, wiek=wiek, plec=plec,
                       bled=True))
        print()
        print(r.pasek(bmi))
        wp = historia.dodaj(Pomiar(date.today().isoformat(), waga, wzrost, bmi, wiek, plec))
        print(kol(f"[ok] Dodano do historii: {wp.data}", "green"))
        if HAS_MPL:
            baza = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bmi_wykres")
            print(kol(f"[ok] Wykres pozycji BMI: {rysuj_gauge(bmi, f'{baza}_gauge.{format_wykresu}', waga, wzrost, format_wykresu, imperial)}", "green"))
            p2 = rysuj_historia(f"{baza}_historia.{format_wykresu}", format_wykresu)
            print(kol(f"[ok] Wykres historii BMI: {p2}" if p2 else "[i] Za mało punktów (min. 2) na trend.", "gray"))
        else:
            print(kol("\n[matplotlib niedostępny — wykresy PNG pominięte]", "gray"))
        print()


# --------------------------------------------------------------- CLI

def zbuduj_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Zaawansowany kalkulator BMI (Deluxe)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("-w", "--waga", type=float, help="waga w kg (lub lbs przy --unit imperial)")
    p.add_argument("-z", "--wzrost", type=float, help="wzrost w metrach (lub cali przy --unit imperial)")
    p.add_argument("--unit", choices=["metric", "imperial"], default="metric",
                   help="jednostki wejściowe")
    p.add_argument("--wiek", type=int, default=None)
    p.add_argument("--plec", choices=["M", "K", "m", "k"], default=None,
                   help="płeć (akceptuje też małe litery)")
    p.add_argument("--tdee", action="store_true", help="oblicz RMR/TDEE (wyma wiek + plec)")
    p.add_argument("--poziom", choices=list(AKTYWNOSC), default="siedzący",
                   help="poziom aktywności do TDEE")
    p.add_argument("--cel", type=float, default=None, help="celowy BMI (cele wagowe)")
    p.add_argument("--bled", action="store_true", help="pokaż zakres BMI z zaokrąglenia")
    p.add_argument("--kolory", action="store_false", dest="kolory",
                   help="wyłącz kolory (domyślnie: gdy TTY)")
    p.add_argument("--pl", action="store_true", help="licby z przecinkiem (12,34)")
    p.add_argument("--json", action="store_true", help="wyjście JSON (maszynowe)")
    p.add_argument("--share-url", action="store_true", help="dodaj link udostępnienia")
    p.add_argument("--historia", default=None, help="ścieżka pliku historii")
    p.add_argument("--wykres", default=None, help="katalog wykresów")
    p.add_argument("--format", choices=["png", "svg", "pdf"], default="png",
                   help="format zapisu wykresów")
    p.add_argument("--history", choices=["asc", "desc"], default=None,
                   help="pokaż historię (sortuj)")
    p.add_argument("--lista-history", dest="history", action="store_const",
                   const="asc", help="wariant --history")
    p.add_argument("--od", type=float, default=None, help="min. BMI w filtrze --history")
    p.add_argument("--do", type=float, default=None, help="max. BMI w filtrze --history")
    p.add_argument("--usun", type=int, default=None, help="Usuń wpis historii (indeks)")
    p.add_argument("--edytuj", type=int, default=None, metavar="indeks",
                   help="Edytuj wpis (--edytuj N --waga X --wzrost Y --wiek Z --plec M)")
    p.add_argument("--wyczysc", action="store_true", help="wyczyść historię i wyjdź")
    p.add_argument("--bez-historii", action="store_true",
                    help="nie zapisuj pomiaru w historii")
    p.add_argument("--eksport", default=None, help="Eksportuj historię do CSV")
    p.add_argument("--import", dest="import_", default=None, metavar="PLIK",
                   help="Importuj historię z CSV")
    p.add_argument("--interactive", action="store_true", help="tryb interaktywny")
    p.add_argument("--interactive-chart", action="store_true",
                   help="interaktywny wykres Plotly (jeśli dostępny)")
    return p


def jako_json(d: dict) -> str:
    return json.dumps(d, ensure_ascii=False, indent=2)


def main(argv: list[str] | None = None) -> int:
    a = zbuduj_parser().parse_args(argv)
    imperial = a.unit == "imperial"
    # konwersja jednostek imperialnych na metryczne
    if imperial and a.waga is not None and a.wzrost is not None:
        a.waga /= 2.20462          # lbs -> kg
        a.wzrost *= 0.0254         # cali -> m

    kol = Kolory(wlczone=(a.kolory and sys.stdout.isatty()))
    pl = a.pl
    hist_path = a.historia or DEFAULT_HISTORIA
    hist = Historia(hist_path)

    if a.import_:
        n = hist.import_csv(a.import_)
        print(f"Imported {n} wpisy z {a.import_}.")
        return 0
    if a.eksport:
        n = hist.eksport_csv(a.eksport)
        print(f"Eksportowano {n} wpisów do {a.eksport}.")
        return 0
    if a.wyczysc:
        hist.czyszcza(); print(kol("Historia wyczyszczona.", "green"))
        return 0

    # ---- operacje na historii
    if a.usun is not None and not (a.waga is not None and a.wzrost is not None):
        if hist.usun(a.usun):
            print(kol(f"Usunięto wpis {a.usun}.", "green"))
        else:
            print(kol(f"Brak wpisu o indeksie {a.usun}.", "red"))
        return 0
    if a.edytuj is not None and not (a.waga is not None and a.wzrost is not None):
        pole = {}
        if a.waga is not None: pole["waga"] = a.waga
        if a.wzrost is not None: pole["wzrost"] = a.wzrost
        if a.wiek is not None: pole["wiek"] = a.wiek
        if a.plec is not None: pole["plec"] = a.plec.upper()
        if hist.edytuj(a.edytuj, **pole):
            print(kol(f"Zmodyfikowano wpis {a.edytuj}.", "green"))
        else:
            print(kol(f"Brak wpisu o indeksie {a.edytuj}.", "red"))
        return 0
    if a.history:
        wpisy = hist.lista(sortuj=a.history)
        wpisy = [p for p in wpisy
                 if (a.od is None or p.bmi >= a.od)
                 and (a.do is None or p.bmi <= a.do)]
        if not wpisy:
            print("Brak zapisanych pomiarów."); return 0
        for i, p in enumerate(wpisy):
            n, _, _ = BMICalculator.kategoria(p.bmi)
            print(f"{i}: {p.data}  {liczba(p.waga,1)} kg  BMI {liczba(p.bmi,2)}  {n}")
        return 0

    # ---- wynik pojedynczy
    if a.waga is not None and a.wzrost is not None:
        try:
            bmi = BMICalculator.oblicz_bmi(a.waga, a.wzrost)
        except ValueError as e:
            print(kol(f"Błąd: {e}", "red"))
            return 2
        r = Raport(kol, pl)
        if a.json:
            wy = {
                "bmi": round(bmi, 2),
                "kategoria": BMICalculator.kategoria(bmi)[0],
                "bmi_prime": round(BMICalculator.bmi_prime(bmi), 2),
                "zdrowy_zakres_kg": [round(BMICalculator.zdrowy_zakres_kg(a.wzrost)[0], 1),
                                     round(BMICalculator.zdrowy_zakres_kg(a.wzrost)[1], 1)],
                "jednostki": "imperial" if imperial else "metric",
            }
            if a.cel is not None:
                wy["cel_wagowy"] = BMICalculator.cel_wagowy(a.waga, a.wzrost, a.cel)
            if a.wiek and a.plec:
                wy["tuk_deurenberg"] = round(BMICalculator.tuk_deurenberg(bmi, a.wiek, a.plec), 1)
                wy["tuk_ross"] = round(BMICalculator.tuk_ross(bmi, a.wiek, a.plec), 1)
                ffm_val = BMICalculator.ffm(bmi, a.wiek, a.plec, a.waga)
                wy["ffm"] = round(ffm_val, 1) if ffm_val else None
                p = BMICalculator.procentil_bmi(bmi, a.wiek, a.plec)
                if p: wy["procentyl_bmi"] = p
                wy["rmr_mifflin"] = round(BMICalculator.rmr_mifflin(a.waga, a.wzrost, a.wiek, a.plec), 0)
                wy["rmr_harris"] = round(BMICalculator.rmr_harris(a.waga, a.wzrost, a.wiek, a.plec), 0)
                wy["tdee"] = round(tdee(wy["rmr_mifflin"], a.poziom), 0)
            if a.bled:
                wy["bmi_range_rounded"] = [round(v, 2) for v in BMICalculator.bld_zaokrglenia(a.waga, a.wzrost)]
            print(jako_json(wy))
        else:
            print(r.raport(bmi=bmi, waga_kg=a.waga, wzrost_m=a.wzrost,
                           wiek=a.wiek, plec=a.plec.upper() if a.plec else None,
                           calornic=a.tdee, poziom_aktywnosci=a.poziom,
                           bmi_cel=a.cel, bled=a.bled, imperial=imperial))
            print()
            print(Raport(kol, pl).pasek(bmi))
            if HAS_MPL:
                baza = a.wykres or os.path.join(os.path.dirname(os.path.abspath(__file__)), "bmi_wykres")
                p1 = rysuj_gauge(bmi, f"{baza}_gauge.{a.format}", a.waga, a.wzrost, a.format, imperial)
                print(kol(f"[ok] Wykres pozycji BMI: {p1}", "green"))
                p2 = rysuj_historia(f"{baza}_historia.{a.format}", a.format,
                                      sciezka_historia=hist_path)
                if p2:
                    print(kol(f"[ok] Wykres historii BMI: {p2}", "green"))
                else:
                    print(kol("[i] Historia zawiera za mało punktów na wykres trendu (min. 2).", "gray"))
            else:
                print(kol("\n[matplotlib niedostępne — wykresy pominięte]", "gray"))
            if a.share_url:
                print(kol(f"[i] Link: {BMICalculator.share_url(a.waga, a.wzrost)}", "gray"))
            if not a.bez_historii:
                dod = hist.dodaj(Pomiar(date.today().isoformat(), a.waga, a.wzrost, bmi,
                                        a.wiek, a.plec.upper() if a.plec else None))
                print(kol(f"[ok] Dodano do historii: {dod.data}", "green"))
        return 0

    # ---- interaktywny
    tryb_interaktywny(hist, kol, pl, imperial, a.format)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
