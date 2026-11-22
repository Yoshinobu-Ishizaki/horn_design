"""b3bow の中心線のスプライン化(曲率が穏やかに変動する G2 のスプライン)。方法は bow_spline.py。
  uv run python cad/bows/ocp/b3bow_spline.py
"""

from bow_spline import report

if __name__ == "__main__":
    report("b3bow")
