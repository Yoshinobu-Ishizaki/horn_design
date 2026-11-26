"""model202611(2026-11 に設計中のホルン)のスクリプトが使う import パス。

フォルダの深さによらず、このファイルの場所からリポジトリのルートと各部品のフォルダを決める。
各スクリプトの冒頭(ルートの決め方とパス):

    HERE = Path(__file__).resolve().parent
    sys.path.insert(0, str(next(p for p in HERE.parents if p.name == "model202611")))
    import model_paths  # noqa: E402

    ROOT = model_paths.add()

構成(組立のレベルごと。2026-11-25):
    bb_length/              Bb 管の全長の集計(モデル全体)
    valve_assy/             植込組立: 植込みどうしをつなぐ管
        bb34/               第 3〜第 4 の U・直管・L 字管
        bb_return/          Bb の戻り(Bb抜差組立: 中管・U・山形管)
    body_assy/              管体組立: ベルに沿う管
        branch2/            1番管の L 字管・(外した)2番管
        main_aux_tube/      主管補助管 1・2
        main_slide/         主管抜差・主管頭
        mouthpipe/          吹込管
        f_slide/            F管抜差(仮)
共通の部品(植込み cad/valves、ベル cad/bell03、bellscrew、bows、tubes)は cad/ の直下のまま。
"""

from __future__ import annotations

import sys
from pathlib import Path

MODEL = Path(__file__).resolve().parent
ROOT = MODEL.parents[1]

PARTS = {
    "bb_length": MODEL / "bb_length",
    "bb34": MODEL / "valve_assy/bb34",
    "bb_return": MODEL / "valve_assy/bb_return",
    "branch2": MODEL / "body_assy/branch2",
    "main_aux_tube": MODEL / "body_assy/main_aux_tube",
    "main_slide": MODEL / "body_assy/main_slide",
    "mouthpipe": MODEL / "body_assy/mouthpipe",
    "f_slide": MODEL / "body_assy/f_slide",
}
COMMON = ["cad/bellscrew/ocp", "cad/valves/ocp", "cad/bows/ocp", "cad/bell03/ocp", "cad/bell03/tools", "cad/tubes/ocp", "src"]


def part(name: str) -> Path:
    """部品のフォルダ(例: part("mouthpipe") / "worklog.md")。"""
    return PARTS[name]


def dirs() -> list[Path]:
    """import に使うフォルダ: 各部品の ocp・tools と、共通の部品。モジュール名の重なりはない(2026-11-25 確認)。"""
    out = [p / s for p in PARTS.values() for s in ("ocp", "tools") if (p / s).is_dir()]
    return out + [ROOT / c for c in COMMON]


def add() -> Path:
    """dirs() を sys.path の先頭へ(すでにあれば足さない)。戻り値はリポジトリのルート。"""
    for d in reversed(dirs()):
        if str(d) not in sys.path:
            sys.path.insert(0, str(d))
    return ROOT
