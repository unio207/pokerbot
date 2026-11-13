import pickle,sys,math,collections
hdr,C=pickle.load(open(sys.argv[1],'rb')); you=hdr['you']; name={e['entry_id']:e['team_name'] for e in hdr['entries']}
teams=[t for t in name if C[(t,'tables')]>=300]
def s(t,*k): return C[(t,)+k]
ST=('5-8','3-4'); D=('d<=10','d10-20','d>20'); E=('e<=10','e10-25','e>25')
def stats(t):
    o={}
    op={a:sum(s(t,'open',st,d,a) for st in ST for d in D) for a in('fold','limp','raise','shove')}; tot=sum(op.values())
    o['first-in raise %']=100*(op['raise']+op['shove'])/tot; o['first-in limp %']=100*op['limp']/tot
    vr={a:sum(s(t,'vsraise',st,d,a) for st in ST for d in D) for a in('fold','call','raise','shove')}; tot=sum(vr.values())
    o['vs raise: call %']=100*vr['call']/tot; o['vs raise: re-raise %']=100*(vr['raise']+vr['shove'])/tot; o['vs raise: fold %']=100*vr['fold']/tot
    o['re-raise share of continues %']=100*(vr['raise']+vr['shove'])/max(1,vr['raise']+vr['shove']+vr['call'])
    hb={a:sum(s(t,'hu_btn',e,a) for e in E) for a in('fold','limp','raise','shove')}; tot=max(1,sum(hb.values()))
    o['HU button raise %']=100*(hb['raise']+hb['shove'])/tot
    hr={a:sum(s(t,'hu_bb_vs_raise',e,a) for e in E) for a in('fold','call','raise','shove')}; tot=max(1,sum(hr.values()))
    o['HU BB vs raise: re-raise %']=100*(hr['raise']+hr['shove'])/tot; o['HU BB vs raise: call %']=100*hr['call']/tot
    hs={a:sum(s(t,'hu_bb_vs_shove',e,a) for e in E) for a in('fold','call')}; o['HU BB call a shove %']=100*hs['call']/max(1,sum(hs.values()))
    h=sum(s(t,'h',st) for st in('5-8','3-4','HU'))
    pa=sum(s(t,'cls_h',st,'post_agg') for st in('5-8','3-4','HU')); pc=sum(s(t,'cls_h',st,'post_call') for st in('5-8','3-4','HU')); pp=sum(s(t,'cls_h',st,'post_passive') for st in('5-8','3-4','HU'))
    o['postflop: bet/raise share of flops seen %']=100*pa/max(1,pa+pc+pp); o['postflop: call-only share %']=100*pc/max(1,pa+pc+pp)
    o['hands with money in voluntarily %']=100*(1-sum(s(t,'cls_h',st,'novol') for st in('5-8','3-4','HU'))/h)
    o['preflop all-in as shover %']=100*sum(s(t,'cls_h',st,'allin_pre_shove') for st in('5-8','3-4','HU'))/h
    o['preflop all-in as caller %']=100*sum(s(t,'cls_h',st,'allin_pre_call') for st in('5-8','3-4','HU'))/h
    o['points']=s(t,'pts')/s(t,'tables')
    return o
S={t:stats(t) for t in teams}
rk=sorted(teams,key=lambda t:-S[t]['points']); n=len(rk); q=n//4
def mean(ts,k): return sum(S[t][k] for t in ts)/len(ts)
def corr(k):
    xs=[S[t][k] for t in teams]; ys=[S[t]['points'] for t in teams]; mx=sum(xs)/n; my=sum(ys)/n
    sx=math.sqrt(sum((x-mx)**2 for x in xs)); sy=math.sqrt(sum((y-my)**2 for y in ys))
    return sum((x-mx)*(y-my) for x,y in zip(xs,ys))/(sx*sy) if sx*sy else 0
print(f'teams {n}; our rank {rk.index(you)+1}')
print(f"{'metric':44s} {'corr':>6s} {'top10':>7s} {'topQ':>7s} {'midHalf':>7s} {'botQ':>7s} {'US':>7s}")
for k in sorted([k for k in S[you] if k!='points'],key=lambda k:-abs(corr(k)))+['points']:
    print(f"{k:44s} {corr(k):+6.2f} {mean(rk[:10],k):7.1f} {mean(rk[:q],k):7.1f} {mean(rk[q:n-q],k):7.1f} {mean(rk[n-q:],k):7.1f} {S[you][k]:7.1f}")
