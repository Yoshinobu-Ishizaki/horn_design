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
    return bopen, fopen


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


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Basic slide pipe length are measured (adding ferrule length and slide gap),
    notice that slide long length is coincide with the future calculated length for F2.
    """)
    return


@app.cell
def _():
    slide_short = 36 + 6 + 1
    slide_long = 67 + 6 + 1 -3

    slide_short, slide_long
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
    return (b2_bow,)


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


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## F2 slide

    For F2, use same bow as b2 , then calculate length for slide tubes.
    """)
    return


@app.cell
def _(fopen, halftone_ratio):
    f2_len = fopen * (halftone_ratio-1)
    return (f2_len,)


@app.cell
def _(b2_bow, f2_len, portlen):
    f2_slide_len = round((f2_len - b2_bow - portlen)/2)
    f2_slide_len
    return


@app.cell
def _(slide_long):
    slide_long
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## F1 slide
    """)
    return


@app.cell
def _(fopen, holetone_ratio):
    f1_len = fopen * (holetone_ratio-1)
    return (f1_len,)


@app.cell
def _(f1_len, portlen, slide_long):
    f1_bow = f1_len - slide_long*2 - portlen
    f1_bow
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## F3 slide

    As same as b3 slide, its length is calculated for 2-3 combination.
    """)
    return


@app.cell
def _(fopen, twotone_ratio):
    f23_len = fopen * (twotone_ratio -1)
    return (f23_len,)


@app.cell
def _(f23_len, f2_len):
    f3_len = f23_len - f2_len
    return (f3_len,)


@app.cell
def _(f3_len, portlen, slide_long):
    f3_bow = f3_len - slide_long*2 - portlen
    f3_bow
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
