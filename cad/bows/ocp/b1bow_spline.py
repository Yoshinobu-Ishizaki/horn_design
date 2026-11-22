"""b1bow の中心線のスプライン化(曲率が穏やかに変動する G2 のスプライン)。

方法は bow_spline.py(どの頭管にも使える一般化したもの)に書いてある。ここは b1bow を指定して呼ぶだけ。
  uv run python cad/bows/ocp/b1bow_spline.py
"""

from bow_spline import report

if __name__ == "__main__":
    report("b1bow")
