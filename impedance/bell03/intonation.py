"""bell03 の候補 c(result_c.json)で、Bb 管・F 管の入力インピーダンスと音程を計算し、RefHorn と比べる。

計算の条件と方法は impedance/bell01/intonation.py と同じ(上流は refhornBb000.men の x=0〜1413、右手 220 mm、
a' = 442 Hz、24 ℃)。bell03 は ⌀12 の円筒を dcyl だけ縮め(上流側)、F 管は延長管 Fx を足す。
RefHorn の F 管の延長管は、F 管の f' = Bb 管の f' + F_ABOVE_BB になる長さ。

    uv run python impedance/bell03/intonation.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from scipy.optimize import brentq

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "bell02"))  # bell02 の合わせ込みの部品(rows_of、adjust_up)を使う
import refine_perturb as R  # noqa: E402
import scan_length as S  # noqa: E402

I = S.I  # noqa: E741
RESULT = HERE / "result_c.json"


def params() -> dict:
    r = json.loads(RESULT.read_text())
    p, ang, q, a_, l0, lam, dcyl, fx = r["x"]
    return {"xe": r["xe"], "p": p, "ang": ang, "q": q, "pert": [(a_, l0, lam / R.WIN, lam)], "dcyl": dcyl, "fx": fx}


def cents(men: Path, key: str) -> list:
    return I.cents_vs_series(I.peaks(men), key)


def main() -> None:
    hr = I.read_refhorn()
    i_up = next(i for i, r in enumerate(hr) if I.UPSTREAM_END in r[3])
    up, hr_tail = hr[:i_up], hr[i_up:]
    v = params()
    rows, _ = R.rows_of(v["p"], v["ang"], v["q"], v["xe"], v["pert"])
    u = S.adjust_up(up, v["dcyl"])
    res = {
        ("bell03", "Bb"): cents(I.build_rows("bell03_Bb", u + rows, HERE), "Bb"),
        ("bell03", "F"): cents(I.build_rows("bell03_F", u + [(12.0, 12.0, v["fx"], "F extra")] + rows, HERE), "F"),
        ("refhorn", "Bb"): cents(I.build_rows("refhorn_Bb", up + hr_tail, HERE), "Bb"),
    }
    hb6 = next(c for n, _, _, c in res[("refhorn", "Bb")] if n == 6)

    def f_err(fx):
        c = {n: ct for n, _, _, ct in cents(I.build_rows("refhorn_F", up + [(12.0, 12.0, fx, "F extra")] + hr_tail, HERE), "F")}
        return c[8] - (hb6 + I.F_ABOVE_BB)

    fx_h = brentq(f_err, 800, 1100, xtol=0.05)
    res[("refhorn", "F")] = cents(I.build_rows("refhorn_F", up + [(12.0, 12.0, fx_h, "F extra")] + hr_tail, HERE), "F")
    total = sum(r[2] for r in u) + v["xe"]
    print(f"bell03: Bb total {total:.1f} mm (upstream {sum(r[2] for r in u):.1f} + bell03 {v['xe']:.1f}), F extra {v['fx']:.1f} mm; "
          f"RefHorn F extra {fx_h:.1f} mm")

    lines = []
    for key in ("Bb", "F"):
        a = {n: (nm, f, c) for n, nm, f, c in res[("bell03", key)]}
        b = {n: (nm, f, c) for n, nm, f, c in res[("refhorn", key)]}
        lines.append(f"\n{key} horn (cents vs equal temperament, A={I.A4:.0f})")
        lines.append(" n  note     bell03 Hz  cents |  RefHorn Hz  cents | diff")
        for n in sorted(k for k in set(a) & set(b) if k <= I.N_MAX):
            lines.append(f"{n:2d}  {a[n][0]:5s} {a[n][1]:9.2f} {a[n][2]:+6.1f} | {b[n][1]:9.2f} {b[n][2]:+6.1f} | "
                         f"{a[n][2] - b[n][2]:+6.1f}")
    text = "\n".join(lines)
    print(text)
    (HERE / "intonation.txt").write_text(text.lstrip() + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
