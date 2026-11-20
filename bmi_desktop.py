#!/usr/bin/env python3
"""Desktop GUI (PySide6) dla BMI Deluxe.

Wymagania:  pip install PySide6 matplotlib
Uruchom:    python bmi_desktop.py
Headless:   QT_QPA_PLATFORM=offscreen BMI_DESKTOP_SMOKE=1 python bmi_desktop.py
"""

from __future__ import annotations

import os
import sys
from datetime import date

try:
    from PySide6 import QtCore, QtGui, QtWidgets
except ImportError as e:  # pragma: no cover
    raise SystemExit(f"Brak PySide6: {e}. Zainstaluj: pip install PySide6")

import bmi_core

HAS_MPL = False
try:
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavToolbar
    from matplotlib.patches import Polygon
    HAS_MPL = True
except ImportError:
    Figure = None
    FigureCanvas = None
    NavToolbar = None
    Polygon = None


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BMI Deluxe — Desktop")
        self.resize(1000, 750)

        self.tabs = QtWidgets.QTabWidget()
        self.setCentralWidget(self.tabs)

        # ---------- Tab 1: BMI ----------
        tab1 = QtWidgets.QWidget()
        layout1 = QtWidgets.QHBoxLayout(tab1)

        form_box = QtWidgets.QGroupBox("Dane")
        form_layout = QtWidgets.QFormLayout(form_box)

        self.waga = QtWidgets.QDoubleSpinBox()
        self.waga.setRange(0, 10000)
        self.waga.setDecimals(2)
        self.waga.setValue(70.0)
        form_layout.addRow("Waga:", self.waga)

        self.wzrost = QtWidgets.QDoubleSpinBox()
        self.wzrost.setRange(0, 10000)
        self.wzrost.setDecimals(2)
        self.wzrost.setValue(1.75)
        form_layout.addRow("Wzrost:", self.wzrost)

        self.unit = QtWidgets.QComboBox()
        self.unit.addItems(["metric (kg, m)", "imperial (lbs, cal)"])
        form_layout.addRow("Jednostki:", self.unit)

        self.wiek = QtWidgets.QSpinBox()
        self.wiek.setRange(0, 120)
        self.wiek.setValue(0)
        self.wiek.setSpecialValueText("—")
        form_layout.addRow("Wiek:", self.wiek)

        self.plec = QtWidgets.QComboBox()
        self.plec.addItems(["", "M", "K"])
        form_layout.addRow("Płeć:", self.plec)

        self.talia = QtWidgets.QDoubleSpinBox()
        self.talia.setRange(0, 300)
        self.talia.setDecimals(1)
        self.talia.setValue(0)
        self.talia.setSpecialValueText("—")
        form_layout.addRow("Talia (cm):", self.talia)

        self.biodra = QtWidgets.QDoubleSpinBox()
        self.biodra.setRange(0, 300)
        self.biodra.setDecimals(1)
        self.biodra.setValue(0)
        self.biodra.setSpecialValueText("—")
        form_layout.addRow("Biodra (cm):", self.biodra)

        self.cel = QtWidgets.QDoubleSpinBox()
        self.cel.setRange(0, 100)
        self.cel.setDecimals(1)
        self.cel.setValue(0)
        self.cel.setSpecialValueText("—")
        form_layout.addRow("Cel BMI:", self.cel)

        self.tdee = QtWidgets.QCheckBox("Oblicz RMR/TDEE")
        form_layout.addRow(self.tdee)

        self.zapisz = QtWidgets.QCheckBox("Zapisz do historii")
        self.zapisz.setChecked(True)
        form_layout.addRow(self.zapisz)

        self.dark = QtWidgets.QCheckBox("Tryb ciemny")
        self.dark.toggled.connect(self.zmien_motyw)
        form_layout.addRow(self.dark)

        self.btn = QtWidgets.QPushButton("Oblicz")
        self.btn.clicked.connect(self.oblicz)
        form_layout.addRow(self.btn)

        self.export_btn = QtWidgets.QPushButton("Eksportuj wykres (PNG)")
        self.export_btn.clicked.connect(self.eksportuj_png)
        form_layout.addRow(self.export_btn)

        self.copy_btn = QtWidgets.QPushButton("Kopiuj wykres do schowka")
        self.copy_btn.clicked.connect(self.kopiuj_wykres)
        form_layout.addRow(self.copy_btn)

        layout1.addWidget(form_box, 1)

        right_box = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right_box)

        self.report = QtWidgets.QTextEdit()
        self.report.setReadOnly(True)
        self.report.setFont(QtGui.QFont("Monospace", 10))
        right_layout.addWidget(self.report, 2)

        if HAS_MPL:
            self.fig = Figure(figsize=(6, 2.8), dpi=100)
            self.canvas = FigureCanvas(self.fig)
            self.toolbar = NavToolbar(self.canvas, self)
            right_layout.addWidget(self.toolbar)
            right_layout.addWidget(self.canvas, 1)
        else:
            right_layout.addWidget(QtWidgets.QLabel("matplotlib niedostępne — brak wykresu"))

        layout1.addWidget(right_box, 2)
        self.tabs.addTab(tab1, "BMI")

        # ---------- Tab 2: Trend ----------
        tab2 = QtWidgets.QWidget()
        layout2 = QtWidgets.QVBoxLayout(tab2)
        if HAS_MPL:
            self.fig_trend = Figure(figsize=(8, 4), dpi=100)
            self.canvas_trend = FigureCanvas(self.fig_trend)
            self.toolbar_trend = NavToolbar(self.canvas_trend, self)
            layout2.addWidget(self.toolbar_trend)
            layout2.addWidget(self.canvas_trend)
            btn_refresh = QtWidgets.QPushButton("Odśwież trend")
            btn_refresh.clicked.connect(self.rysuj_trend)
            layout2.addWidget(btn_refresh)
        else:
            layout2.addWidget(QtWidgets.QLabel("matplotlib niedostępne"))
        self.tabs.addTab(tab2, "Trend BMI")

        self.status = QtWidgets.QLabel("")
        self.statusBar().addWidget(self.status)

        self._gauge_params = None
        self._arrow_pos = None
        self._arrow_target = None
        self._anim_timer = QtCore.QTimer(self)
        self._anim_timer.timeout.connect(self._krok_animacji)

    def _val_or_none(self, spin):
        v = spin.value()
        return v if v and v > 0 else None

    def oblicz(self):
        waga_raw = self.waga.value()
        wzrost_raw = self.wzrost.value()
        imperial = self.unit.currentIndex() == 1
        if imperial:
            waga = waga_raw / 2.20462
            wzrost = wzrost_raw * 0.0254
        else:
            waga = waga_raw
            wzrost = wzrost_raw

        wiek = self.wiek.value() or None
        plec = self.plec.currentText() or None
        talia_cm = self._val_or_none(self.talia)
        biodra_cm = self._val_or_none(self.biodra)
        talia_m = talia_cm / 100.0 if talia_cm else None
        biodra_m = biodra_cm / 100.0 if biodra_cm else None
        cel = self._val_or_none(self.cel)

        try:
            bmi_core.BMICalculator.walidacja(waga, wzrost)
            if wiek is not None:
                bmi_core.BMICalculator.walidacja_wieku(wiek)
            bmi_val = bmi_core.BMICalculator.oblicz_bmi(waga, wzrost)
        except ValueError as e:
            self.report.setPlainText(f"Błąd: {e}")
            return

        kol = bmi_core.Kolory(wlczone=False)
        r = bmi_core.Raport(kol, pl=False)
        tekst = r.raport(bmi=bmi_val, waga_kg=waga, wzrost_m=wzrost,
                         wiek=wiek, plec=plec, calornic=self.tdee.isChecked(),
                         poziom_aktywnosci="siedzący", bmi_cel=cel, bled=True,
                         talia_m=talia_m, biodra_m=biodra_m)
        tekst += "\n\n" + r.pasek(bmi_val)
        self.report.setPlainText(tekst)

        self._gauge_params = (bmi_val, waga, wzrost, imperial)
        target = min(max(bmi_val, 12.0), 42.0)
        if self._arrow_pos is None:
            self._arrow_pos = target
        self._arrow_target = target
        self.rysuj_gauge(arrow_x=self._arrow_pos)
        self._anim_timer.start(16)

        if self.zapisz.isChecked():
            hist = bmi_core.Historia(bmi_core.DEFAULT_HISTORIA)
            hist.dodaj(bmi_core.Pomiar(
                date.today().isoformat(), waga, wzrost, bmi_val, wiek, plec))
            self.status.setText("Zapisano do historii.")
            self.rysuj_trend()

    def rysuj_trend(self):
        if not HAS_MPL:
            return
        hist = bmi_core.Historia(bmi_core.DEFAULT_HISTORIA)
        wpisy = sorted(hist.wczytaj(), key=lambda p: p.data)
        self.fig_trend.clear()
        ax = self.fig_trend.add_subplot(111)
        _k = self._kolory()
        self.fig_trend.patch.set_facecolor(_k["bg"])
        ax.set_facecolor(_k["bg"])
        if len(wpisy) < 2:
            ax.text(0.5, 0.5, "Za mało danych (min. 2)", ha="center", va="center")
            ax.axis("off")
            self.canvas_trend.draw()
            return
        xs = [p.data for p in wpisy]
        ys = [p.bmi for p in wpisy]
        ax.axhspan(bmi_core.BMI_MIN_ZDROWY, bmi_core.BMI_MAX_ZDROWY,
                   color=bmi_core.KOLORY_KATEGORII["Prawidłowa masa"], alpha=0.2,
                   label="Zdrowy zakres")
        for dol, kolor in [(25, bmi_core.KOLORY_KATEGORII["Nadwaga"]),
                           (30, bmi_core.KOLORY_KATEGORII["Otyłość I stopnia"]),
                           (35, bmi_core.KOLORY_KATEGORII["Otyłość II stopnia"])]:
            ax.axhline(dol, color=kolor, linestyle="--", linewidth=1)
        kolory = [bmi_core.KOLORY_KATEGORII[bmi_core.BMICalculator.kategoria(p.bmi)[0]]
                  for p in wpisy]
        ax.plot(xs, ys, color="#1d3557", linewidth=2, marker="o", zorder=3, label="BMI")
        for x, y, c in zip(xs, ys, kolory):
            ax.scatter([x], [y], s=70, color=c, edgecolor="white", zorder=4)
            ax.annotate(f"{y:.1f}", (x, y), textcoords="offset points",
                        xytext=(0, 9), ha="center", fontsize=8)
        ax.set_title("Trend BMI w czasie", fontsize=13, fontweight="bold")
        ax.set_ylabel("BMI")
        ax.set_xlabel("Data pomiaru")
        ax.legend(loc="best")
        ax.grid(True, alpha=0.3)
        self.fig_trend.autofmt_xdate()
        self._trend_data = (list(range(len(xs))), ys, xs)
        self._annot = ax.annotate("", xy=(0, 0), xytext=(10, 10),
                                 textcoords="offset points",
                                 bbox=dict(boxstyle="round", fc="yellow", alpha=0.8),
                                 arrowprops=dict(arrowstyle="->"))
        self._annot.set_visible(False)
        self.canvas_trend.mpl_connect("motion_notify_event", self._hover_trend)
        self.fig_trend.tight_layout()
        self.canvas_trend.draw()

    def rysuj_gauge(self, arrow_x=None):
        if not HAS_MPL or not self._gauge_params:
            return
        bmi_val, waga, wzrost, imperial = self._gauge_params
        if arrow_x is None:
            arrow_x = min(max(bmi_val, 12.0), 42.0)
        _k = self._kolory()
        self.fig.clear()
        ax = self.fig.add_subplot(111)
        self.fig.patch.set_facecolor(_k["bg"])
        ax.set_facecolor(_k["bg"])
        min_v, max_v = 12.0, 42.0
        ax.set_xlim(min_v, max_v)
        ax.set_ylim(0, 10)
        ax.axis("off")
        ax.set_title("Twoje BMI na skali WHO", fontsize=13, fontweight="bold", pad=10,
                     color=_k["fg"])

        for nazwa, dol, gor, kolor, _ in bmi_core.KATEGORIE_WHO:
            a = max(dol, min_v)
            b = min(gor, max_v)
            ax.barh(5, b - a, left=a, height=2.2, color=kolor, alpha=0.85,
                    edgecolor="white", linewidth=1.5)
            if b - a > 2.5:
                ax.text((a + b) / 2, 5, f"{a:g}–{b:g}", ha="center",
                        va="center", fontsize=8.5, color="white", fontweight="bold")

        ax.add_patch(Polygon(
            [(arrow_x - 0.9, 8.4), (arrow_x + 0.9, 8.4), (arrow_x, 6.6)],
            color="#1d3557", zorder=5))
        ax.text(arrow_x, 8.8, f"BMI {bmi_val:.1f}", ha="center", va="bottom",
                fontsize=11, fontweight="bold", color="#1d3557")

        lo, hi = bmi_core.BMICalculator.zdrowy_zakres_kg(wzrost)
        jednostka = "lbs" if imperial else "kg"
        ax.text((min_v + max_v) / 2, 3.0,
                f"Zdrowa waga dla {wzrost * 100:.0f} cm: {lo:.1f}–{hi:.1f} {jednostka}",
                ha="center", fontsize=9.5, color=_k["fg"])
        ax.text((min_v + max_v) / 2, 1.4,
                f"Waga: {waga:.1f} {jednostka}   Wzrost: {wzrost * 100:.1f} cm",
                ha="center", fontsize=9, color="#888888")
        self.canvas.draw()

    def _krok_animacji(self):
        if self._arrow_pos is None or self._arrow_target is None:
            self._anim_timer.stop()
            return
        diff = self._arrow_target - self._arrow_pos
        if abs(diff) < 0.05:
            self._arrow_pos = self._arrow_target
            self.rysuj_gauge(arrow_x=self._arrow_pos)
            self._anim_timer.stop()
            return
        self._arrow_pos += diff * 0.25
        self.rysuj_gauge(arrow_x=self._arrow_pos)

    def eksportuj_png(self):
        if not HAS_MPL:
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Zapisz wykres", "bmi_wykres.png", "PNG (*.png);;SVG (*.svg)")
        if not path:
            return
        self.fig.savefig(path, bbox_inches="tight")
        self.status.setText(f"Zapisano wykres: {path}")

    def _ciemny(self):
        return self.dark.isChecked()

    def _kolory(self):
        if self._ciemny():
            return {"bg": "#2b2b2b", "fg": "#e0e0e0", "grid": "#555555",
                    "title": "#ffffff", "healthy": "#2e7d32"}
        return {"bg": "white", "fg": "#222222", "grid": "#cccccc",
                "title": "#000000", "healthy": "#2e7d32"}

    def zmien_motyw(self):
        # zastosuj motyw do aplikacji
        app = QtWidgets.QApplication.instance()
        if self._ciemny():
            app.setStyle("Fusion")
            pal = QtGui.QPalette()
            pal.setColor(QtGui.QPalette.Window, QtGui.QColor(53, 53, 53))
            pal.setColor(QtGui.QPalette.WindowText, QtGui.QColor(220, 220, 220))
            pal.setColor(QtGui.QPalette.Base, QtGui.QColor(35, 35, 35))
            pal.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor(53, 53, 53))
            pal.setColor(QtGui.QPalette.Text, QtGui.QColor(220, 220, 220))
            pal.setColor(QtGui.QPalette.Button, QtGui.QColor(53, 53, 53))
            pal.setColor(QtGui.QPalette.ButtonText, QtGui.QColor(220, 220, 220))
            app.setPalette(pal)
        else:
            app.setPalette(QtGui.QPalette())
        if self._gauge_params:
            self.rysuj_gauge(arrow_x=self._arrow_pos if self._arrow_pos is not None else self._arrow_target)
        self.rysuj_trend()
        self.status.setText("Zmieniono motyw.")

    def kopiuj_wykres(self):
        if not HAS_MPL:
            return
        buf = __import__("io").BytesIO()
        self.fig.savefig(buf, format="png", bbox_inches="tight")
        buf.seek(0)
        img = QtGui.QImage.fromData(buf.read())
        QtWidgets.QApplication.clipboard().setImage(img)
        self.status.setText("Wykres skopiowany do schowka.")

    def _hover_trend(self, event):
        if not hasattr(self, "_annot") or self._annot is None:
            return
        if event.inaxes is None or event.xdata is None:
            self._annot.set_visible(False)
            self.canvas_trend.draw_idle()
            return
        # znajdź najbliższy punkt
        if not hasattr(self, "_trend_data"):
            return
        xs_idx, ys, xs_dates = self._trend_data
        import numpy as np
        idx = min(range(len(xs_idx)), key=lambda i: abs(xs_idx[i] - (event.xdata or 0)))
        # xs są stringami dat — mapuj na indeksy
        if idx < len(ys):
            self._annot.xy = (idx, ys[idx])
            self._annot.set_text(f"{xs_dates[idx]}\nBMI {ys[idx]:.2f}")
            self._annot.set_visible(True)
            self.canvas_trend.draw_idle()

    def closeEvent(self, event):
        event.accept()


def main() -> int:
    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow()
    win.show()
    if os.environ.get("BMI_DESKTOP_SMOKE") == "1":
        QtCore.QTimer.singleShot(100, win.oblicz)
        QtCore.QTimer.singleShot(200, win.rysuj_trend)
        QtCore.QTimer.singleShot(500, app.quit)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
