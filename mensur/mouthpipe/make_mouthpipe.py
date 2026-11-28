import marimo

__generated_with = "0.18.4"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import matplotlib.pyplot as plt
    import numpy as np
    from scipy.optimize import brentq

    return brentq, mo, np, plt


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # 吹込管のメンズール: $D(x) = a\,(x+b)^p$

    $x$ はマウスピースの出口(差し込んだマウスピースの先端)からの芯線に沿った長さ [mm]、$D$ は内径 [mm]。
    ここではマウスピースより先のメンズールだけを扱う。マウスピースを差し込むシャンク部分は含めない。

    与える条件は 3 つ:

    1. $D(0) = d_0$(マウスピースの出口)
    2. $D(L_1) = d_1$(太い側。ここまでで広がり終わる)
    3. $D(L_2) = d_2$($0 < L_2 < L_1$)

    **指数 $p$ について**: $p = 1$ のとき $D$ は $x$ の 1 次式で、単純な直線のテーパーになる。
    吹込管は基本的に中膨らみ(直線のテーパーより太い、上に凸)の形なので、**$0 < p < 1$** とする。
    $p$ が小さいほど入口側で急に広がり、太い側では緩やかになる。

    はじめに 4 パラメータの $D(x) = a\,(x+b)^p + d$ で考える。3 条件を与えると、残る 1 つの自由度では形がほとんど変わらない。
    そのため 3 パラメータ($d$ を消した形)で足りることを示し、その形で決める。
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 条件の値

    ### シャンク部分から $d_0$ を決める

    実際の吹込管には、マウスピースを差し込むシャンク部分がある。通常、内径は入口の 8.3〜8.4 から、
    マウスピースの差込長さ(18〜20 mm)にわたってテーパー率 0.03(長さ 1 mm あたりの直径の減り)で細くなる。
    マウスピースの出口(= この式の $x=0$)での径は

    $$
    d_0 = D_\mathrm{shank} - 0.03 \times L_\mathrm{insert}
    $$

    で、8.4 から始めて差込長さ 18 なら $8.4 - 0.54 = 7.86$ になる。
    """)
    return


@app.cell
def _(mo):
    d_shank = mo.ui.slider(8.3, 8.4, step=0.01, value=8.4, show_value=True, label="シャンクの入口の内径 D_shank")
    l_insert = mo.ui.slider(18.0, 20.0, step=0.5, value=18.0, show_value=True, label="マウスピースの差込長さ L_insert")
    mo.vstack([d_shank, l_insert])
    return d_shank, l_insert


@app.cell
def _(d_shank, l_insert, mo):
    TAPER_SHANK = 0.03  # シャンクのテーパー率(直径の減り / 長さ)
    d0 = d_shank.value - TAPER_SHANK * l_insert.value  # マウスピースの出口の内径(x = 0)
    mo.md(f"$d_0$ = {d_shank.value:g} − {TAPER_SHANK:g} × {l_insert.value:g} = **{d0:.4f}**")
    return (d0,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### そのほかの条件

    $L_1, d_1$ は今の吹込管(`mouthpipe_try.py`: 450 で 12)と同じにした。$L_2, d_2$ は仮の値なので置き換える。
    """)
    return


@app.cell
def _(mo):
    L1_in = mo.ui.number(value=450.0, step=1.0, label="L1(太い側の位置)")
    d1_in = mo.ui.number(value=12.0, step=0.01, label="d1(太い側の内径)")
    L2_in = mo.ui.number(value=150.0, step=1.0, label="L2(途中の位置、仮)")
    d2_in = mo.ui.number(value=9.6, step=0.01, label="d2(途中の内径、仮)")
    mo.vstack([L1_in, d1_in, L2_in, d2_in])
    return L1_in, L2_in, d1_in, d2_in


@app.cell
def _(L1_in, L2_in, d1_in, d2_in, np):
    L1, d1, L2, d2 = L1_in.value, d1_in.value, L2_in.value, d2_in.value
    xx = np.linspace(0.0, L1, int(L1) + 1)  # 1 mm おき
    return L1, L2, d1, d2, xx


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 4 パラメータの形: $D(x) = a\,(x+b)^p + d$

    $x = 0$ で $a\,b^p + d$ になる。$b \ge 0$ なら $[0, L_1]$ で $x+b>0$。

    ### $p$ を決めたときの $a, b, d$

    3 つの条件を式で書くと

    $$
    d_0 = a\,b^p + d,\qquad d_1 = a\,(L_1+b)^p + d,\qquad d_2 = a\,(L_2+b)^p + d
    $$

    条件 2 から条件 1 を、条件 3 から条件 1 を引くと $d$ が消える。

    $$
    d_1 - d_0 = a\left[(L_1+b)^p - b^p\right],\qquad
    d_2 - d_0 = a\left[(L_2+b)^p - b^p\right]
    $$

    2 つ目を 1 つ目で割ると $a$ も消え、$b$ だけの式になる。左辺の比を $r$ と置く。

    $$
    r \equiv \frac{d_2-d_0}{d_1-d_0} = \frac{(L_2+b)^p - b^p}{(L_1+b)^p - b^p}
    $$

    $r$ は、全体の広がり $d_1-d_0$ のうち、$L_2$ までにどれだけ広がったかの割合で、条件の値だけで決まる。

    - $p = 1$ なら右辺は $b$ によらず $L_2/L_1$。直線のテーパーは $r = L_2/L_1$ のときだけ 3 点を通る。
    - $0 < p < 1$ なら右辺は $b=0$ で $(L_2/L_1)^p$、$b\to\infty$ で $L_2/L_1$(直線に近づく)。
      したがって解があるのは $L_2/L_1 < r < (L_2/L_1)^p$ のとき。$r > L_2/L_1$ は、3 点が中膨らみに並んでいるということ。

    $b$ が決まれば

    $$
    a = \frac{d_1-d_0}{(L_1+b)^p - b^p},\qquad d = d_0 - a\,b^p
    $$
    """)
    return


@app.cell
def _(brentq, np):
    B_MAX = 1e9  # b の探索の上限(これより大きいと、ほぼ直線のテーパー)

    def diameter4(x, a, b, p, d):
        """D(x) = a (x+b)^p + d"""
        return a * np.power(np.asarray(x, dtype=float) + b, p) + d

    def solve4(p, d0, L1, d1, L2, d2):
        """p (0 < p < 1) を与えて、D(0)=d0, D(L1)=d1, D(L2)=d2 を満たす (a, b, p, d) を返す。"""
        if not 0 < L2 < L1:
            raise ValueError("0 < L2 < L1 が必要")
        if not 0 < p < 1:
            raise ValueError("0 < p < 1 が必要(p = 1 は直線)")
        r = (d2 - d0) / (d1 - d0)

        def g(b):
            s0 = b**p
            return ((L2 + b) ** p - s0) / ((L1 + b) ** p - s0) - r

        if g(0.0) * g(B_MAX) > 0:
            raise ValueError(f"p = {p:g} では解がない: r = {r:.6f} は ({L2 / L1:.6f}, {(L2 / L1) ** p:.6f}) の外")
        b = brentq(g, 0.0, B_MAX, xtol=1e-12, rtol=1e-15, maxiter=500)
        a = (d1 - d0) / ((L1 + b) ** p - b**p)
        d = d0 - a * b**p
        return a, b, p, d

    return B_MAX, diameter4, solve4


@app.cell
def _(L1, L2, d0, d1, d2, mo, np):
    r = (d2 - d0) / (d1 - d0)
    p_lim = np.log(r) / np.log(L2 / L1) if L2 / L1 < r < 1 else np.nan  # b = 0 になる p。r = (L2/L1)^p を解いたもの
    mo.md(
        f"$r$ = {r:.6f}(直線なら $L_2/L_1$ = {L2 / L1:.6f})  \n"
        f"解のある $p$ の範囲: 0 < $p$ < {p_lim:.6f}"
    )
    return (p_lim,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### 残る 1 つの自由度で形はどれだけ変わるか

    3 条件を満たしたまま $p$ を動かし、曲線を比べる。
    """)
    return


@app.cell
def _(L1, L2, d0, d1, d2, diameter4, mo, np, p_lim, solve4, xx):
    ps = [pv for pv in (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7) if pv < p_lim]  # p_lim より小さい範囲
    family = {pv: solve4(pv, d0, L1, d1, L2, d2) for pv in ps}
    ys = np.array([diameter4(xx, *family[pv]) for pv in ps])
    spread = ys.max(axis=0) - ys.min(axis=0)
    rows = "\n".join(
        f"| {pv:.1f} | {_a:.5g} | {_b:.5g} | {_d:.5g} |" for pv, (_a, _b, _p, _d) in family.items()
    )
    mo.md(
        "| p | a | b | d |\n|---|---|---|---|\n" + rows
        + f"\n\n径の差の最大: **{spread.max():.4f} mm**(x = {xx[spread.argmax()]:g})"
    )
    return family, ps, spread, ys


@app.cell
def _(L1, L2, d0, d1, d2, diameter4, family, plt, ps, spread, xx):
    fig_family, ax_family = plt.subplots(2, 1, figsize=(8, 7), sharex=True)
    for _p in ps:
        ax_family[0].plot(xx, diameter4(xx, *family[_p]), label=f"p = {_p:.1f}")
    ax_family[0].plot([0, L1], [d0, d1], "k--", lw=0.8, label="linear taper (p = 1)")
    ax_family[0].plot([0, L2, L1], [d0, d2, d1], "ko")
    ax_family[0].set_ylabel("D [mm]")
    ax_family[0].legend()
    ax_family[1].plot(xx, spread)
    ax_family[1].set_ylabel("spread of D [mm]")
    ax_family[1].set_xlabel("x [mm] from the mouthpiece exit")
    for _ax in ax_family:
        _ax.grid(True)
    fig_family
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    $p$ を 0.1 から 0.7 まで変えても、径の差は最大で 0.04 mm 程度しかない。
    動くのは $b$ と $d$ の組み合わせで、形はほとんど変わらない。また $p$ が小さいと $d<0$ になる。

    したがって 4 つ目のパラメータは要らない。$d = 0$ とした 3 パラメータの形を使う。
    これは上の 4 パラメータの族のうち、$d = 0$ になる 1 本にあたる。
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 3 パラメータの形: $D(x) = a\,(x+b)^p$

    $d$ がなければ、条件 2・3 をそれぞれ条件 1 で割ると $a$ が消える。

    $$
    \left(1 + \frac{L_1}{b}\right)^p = \frac{d_1}{d_0},\qquad
    \left(1 + \frac{L_2}{b}\right)^p = \frac{d_2}{d_0}
    $$

    対数を取って 2 つ目を 1 つ目で割ると $p$ も消え、$b$ だけの式になる。左辺の比を $q$ と置く。

    $$
    q \equiv \frac{\ln(d_2/d_0)}{\ln(d_1/d_0)} = \frac{\ln(1 + L_2/b)}{\ln(1 + L_1/b)}
    $$

    $q$ も条件の値だけで決まる。右辺は $b\to\infty$ で $L_2/L_1$、$b\to 0$ で 1。
    したがって **$L_2/L_1 < q < 1$** のときに解があり、$a, b$ は正になる。$b$ が決まれば

    $$
    p = \frac{\ln(d_1/d_0)}{\ln(1 + L_1/b)},\qquad a = \frac{d_0}{b^p}
    $$

    求めた $p$ が $0 < p < 1$(中膨らみ)になっていることを確かめる。
    """)
    return


@app.cell
def _(B_MAX, brentq, np):
    def diameter(x, a, b, p):
        """D(x) = a (x+b)^p"""
        return a * np.power(np.asarray(x, dtype=float) + b, p)

    def slope(x, a, b, p):
        """D'(x) = a p (x+b)^(p-1)"""
        return a * p * np.power(np.asarray(x, dtype=float) + b, p - 1.0)

    def solve3(d0, L1, d1, L2, d2):
        """D(0)=d0, D(L1)=d1, D(L2)=d2 を満たす (a, b, p) を返す。"""
        if not 0 < L2 < L1:
            raise ValueError("0 < L2 < L1 が必要")
        q = np.log(d2 / d0) / np.log(d1 / d0)
        if not L2 / L1 < q < 1:
            raise ValueError(f"解がない: q = {q:.6f} は ({L2 / L1:.6f}, 1) の外")

        def g(b):
            return np.log1p(L2 / b) / np.log1p(L1 / b) - q

        b = brentq(g, 1e-9, B_MAX, xtol=1e-12, rtol=1e-15, maxiter=500)
        p = np.log(d1 / d0) / np.log1p(L1 / b)
        a = d0 / b**p
        return a, b, p

    return diameter, slope, solve3


@app.cell
def _(L1, L2, d0, d1, d2, diameter, mo, np, slope, solve3):
    prm = solve3(d0, L1, d1, L2, d2)
    a, b, p = prm
    _q = np.log(d2 / d0) / np.log(d1 / d0)
    _chk = "\n".join(
        f"| {xq:g} | {float(diameter(xq, *prm)):.6f} | {dq:g} |" for xq, dq in [(0.0, d0), (L2, d2), (L1, d1)]
    )
    mo.md(
        f"$q$ = {_q:.6f}(解のある範囲 {L2 / L1:.6f} .. 1)\n\n"
        f"- $a$ = **{a:.10g}**\n- $b$ = **{b:.10g}**\n- $p$ = **{p:.10g}**("
        + ("$0 < p < 1$ で中膨らみ" if 0 < p < 1 else "**$p \\ge 1$: 中膨らみでない**")
        + ")\n\n| x | D(x) | 目標 |\n|---|---|---|\n" + _chk
        + f"\n\n$D'(0)$ = {float(slope(0.0, *prm)):.6f}、$D'(L_1)$ = {float(slope(L1, *prm)):.6f}"
    )
    return p, prm


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### 確かめ: 4 パラメータで同じ $p$ を使うと $d = 0$ になる
    """)
    return


@app.cell
def _(L1, L2, d0, d1, d2, diameter, mo, np, p, prm, solve4, xx, ys):
    _a4, _b4, _p4, _d4 = solve4(p, d0, L1, d1, L2, d2)
    mo.md(
        f"$a$ = {_a4:.10g}、$b$ = {_b4:.10g}、$d$ = {_d4:.3g}  \n"
        f"4 パラメータの族との差の最大: {np.abs(ys - diameter(xx, *prm)).max():.4f} mm"
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 形を見る
    """)
    return


@app.cell
def _(L1, L2, d0, d1, d2, diameter, plt, prm, slope, xx):
    fig_shape, ax_shape = plt.subplots(2, 1, figsize=(8, 7), sharex=True)
    ax_shape[0].plot(xx, diameter(xx, *prm), label=f"a = {prm[0]:.4g}, b = {prm[1]:.4g}, p = {prm[2]:.4g}")
    ax_shape[0].plot([0, L1], [d0, d1], "k--", lw=0.8, label="linear taper (p = 1)")
    ax_shape[0].plot([0, L2, L1], [d0, d2, d1], "ko")
    ax_shape[1].plot(xx, slope(xx, *prm))
    ax_shape[1].axhline((d1 - d0) / L1, color="k", ls="--", lw=0.8)
    ax_shape[0].set_ylabel("D [mm]")
    ax_shape[1].set_ylabel("dD/dx")
    ax_shape[1].set_xlabel("x [mm] from the mouthpiece exit")
    ax_shape[0].legend()
    for _ax in ax_shape:
        _ax.grid(True)
    fig_shape
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 表に出す

    1 mm おきの L-D 表(`make_bell.ipynb` と同じ x, y の列)。ボタンを押すと `mouthpipe_xy.csv` に書き出す。
    """)
    return


@app.cell
def _(mo):
    save_button = mo.ui.run_button(label="mouthpipe_xy.csv に書き出す")
    save_button
    return (save_button,)


@app.cell
def _(diameter, mo, np, prm, save_button, xx):
    from pathlib import Path

    table = np.column_stack([xx, diameter(xx, *prm)])
    _out = Path(__file__).parent / "mouthpipe_xy.csv"
    if save_button.value:
        np.savetxt(_out, table, delimiter=",", header="x,y", comments="", fmt="%.6f")
        _msg = f"書き出した: `{_out}`"
    else:
        _msg = "(まだ書き出していない)"
    mo.vstack([mo.md(_msg), mo.ui.table({"x": table[:, 0].tolist(), "y": table[:, 1].tolist()}, page_size=10)])
    return


if __name__ == "__main__":
    app.run()
