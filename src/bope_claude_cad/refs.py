"""参照用の楽器(RefBell など)を探して読む。

社内図面は git 管理外で、機種名もリポジトリに書かない。ファイルは実行時に探す。

- RefBell: ベル(ベル + 1番管の手前まで)の芯線と L-D 表を持つ DXF。
  環境変数 HORN_REFBELL_DXF があればそのファイル、なければリポジトリの jigs/*_seat/input/*_bell_assy.dxf。
  読み方は claude_cad_vss のサンプル(.claude/skills/claude_cad_vss/scripts/bell_from_dxf.py)。

    from bope_claude_cad.refs import refbell
    cl, L, D = refbell()   # 芯線(build123d の Wire、設計の座標)、L-D 表
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REFBELL_GLOB = "jigs/*_seat/input/*_bell_assy.dxf"


def refbell_dxf() -> Path:
    """RefBell の DXF の場所。見つからなければ FileNotFoundError。"""
    env = os.environ.get("HORN_REFBELL_DXF")
    if env:
        p = Path(env).expanduser()
        if not p.is_file():
            raise FileNotFoundError(f"HORN_REFBELL_DXF のファイルがない: {p}")
        return p
    found = sorted(ROOT.glob(REFBELL_GLOB))
    if not found:
        raise FileNotFoundError(f"RefBell の DXF が見つからない({REFBELL_GLOB}、または環境変数 HORN_REFBELL_DXF)")
    return found[0]


def refbell():
    """RefBell の芯線(Wire)と L-D 表(L, D の配列)を返す。"""
    import ezdxf

    scripts = ROOT / ".claude/skills/claude_cad_vss/scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    from bell_from_dxf import build_centerline, read_table

    msp = ezdxf.readfile(refbell_dxf()).modelspace()
    L, D = read_table(msp)
    return build_centerline(msp), L, D
