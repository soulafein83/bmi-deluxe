from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
import tempfile
import urllib.parse
from dataclasses import dataclass, asdict
from datetime import date, datetime

DEFAULT_HISTORIA = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "bmi_historia_deluxe.json")

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
    if n is None or (isinstance(n, float) and (math.isnan(n) or math.isinf(n))):
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
            try:
                os.chmod(self.sciezka, 0o644)
            except OSError:
                pass
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
        # przelicz BMI, jeśli zmieniono wagę lub wzrost (użyj pozostałej wartości z wpisu)
        if "waga" in pole or "wzrost" in pole:
            try:
                wpisy[idx].bmi = BMICalculator.oblicz_bmi(wpisy[idx].waga, wpisy[idx].wzrost)
            except (ValueError, AttributeError):
                pass
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
    def walidacja_wieku(wiek: int | None) -> None:
        if wiek is None:
            return
        lo, hi = LIMITY["wiek"]
        if not (lo <= wiek <= hi):
            raise ValueError(f"Wiek {wiek} poza zakresem {lo}–{hi} lat.")
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

    # -- nowe metryki antropometryczne
    @staticmethod
    def whr(talia_m: float, biodra_m: float) -> float:
        return talia_m / biodra_m

    @staticmethod
    def whtr(talia_m: float, wzrost_m: float) -> float:
        return talia_m / wzrost_m

    @staticmethod
    def bai(biodra_m: float, wzrost_m: float) -> float:
        # BAI oczekuje obwodu bioder w cm
        biodra_cm = biodra_m * 100.0 if biodra_m < 3 else biodra_m
        return (biodra_cm / (wzrost_m ** 1.5)) - 18.0

    @staticmethod
    def absi(talia_m: float, bmi: float, wzrost_m: float) -> float:
        return talia_m / ((bmi ** (2.0 / 3.0)) * (wzrost_m ** 0.5))

    @staticmethod
    def rfm(wzrost_m: float, talia_m: float, plec: str) -> float:
        ratio = wzrost_m / talia_m
        if plec == "M":
            return 64.0 - 20.0 * ratio
        return 76.0 - 20.0 * ratio

    @staticmethod
    def bmr_katch(waga_kg: float, bf_proc: float) -> float:
        lbm = waga_kg * (1.0 - bf_proc / 100.0)
        return 370.0 + 21.6 * lbm


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
                bmi_cel=None, bled=False, imperial=False,
                talia_m=None, biodra_m=None) -> str:
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
        if talia_m is not None:
            w.append(c(f"  WHtR:              {l(BMICalculator.whtr(talia_m, wzrost_m), 2)}", "white"))
            if biodra_m is not None:
                w.append(c(f"  WHR:               {l(BMICalculator.whr(talia_m, biodra_m), 2)}", "white"))
                w.append(c(f"  BAI:               {l(BMICalculator.bai(biodra_m, wzrost_m), 1)}", "white"))
            w.append(c(f"  ABSI:              {l(BMICalculator.absi(talia_m, bmi, wzrost_m), 3)}", "white"))
            w.append(c(f"  RFM:               {l(BMICalculator.rfm(wzrost_m, talia_m, plec or 'K'), 1)} % tłuszczu", "white"))
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
                if talia_m is not None:
                    bf_rfm = BMICalculator.rfm(wzrost_m, talia_m, plec)
                else:
                    bf_rfm = BMICalculator.tuk_deurenberg(bmi, wiek, plec)
                if 0 < bf_rfm < 70:
                    bmr_k = BMICalculator.bmr_katch(waga_kg, bf_rfm)
                    w.append(c(f"  BMR (Katch-McArdle): {l(bmr_k,0)} kcal  (BF~{l(bf_rfm,1)}%)", "white"))
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

