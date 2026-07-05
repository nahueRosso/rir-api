import marimo

__generated_with = "0.23.3"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # M3 · Gráficas de resultados

    Las tres figuras que pide el informe (Resultados, 30%): curva de
    decaimiento con regresiones, banco de filtros de octava, y
    validación contra software comercial.
    """)
    return


@app.cell
def _():
    import marimo as mo
    import numpy as np
    import matplotlib.pyplot as plt
    from scipy import signal as sig

    # Paleta (dataviz skill): tinta primaria/secundaria + slots categoricos
    # validados (blue, aqua, yellow, ...). Fondo claro para reporte impreso.
    INK_PRIMARY = "#0b0b0b"
    INK_SECONDARY = "#52514e"
    INK_MUTED = "#898781"
    GRID = "#e1e0d9"
    BLUE = "#2a78d6"
    AQUA = "#1baf7a"
    YELLOW = "#eda100"
    VIOLET = "#4a3aa7"
    SURFACE = "#fcfcfb"

    def estilo_reporte(ax):
        """Aplica el estilo comun a las tres figuras: fondo claro, grillas
        recesivas, ejes en tinta secundaria."""
        ax.set_facecolor(SURFACE)
        ax.figure.set_facecolor(SURFACE)
        ax.grid(True, color=GRID, linewidth=0.8, zorder=0)
        ax.set_axisbelow(True)
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)
        for spine in ("left", "bottom"):
            ax.spines[spine].set_color(INK_MUTED)
        ax.tick_params(colors=INK_SECONDARY, labelsize=8)
        ax.title.set_color(INK_PRIMARY)
        ax.xaxis.label.set_color(INK_SECONDARY)
        ax.yaxis.label.set_color(INK_SECONDARY)

    def integral_schroeder(ri: np.ndarray) -> np.ndarray:
        """Integral de Schroeder en dB, normalizada a 0 dB (ver acoustic_parameters.py)."""
        energia = ri.astype(np.float64) ** 2
        integral_inversa = np.cumsum(energia[::-1])[::-1]
        referencia = integral_inversa[0] if integral_inversa[0] > 0 else 1e-12
        return 10.0 * np.log10(integral_inversa / referencia + 1e-12)

    def regresion_lineal(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
        pendiente, ordenada = np.polyfit(x, y, deg=1)
        return float(pendiente), float(ordenada)

    def segmento(tiempo, edc_db, db_inicio, db_fin):
        mask = (edc_db <= db_inicio) & (edc_db >= db_fin)
        idx = np.flatnonzero(mask)
        return tiempo[idx], edc_db[idx]

    return (
        AQUA,
        BLUE,
        INK_MUTED,
        INK_PRIMARY,
        INK_SECONDARY,
        VIOLET,
        YELLOW,
        estilo_reporte,
        integral_schroeder,
        mo,
        np,
        plt,
        regresion_lineal,
        segmento,
        sig,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 1 · Curva de decaimiento (Schroeder + regresiones)
    """)
    return


@app.cell
def _(
    AQUA,
    BLUE,
    INK_PRIMARY,
    INK_SECONDARY,
    VIOLET,
    YELLOW,
    estilo_reporte,
    integral_schroeder,
    np,
    plt,
    regresion_lineal,
    segmento,
):
    # RI sintetica representativa (T60 = 2.0 s, banda 1000 Hz) para ilustrar
    # el metodo: no requiere subir un archivo, es puramente didactica.
    _fs = 44100
    _t60 = 2.0
    _dur = 1.2
    _n = int(_dur * _fs)
    _t = np.arange(_n) / _fs
    _alpha = 3.0 * np.log(10.0) / _t60
    _rng = np.random.default_rng(7)
    _ri = _rng.standard_normal(_n) * np.exp(-_alpha * _t)

    _edc = integral_schroeder(_ri)

    # Regresiones EDT / T20 / T30, extrapoladas a -60 dB
    _t_edt, _y_edt = segmento(_t, _edc, 0.0, -10.0)
    _t_t20, _y_t20 = segmento(_t, _edc, -5.0, -25.0)
    _t_t30, _y_t30 = segmento(_t, _edc, -5.0, -35.0)

    _m_edt, _b_edt = regresion_lineal(_t_edt, _y_edt)
    _m_t20, _b_t20 = regresion_lineal(_t_t20, _y_t20)
    _m_t30, _b_t30 = regresion_lineal(_t_t30, _y_t30)

    _edt = -60.0 / _m_edt
    _t20 = -60.0 / _m_t20
    _t30 = -60.0 / _m_t30

    fig1, ax1 = plt.subplots(figsize=(6, 4))
    estilo_reporte(ax1)

    ax1.plot(_t, _edc, color=INK_PRIMARY, linewidth=1.6, label="Schroeder [dB]", zorder=3)

    _t_ext = np.array([0.0, 60.0 / abs(_m_t30) * 1.05])
    ax1.plot(
        _t_ext, _m_edt * _t_ext + _b_edt, "--", color=VIOLET, linewidth=1.4,
        label=f"EDT (0 a -10 dB) = {_edt:.2f} s",
    )
    ax1.plot(
        _t_ext, _m_t20 * _t_ext + _b_t20, "--", color=YELLOW, linewidth=1.4,
        label=f"T20 (-5 a -25 dB) = {_t20:.2f} s",
    )
    ax1.plot(
        _t_ext, _m_t30 * _t_ext + _b_t30, "--", color=BLUE, linewidth=1.4,
        label=f"T30 (-5 a -35 dB) = {_t30:.2f} s",
    )

    for _db in (-5, -15, -25, -35):
        _idx = np.argmin(np.abs(_edc - _db))
        ax1.scatter([_t[_idx]], [_db], s=36, color=AQUA, zorder=4, edgecolors="white", linewidths=0.6)
        ax1.annotate(
            f"{_db} dB", (_t[_idx], _db), textcoords="offset points", xytext=(6, 4),
            fontsize=7, color=INK_SECONDARY,
        )

    ax1.set_xlim(0, _dur)
    ax1.set_ylim(-70, 5)
    ax1.set_xlabel("Tiempo [s]")
    ax1.set_ylabel("Nivel [dB]")
    ax1.set_title("Curva de Schroeder — regresión y extrapolación a -60 dB")
    ax1.legend(frameon=False, fontsize=7.5, loc="lower left")

    fig1
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 2 · Banco de filtros de octava (IEC 61260)
    """)
    return


@app.cell
def _(AQUA, INK_SECONDARY, estilo_reporte, np, plt, sig):
    _fs = 44100
    _nyq = _fs / 2.0
    _bandas = (31.5, 63, 125, 250, 500, 1000, 2000, 4000, 8000, 16000)

    # Rampa secuencial (un solo hue, claro -> oscuro) para las bandas: son
    # categorias ORDENADAS por frecuencia, no identidades sin orden.
    _ramp = [
        "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#2a78d6",
        "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b",
    ]

    fig2, ax2 = plt.subplots(figsize=(6, 4))
    estilo_reporte(ax2)

    for _fc, _color in zip(_bandas, _ramp, strict=True):
        _f_inf, _f_sup = _fc / np.sqrt(2), _fc * np.sqrt(2)
        if _f_sup >= _nyq:
            continue
        _sos = sig.butter(4, [_f_inf / _nyq, _f_sup / _nyq], btype="band", output="sos")
        _w, _h = sig.sosfreqz(_sos, worN=4096, fs=_fs)
        _mag_db = 20 * np.log10(np.abs(_h) + 1e-12)
        ax2.semilogx(_w, _mag_db, color=_color, linewidth=1.3)

    ax2.axhline(-3, color=AQUA, linewidth=0.9, linestyle=":", zorder=2)
    ax2.annotate("-3 dB", (35, -3), fontsize=7, color=INK_SECONDARY, va="bottom")

    ax2.set_xlim(20, 20000)
    ax2.set_ylim(-60, 3)
    ax2.set_xlabel("Frecuencia [Hz]")
    ax2.set_ylabel("Magnitud [dB]")
    ax2.set_title("Banco de filtros de octava (IEC 61260)")
    ax2.set_xticks(list(_bandas))
    ax2.set_xticklabels([str(b) for b in _bandas], rotation=45, fontsize=7)

    fig2
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 3 · Validación de T30 — RIR-API vs. REW
    """)
    return


@app.cell
def _(BLUE, INK_MUTED, INK_SECONDARY, estilo_reporte, np, plt):
    # Datos reales obtenidos comparando RIR-API contra REW sobre la misma RI
    # (ir_posic2-pb_-_sfdc.wav).
    _bandas = ("125", "250", "500", "1k", "2k", "4k")
    _rirapp_t30 = np.array([1.63, 1.95, 2.07, 2.07, 1.90, 1.55])
    _rew_t30 = np.array([1.75, 1.86, 2.09, 2.05, 1.85, 1.51])

    _x = np.arange(len(_bandas))
    _w = 0.34

    fig3, ax3 = plt.subplots(figsize=(6, 4))
    estilo_reporte(ax3)

    ax3.bar(_x - _w / 2, _rirapp_t30, _w, color=BLUE, label="RIR-API", zorder=3)
    ax3.bar(_x + _w / 2, _rew_t30, _w, color=INK_MUTED, label="REW (referencia)", zorder=3)

    for _xi, (_a, _b) in enumerate(zip(_rirapp_t30, _rew_t30, strict=True)):
        ax3.text(_xi - _w / 2, _a + 0.03, f"{_a:.2f}", ha="center", fontsize=7, color=INK_SECONDARY)
        ax3.text(_xi + _w / 2, _b + 0.03, f"{_b:.2f}", ha="center", fontsize=7, color=INK_SECONDARY)

    ax3.set_xticks(_x)
    ax3.set_xticklabels([f"{b} Hz" for b in _bandas])
    ax3.set_ylim(0, 2.6)
    ax3.set_ylabel("T30 [s]")
    ax3.set_title("Validación de T30 · RIR-API vs. REW (misma RI)")
    ax3.legend(frameon=False, fontsize=8, loc="upper right")

    fig3
    return


if __name__ == "__main__":
    app.run()
