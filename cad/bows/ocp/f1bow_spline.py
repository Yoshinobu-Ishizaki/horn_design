"""f1bow の中心線のスプライン化(曲率が穏やかに変動する G2 のスプライン)。b1bow と同じ方法(bow_spline.py)。
  uv run python cad/bows/ocp/f1bow_spline.py
"""

from bow_spline import report

if __name__ == "__main__":
    report("f1bow")
