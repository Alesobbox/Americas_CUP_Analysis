"""Hand-checkable SYNTHETIC examples; standard library only, no repository imports.
Run: python concept_lab.py. These illustrate concepts, not full producer behavior.
"""
import math, json

def angle(a,b,f):
    return (a+((b-a+180)%360-180)*f)%360
def crossing(p0,p1,a,b):
    cross=lambda u,v:u[0]*v[1]-u[1]*v[0]
    sub=lambda u,v:(u[0]-v[0],u[1]-v[1])
    r,s=sub(p1,p0),sub(b,a)
    d=cross(r,s)
    if abs(d)<1e-12:return None
    t=cross(sub(a,p0),s)/d
    u=cross(sub(a,p0),r)/d
    return (t,u) if 0<=t<=1 and 0<=u<=1 else None
def indexes(selected,peer):
    return sum(100*a/b for a,b in zip(selected,peer))/len(selected)
def expected_position(win_distribution,nonfinish,n):
    return sum((k+1)*p for k,p in enumerate(win_distribution))+n*nonfinish
def brier(p,winner):
    return sum((v-int(k==winner))**2 for k,v in enumerate(p))
def bounds(counts,unresolved,trials):
    assert sum(counts)+unresolved==trials
    return [(c/trials,(c+unresolved)/trials) for c in counts]
def main():
    examples={}
    examples['units']={'description':'synthetic 10 m/s to knots','value':10*3600/1852}
    examples['angular_interpolation']={'description':'synthetic shortest arc 350 to 10 degrees halfway','value':angle(350,10,.5)}
    assert abs(angle(350,10,.5))<1e-12
    c=crossing((-2,0),(2,0),(0,-5),(0,5))
    assert c==(.5,.5)
    examples['strict_crossing']={'description':'synthetic strict segments, no moving marks or repository endpoint extension','time_fraction':c[0],'gate_fraction':c[1]}
    idx=indexes([20,30],[10,30]); ratio=100*25/20
    assert idx==150 and ratio==125
    examples['performance']={'description':'synthetic equal mean of leg ratios','index':idx,'ratio_of_means':ratio}
    ep=expected_position([.2,.3,.1],.4,4)
    assert abs(ep-2.7)<1e-12
    examples['nonfinish']={'description':'synthetic 4 scheduled, finish masses .2,.3,.1,0; nonfinish .4 scored at 4','expected_position':ep}
    score=brier([.7,.2,.1],2)
    assert abs(score-1.34)<1e-12
    examples['brier']={'description':'synthetic summed multiclass Brier with third team winner','value':score}
    bd=bounds([40,25,15],20,100)
    assert abs(sum(x[0] for x in bd)-.8)<1e-12
    assert abs(sum(x[1] for x in bd)-1.4)<1e-12
    examples['unresolved_paths']={'description':'synthetic conservative coordinatewise bounds, not a probability vector','intervals':bd,'sum_lower':.8,'sum_upper':1.4}
    # Persistent latent strength makes repeated matches dependent. Analytic example.
    mean_p=.5*(.8+.2)
    both=.5*(.8**2+.2**2)
    assert abs(both-.34)<1e-12
    examples['persistent_strength']={'description':'synthetic fair mixture of p=.8 and p=.2 fixed for both races','marginal_p':mean_p,'two_wins':both,'incorrect_independent_product':mean_p**2}
    z=1.96*math.sqrt(.5*.5/5000)
    examples['monte_carlo']={'description':'synthetic worst-case binomial 95 percent half-width for 5000 independent trials','half_width':z}
    print(json.dumps({'evidence':'ALL SYNTHETIC: simplified pedagogical calculations, not exported forecasts','checks':'passed','examples':examples},indent=2))
if __name__=='__main__': main()
