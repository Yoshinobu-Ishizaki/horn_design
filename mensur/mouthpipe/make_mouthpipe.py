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
    # 吹込管のメンズール

    $x$ はマウスピースの出口(差し込んだマウスピースの先端)からの芯線に沿った長さ [mm]、$D$ は内径 [mm]。
    ここではマウスピースより先のメンズールだけを扱う。マウスピースを差し込むシャンク部分は含めない。

    与える条件は 3 つ:

    1. $D(0) = d_0$(マウスピースの出口)
    2. $D(L_1) = d_1$(太い側。ここまでで広がり終わる)
    3. $D(L_2) = d_2$($0 < L_2 < L_1$)

    はじめに 4 パラメータの $D(x) = a\,(x+b)^p + d$ で考え、3 パラメータの $D(x) = a\,(x+b)^p$ に減らす。
    さらにそれを、両端の径と形のパラメータ $k$ ひとつで書く形

    $$
    D(x) = d_0 \left(\frac{d_1}{d_0}\right)^{\varphi(x/L_1)},\qquad
    \varphi(u) = \frac{\ln(1 + k\,u)}{\ln(1 + k)}
    $$

    に直す。実例はこの形で計算する。
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


@app.cell
def _(mo):
    mo.md(r"""
    ## 4 パラメータの形: $D(x) = a\,(x+b)^p + d$

    $x = 0$ で $a\,b^p + d$ になる。$b \ge 0$ なら $[0, L_1]$ で $x+b>0$。

    **指数 $p$ について**: $p = 1$ のとき $D$ は $x$ の 1 次式で、単純な直線のテーパーになる。
    吹込管は基本的に中膨らみ(直線のテーパーより太い、上に凸)の形なので、**$0 < p < 1$** とする。
    $p$ が小さいほど入口側で急に広がり、太い側では緩やかになる。

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

    ### 残る 1 つの自由度

    3 条件で $a, b, d$ は $p$ の関数として決まり、$p$ の分の自由度が 1 つ残る。
    ところが $p$ を大きく変えても、曲線の形はほとんど変わらない(径の差は数百分の 1 mm。実例で確かめる)。
    動くのは $b$ と $d$ の組み合わせだけで、$p$ が小さいと $d<0$ にもなる。

    したがって 4 つ目のパラメータは要らない。$d = 0$ とした 3 パラメータの形を使う。
    これは 4 パラメータの族のうち、$d = 0$ になる 1 本にあたる。
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 3 パラメータの形: $D(x) = a\,(x+b)^p$

    3 つの条件で $a, b, p$ が決まる。条件 2・3 をそれぞれ条件 1 で割ると $a$ が消える。

    $$
    \left(1 + \frac{L_1}{b}\right)^p = \frac{d_1}{d_0},\qquad
    \left(1 + \frac{L_2}{b}\right)^p = \frac{d_2}{d_0}
    $$

    対数を取って 2 つ目を 1 つ目で割ると $p$ も消え、$b$ だけの式になる。左辺の比を $q$ と置く。

    $$
    q \equiv \frac{\ln(d_2/d_0)}{\ln(d_1/d_0)} = \frac{\ln(1 + L_2/b)}{\ln(1 + L_1/b)}
    $$

    $q$ も条件の値だけで決まる。$b$ が決まれば

    $$
    p = \frac{\ln(d_1/d_0)}{\ln(1 + L_1/b)},\qquad a = \frac{d_0}{b^p}
    $$

    この式の組み立ては、次の $k$ の形にするとすっきりする。
    """)
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## $k$ の形: $D(x) = d_0\,(d_1/d_0)^{\varphi(x/L_1)}$

    条件 1 から $a\,b^p = d_0$ なので

    $$
    D(x) = a\,b^p \left(1 + \frac{x}{b}\right)^p = d_0 \left(1 + \frac{x}{b}\right)^p
    $$

    $u = x/L_1$(0〜1)、$k = L_1/b$($>0$)と置くと $D = d_0\,(1 + k\,u)^p$。
    条件 2 から $(1+k)^p = d_1/d_0$、すなわち

    $$
    p = \frac{\ln(d_1/d_0)}{\ln(1+k)}
    $$

    これを代入すると $D = d_0 \exp\!\left[p \ln(1+k\,u)\right]$ から

    $$
    \boxed{\;D(x) = d_0 \left(\frac{d_1}{d_0}\right)^{\varphi(u)},\qquad
    \varphi(u) = \frac{\ln(1 + k\,u)}{\ln(1 + k)},\qquad u = \frac{x}{L_1}\;}
    $$

    $\varphi(0) = 0$、$\varphi(1) = 1$。両端の径 $d_0, d_1$ がそのまま式に出て、形は $k$ ひとつで決まる。
    径の対数を $\ln d_0$ から $\ln d_1$ まで $\varphi(u)$ で補間している形になっている。

    $a, b, p$ は $k$ から $b = L_1/k$、$p = \ln(d_1/d_0)/\ln(1+k)$、$a = d_0/b^p$ と決まる。

    | $k$ | 形 | $p$ |
    |---|---|---|
    | $k \to 0$ | $\varphi = u$。径が一定の比率で増える指数の形(下に凸) | $p \to \infty$ |
    | $k = d_1/d_0 - 1$ | 直線のテーパー | $p = 1$ |
    | $k > d_1/d_0 - 1$ | 中膨らみ | $p < 1$ |
    | $k \to \infty$ | 入口ですぐ太くなる、段に近い形 | $p \to 0$ |

    ### 3 点の条件

    条件 3 は $\left(d_2/d_0\right) = \left(d_1/d_0\right)^{\varphi(L_2/L_1)}$、すなわち

    $$
    \varphi\!\left(\frac{L_2}{L_1}\right) = q = \frac{\ln(d_2/d_0)}{\ln(d_1/d_0)}
    $$

    で、3 パラメータの節の $q$ の式そのもの。$\varphi(L_2/L_1)$ は $k$ について単調に増え、
    $k\to 0$ で $L_2/L_1$、$k\to\infty$ で 1 になるので、$L_2/L_1 < q < 1$ なら $k$ がただ一つ決まる。
    中膨らみ($k > d_1/d_0 - 1$)になるのは、$q$ が直線のときの値 $\ln\!\left(1 + (d_1/d_0 - 1)\,L_2/L_1\right) / \ln(d_1/d_0)$ より大きいとき。

    ### 形のパラメータ $\mu = \ln k$

    $k$ は 0 から $\infty$ まで動き、形の変わり方は $k$ の対数に対してほぼ均等になる(実例で確かめる)。
    そこで $\mu = \ln k$ を形のパラメータとし、$k = e^{\mu}$ とする。直線のテーパーは $\mu = \ln(d_1/d_0 - 1)$。
    """)
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## 実例

    ### 計算に使う関数

    形の大きさの目安として、直線のテーパーからの最大の膨らみ

    $$
    h = \max_{0 \le x \le L_1} \left[ D(x) - \left(d_0 + \frac{d_1-d_0}{L_1}\,x\right) \right]
    $$

    も求める。最大の位置は $D'(x)$ が直線の傾き $(d_1-d_0)/L_1$ に等しいところ。
    $D'(x) = D(x)\,\ln(d_1/d_0)\,\dfrac{k}{L_1\,(1+k\,u)\,\ln(1+k)}$。
    """)
    return


@app.cell
def _(L1, brentq, d0, d1, np):
    LN_R = np.log(d1 / d0)  # ln(d1/d0)
    K_LIN = d1 / d0 - 1.0  # 直線のテーパーになる k

    def phi(u, k):
        """φ(u) = ln(1 + k u) / ln(1 + k)"""
        return np.log1p(k * np.asarray(u, dtype=float)) / np.log1p(k)

    def diameter(x, k):
        """D(x) = d0 (d1/d0)^φ(x/L1)"""
        return d0 * np.exp(LN_R * phi(np.asarray(x, dtype=float) / L1, k))

    def slope(x, k):
        """D'(x)"""
        _u = np.asarray(x, dtype=float) / L1
        return diameter(x, k) * LN_R * k / (L1 * (1.0 + k * _u) * np.log1p(k))

    def k_to_abp(k):
        """k から 3 パラメータの形の (a, b, p) を返す。"""
        _b = L1 / k
        _p = LN_R / np.log1p(k)
        return d0 / _b**_p, _b, _p

    def bulge(k):
        """直線のテーパーからの最大の膨らみ h と、その位置 x* を返す。中膨らみでなければ (0, nan)。"""
        if k <= K_LIN * (1.0 + 1e-9):
            return 0.0, np.nan
        _m = (d1 - d0) / L1
        _x = brentq(lambda x: slope(x, k) - _m, 0.0, L1, xtol=1e-10)  # 中膨らみなら D' は単調に減る
        return float(diameter(_x, k)) - (d0 + _m * _x), _x

    def solve_k(L2, d2):
        """3 点目 D(L2) = d2 を満たす k を返す(φ(L2/L1) = q を μ = ln k について解く)。"""
        _q = np.log(d2 / d0) / LN_R
        if not 0 < L2 < L1:
            raise ValueError("0 < L2 < L1 が必要")
        if not L2 / L1 < _q < 1:
            raise ValueError(f"解がない: q = {_q:.6f} は ({L2 / L1:.6f}, 1) の外")
        _mu = brentq(lambda m: phi(L2 / L1, np.exp(m)) - _q, -30.0, 60.0, xtol=1e-14)
        return float(np.exp(_mu))
    return K_LIN, bulge, diameter, k_to_abp, slope, solve_k


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### 3 点から $k$ を求める
    """)
    return


@app.cell
def _(
    K_LIN,
    L1,
    L2,
    bulge,
    d0,
    d1,
    d2,
    diameter,
    k_to_abp,
    mo,
    np,
    slope,
    solve_k,
):
    k_fit = solve_k(L2, d2)
    a_fit, b_fit, p_fit = k_to_abp(k_fit)
    h_fit, x_fit = bulge(k_fit)
    _q = np.log(d2 / d0) / np.log(d1 / d0)
    _q_lin = np.log1p(K_LIN * L2 / L1) / np.log(d1 / d0)
    _chk = "\n".join(
        f"| {xq:g} | {float(diameter(xq, k_fit)):.6f} | {dq:g} |" for xq, dq in [(0.0, d0), (L2, d2), (L1, d1)]
    )
    mo.md(
        f"$q$ = {_q:.6f}(解のある範囲 {L2 / L1:.6f} .. 1、直線なら {_q_lin:.6f})\n\n"
        f"- $k$ = **{k_fit:.10g}**($\\mu = \\ln k$ = {np.log(k_fit):.6f}、直線は $k$ = {K_LIN:.6f}、"
        + ("中膨らみ" if k_fit > K_LIN else "**中膨らみでない**")
        + ")\n"
        f"- 3 パラメータの形では $a$ = {a_fit:.10g}、$b$ = {b_fit:.10g}、$p$ = {p_fit:.10g}\n"
        f"- 最大の膨らみ $h$ = {h_fit:.4f} mm($x$ = {x_fit:.1f})\n\n"
        "| x | D(x) | 目標 |\n|---|---|---|\n" + _chk
        + f"\n\n$D'(0)$ = {float(slope(0.0, k_fit)):.6f}、$D'(L_1)$ = {float(slope(L1, k_fit)):.6f}"
    )
    return h_fit, k_fit, p_fit


@app.cell
def _(L1, L2, d0, d1, d2, diameter, k_fit, np, plt, slope, xx):
    fig_shape, ax_shape = plt.subplots(2, 1, figsize=(8, 7), sharex=True)
    ax_shape[0].plot(xx, diameter(xx, k_fit), label=f"k = {k_fit:.4g} (mu = {np.log(k_fit):.4g})")
    ax_shape[0].plot([0, L1], [d0, d1], "k--", lw=0.8, label="linear taper")
    ax_shape[0].plot([0, L2, L1], [d0, d2, d1], "ko")
    ax_shape[1].plot(xx, slope(xx, k_fit))
    ax_shape[1].axhline((d1 - d0) / L1, color="k", ls="--", lw=0.8)
    ax_shape[0].set_ylabel("D [mm]")
    ax_shape[1].set_ylabel("dD/dx")
    ax_shape[1].set_xlabel("x [mm] from the mouthpiece exit")
    ax_shape[0].legend()
    for _ax in ax_shape:
        _ax.grid(True)
    fig_shape
    return


@app.cell
def _(mo):
    mo.md(r"""
    ### 4 パラメータの族と比べる

    4 パラメータの形で、3 条件を満たしたまま $p$ を動かす。
    """)
    return


@app.cell
def _(L1, L2, brentq, d0, d1, d2, mo, np, p_fit, xx):
    def solve4(pv):
        """4 パラメータの形で、p を与えて 3 条件を満たす (a, b, d) を返す。"""
        _r = (d2 - d0) / (d1 - d0)

        def g(b):
            return ((L2 + b) ** pv - b**pv) / ((L1 + b) ** pv - b**pv) - _r

        _b = brentq(g, 0.0, 1e9, xtol=1e-12, rtol=1e-15, maxiter=500)
        _a = (d1 - d0) / ((L1 + _b) ** pv - _b**pv)
        return _a, _b, d0 - _a * _b**pv

    _r = (d2 - d0) / (d1 - d0)
    p_lim = np.log(_r) / np.log(L2 / L1)  # b = 0 になる p。これより小さい p で解がある
    ps4 = [pv for pv in (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7) if pv < p_lim]
    family4 = {pv: solve4(pv) for pv in ps4}
    ys4 = np.array([_a * (xx + _b) ** pv + _d for pv, (_a, _b, _d) in family4.items()])
    spread4 = ys4.max(axis=0) - ys4.min(axis=0)
    _a0, _b0, _d0 = solve4(p_fit)  # k の形と同じ p
    _rows = "\n".join(f"| {pv:.1f} | {_a:.5g} | {_b:.5g} | {_d:.5g} |" for pv, (_a, _b, _d) in family4.items())
    mo.md(
        f"解のある $p$ の範囲: 0 < $p$ < {p_lim:.6f}\n\n"
        "| p | a | b | d |\n|---|---|---|---|\n" + _rows
        + f"\n\n径の差の最大: **{spread4.max():.4f} mm**(x = {xx[spread4.argmax()]:g})  \n"
        f"$k$ の形と同じ $p$ = {p_fit:.6f} では $d$ = {_d0:.3g}(つまり $d = 0$ の 1 本が $k$ の形)。"
    )
    return ps4, spread4, ys4


@app.cell
def _(L1, L2, d0, d1, d2, diameter, k_fit, mo, np, plt, ps4, spread4, xx, ys4):
    _dk = np.abs(ys4 - diameter(xx, k_fit)).max()
    fig_family, ax_family = plt.subplots(2, 1, figsize=(8, 7), sharex=True)
    for _pv, _y in zip(ps4, ys4):
        ax_family[0].plot(xx, _y, label=f"p = {_pv:.1f}")
    ax_family[0].plot(xx, diameter(xx, k_fit), "k:", lw=1.2, label="k form")
    ax_family[0].plot([0, L2, L1], [d0, d2, d1], "ko")
    ax_family[0].set_ylabel("D [mm]")
    ax_family[0].legend()
    ax_family[1].plot(xx, spread4)
    ax_family[1].set_ylabel("spread of D [mm]")
    ax_family[1].set_xlabel("x [mm] from the mouthpiece exit")
    for _ax in ax_family:
        _ax.grid(True)
    mo.vstack([mo.md(f"$k$ の形と 4 パラメータの族との差の最大: **{_dk:.4f} mm**"), fig_family])
    return


@app.cell
def _(mo):
    mo.md(r"""
    ### パラメータと形の変わり方

    $D(0) = d_0$、$D(L_1) = d_1$ だけを満たす曲線(条件 3 は外す)で、パラメータを変えたときの最大の膨らみ $h$ を比べる。
    横軸は $p$、$\ln p$、$\mu = \ln k$。
    """)
    return


@app.cell
def _(K_LIN, bulge, k_to_abp, np, plt):
    _mus = np.linspace(np.log(K_LIN), 4.0, 200)
    _hs = np.array([bulge(np.exp(_m))[0] for _m in _mus])
    _ps = np.array([k_to_abp(np.exp(_m))[2] for _m in _mus])
    fig_param, ax_param = plt.subplots(1, 3, figsize=(12, 3.4), sharey=True)
    for _ax, (_name, _v) in zip(ax_param, {"p": _ps, "ln p": np.log(_ps), "mu = ln k": _mus}.items()):
        _ax.plot(_v, _hs)
        _ax.set_xlabel(_name)
        _ax.grid(True)
    ax_param[0].set_ylabel("bulge h [mm]")
    fig_param.tight_layout()
    fig_param
    return


@app.cell
def _(mo):
    mo.md(r"""
    $p$ では小さい側で急に形が変わる。$\ln p$ でもまだ偏りが残る。$\mu = \ln k$ では、直線の近くを除いてほぼ直線的に $h$ が増える。

    ### $\mu$ を変えたときの比較

    $D(0) = d_0$、$D(L_1) = d_1$ だけを満たし、$\mu$ を直線の値から 0.5 ずつ増やす。
    曲線どうしの径の差が最も大きい位置を取り上げ、その位置での値も表にする。
    """)
    return


@app.cell
def _(K_LIN, diameter, np, xx):
    mu_list = [float(np.log(K_LIN)) + 0.5 * i for i in range(7)]
    ys_mu = np.array([diameter(xx, np.exp(_m)) for _m in mu_list])
    spread_mu = ys_mu.max(axis=0) - ys_mu.min(axis=0)
    i_max = int(spread_mu.argmax())
    x_max = float(xx[i_max])
    return i_max, mu_list, spread_mu, x_max, ys_mu


@app.cell
def _(
    L1,
    L2,
    d0,
    d1,
    d2,
    diameter,
    h_fit,
    k_fit,
    mu_list,
    np,
    plt,
    spread_mu,
    x_max,
    xx,
    ys_mu,
):
    fig_mu, ax_mu = plt.subplots(2, 1, figsize=(8, 7), sharex=True)
    for _m, _y in zip(mu_list, ys_mu):
        ax_mu[0].plot(xx, _y, label=f"mu = {_m:.3f}")
    ax_mu[0].plot(xx, diameter(xx, k_fit), "k:", lw=1.2, label=f"3-point fit (mu = {np.log(k_fit):.3f}, h = {h_fit:.3f})")
    ax_mu[0].plot([0, L2, L1], [d0, d2, d1], "ko")
    ax_mu[0].axvline(x_max, color="gray", lw=0.8)
    ax_mu[0].set_ylabel("D [mm]")
    ax_mu[0].legend(fontsize=8)
    ax_mu[1].plot(xx, spread_mu)
    ax_mu[1].axvline(x_max, color="gray", lw=0.8)
    ax_mu[1].set_ylabel("spread of D [mm]")
    ax_mu[1].set_xlabel("x [mm] from the mouthpiece exit")
    for _ax in ax_mu:
        _ax.grid(True)
    fig_mu
    return


@app.cell
def _(
    L1,
    bulge,
    d0,
    d1,
    i_max,
    k_to_abp,
    mo,
    mu_list,
    np,
    slope,
    spread_mu,
    x_max,
    ys_mu,
):
    _lin = d0 + (d1 - d0) * x_max / L1  # 直線での径
    _rows = []
    for _i, _m in enumerate(mu_list):
        _k = float(np.exp(_m))
        _h, _x = bulge(_k)
        _rows.append(
            f"| {_m:.3f} | {_k:.4g} | {k_to_abp(_k)[2]:.4f} | {_h:.4f} | "
            + ("–" if np.isnan(_x) else f"{_x:.1f}")
            + f" | {ys_mu[_i, i_max]:.4f} | {ys_mu[_i, i_max] - _lin:+.4f} | {float(slope(0.0, _k)):.5f} |"
        )
    mo.md(
        f"径の差が最も大きい位置: **x = {x_max:g}**(差 {spread_mu[i_max]:.4f} mm)\n\n"
        f"| μ | k | p | h | 膨らみ最大の x | D({x_max:g}) | 直線との差 | D'(0) |\n"
        "|---|---|---|---|---|---|---|---|\n" + "\n".join(_rows)
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 表に出す

    3 点から求めた $k$ の曲線の、1 mm おきの L-D 表(`make_bell.ipynb` と同じ x, y の列)。ボタンを押すと `mouthpipe_xy.csv` に書き出す。
    """)
    return


@app.cell
def _(mo):
    save_button = mo.ui.run_button(label="mouthpipe_xy.csv に書き出す")
    save_button
    return (save_button,)


@app.cell
def _(diameter, k_fit, mo, np, save_button, xx):
    from pathlib import Path

    table = np.column_stack([xx, diameter(xx, k_fit)])
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
