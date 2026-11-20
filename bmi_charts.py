from __future__ import annotations
import os
from bmi_core import *

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
    katalog = os.path.dirname(os.path.abspath(sciezka))
    os.makedirs(katalog, exist_ok=True)
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
    katalog = os.path.dirname(os.path.abspath(sciezka))
    os.makedirs(katalog, exist_ok=True)
    fig.savefig(sciezka, bbox_inches="tight")
    plt.close(fig)
    return sciezka


def rysuj_historia_interaktywna(wpisy, sciezka: str = "bmi_historia_interaktywna.html") -> str | None:
    if not HAS_PLOTLY or len(wpisy) < 2:
        return None
    kol = [KOLORY_KATEGORII[BMICalculator.kategoria(p.bmi)[0]] for p in wpisy]
    fig = gobj.Figure(data=[
        gobj.Scatter(x=[p.data for p in wpisy], y=[p.bmi for p in wpisy],
                     mode="markers+lines", marker=dict(color=kol, size=9))
    ])
    fig.update_layout(title="Trend BMI (interaktywny)", xaxis_title="Data", yaxis_title="BMI")
    katalog = os.path.dirname(os.path.abspath(sciezka))
    os.makedirs(katalog, exist_ok=True)
    fig.write_html(sciezka)
    return sciezka


