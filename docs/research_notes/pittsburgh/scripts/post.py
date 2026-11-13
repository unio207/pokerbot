import gzip, json, sys, collections, math
from multiprocessing import Pool
ACT=('fold','check','call','raise','bet')
def work(lines):
    C=collections.Counter()
    for line in lines:
        t=json.loads(line); seats=t['seats']; fil=t['fillers']; hands=t['hands']; n=len(seats)
        last=hands[-1]
        for i in range(n):
            if fil[i] or hands[0]['stacks_before'][i]<=0: continue
            T=seats[i]; C[(T,'tables')]+=1; p=last['equity_after'][i]; C[(T,'pts')]+=p
        for h in hands:
            sb=h['stacks_before']; sa=h['stacks_after']; bbv=h['blinds'][1]
            alive=[i for i in range(n) if sb[i]>0]; na=len(alive)
            inv=collections.Counter(); street=collections.Counter(); st=0; nb=0
            allin={}; foldst={}; shown=set(); agg=set(); faced=set(); raiser=None
            flopbet=False; cb_done=False; pre_r=0; pre_c=0; first={}
            bbseat=None
            for e in h['events']:
                kd=e['kind']; s=e.get('seat')
                if kd=='blind':
                    inv[s]+=e['amount']; street[s]+=e['amount']
                    if e['amount']==bbv or bbseat is None: bbseat=s if e['amount']>=bbv or bbseat is None else bbseat
                    if inv[s]>=sb[s] and s not in allin: allin[s]=(0,'blind')
                    continue
                if kd=='board':
                    if e['amount']==1:
                        nb+=1; st=nb; street=collections.Counter(); faced=set()
                    continue
                if kd=='show': shown.add(s); continue
                if kd not in ACT: continue
                mx=max(street.values()) if street else 0
                facing = mx>street[s]
                T=seats[s]; ok=not fil[s]
                if st==0:
                    if s not in first:
                        first[s]=1
                        if ok and na>2 and pre_r==0 and pre_c==0 and s!=bbseat and sb[s]/bbv<=5:
                            C[(T,'fi5', 'shove' if kd=='raise' else ('limp' if kd=='call' else kd))]+=1
                    if kd=='raise': pre_r+=1; raiser=s
                    elif kd=='call': pre_c+=1
                else:
                    if facing and s not in faced:
                        faced.add(s)
                        if ok: C[(T,'fb',st,kd)]+=1
                    if st==1 and s==raiser and not cb_done:
                        cb_done=True
                        if not flopbet and ok: C[(T,'cbet',kd in('raise','bet'))]+=1
                    if kd in('raise','bet'):
                        agg.add(s)
                        if st==1: flopbet=True
                if kd=='call': inv[s]+=e['amount']; street[s]+=e['amount']
                elif kd in('raise','bet'): inv[s]+=e['amount']-street[s]; street[s]=e['amount']
                elif kd=='fold': foldst[s]=st
                if inv[s]>=sb[s] and s not in allin: allin[s]=(st,kd)
            for i in alive:
                if fil[i]: continue
                T=seats[i]; de=h['equity_after'][i]-h['equity_before'][i]
                C[(T,'h')]+=1
                if sb[i]/bbv<=5: C[(T,'h5')]+=1
                if i in foldst: cls='fold%d'%foldst[i]
                elif i in shown: cls='sd_agg' if i in agg else 'sd_pass'
                else: cls='other'
                C[(T,'cn',cls)]+=1; C[(T,'ce',cls)]+=de
                if sa[i]==0:
                    a=allin.get(i)
                    if a is None: m='unclassified'
                    elif a[1]=='blind': m='blinded'
                    elif a[0]==0: m='pre_shover' if a[1]=='raise' else 'pre_caller'
                    else: m='postflop'
                    C[(T,'bust',m)]+=1
    return C
if __name__=='__main__':
    f=gzip.open(sys.argv[1],'rt'); hdr=json.loads(f.readline()); you=hdr['you']; name={e['entry_id']:e['team_name'] for e in hdr['entries']}
    def batches():
        b=[]
        for line in f:
            if line.startswith('{"you"'): continue
            b.append(line)
            if len(b)>=40: yield b; b=[]
        if b: yield b
    C=collections.Counter()
    with Pool(8) as p:
        for c in p.imap_unordered(work,batches()): C.update(c)
    teams=[t for t in name if C[(t,'tables')]>0]
    st=sorted(((C[(t,'pts')]/C[(t,'tables')],t) for t in teams),reverse=True)
    rank=[t for _,t in st].index(you)+1
    top=[t for _,t in st if t!=you][:5]
    print('rank',rank,'/',len(st),'us pts',round(C[(you,'pts')]/C[(you,'tables')],2),'tables',C[(you,'tables')])
    print('top5',[(name[t],round(m,2),C[(t,'tables')]) for m,t in st if t in top])
    G={'US':[you],'TOP5':top}
    g=lambda grp,*k: sum(C[(t,)+k] for t in G[grp])
    for grp in G:
        nt=g(grp,'tables'); print('==',grp,'tables',nt)
        for s,nm in((1,'flop'),(2,'turn'),(3,'river')):
            tot=sum(g(grp,'fb',s,k) for k in ACT); print(f"  fold-to-bet {nm}: {g(grp,'fb',s,'fold')/tot:.1%} call {g(grp,'fb',s,'call')/tot:.1%} raise {g(grp,'fb',s,'raise')/tot:.1%} (n={tot})")
        tot=g(grp,'cbet',True)+g(grp,'cbet',False); print(f"  cbet {g(grp,'cbet',True)/tot:.1%} (n={tot})")
        for cls in('fold0','fold1','fold2','fold3','sd_agg','sd_pass','other'):
            print(f"  {cls:8s} n={g(grp,'cn',cls):7d} share {g(grp,'cn',cls)/g(grp,'h'):.2%} eq/table {g(grp,'ce',cls)/nt:+.2f}")
        ms=('blinded','pre_shover','pre_caller','postflop','unclassified'); tot=sum(g(grp,'bust',m) for m in ms)
        print('  busts n=%d: '%tot+' '.join(f"{m} {g(grp,'bust',m)/tot:.1%}" for m in ms))
        print(f"  hands <=5bb share {g(grp,'h5')/g(grp,'h'):.2%} (n={g(grp,'h5')})")
        ks=('fold','limp','shove'); tot=sum(g(grp,'fi5',k) for k in ks+('check',)); print('  first-in <=5bb non-HU: '+' '.join(f"{k} {g(grp,'fi5',k)/max(1,tot):.1%}" for k in ks)+f" (n={tot})")
