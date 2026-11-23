"""補助管の分割(main_aux_split.py)の探索を、手元で何度も回すための道具。障害物の頂点群と基準の芯線(`main_aux_split.py --search --dump` が
/tmp/claude-1000/ に保存)を読んで、差分進化で y = (P_m、補助管 1 の円弧の半径、補助管 2 の円弧の半径)を探す。結果は main_aux_split.PRESET に書き写す。
引数 1: 隙間の下限(既定 0.3)。1 つの種で 1〜2 分。

    uv run python cad/main_aux_tube/tools/split_search.py 0.3
"""
import sys, math, time, numpy as np
sys.path[:0]=["/home/yoshinobu/horn/horn_design/cad/main_aux_tube/ocp","/home/yoshinobu/horn/horn_design/cad/bb34/ocp","/home/yoshinobu/horn/horn_design/cad/branch2/ocp","/home/yoshinobu/horn/horn_design/cad/bellscrew/ocp","/home/yoshinobu/horn/horn_design/cad/valves/ocp","/home/yoshinobu/horn/horn_design/cad/bows/ocp","/home/yoshinobu/horn/horn_design/cad/bell03/ocp","/home/yoshinobu/horn/horn_design/cad/bell03/tools"]
import main_aux_split as S
from scipy.spatial import cKDTree
from scipy.optimize import differential_evolution
obs=np.load("/tmp/claude-1000/split_obs.npy"); ref=np.load("/tmp/claude-1000/split_ref.npy")
tree=cKDTree(obs); tref=cKDTree(ref)
E=np.array([59.0,-17.53,20.689]); u=np.array([0,-0.8707,0.4919]); u/=np.linalg.norm(u)
S_end=ref[-1]; tS=np.array([1.0,0,0])
gap_req=float(sys.argv[1]) if len(sys.argv)>1 else 0.3; r_min=10.0
ref_s=np.concatenate([[0],np.cumsum(np.linalg.norm(np.diff(ref,axis=0),axis=1))])
def tm_of(Pm):
    n1=np.cross(u,Pm-E); n2=np.cross(tS,S_end-Pm)
    t=np.cross(n1,n2); nt=np.linalg.norm(t)
    if nt<1e-9: return None
    t/=nt
    if t@(S_end-E)<0: t=-t
    return t
def paths(y):
    Pm=y[:3]; r1,r2=y[3],y[4]
    tm=tm_of(Pm)
    if tm is None: return None
    p1=S.csc_path(E,u,Pm,tm,r1,4.0,4.0)
    p2=S.csc_path(Pm,tm,S_end,tS,r2,4.0,5.0)
    return tm,p1,p2
def cost(y):
    r=paths(y)
    if r is None: return 1e4
    tm,p1,p2=r
    if not(p1["ok"] and p2["ok"]): return 1e3
    Pm=y[:3]
    Pn=np.vstack([p1["P"],p2["P"]])
    d1_=tref.query(Pn)[0]; d2_=cKDTree(Pn).query(ref)[0]
    dev=d1_.mean()+d2_.mean()+0.5*max(d1_.max(),d2_.max())
    gap=tree.query(Pn)[0].min()-6.4
    la,lb=p1["length"],p2["length"]; fl=la/(la+lb)
    return dev+1500*max(0,gap_req-gap)+60*max(0,abs(fl-0.5)-0.15)+0.05*(la+lb)
mid=ref[len(ref)//2]
t0=time.time(); best=None
for seed in range(1):
    rng=np.random.default_rng(seed)
    bounds=[(mid[i]-40,mid[i]+40) for i in range(3)]+[(10,60),(10,60)]
    init=np.array([np.concatenate([mid+rng.normal(0,12,3),[rng.uniform(10,40),rng.uniform(10,40)]]) for _ in range(60)])
    res=differential_evolution(cost,bounds,seed=seed,init=init,maxiter=100,tol=1e-10,polish=False)
    tm,p1,p2=paths(res.x)
    Pm_=res.x[:3]
    print(f"seed {seed}: cost {res.fun:.3f} y {np.round(res.x,3).tolist()} t {time.time()-t0:.0f}s",flush=True)
    if best is None or res.fun<best[0]: best=(res.fun,res.x)
c,y=best; Pm=y[:3]; tm,p1,p2=paths(y)
Pn=np.vstack([p1["P"],p2["P"]]); d1_=tref.query(Pn)[0]; d2_=cKDTree(Pn).query(ref)[0]
print("BEST y",np.round(y,4).tolist(),"tm",np.round(tm,4).tolist())
for nm,p in (("aux1",p1),("aux2",p2)): print(nm,p["kind"],"r",round(p["R"],2),"arcs",round(p["al"],1),round(p["be"],1),"L",round(p["L"],2),"length",round(p["length"],2),"resid",round(p["resid"],6))
print("gap",round(tree.query(Pn)[0].min()-6.4,3),"dev max",round(max(d1_.max(),d2_.max()),2),"mean",round(d1_.mean(),2),"total",round(p1["length"]+p2["length"],2))
