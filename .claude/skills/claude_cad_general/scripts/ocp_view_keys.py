"""OCP CAD Viewer 拡張に、ユーザー定義の視点を数字キーで出すパッチ(標準ライブラリだけで動く)。

  7 キー: top view(X 方向が左、+Y 方向が上)。Z 上の座標系で、-Z 側から +Z を見る向き(カメラは (0,0,-1) の側、
          上方向 +Y、右方向 -X)。拡張の元の視点ボタン(top / bottom など)とは別に、同じ preset の仕組みで足す。
  入力欄(INPUT / TEXTAREA / SELECT)にフォーカスがあるとき、Ctrl・Alt・Meta を押しているときは動かさない。

使い方:
    python ocp_view_keys.py status      # 対象ファイルとパッチの有無
    python ocp_view_keys.py apply       # 当てる(すでに当たっていれば何もしない)
    python ocp_view_keys.py revert      # このパッチだけを外す(ほかのパッチは残る)

当てたあとは VS Code のウィンドウを再読み込みする(Developer: Reload Window)。拡張を更新すると改造は消えるので、そのときは apply をやり直す。
ホバーやマウスのパッチを当て直すとこのパッチが消えることがあるので、そのあとも apply をやり直す。
元のファイルは .orig に保存する(ocp_hover_name.py・ocp_mouse.py と共用。無いときだけ作る)。差し込み先が見つからないときは、
何も書き換えずに終了コード 2 で終わる。
"""

import shutil
import sys
from pathlib import Path

EXT_GLOB = "bernhard-42.ocp-cad-viewer-*"
REL = Path("node_modules/three-cad-viewer/dist/three-cad-viewer.esm.js")
MARK = "PATCH(local): view-keys"
BEGIN, END = f"// {MARK} BEGIN", f"// {MARK} END"

DIR_ANCHOR = """        bottom: {
            pos: new Vector3(0, 0, -1),
            quat: new Quaternion(1, 0, 0, 0),
        },
    },
    legacy: {"""
DIR_NEW = f"""        bottom: {{
            pos: new Vector3(0, 0, -1),
            quat: new Quaternion(1, 0, 0, 0),
        }},
        {BEGIN} top view (X left, +Y up): camera on the -Z side, up +Y
        xleft_top: {{
            pos: new Vector3(0, 0, -1),
            quat: new Quaternion(0, 1, 0, 0),
        }},
        {END}
    }},
    legacy: {{"""

KEY_ANCHOR = """            this.rendered.camera.presetCamera(dir, zoom);
            this.rendered.controls.setTarget(this.rendered.camera.target);
            this.update(true, notify);
        };"""
KEY_NEW = KEY_ANCHOR + f"""
        {BEGIN} key 7 = top view (X left, +Y up)
        window.addEventListener("keydown", (ev) => {{
            const t = ev.target && ev.target.tagName;
            if (ev.key !== "7" || ev.ctrlKey || ev.altKey || ev.metaKey || t === "INPUT" || t === "TEXTAREA" || t === "SELECT") return;
            if (!this.rendered || !this.rendered.camera || this.rendered.camera.up !== "z_up") return;
            this.presetCamera("xleft_top");
        }});
        {END}"""


def target() -> Path:
    cands = sorted((Path.home() / ".vscode" / "extensions").glob(EXT_GLOB))
    if not cands:
        sys.exit("拡張が見つからない")
    return cands[-1] / REL


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    f = target()
    s = f.read_text(encoding="utf-8")
    has = MARK in s
    if cmd == "status":
        print(f"{f}\nパッチ: {'あり' if has else 'なし'}")
        return
    if cmd == "apply":
        if has:
            print("すでに当たっている")
            return
        if DIR_ANCHOR not in s or KEY_ANCHOR not in s:
            print("差し込み先が見つからない(拡張のバージョンが違う)", file=sys.stderr)
            sys.exit(2)
        orig = f.with_suffix(f.suffix + ".orig")
        if not orig.exists():
            shutil.copy2(f, orig)
        f.write_text(s.replace(DIR_ANCHOR, DIR_NEW, 1).replace(KEY_ANCHOR, KEY_NEW, 1), encoding="utf-8")
        print("当てた。VS Code のウィンドウを再読み込みする(Developer: Reload Window)")
    elif cmd == "revert":
        if not has:
            print("パッチは当たっていない")
            return
        out = []
        skip = False
        for line in s.split("\n"):
            if BEGIN in line:
                skip = True
            if not skip:
                out.append(line)
            if END in line:
                skip = False
        f.write_text("\n".join(out), encoding="utf-8")
        print("外した")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
