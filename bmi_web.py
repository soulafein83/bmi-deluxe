#!/usr/bin/env python3
"""Prosty interfejs webowy (GUI w przeglądarce) dla kalkulatora BMI.

Uruchom:  python bmi_web.py
Następnie otwórz:  http://127.0.0.1:8000
"""

from __future__ import annotations

import base64
import html
import os
import tempfile
import urllib.parse
from datetime import date
from http.server import BaseHTTPRequestHandler, HTTPServer

import bmi


HOST = "127.0.0.1"
PORT = 8000


def _formularz() -> str:
    return """
    <h1>Kalkulator BMI — GUI (web)</h1>
    <form method="POST">
      <label>Waga: <input name="waga" type="number" step="any" required></label><br>
      <label>Wzrost: <input name="wzrost" type="number" step="any" required></label><br>
      <label>Jednostki:
        <select name="unit">
          <option value="metric">metryczne (kg, m)</option>
          <option value="imperial">imperialne (lbs, cale)</option>
        </select>
      </label><br>
      <label>Wiek: <input name="wiek" type="number"></label><br>
      <label>Płeć:
        <select name="plec">
          <option value="">—</option>
          <option value="M">M</option>
          <option value="K">K</option>
        </select>
      </label><br>
      <label>Cel BMI: <input name="cel" type="number" step="any"></label><br>
      <label><input type="checkbox" name="tdee"> Oblicz RMR/TDEE</label><br>
      <label><input type="checkbox" name="zapisz" checked> Zapisz do historii</label><br>
      <button type="submit">Oblicz</button>
    </form>
    """


def _przetworz(form: dict) -> str:
    kol = bmi.Kolory(wlczone=False)
    pl = False
    try:
        waga = float(form.get("waga", ""))
        wzrost = float(form.get("wzrost", ""))
    except ValueError:
        return "<p class='err'>Waga i wzrost muszą być liczbami.</p>" + _formularz()

    imperial = form.get("unit") == "imperial"
    if imperial:
        waga = waga / 2.20462
        wzrost = wzrost * 0.0254

    wiek = None
    if form.get("wiek"):
        try:
            wiek = int(form["wiek"])
            bmi.BMICalculator.walidacja_wieku(wiek)
        except ValueError as e:
            return f"<p class='err'>{html.escape(str(e))}</p>" + _formularz()

    plec = (form.get("plec") or "").upper() or None
    cel = None
    if form.get("cel"):
        try:
            cel = float(form["cel"])
        except ValueError:
            return "<p class='err'>Cel BMI musi być liczbą.</p>" + _formularz()

    try:
        bmi.BMICalculator.walidacja(waga, wzrost)
        bmi_val = bmi.BMICalculator.oblicz_bmi(waga, wzrost)
    except ValueError as e:
        return f"<p class='err'>{html.escape(str(e))}</p>" + _formularz()

    r = bmi.Raport(kol, pl)
    raport_txt = r.raport(bmi=bmi_val, waga_kg=waga, wzrost_m=wzrost,
                          wiek=wiek, plec=plec, calornic=("tdee" in form),
                          poziom_aktywnosci="siedzący", bmi_cel=cel, bled=True)
    pasek_txt = r.pasek(bmi_val)

    # wykres gauge (base64)
    wykres_html = ""
    if bmi.HAS_MPL:
        fd, sciezka = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        bmi.rysuj_gauge(bmi_val, sciezka, waga, wzrost, "png", imperial)
        with open(sciezka, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        os.remove(sciezka)
        wykres_html = f'<img src="data:image/png;base64,{b64}" alt="wykres BMI">'

    # historia
    if "zapisz" in form:
        hist = bmi.Historia(bmi.DEFAULT_HISTORIA)
        hist.dodaj(bmi.Pomiar(date.today().isoformat(),
                               waga, wzrost, bmi_val, wiek, plec))

    out = [f"<pre>{html.escape(raport_txt)}\n\n{html.escape(pasek_txt)}</pre>"]
    if wykres_html:
        out.append(wykres_html)
    out.append("<p><a href='/'>← ponownie</a></p>")
    return "\n".join(out)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = "<html><head><meta charset='utf-8'><style>.err{color:red}</style></head><body>"
        body += _formularz()
        body += "</body></html>"
        data = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(n).decode("utf-8")
        form = urllib.parse.parse_qs(raw)
        # parse_qs zwraca listy — spłaszcz
        flat = {k: (v[0] if isinstance(v, list) else v) for k, v in form.items()}
        # checkboxy
        if "tdee" in form:
            flat["tdee"] = "on"
        if "zapisz" in form:
            flat["zapisz"] = "on"
        wynik = _przetworz(flat)
        body = "<html><head><meta charset='utf-8'><style>.err{color:red}</style></head><body>"
        body += wynik
        body += "</body></html>"
        data = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


def main() -> None:
    httpd = HTTPServer((HOST, PORT), Handler)
    print(f"GUI webowe: http://{HOST}:{PORT}  (Ctrl+C aby zakończyć)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nZatrzymano.")


if __name__ == "__main__":
    main()
