# Plan: Desktop GUI dla BMI Deluxe

## Cel
Dodać natywny interfejs desktopowy (okno) do istniejącego kalkulatora BMI, reużywając logiki z `bmi_core` i `bmi_charts`, bez duplikowania obliczeń.

## Ograniczenia środowiska
- Brak Tkinter (libtk8.6.so) i brak Qt/PySide w obecnym środowisku.
- Dostępne: Python 3.14, stdlib, opcjonalnie matplotlib (pip), plotly (pip).
- Web GUI (`bmi_web.py`) już działa i może służyć jako wzorzec UX.

## Rekomendowana ścieżka
**Tkinter + matplotlib FigureCanvasTkAgg**, po instalacji systemowego pakietu `tk` (Arch: `sudo pacman -S tk`).  
Powód: najlżejsza zależność, stdlib, dobra integracja z matplotlib.  
Alternatywa: PySide6 (pip, self-contained Qt) jeśli użytkownik woli nowoczesny wygląd i nie chce instalować pakietów systemowych.

## Faza 0 — Przygotowanie (0.5 dnia)
- [ ] Potwierdzić możliwość instalacji `tk` (sudo) lub wybrać PySide6.
- [ ] Zainstalować wybrany framework.
- [ ] Dodać zależność do `pyproject.toml` (optional: `desktop = ["..."]`).
- [ ] Utworzyć plik `bmi_desktop.py` (lub pakiet `bmi_desktop/`).

## Faza 1 — MVP okna (1–2 dni)
- [ ] Główne okno (tytuł, rozmiar, ikona).
- [ ] Formularz: waga, wzrost, jednostki (metric/imperial), wiek, płeć, talia, biodra, cel BMI, checkbox TDEE.
- [ ] Przycisk „Oblicz” → walidacja → obliczenie BMI → raport tekstowy w `ScrolledText`/`QTextEdit`.
- [ ] Wyświetlenie paska BMI (tekstowy, z `Raport.pasek`).
- [ ] Wykres gauge (matplotlib) osadzony w oknie (canvas).
- [ ] Zapis do historii (checkbox, domyślnie włączone).

## Faza 2 — Historia i zarządzanie (1–2 dni)
- [ ] Tabela/lista wpisów (data, waga, wzrost, BMI, kategoria).
- [ ] Usuwanie wpisu (z potwierdzeniem).
- [ ] Edycja wpisu (dialog z polami).
- [ ] Filtrowanie/sortowanie (po dacie/BMI/wadze).
- [ ] Eksport/import CSV (dialog zapisu/otwarcia).

## Faza 3 — Wykresy i analiza (1 dzień)
- [ ] Wykres trendu BMI (matplotlib) w osobnej zakładce/oknie.
- [ ] Interaktywny wykres Plotly (otwarcie w przeglądarce) — opcjonalnie.
- [ ] Nowe metryki (WHR/WHtR/BAI/ABSI/RFM) w raporcie (już w core).

## Faza 4 — UX i ustawienia (0.5–1 dzień)
- [ ] Menu (Plik, Widok, Pomoc).
- [ ] Zapisywanie preferencji (jednostki, format wykresu, ścieżka historii) w `~/.config/bmi/config.toml`.
- [ ] Skróty klawiszowe (Enter = oblicz, Ctrl+Q = wyjście).
- [ ] Tryb ciemny/jasny (opcjonalnie).

## Faza 5 — Pakietowanie (0.5–1 dzień)
- [ ] PyInstaller (onefile) dla Linux (i ewentualnie Windows/macOS).
- [ ] Test instalacji na czystym systemie.
- [ ] Aktualizacja README i CI (build desktop).

## Architektura
- `bmi_desktop.py` (lub pakiet) importuje `bmi_core` i `bmi_charts`.
- Brak duplikacji logiki obliczeń — tylko warstwa prezentacji.
- Historia przez `bmi.Historia` (wspólna z CLI/web).
- Konfiguracja przez ten sam plik co CLI (opcjonalnie).

## Testy
- Smoke test: uruchomienie okna (headless: `QT_QPA_PLATFORM=offscreen` dla Qt lub `Xvfb` dla Tk).
- Testy jednostkowe logiki pozostają w `tests/` (bez GUI).
- Manualne testy UX (checklista).

## Kryteria akceptacji (MVP)
- [ ] Okno się uruchamia i nie crashuje.
- [ ] Formularz oblicza BMI i pokazuje raport.
- [ ] Wykres gauge wyświetla się w oknie.
- [ ] Historia zapisuje pomiar.
- [ ] Brak regresji w testach CLI (`pytest` zielone).

## Szacowany czas
- MVP (Fazy 0–1): 2–3 dni.
- Pełna wersja (Fazy 2–5): +3–4 dni.

## Ryzyka
- Brak uprawnień sudo → Tkinter/Qt niedostępne → fallback do web GUI.
- Różnice między platformami (Linux/Windows/macOS) w pakietowaniu.
- Testy GUI w CI wymagają środowiska graficznego (Xvfb).