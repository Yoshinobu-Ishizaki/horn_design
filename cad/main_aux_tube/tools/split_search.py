"""補助管の分割(main_aux_split.py)の探索を、手元で何度も回すための道具。障害物の頂点群と基準の芯線(`main_aux_split.py --dump` が /tmp/claude-1000/ に保存)を
読んで、複数の乱数の種で差分進化 + SLSQP を回し、コスト最小の y = (P_m, θ, φ) を出す。1 つの種で 5〜6 分。結果は main_aux_split.PRESET に書き写す。

    uv run python cad/main_aux_tube/tools/split_search.py
"""
import sys, math, time, numpy as np
sys.path[:0]=["/home/yoshinobu/horn/horn_design/cad/main_aux_tube/ocp","/home/yoshinobu/horn/horn_design/cad/bb34/ocp","/home/yoshinobu/horn/horn_design/cad/branch2/ocp","/home/yoshinobu/horn/horn_design/cad/bellscrew/ocp","/home/yoshinobu/horn/horn_design/cad/valves/ocp","/home/yoshinobu/horn/horn_design/cad/bows/ocp","/home/yoshinobu/horn/horn_design/cad/bell03/ocp","/home/yoshinobu/horn/horn_design/cad/bell03/tools"]
import main_aux_split as S
from scipy.spatial import cKDTree
from scipy.optimize import differential_evolution, minimize
obs=np.load("/tmp/claude-1000/split_obs.npy"); ref=np.load("/tmp/claude-1000/split_ref.npy")
tree=cKDTree(obs); tref=cKDTree(ref)
E=np.array([59.0,-17.53,20.689]); u=np.array([0,-0.8707,0.4919]); u/=np.linalg.norm(u)
S_end=ref[-1]; tS=np.array([1.0,0,0])
D=12.0; gap_req=0.3; r_min=10.0
ref_s=np.concatenate([[0],np.cumsum(np.linalg.norm(np.diff(ref,axis=0),axis=1))])
def info(y):
    Pm,tm,p1,p2=S.build(y,E,u,S_end,tS)
    return Pm,tm,p1,p2
def cost(y,soft=True,wdev=1.0,wfr=True):
    Pm,tm,p1,p2=S.build(y,E,u,S_end,tS)
    c=(100.0 if soft else 0.0)*(p1["resid"]+p2["resid"])
    if not(p1["ok"] and p2["ok"]): return 1e3+200*(p1["viol"]+p2["viol"])+c
    Pn=np.vstack([p1["P"],p2["P"]])
    d1_=tref.query(Pn)[0]; d2_=cKDTree(Pn).query(ref)[0]
    dev=d1_.mean()+d2_.mean()+0.5*max(d1_.max(),d2_.max())
    gap=tree.query(Pn)[0].min()-D/2-0.4
    rmin=min(p1["R"],p2["R"])
    i0=tref.query(Pm)[1]; fr=ref_s[i0]/ref_s[-1]
    return wdev*dev+c+1500*max(0,gap_req-gap)+40*max(0,r_min-rmin)+50*max(0,abs(fr-0.5)-0.15)
def resid2(y):
    _,_,p1,p2=S.build(y,E,u,S_end,tS); return p1["resid"],p2["resid"]
mid=ref[len(ref)//2]
best=None
t0=time.time()
for seed in range(6):
    rng=np.random.default_rng(seed)
    bounds=[(mid[0]-45,mid[0]+45),(mid[1]-45,mid[1]+45),(mid[2]-45,mid[2]+45),(0.05,math.pi-0.05),(-math.pi,math.pi)]
    res=differential_evolution(cost,bounds,seed=seed,popsize=60,maxiter=300,tol=1e-9,polish=False)
    r2=minimize(lambda y:cost(y,False),res.x,method="SLSQP",bounds=bounds,constraints=[{"type":"eq","fun":lambda y:resid2(y)[0]},{"type":"eq","fun":lambda y:resid2(y)[1]}],options=dict(maxiter=300,ftol=1e-10))
    y=r2.x if (max(resid2(r2.x))<1e-4 and cost(r2.x)<=cost(res.x)+1e-6) else res.x
    c=cost(y); print(f"seed {seed}: cost {c:.2f} y {np.round(y,3).tolist()} resid {max(resid2(y)):.1e} t {time.time()-t0:.0f}s",flush=True)
    if best is None or c<best[0]: best=(c,list(y))
print("BEST",best)
