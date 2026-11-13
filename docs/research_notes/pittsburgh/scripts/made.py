import gzip, json, sys, collections, pickle, itertools
from multiprocessing import Pool
RK='23456789TJQKA'
def ev5(cs):
    r=sorted((RK.index(c[0]) for c in cs),reverse=True); cnt=collections.Counter(r)
    g=sorted(cnt.items(),key=lambda x:(-x[1],-x[0])); shape=[x[1] for x in g]
    fl=len({c[1] for c in cs})==1
    u=sorted(set(r),reverse=True); st=len(u)==5 and (u[0]-u[4]==4 or u==[12,3,2,1,0])
    if st and fl: cat=8
    elif shape[0]==4: cat=7
    elif shape[:2]==[3,2]: cat=6
    elif fl: cat=5
    elif st: cat=4
    elif shape[0]==3: cat=3
    elif shape[:2]==[2,2]: cat=2
    elif shape[0]==2: cat=1
    else: cat=0
    return (cat,[x[0] for x in g])
def board_cat(b):
    cnt=sorted(collections.Counter(RK.index(c[0]) for c in b).values(),reverse=True)
    if cnt[0]==4: return 7
    if cnt[0]==3: return 6 if len(cnt)>1 and cnt[1]>=2 else 3
    if cnt[0]==2: return 2 if len(cnt)>1 and cnt[1]==2 else 1
    return 0
def strength(hole,b):
    best=None
    for h2 in itertools.combinations(hole,2):
        for b3 in itertools.combinations(b,3):
            v=ev5(h2+b3)
            if best is None or v>best: best=v
    cat=best[0]; bc=board_cat(b); br=sorted((RK.index(c[0]) for c in b),reverse=True); hr=[RK.index(c[0]) for c in hole]
    if cat>=2 and cat>bc: return 4 if cat>=3 else 3   # 4 = trips+, 3 = two pair
    if cat==1 or (cat==2 and bc==1) or (cat>bc):
        pr=best[1][0] if cat==1 else max([x for x in set(hr) if x in br or hr.count(x)>=2],default=-1)
        if pr in hr or hr.count(pr)>=2:
            return 2 if pr>=br[0] else 1    # 2 top pair/overpair, 1 lower pair
    if len(b)<5:
        for h2 in itertools.combinations(hole,2):
            cs=list(h2)+list(b)
            if max(collections.Counter(c[1] for c in cs).values())>=4 and any(collections.Counter(c[1] for c in cs)[c[1]]>=4 for c in h2): return 0.5
    return 0
NAME={4:'trips+',3:'twopair',2:'toppair',1:'lowpair',0.5:'fdraw',0:'air'}
def work(lines):
    C=collections.Counter()
    for line,yl in lines:
        if not yl: continue
        t=json.loads(line); Y=json.loads(yl)['you']; me=Y['seat']; hands=t['hands']
        for k,h in enumerate(hands):
            if k>=len(Y['cards']) or len(Y['cards'][k])!=3: continue
            hole=tuple(Y['cards'][k]); sb=h['stacks_before']; bbv=h['blinds'][1]
            if sb[me]<=0: continue
            de=h['equity_after'][me]-h['equity_before'][me]; dbb=(h['stacks_after'][me]-sb[me])/bbv
            boards={1:[],2:[]}; st=0; street=collections.Counter(); mx=0; seen=set(); live=set(i for i,s in enumerate(sb) if s>0)
            pot=0; kept=None
            for e in h['events']:
                kd=e['kind']
                if kd=='blind': street[e['seat']]+=e['amount']; mx=max(mx,street[e['seat']]); pot+=e['amount']
                elif kd=='board':
                    if e['amount']==1: st+=1; street=collections.Counter(); mx=0
                    boards[e['amount']]+=e['cards']
                elif kd=='fold': live.discard(e['seat'])
                if kd in('fold','check','call','raise','bet') and st>=1 and e['seat']==me and (st,) not in seen:
                    if len(boards[1])<3 or len(boards[2])!=len(boards[1]): pass
                    else:
                        seen.add((st,))
                        s1=strength(hole,boards[1]); s2=strength(hole,boards[2])
                        hi,lo=max(s1,s2),min(s1,s2)
                        key=NAME[hi]+'/'+NAME[lo]
                        facing=mx>street[me]
                        act=kd if kd!='bet' else 'raise'
                        sit='facing_bet' if facing else 'no_bet'
                        nl='HUpot' if len(live)==2 else 'multi'
                        for kk in ((sit,st,key,act),(sit,st,'ALL',act),(sit+'_'+nl,st,key,act)):
                            C[kk+('n',)]+=1; C[kk+('eq',)]+=de; C[kk+('bb',)]+=dbb
                if kd=='call': street[e['seat']]+=e['amount']; pot+=e['amount']
                elif kd in('raise','bet'):
                    pot+=e['amount']-street[e['seat']]; street[e['seat']]=e['amount']; mx=max(mx,e['amount'])
    return C
if __name__=='__main__':
    out=sys.argv[1]; Ct=collections.Counter()
    for path in sys.argv[2:]:
        f=gzip.open(path,'rt'); f.readline(); rows=[]; prev=None
        for line in f:
            if line.startswith('{"you"'): rows.append((prev,line)); prev=None
            else: prev=line
        with Pool(8) as p:
            for c in p.imap_unordered(work,[rows[i:i+40] for i in range(0,len(rows),40)]): Ct.update(c)
        print('done',len(rows),flush=True)
    pickle.dump(Ct,open(out,'wb'))
    ST={1:'flop',2:'turn',3:'river'}
    for sit in('facing_bet','no_bet'):
        for st in(1,2,3):
            print(f'\n== {sit} {ST[st]}: class(best board/other board): action share n eq/hand')
            keys=sorted({k[2] for k in Ct if k[0]==sit and k[1]==st},key=lambda c:-sum(Ct[(sit,st,c,a,'n')] for a in('fold','check','call','raise')))
            for c in keys:
                tot=sum(Ct[(sit,st,c,a,'n')] for a in('fold','check','call','raise'))
                if tot<150: continue
                print(f'  {c:17s} n={tot:6d} | '+' | '.join(f"{a} {Ct[(sit,st,c,a,'n')]/tot:.0%} eq {Ct[(sit,st,c,a,'eq')]/Ct[(sit,st,c,a,'n')]:+.2f} bb {Ct[(sit,st,c,a,'bb')]/Ct[(sit,st,c,a,'n')]:+.1f}" for a in('fold','check','call','raise') if Ct[(sit,st,c,a,'n')]>=25))
