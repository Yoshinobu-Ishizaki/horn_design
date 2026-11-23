"""全部の抜差(Bb 第 1〜3、F 第 1〜3)を、植込み 4 つと一緒にビューアに出す。作った形はキャッシュから読む。
  python3 cad/valves/ocp/warm.py run cad/valves/ocp/all_slides.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def collect():
    import valve1_bb1_slide as B1
    import valve1_f1_slide as F1
    import valve2_bb2_slide as B2
    import valve2_f2_slide as F2
    import valve3_bb3_slide as B3
    import valve3_f3_slide as F3

    out = {"Bb1": B1.build()[0], "Bb2": B2.build()[0], "Bb3": B3.build()[0], "F1": F1.build()[0], "F2": F2.build()[0], "F3": F3.build()[0]}
    return out


V4_NAMES = ["valve4_knuckle_F1_225_twisted", "valve4_knuckle_F2_135_45deg", "valve4_knuckle_F1_135_45deg", "valve4_knuckle_F1_315_mirrored_twisted",
            "valve4_knuckle_F2_225_twisted", "valve4_knuckle_F2_315_45deg_plusx"]


def valve4_knuckles():
    """第 4 植込みの枝管 6 本(valve4_knuckle.py)。ソースが変わっていなければキャッシュから読む。"""
    from shape_cache import cached

    import valve4_knuckle as V

    def build():
        return [V.twisted_knuckle(), V.connect_knuckle(V.Z_F2), V.connect_knuckle(V.Z_F1), V.mirrored_twisted_knuckle(), V.twisted_knuckle_2f(), V.knuckle_2f_right()]

    return cached("valve4_knuckles", "v1", Path(__file__).resolve().parent / "valve4_knuckle.py", build)


def show_all(slides):
    from ocp_vscode import Camera

    from bope_claude_cad.viewer import show
    from valve_row import build_row_cached

    row = build_row_cached()
    parts, names = [], []
    for v, (case, ks, nms) in row.items():
        parts += [case] + ks
        names += [f"{v}_case"] + nms
    parts += valve4_knuckles()
    names += V4_NAMES
    for tag, p in slides.items():
        parts += list(p.values())
        names += [f"{tag}_{k}" for k in p]
    show(*parts, names=names, reset_camera=Camera.KEEP)


def report(tag, info, meta):
    print(f"{tag}: ΔL = {meta['need']:.3f}、頭管 {meta['l_in']:g}+…+{meta['l_out']:g} を両端 {meta['j']:g} mm 切り詰め(厳密値 {meta['j_exact']:.3f})→ 中心線 {meta['bow_len']:.3f}")
    if meta.get("pipe_gap") is not None:
        print(f"  上側の横向き枝管の延長との距離(d=0): 下げる前 {meta['dist0']:.3f} → 要求 ≥ {meta['pipe_gap']:g} のため頭を {meta['drop']:g} mm 下げた(直管をその分長く)")
    print(f"  中管 {meta["L"]:g}、外管 {info['outer_len']:g}、抜き量 d = {meta['d']:.3f} mm(ちょうどの音程)、継ぎ目 y={info['y_j']:.3f}、頭管側の直管の残り 入口 {meta['l_in'] - meta['j']:g}・出口 {meta['l_out'] - meta['j']:g}")


def main(tag=None, build=None):
    slides = collect()
    if build is not None:
        parts, info, meta = build()
        report(tag, info, meta)
    show_all(slides)
    if "--check" in sys.argv and build is not None:
        check(slides, tag)


def check(slides, tag):
    from valve_row import build_row_cached

    row = build_row_cached()
    mine = slides[tag]
    allp = list(mine.values())
    for k in ("outer_tube_L", "inner_tube_L", "ferrule_L", "bow"):
        pass
    print("--- 確認")
    for nm in ("L", "R"):
        for an, a, bn, b in [("桂", mine[f"ferrule_{nm}"], "頭管", mine["bow"]), ("桂", mine[f"ferrule_{nm}"], "中管", mine[f"inner_tube_{nm}"]),
                              ("外管", mine[f"outer_tube_{nm}"], "中管", mine[f"inner_tube_{nm}"])]:
            print(f"{an}{nm} ↔ {bn}: 距離 {a.distance_to(b):.4f}")
    for t, p in slides.items():
        if t != tag:
            print(f"{tag} ↔ {t}: 最小距離 {min(a.distance_to(b) for a in allp for b in p.values()):.3f}")
    for v, (case, ks, nms) in row.items():
        print(f"{tag} ↔ {v}(ケースと枝管): 最小距離 {min(min(a.distance_to(x) for x in [case] + list(ks)) for a in allp):.3f}")




def check_all():
    """抜差どうしの最小距離と、頭管と「上側の横向き枝管の延長」との距離(d は今の抜いた状態。差し込み切った状態は各スクリプトの確認)。"""
    import f_slide as F
    from valve_row import VALVES, build_row_cached

    slides = collect()
    tags = list(slides)
    print("--- 抜差どうしの最小距離(0.4 mm 未満があれば要注意)")
    worst = []
    for i, a in enumerate(tags):
        for b in tags[i + 1:]:
            dmin = min(x.distance_to(y) for x in slides[a].values() for y in slides[b].values())
            worst.append((dmin, a, b))
    for dmin, a, b in sorted(worst)[:8]:
        print(f"{a} ↔ {b}: {dmin:.3f}")
    row = build_row_cached()
    print("--- 頭管と、他の植込みのケース・枝管")
    for tag, p in slides.items():
        own = {"Bb1": "valve1", "Bb2": "valve2", "Bb3": "valve3", "F1": "valve1", "F2": "valve2", "F3": "valve3"}[tag]
        for v, (case, ks, nms) in row.items():
            if v == own:
                continue
            dm = min(p["bow"].distance_to(x) for x in [case] + list(ks))
            if dm < 3.0:
                print(f"{tag} 頭管 ↔ {v}: {dm:.3f}")
    print("--- 差し込み切った状態(d=0)の F 頭管と、延長パイプ")


if __name__ == "__main__":
    main()
    if "--check-all" in sys.argv:
        check_all()
