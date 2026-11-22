"""OCP CAD Viewer 拡張のマウス操作(回転・パン・ズーム)の割り当てを変えるパッチ(標準ライブラリだけで動く)。

OCP CAD Viewer(three-cad-viewer)は、左ドラッグで回転、右ドラッグでパン、中ドラッグとホイールでズームする。
拡張の設定で変えられるのは修飾キーの読み替え(`OcpCadViewer.view.modifier_keys`)だけで、
どのボタンで回すかは変えられない。このパッチは、VS Code にインストールされた拡張の
three-cad-viewer.esm.js の `Controls`(trackball / orbit の両方)に、ボタン+修飾キー → 操作の表を差し込む。

元の処理には手を入れず、押されたボタンと修飾キーを「元の処理が同じ操作をするボタン」に読み替えて渡す
(回転=左、ズーム=中、パン=右、修飾キーなし。回転の向きの制限だけ、元の修飾キーの意味で渡す)。
左クリックでの選択と、右クリック(カメラが動かないとき)での選択の取り消しは、元のまま動く。

割り当ての方式(--preset):
    geomagic   右ドラッグ=回転、Ctrl+右=パン、Shift+右=ズーム、中ドラッグ=パン、左は選択だけ(既定)
    robodk     右ドラッグ=回転、中ドラッグ=パン、左は選択だけ
    creo       中ドラッグ=回転、Shift+中=パン、Ctrl+中=ズーム、左は選択だけ
    solidworks 中ドラッグ=回転、Ctrl+中=パン、Shift+中=ズーム、左は選択だけ
    ocp        拡張の元の割り当て(左=回転、Shift+左=パン、右=パン、中=ズーム ほか)
ホイールはどの方式でもズーム。向き(--wheel normal|reverse)とズームの中心(--zoom-center target|cursor)は別に選ぶ。
target は回転中心(今の動き)、cursor はマウスの位置を止めたまま拡大・縮小する。

使い方:
    python ocp_mouse.py status                    # 対象ファイル、パッチの有無、保存した設定と割り当て表
    python ocp_mouse.py presets                   # 方式ごとの割り当て表
    python ocp_mouse.py set --preset geomagic     # 設定を保存して当てる(--wheel / --zoom-center / --bind も)
    python ocp_mouse.py set --bind right+alt=rotate_h --bind left+ctrl=none   # 一部だけ上書き
    python ocp_mouse.py set --clear-binds         # 上書きを消す
    python ocp_mouse.py apply                     # 保存した設定で当てる(拡張を更新したあとはこれ)
    python ocp_mouse.py revert                    # このパッチだけを外す(ホバーのパッチは残る)

--bind の書式は `ボタン[+修飾キー...]=操作`。ボタンは left / middle / right、修飾キーは ctrl / shift / alt、
操作は rotate / rotate_h(横回転だけ)/ rotate_v(縦回転だけ)/ pan / zoom / none。
修飾キーは完全一致で引く(Ctrl+Shift+右 は right+ctrl+shift の行だけを見る)。

設定は ~/.ocp_mouse.json に保存する(無ければ geomagic、ホイールは normal、中心は target)。
当てたあとは VS Code のウィンドウを再読み込みする(Developer: Reload Window)。
拡張を更新すると改造は消えるので、そのときは apply をやり直す。
元のファイルは .orig に保存する(ocp_hover_name.py と共用。無いときだけ作る)。
拡張のバージョンが変わって差し込み先が見つからないときは、何も書き換えずに終了コード 2 で終わる。
"""

import argparse
import json
import re
import sys
from pathlib import Path

EXT_GLOB = "bernhard-42.ocp-cad-viewer-*"
REL = Path("node_modules/three-cad-viewer/dist/three-cad-viewer.esm.js")
CONFIG = Path.home() / ".ocp_mouse.json"

MARK = "PATCH(local): mouse-map"
BEGIN = f"// {MARK} BEGIN"
END = f"// {MARK} END"
ANCHOR_CLASS = "class Controls {"
ANCHORS = {
    "trackball": "this.controls = new CADTrackballControls(this.camera, this.domElement);",
    "orbit": "this.controls = new CADOrbitControls(this.camera, this.domElement);",
}


def install_suffix(kind: str) -> str:
    return f' ocpMouseInstall(this.controls, "{kind}"); /* {MARK} */'


BUTTONS = ("left", "middle", "right")
MODS = ("ctrl", "shift", "alt")
ACTIONS = ("rotate", "rotate_h", "rotate_v", "pan", "zoom", "none")
WHEELS = ("normal", "reverse")
CENTERS = ("target", "cursor")

PRESETS: dict[str, dict[str, str]] = {
    "geomagic": {
        "right": "rotate",
        "right+ctrl": "pan",
        "right+shift": "zoom",
        "right+alt": "rotate_h",
        "right+shift+alt": "rotate_v",
        "middle": "pan",
    },
    "robodk": {
        "right": "rotate",
        "middle": "pan",
    },
    "creo": {
        "middle": "rotate",
        "middle+shift": "pan",
        "middle+ctrl": "zoom",
    },
    "solidworks": {
        "middle": "rotate",
        "middle+ctrl": "pan",
        "middle+shift": "zoom",
    },
    "ocp": {  # 拡張の元の割り当て(Windows の既定の modifier_keys のとき)
        "left": "rotate",
        "left+shift": "pan",
        "left+ctrl": "rotate_v",
        "left+alt": "rotate_h",
        "right": "pan",
        "right+ctrl": "rotate",
        "right+shift": "rotate",
        "right+alt": "rotate",
        "middle": "zoom",
    },
}
DEFAULT_SETTINGS = {"preset": "geomagic", "binds": {}, "wheel": "normal", "zoom_center": "target"}


def canon_key(key: str) -> str:
    """`Right+Shift+ctrl` → `right+ctrl+shift`(ボタン+修飾キーを ctrl, shift, alt の順に)。"""
    parts = [p.strip().lower() for p in key.split("+") if p.strip()]
    if not parts or parts[0] not in BUTTONS:
        raise ValueError(f"ボタンは {'/'.join(BUTTONS)} のどれか: {key!r}")
    mods = set(parts[1:])
    bad = mods - set(MODS)
    if bad or len(mods) != len(parts) - 1:
        raise ValueError(f"修飾キーは {'/'.join(MODS)} を重ねずに: {key!r}")
    return "+".join([parts[0], *[m for m in MODS if m in mods]])


def parse_bind(text: str) -> tuple[str, str]:
    if "=" not in text:
        raise ValueError(f"`ボタン[+修飾キー]=操作` の形で: {text!r}")
    key, action = text.split("=", 1)
    action = action.strip().lower()
    if action not in ACTIONS:
        raise ValueError(f"操作は {'/'.join(ACTIONS)} のどれか: {text!r}")
    return canon_key(key), action


def bindings(settings: dict) -> dict[str, str]:
    """方式の表に上書きを重ねた、実際の割り当て(none は消す)。"""
    preset = settings.get("preset", DEFAULT_SETTINGS["preset"])
    if preset not in PRESETS:
        raise ValueError(f"方式は {'/'.join(PRESETS)} のどれか: {preset!r}")
    table = {canon_key(k): v for k, v in PRESETS[preset].items()}
    for k, v in settings.get("binds", {}).items():
        table[canon_key(k)] = v
    return {k: v for k, v in table.items() if v != "none"}


def js_config(settings: dict) -> dict:
    wheel = settings.get("wheel", "normal")
    center = settings.get("zoom_center", "target")
    if wheel not in WHEELS:
        raise ValueError(f"wheel は {'/'.join(WHEELS)} のどれか: {wheel!r}")
    if center not in CENTERS:
        raise ValueError(f"zoom_center は {'/'.join(CENTERS)} のどれか: {center!r}")
    return {
        "preset": settings.get("preset"),
        "bindings": bindings(settings),
        "wheel_reverse": wheel == "reverse",
        "zoom_to_cursor": center == "cursor",
    }


JS_BODY = r"""
// Resolve a mouse event to an action of the table: rotate / rotate_h / rotate_v / pan / zoom, or null.
function ocpMouseResolve(ev) {
    const b = ["left", "middle", "right"][ev.button];
    if (!b) return null;
    const key = [b];
    if (ev.ctrlKey) key.push("ctrl");
    if (ev.shiftKey) key.push("shift");
    if (ev.altKey) key.push("alt");
    return OCP_MOUSE_CFG.bindings[key.join("+")] || null;
}
// A stand-in event for the original handlers, which do (without modifiers) rotate on button 0,
// zoom on button 1 and pan on button 2. lock "v" sets the viewer's "ctrl" (vertical rotation only),
// lock "h" its "meta" (horizontal rotation only), through KeyMapper so a remapped modifier_keys still works.
function ocpMouseProxy(ev, button, lock) {
    const p = {
        button: button, pageX: ev.pageX, pageY: ev.pageY, clientX: ev.clientX, clientY: ev.clientY,
        pointerId: ev.pointerId, pointerType: ev.pointerType,
        ctrlKey: false, shiftKey: false, altKey: false, metaKey: false,
        preventDefault: () => ev.preventDefault(), stopPropagation: () => ev.stopPropagation(),
    };
    if (lock === "v") p[KeyMapper.keyMapping.ctrl] = true;
    if (lock === "h") p[KeyMapper.keyMapping.meta] = true;
    return p;
}
function ocpMouseButtonFor(action) {
    if (action == null) return -1;
    if (action === "zoom") return 1;
    if (action === "pan") return 2;
    return 0;
}
function ocpMouseLockFor(action) {
    return action === "rotate_v" ? "v" : action === "rotate_h" ? "h" : null;
}
function ocpMouseWheelProxy(ev) {
    const s = OCP_MOUSE_CFG.wheel_reverse ? -1 : 1;
    return {
        deltaX: ev.deltaX, deltaY: s * ev.deltaY, deltaZ: ev.deltaZ, deltaMode: ev.deltaMode,
        clientX: ev.clientX, clientY: ev.clientY, pageX: ev.pageX, pageY: ev.pageY,
        ctrlKey: ev.ctrlKey, shiftKey: ev.shiftKey, altKey: ev.altKey, metaKey: ev.metaKey,
        preventDefault: () => ev.preventDefault(), stopPropagation: () => ev.stopPropagation(),
    };
}
// World point under the cursor, on the plane through the target facing the camera.
function ocpMouseWorldAt(controls, ev) {
    const cam = controls.object;
    cam.updateMatrixWorld();
    const r = controls.domElement.getBoundingClientRect();
    const v = controls.target.clone().project(cam);
    v.x = ((ev.clientX - r.left) / r.width) * 2 - 1;
    v.y = -((ev.clientY - r.top) / r.height) * 2 + 1;
    return v.unproject(cam);
}
// Shift camera and target so that the point under the cursor stays where it was before the zoom.
function ocpMouseKeepCursor(controls, ev, before) {
    const d = before.sub(ocpMouseWorldAt(controls, ev));
    controls.object.position.add(d);
    controls.target.add(d);
    controls.update();
    controls.dispatchEvent({ type: "change" });
}
function ocpMouseInstall(controls, kind) {
    const el = controls.domElement;
    if (!el) return;
    const origDown = controls._onMouseDown;
    controls._onMouseDown = (ev) => origDown(ocpMouseProxy(ev, ocpMouseButtonFor(ocpMouseResolve(ev)), null));
    // rotation start / axis lock listeners of the CAD controls
    const lockName = kind === "trackball" ? "_holroydPointerDown" : "_onCADPointerDown";
    const origLock = controls[lockName];
    if (origLock) {
        el.removeEventListener("pointerdown", origLock);
        const w = (ev) => {
            if (ev.pointerType === "touch") return origLock(ev);
            const a = ocpMouseResolve(ev);
            const rot = a != null && a.startsWith("rotate");
            // trackball: the holroyd handler only starts on button 0; orbit: it only sets the axis lock
            return origLock(ocpMouseProxy(ev, rot || kind !== "trackball" ? 0 : 1, rot ? ocpMouseLockFor(a) : null));
        };
        controls[lockName] = w;
        el.addEventListener("pointerdown", w);
    }
    // wheel: direction, and zoom to cursor
    const origWheel = controls._onMouseWheel;
    el.removeEventListener("wheel", origWheel);
    let wheel;
    if (kind === "trackball") {
        const origH = controls._holroydWheel;
        if (origH) el.removeEventListener("wheel", origH);
        wheel = (ev) => {
            const before = OCP_MOUSE_CFG.zoom_to_cursor && !controls.noZoom ? ocpMouseWorldAt(controls, ev) : null;
            origWheel(ocpMouseWheelProxy(ev));
            if (origH) origH(ev);
            if (before) ocpMouseKeepCursor(controls, ev, before);
        };
        if (origH) controls._holroydWheel = wheel;
    } else {
        controls.zoomToCursor = OCP_MOUSE_CFG.zoom_to_cursor;
        wheel = (ev) => origWheel(ocpMouseWheelProxy(ev));
    }
    controls._onMouseWheel = wheel;
    el.addEventListener("wheel", wheel, { passive: false });
}
"""


def js_block(settings: dict, nl: str = "\n") -> str:
    cfg = json.dumps(js_config(settings), ensure_ascii=True)
    text = (
        f"{BEGIN} - remap mouse buttons/modifiers for rotate, pan and zoom (bope_claude_cad ocp_mouse.py)\n"
        f"const OCP_MOUSE_CFG = {cfg};"
        f"{JS_BODY}"
        f"{END}\n"
    )
    return text.replace("\n", nl)


def is_patched(text: str) -> bool:
    return MARK in text


def unpatch_text(text: str) -> str:
    text = re.sub(
        re.escape(BEGIN) + r".*?" + re.escape(END) + r"\r?\n", "", text, count=1, flags=re.DOTALL
    )
    for kind in ANCHORS:
        text = text.replace(install_suffix(kind), "")
    return text


def patch_text(text: str, settings: dict) -> str:
    """パッチを当てた全文を返す(当たっていれば外してから当て直す)。差し込み先が無ければ ValueError。"""
    text = unpatch_text(text)
    nl = "\r\n" if "\r\n" in text else "\n"
    line_start = nl + ANCHOR_CLASS
    if text.count(line_start) != 1:
        raise ValueError(f"`{ANCHOR_CLASS}` が見つからない(または複数)")
    for kind, anchor in ANCHORS.items():
        if text.count(anchor) != 1:
            raise ValueError(f"`{anchor}` が見つからない(または複数)")
        text = text.replace(anchor, anchor + install_suffix(kind), 1)
    return text.replace(line_start, nl + js_block(settings, nl) + ANCHOR_CLASS, 1)


def load_settings() -> dict:
    if CONFIG.is_file():
        data = json.loads(CONFIG.read_text(encoding="utf-8"))
        return {**DEFAULT_SETTINGS, **data}
    return dict(DEFAULT_SETTINGS)


def save_settings(settings: dict) -> None:
    js_config(settings)  # 検査
    CONFIG.write_text(json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"設定を保存: {CONFIG}")


ACTION_JA = {
    "rotate": "回転",
    "rotate_h": "回転(横だけ)",
    "rotate_v": "回転(縦だけ)",
    "pan": "パン",
    "zoom": "ズーム",
}


def describe(settings: dict) -> str:
    table = bindings(settings)
    order = {b: i for i, b in enumerate(BUTTONS)}
    rows = sorted(
        table.items(), key=lambda kv: (order[kv[0].split("+")[0]], kv[0].count("+"), kv[0])
    )
    lines = [f"  {k:<22} {ACTION_JA[v]}" for k, v in rows]
    left = [k for k in table if k.split("+")[0] == "left"]
    if not left:
        lines.append("  (左ボタンは選択だけ)")
    lines.append(
        f"  ホイール: ズーム、向き {settings.get('wheel')}、中心 {settings.get('zoom_center')}"
    )
    return "\n".join(lines)


def find_targets() -> list[Path]:
    root = Path.home() / ".vscode" / "extensions"
    return sorted(d / REL for d in root.glob(EXT_GLOB) if (d / REL).is_file())


def apply(path: Path, settings: dict) -> int:
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    try:
        new = patch_text(text, settings)
    except ValueError as e:
        print(f"{e}: {path}", file=sys.stderr)
        return 2
    if new == text:
        print(f"変更なし(同じ設定で当たっている): {path}")
        return 0
    orig = path.with_name(path.name + ".orig")
    if not orig.exists() and not is_patched(text):
        orig.write_bytes(raw)
        print(f"バックアップ: {orig}")
    path.write_bytes(new.encode("utf-8"))
    print(
        f"パッチを当てた: {path}\nVS Code のウィンドウを再読み込みしてください(Developer: Reload Window)"
    )
    return 0


def revert(path: Path) -> int:
    text = path.read_bytes().decode("utf-8")
    if not is_patched(text):
        print(f"当たっていない: {path}")
        return 0
    path.write_bytes(unpatch_text(text).encode("utf-8"))
    print(
        f"このパッチを外した: {path}\nVS Code のウィンドウを再読み込みしてください(Developer: Reload Window)"
    )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    sub.add_parser("presets")
    sub.add_parser("apply")
    sub.add_parser("revert")
    s = sub.add_parser("set")
    s.add_argument("--preset", choices=list(PRESETS))
    s.add_argument("--wheel", choices=WHEELS)
    s.add_argument("--zoom-center", choices=CENTERS)
    s.add_argument("--bind", action="append", default=[], help="ボタン[+修飾キー]=操作(複数可)")
    s.add_argument("--clear-binds", action="store_true", help="上書きを消して方式の表に戻す")
    s.add_argument("--no-apply", action="store_true", help="保存だけして当てない")
    args = ap.parse_args()

    if args.cmd == "presets":
        for name in PRESETS:
            print(f"[{name}]")
            print(describe({**DEFAULT_SETTINGS, "preset": name}))
        return 0

    settings = load_settings()
    if args.cmd == "set":
        if args.preset:
            settings["preset"] = args.preset
        if args.wheel:
            settings["wheel"] = args.wheel
        if args.zoom_center:
            settings["zoom_center"] = args.zoom_center
        binds = {} if args.clear_binds else dict(settings.get("binds", {}))
        try:
            for b in args.bind:
                k, v = parse_bind(b)
                binds[k] = v
            settings["binds"] = binds
            save_settings(settings)
        except ValueError as e:
            print(e, file=sys.stderr)
            return 2
        if args.no_apply:
            return 0

    targets = find_targets()
    if not targets:
        print("OCP CAD Viewer の拡張が見つからない(~/.vscode/extensions)", file=sys.stderr)
        return 2
    rc = 0
    for t in targets:
        if args.cmd == "status":
            print(
                ("パッチ済み" if is_patched(t.read_text(encoding="utf-8")) else "未パッチ")
                + f": {t}"
            )
        elif args.cmd in ("apply", "set"):
            rc = max(rc, apply(t, settings))
        else:
            rc = max(rc, revert(t))
    if args.cmd == "status":
        print(f"設定({CONFIG if CONFIG.is_file() else '未保存。既定'}): 方式 {settings['preset']}")
        print(describe(settings))
    return rc


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    sys.exit(main())
