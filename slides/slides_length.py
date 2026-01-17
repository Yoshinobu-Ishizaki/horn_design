import marimo

__generated_with = "0.18.4"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Slide length calculation

    - F/Bb open lengths are assumed as below.
    """)
    return


@app.cell
def _():
    bopen = 9 * 304.8 * 1.03 # 3% longer than 9 ft
    fopen = 12 * 304.8 * 1.03 # 3% longer than 12 ft
    return (bopen,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Also, each valve port length is assumed as,
    """)
    return


@app.cell
def _():
    portlen = 35.0
    return (portlen,)


@app.cell
def _(mo):
    mo.md(r"""
    Basic slide pipe length are measured (adding ferrule length and slide gap),
    """)
    return


@app.cell
def _():
    slide_short = 36 + 6 + 1
    slide_long = 67 + 6 + 1
    return slide_long, slide_short


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Bb 2nd slide

    half tone longer than Bb open.
    """)
    return


@app.cell
def _():
    halftone_ratio = 2**(1/12)
    return (halftone_ratio,)


@app.cell
def _(bopen, halftone_ratio):
    b2_len = bopen * (halftone_ratio-1)
    b2_len
    return (b2_len,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    b2 bow length are calculated as,
    """)
    return


@app.cell
def _(b2_len, portlen, slide_short):
    b2_bow = b2_len - portlen - 2 * slide_short
    b2_bow
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### B1 slide
    """)
    return


@app.cell
def _():
    holetone_ratio = 2**(1/6)
    return (holetone_ratio,)


@app.cell
def _(bopen, holetone_ratio):
    b1_len = bopen * (holetone_ratio-1)
    b1_len
    return (b1_len,)


@app.cell
def _(b1_len, portlen, slide_long):
    b1_bow = b1_len - portlen - 2*slide_long
    b1_bow
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### B3 slide

    The length of b3 slide is calculated for 2-3 combination, then subtract b2 length.
    """)
    return


@app.cell
def _():
    twotone_ratio = 2 ** (4/12)
    return (twotone_ratio,)


@app.cell
def _(bopen, twotone_ratio):
    b23_len = bopen * (twotone_ratio-1)
    return (b23_len,)


@app.cell
def _(b23_len, b2_len):
    b3_len = b23_len - b2_len
    b3_len
    return (b3_len,)


@app.cell
def _(b3_len, portlen, slide_long):
    b3_bow = b3_len - portlen - 2*slide_long
    b3_bow
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
