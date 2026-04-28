import marimo

__generated_with = "0.23.3"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import matplotlib.pyplot as plt
    import numpy as np


    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    $\int_0^22$
    """)
    return


if __name__ == "__main__":
    app.run()
