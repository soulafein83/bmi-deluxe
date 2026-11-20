#!/usr/bin/env python3
"""Zaawansowany KALKULATOR BMI (Deluxe) — CLI."""

from __future__ import annotations

import argparse
import os
import sys

from bmi_core import *
from bmi_charts import *

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
    ostatnia = None  # (waga, wzrost, wiek, plec)
    jedn_w = "lbs" if imperial else "kg"
    jedn_z = "cale" if imperial else "m"
    while True:
        surowa = input(f"Waga ({jedn_w}) lub komenda (history/clr/cel <bmi>/tdee/help/k): ").strip()
        low = surowa.lower()
        if low in ("k", "q", "quit", "x", ""):
            if low == "":
                continue
            break
        if low == "help":
            print(POMOC)
            continue
        if low == "history":
            wpisy = historia.wczytaj()
            if not wpisy:
                print("Brak zapisanych pomiarów.")
            else:
                for i, p in enumerate(wpisy):
                    n, _, _ = BMICalculator.kategoria(p.bmi)
                    print(f"{i}: {p.data}  {liczba(p.waga, 1, pl)} kg  BMI {liczba(p.bmi, 2, pl)}  {n}")
            continue
        if low == "clr":
            historia.czyszcza()
            print(kol("Historia wyczyszczona.", "green"))
            continue
        if low.startswith("cel"):
            parts = low.split()
            if len(parts) < 2:
                print("Użycie: cel <bmi>  (np. cel 22)")
                continue
            try:
                bmi_cel = float(parts[1])
            except ValueError:
                print("Nieprawidłowa wartość BMI.")
                continue
            if ostatnia is None:
                print("Brak ostatniego pomiaru — najpierw wpisz wagę i wzrost.")
                continue
            w, z, _, _ = ostatnia
            cel = BMICalculator.cel_wagowy(w, z, bmi_cel)
            print(f"Cel BMI {bmi_cel}: {liczba(cel['waga_cel'], 1, pl)} kg "
                  f"({cel['kierunek']} {liczba(abs(cel['delta']), 1, pl)} kg)")
            continue
        if low == "tdee":
            if ostatnia is None:
                print("Brak ostatniego pomiaru — najpierw wpisz wagę i wzrost.")
                continue
            w, z, _, _ = ostatnia
            try:
                wiek = int(input("Wiek: ") or "0") or None
            except ValueError:
                print("  Wiek musi być liczbą — pomijam.")
                wiek = None
            try:
                BMICalculator.walidacja_wieku(wiek)
            except ValueError as e:
                print(kol(str(e), "red"))
                wiek = None
            plec_raw = (input("Płeć (M/K): ") or "").strip().lower()
            plec = {"m": "M", "k": "K"}.get(plec_raw[:1])
            if not (wiek and plec):
                print("Wiek i płeć są wymagane do TDEE.")
                continue
            poziom = (input(f"Poziom aktywności {list(AKTYWNOSC)} (Enter = siedzący): ") or "").strip() or "siedzący"
            if poziom not in AKTYWNOSC:
                poziom = "siedzący"
            rmr_m = BMICalculator.rmr_mifflin(w, z, wiek, plec)
            rmr_h = BMICalculator.rmr_harris(w, z, wiek, plec)
            print(f"RMR: Mifflin {liczba(rmr_m, 0, pl)} kcal | Harris {liczba(rmr_h, 0, pl)} kcal")
            print(f"TDEE ({poziom}): {liczba(tdee(rmr_m, poziom), 0, pl)} kcal")
            continue

        # --- pomiar ---
        try:
            waga_raw = float(surowa)
        except ValueError:
            print("  Wpisz liczbę lub komendę (help).")
            continue
        wzrost_raw_s = input(f"Wzrost ({jedn_z}, k = wyjście): ").strip()
        if wzrost_raw_s.lower() in ("k", "q", "quit", "x"):
            break
        try:
            wzrost_raw = float(wzrost_raw_s)
        except ValueError:
            print("  Wzrost musi być liczbą.")
            continue
        if imperial:
            waga = waga_raw / 2.20462
            wzrost = wzrost_raw * 0.0254
        else:
            waga = waga_raw
            wzrost = wzrost_raw
        try:
            BMICalculator.walidacja(waga, wzrost)
        except ValueError as e:
            print(kol(f"Błąd: {e}", "red"))
            continue
        try:
            wiek = int(input("Wiek (pusto = pominąć): ") or "0") or None
        except ValueError:
            print("  Wiek musi być liczbą — pomijam.")
            wiek = None
        try:
            BMICalculator.walidacja_wieku(wiek)
        except ValueError as e:
            print(kol(str(e), "red"))
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
        ostatnia = (waga, wzrost, wiek, plec)
        if HAS_MPL:
            baza = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bmi_wykres")
            print(kol(f"[ok] Wykres pozycji BMI: {rysuj_gauge(bmi, f'{baza}_gauge.{format_wykresu}', waga, wzrost, format_wykresu, imperial)}", "green"))
            p2 = rysuj_historia(f"{baza}_historia.{format_wykresu}", format_wykresu)
            print(kol(f"[ok] Wykres historii BMI: {p2}" if p2 else "[i] Za mało punktów (min. 2) na trend.", "gray"))
        else:
            print(kol("\n[matplotlib niedostępne — wykresy PNG pominięte]", "gray"))
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
    p.add_argument("--talia", type=float, default=None, help="obwód talii w cm (nowe metryki)")
    p.add_argument("--biodra", type=float, default=None, help="obwód bioder w cm (nowe metryki)")
    p.add_argument("--bled", action="store_true", help="pokaż zakres BMI z zaokrąglenia")
    p.add_argument("--kolory", action="store_false", dest="kolory",
                   help="wyłącz kolory (domyślnie: gdy TTY; przestarzałe, użyj --no-color)",)
    p.add_argument("--no-color", action="store_true", dest="no_color",
                   help="wyłącz kolory (zalecane)")
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

    kol = Kolory(wlczone=(a.kolory and not getattr(a, "no_color", False) and sys.stdout.isatty()))
    pl = a.pl
    # walidacja wieku
    if a.wiek is not None:
        try:
            BMICalculator.walidacja_wieku(a.wiek)
        except ValueError as e:
            print(kol(str(e), "red"))
            return 2
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
    if a.usun is not None:
        if hist.usun(a.usun):
            print(kol(f"Usunięto wpis {a.usun}.", "green"))
        else:
            print(kol(f"Brak wpisu o indeksie {a.usun}.", "red"))
        return 0
    if a.edytuj is not None:
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
        talia_m = (a.talia / 100.0) if getattr(a, "talia", None) is not None else None
        biodra_m = (a.biodra / 100.0) if getattr(a, "biodra", None) is not None else None
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
            if talia_m is not None:
                wy["whtr"] = round(BMICalculator.whtr(talia_m, a.wzrost), 3)
                wy["absi"] = round(BMICalculator.absi(talia_m, bmi, a.wzrost), 3)
                wy["rfm"] = round(BMICalculator.rfm(a.wzrost, talia_m, a.plec.upper() if a.plec else "K"), 1)
                if biodra_m is not None:
                    wy["whr"] = round(BMICalculator.whr(talia_m, biodra_m), 3)
                    wy["bai"] = round(BMICalculator.bai(biodra_m, a.wzrost), 1)
            print(jako_json(wy))
        else:
            print(r.raport(bmi=bmi, waga_kg=a.waga, wzrost_m=a.wzrost,
                           wiek=a.wiek, plec=a.plec.upper() if a.plec else None,
                           calornic=a.tdee, poziom_aktywnosci=a.poziom,
                           bmi_cel=a.cel, bled=a.bled, imperial=imperial,
                            talia_m=talia_m, biodra_m=biodra_m))
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
            if getattr(a, "interactive_chart", False):
                if HAS_PLOTLY:
                    katalog_w = a.wykres or os.path.dirname(os.path.abspath(__file__))
                    sciezka_ic = os.path.join(katalog_w, "bmi_historia_interaktywna.html")
                    p3 = rysuj_historia_interaktywna(hist.wczytaj(), sciezka_ic)
                    if p3:
                        print(kol(f"[ok] Interaktywny wykres historii: {p3}", "green"))
                    else:
                        print(kol("[i] Historia zawiera za mało punktów na wykres interaktywny (min. 2).", "gray"))
                else:
                    print(kol("[i] plotly niedostępne — pomijam wykres interaktywny.", "gray"))
        return 0

    # ---- interaktywny
    tryb_interaktywny(hist, kol, pl, imperial, a.format)
    return 0




if __name__ == "__main__":
    raise SystemExit(main())
