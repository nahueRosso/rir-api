import marimo

__generated_with = "0.23.6"
app = marimo.App(width="medium")


@app.cell
def _():
    import io
    from pathlib import Path
    import marimo as mo
    import numpy as np
    import soundfile as sf


    def cargar_audio(
        ruta_o_buffer: str | Path | io.BytesIO,
    ) -> tuple[np.ndarray, int]:
        """Carga un archivo de audio WAV o FLAC desde una ruta o desde memoria."""
        # Si es una ruta (string o Path), validamos el archivo en disco
        if isinstance(ruta_o_buffer, (str, Path)):
            ruta_path = Path(ruta_o_buffer)
            if not ruta_path.exists():
                raise FileNotFoundError(
                    f"Error: El archivo no fue encontrado en: '{ruta_o_buffer}'"
                )
            if ruta_path.suffix.lower() not in [".wav", ".flac"]:
                raise ValueError(
                    f"Error: Formato '{ruta_path.suffix}' no soportado."
                )
            origen = ruta_path
        else:
            # Si no es string ni Path, asumimos que ya es un archivo en memoria (BytesIO)
            origen = ruta_o_buffer

        try:
            senal, frecuencia_de_muestreo = sf.read(origen, dtype="float64")
            return senal, frecuencia_de_muestreo
        except Exception as e:
            raise ValueError(f"Error al procesar el archivo de audio: {e}") from e

    return cargar_audio, io, mo


@app.cell
def _(mo):
    # Corrección del parámetro: 'filetypes' sin guion bajo
    archivo_input = mo.ui.file(
        filetypes=[".wav", ".flac"],
        label="Seleccioná un archivo de audio de tu PC",
    )

    archivo_input
    return (archivo_input,)


@app.cell
def _(archivo_input, cargar_audio, io, mo):
    # Inicializamos las variables que usarás después
    senal = None
    fs = None

    if archivo_input.value:
        try:
            # Obtenemos la info del componente de Marimo
            nombre_archivo = archivo_input.value[0].name
            contenido_bytes = archivo_input.value[0].contents

            # Envolvemos los bytes en BytesIO y llamamos a tu función
            archivo_en_memoria = io.BytesIO(contenido_bytes)
            senal, fs = cargar_audio(archivo_en_memoria)

            # Chequeamos canales para el mensaje
            tipo_audio = (
                f"Estéreo ({senal.shape[1]} canales)"
                if len(senal.shape) > 1 and senal.shape[1] > 1
                else "Mono"
            )

            info_md = mo.md(
                f"""
                ### ✅ ¡{nombre_archivo}! cargado con éxito
                * **Frecuencia de muestreo:** {fs} Hz
                * **Dimensiones de la señal:** {senal.shape} *(muestras, canales)*
                * **Tipo de audio:** {tipo_audio}
                """
            )
        except Exception as e:
            info_md = mo.md(f"### ❌ Error al procesar el archivo\n{str(e)}")
    else:
        info_md = mo.md("*Esperando que selecciones un archivo...*")

    info_md
    return


if __name__ == "__main__":
    app.run()
