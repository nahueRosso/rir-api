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
    import io

    import marimo as mo
    import numpy as np
    import matplotlib.pyplot as plt
    import soundfile as sf
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

    def filtro_octava(senal: np.ndarray, fc: float, fs: int, orden: int = 4) -> np.ndarray:
        """Filtro pasabanda de octava (IEC 61260), sos + sosfiltfilt (ver filter.py)."""
        f_inf, f_sup = fc / np.sqrt(2), fc * np.sqrt(2)
        nyq = fs / 2.0
        sos = sig.butter(orden, [f_inf / nyq, f_sup / nyq], btype="band", output="sos")
        return sig.sosfiltfilt(sos, np.asarray(senal, dtype=np.float64))

    return (
        AQUA,
        BLUE,
        INK_MUTED,
        INK_PRIMARY,
        INK_SECONDARY,
        VIOLET,
        YELLOW,
        estilo_reporte,
        filtro_octava,
        integral_schroeder,
        io,
        mo,
        np,
        plt,
        regresion_lineal,
        segmento,
        sf,
        sig,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 1 · Curva de decaimiento (Schroeder + regresiones)

    Subí tu RI real (WAV/FLAC) para usar tu medición; si no subís nada se
    usa un ejemplo sintético (T60 = 2.0 s) solo para ilustrar el método.
    """)
    return


@app.cell
def _(mo):
    archivo_ri = mo.ui.file(
        filetypes=[".wav", ".flac"],
        label="RI real (opcional)",
    )
    banda_fc = mo.ui.dropdown(
        options=["125", "250", "500", "1000", "2000", "4000"],
        value="1000",
        label="Banda de octava",
    )
    mo.hstack([archivo_ri, banda_fc])
    return archivo_ri, banda_fc


@app.cell
def _(archivo_ri, banda_fc, filtro_octava, io, np, sf):
    fc_seleccionada = float(banda_fc.value)

    if archivo_ri.value:
        _contenido = archivo_ri.value[0].contents
        _ri_cruda, fs_ri = sf.read(io.BytesIO(_contenido), dtype="float64", always_2d=False)
        if _ri_cruda.ndim > 1:
            _ri_cruda = _ri_cruda.mean(axis=1)
        _pico = int(np.argmax(np.abs(_ri_cruda)))  # t=0 = arribo del sonido directo
        _ri_alineada = _ri_cruda[_pico:]
        fuente_ri = archivo_ri.value[0].name
    else:
        fs_ri = 44100
        _t60_demo = 2.0
        _n_demo = int(1.2 * fs_ri)
        _t_demo = np.arange(_n_demo) / fs_ri
        _alpha_demo = 3.0 * np.log(10.0) / _t60_demo
        _rng = np.random.default_rng(7)
        _ri_alineada = _rng.standard_normal(_n_demo) * np.exp(-_alpha_demo * _t_demo)
        fuente_ri = "ejemplo sintético (T60 = 2.0 s)"

    ri_banda = filtro_octava(_ri_alineada, fc_seleccionada, fs_ri)
    return fc_seleccionada, fs_ri, fuente_ri, ri_banda


@app.cell
def _(
    AQUA,
    BLUE,
    INK_PRIMARY,
    INK_SECONDARY,
    VIOLET,
    YELLOW,
    estilo_reporte,
    fc_seleccionada,
    fs_ri,
    fuente_ri,
    integral_schroeder,
    mo,
    np,
    plt,
    regresion_lineal,
    ri_banda,
    segmento,
):
    _edc = integral_schroeder(ri_banda)
    _t = np.arange(len(_edc)) / fs_ri
    _dur = _t[-1] if len(_t) else 1.0

    def _ajustar(db_inicio, db_fin):
        _tx, _ty = segmento(_t, _edc, db_inicio, db_fin)
        if len(_tx) < 2:
            return None
        _m, _b = regresion_lineal(_tx, _ty)
        return (_m, _b, -60.0 / _m) if _m < 0 else None

    _edt_fit = _ajustar(0.0, -10.0)
    _t20_fit = _ajustar(-5.0, -25.0)
    _t30_fit = _ajustar(-5.0, -35.0)

    fig1, ax1 = plt.subplots(figsize=(6, 4))
    estilo_reporte(ax1)

    ax1.plot(_t, _edc, color=INK_PRIMARY, linewidth=1.6, label="Schroeder [dB]", zorder=3)

    _t60_ref = next((v[2] for v in (_t30_fit, _t20_fit, _edt_fit) if v), _dur)
    _t_ext = np.array([0.0, min(_t60_ref * 1.1, _dur * 3)])
    for _fit, _color, _nombre, _rango in (
        (_edt_fit, VIOLET, "EDT", "0 a -10 dB"),
        (_t20_fit, YELLOW, "T20", "-5 a -25 dB"),
        (_t30_fit, BLUE, "T30", "-5 a -35 dB"),
    ):
        if _fit is None:
            continue
        _m, _b, _valor = _fit
        ax1.plot(
            _t_ext, _m * _t_ext + _b, "--", color=_color, linewidth=1.4,
            label=f"{_nombre} ({_rango}) = {_valor:.2f} s",
        )

    for _db in (-5, -15, -25, -35):
        if _edc.min() > _db:
            continue
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
    ax1.set_title(f"Curva de Schroeder — {fc_seleccionada:.0f} Hz · {fuente_ri}")
    ax1.legend(frameon=False, fontsize=7.5, loc="lower left")

    mo.vstack([fig1])
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
