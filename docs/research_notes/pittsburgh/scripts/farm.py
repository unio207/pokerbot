import gzip, json, sys, collections, pickle, math
from multiprocessing import Pool
ACT=('fold','check','call','raise','bet')
def work(a):
    lines,tier,you,top=a
    C=collections.Counter()
    for line in lines:
        t=json.loads(line); seats=t['seats']; fil=t['fillers']; n=len(seats); hands=t['hands']
        tr=['filler' if fil[i] else tier.get(seats[i],'mid') for i in range(n)]
        heroes=[(i,'US' if seats[i]==you else 'TOP5') for i in range(n) if not fil[i] and (seats[i]==you or seats[i] in top)]
        fin=hands[-1]['equity_after']
        for i,g in heroes:
            others=[tr[j] for j in range(n) if j!=i]
            nw=sum(1 for x in others if x in('weak','filler')); ns=sum(1 for x in others if x=='top')
            for key in (('byweak',min(nw,4)),('bytop',min(ns,4)),('byfill',min(sum(1 for x in others if x=='filler'),3))):
                C[(g,)+key+('n',)]+=1; C[(g,)+key+('pts',)]+=fin[i]; C[(g,)+key+('first',)]+=fin[i]>=49.9
        for k,h in enumerate(hands):
            sb=h['stacks_before']; sa=h['stacks_after']; bbv=h['blinds'][1]; btn=h['button']
            alive=[i for i in range(n) if sb[i]>0]; na=len(alive)
            d=[(sa[i]-sb[i])/bbv for i in range(n)]
            gain=sum(x for x in d if x>0)
            if gain>0:
                for i,g in heroes:
                    if d[i]>0:
                        for j in range(n):
                            if d[j]<0: C[(g,'flow',tr[j])]+=-d[j]*d[i]/gain
                    elif d[i]<0:
                        for j in range(n):
                            if d[j]>0: C[(g,'flow',tr[j])]+=d[i]*d[j]/gain
            # bust credit: who took a busting player's chips
            for j in alive:
                if sa[j]==0 and gain>0:
                    for i,g in heroes:
                        if d[i]>0: C[(g,'bustcredit',tr[j])]+=d[i]/gain
                    C[('ALL','busts',tr[j])]+=1
            # steals vs BB tier
            ev=h['events']; blinds=[e for e in ev if e['kind']=='blind']
            if na<3 or not blinds: continue
            full=[e['seat'] for e in blinds if e['amount']==bbv]
            bbseat=full[-1] if full else max(blinds,key=lambda e:e['amount'])['seat']
            pre=[]
            for e in ev:
                if e['kind']=='board': break
                if e['kind'] in ACT: pre.append((e['seat'],e['kind']))
            if not pre: continue
            # first voluntary action
            idx=next((x for x,(s,kd) in enumerate(pre) if kd in('raise','call')),None)
            if idx is None: continue
            s,kd=pre[idx]
            if kd=='raise' and s!=bbseat:
                g='US' if (not fil[s] and seats[s]==you) else ('TOP5' if (not fil[s] and seats[s] in top) else 'OTHER')
                allfold=all(x[1]=='fold' for x in pre[idx+1:])
                bbt=tr[bbseat]
                de=h['equity_after'][s]-h['equity_before'][s]
                C[(g,'steal',bbt,'n')]+=1; C[(g,'steal',bbt,'allfold')]+=allfold; C[(g,'steal',bbt,'eq')]+=de; C[(g,'steal',bbt,'bb')]+=d[s]
                # BB response
                r=next((x[1] for x in pre[idx+1:] if x[0]==bbseat),None)
                if r: C[('BBresp',bbt,r)]+=1
            # profile by tier: first action preflop per seat
            seen=set(); raised=False
            for (s2,kd2) in pre:
                if s2 in seen: continue
                seen.add(s2)
                C[('prof',tr[s2],'facing_raise' if raised else 'unopened',kd2)]+=1
                if kd2=='raise': raised=True
    return C
if __name__=='__main__':
    path=sys.argv[1]
    f=gzip.open(path,'rt'); hdr=json.loads(f.readline()); you=hdr['you']; name={e['entry_id']:e['team_name'] for e in hdr['entries']}
    rows=[l for l in f if not l.startswith('{"you"')]
    pts=collections.Counter(); nt=collections.Counter(); p2=collections.Counter()
    for tl in rows:
        i=tl.find('"seats"'); seats=json.loads(tl[tl.find('[',i):tl.find(']',i)+1])
        j=tl.find('"fillers"'); fil=json.loads(tl[tl.find('[',j):tl.find(']',j)+1])
        k=tl.rfind('"equity_after"'); ea=json.loads(tl[tl.find('[',k):tl.find(']',k)+1])
        for s,fl,p in zip(seats,fil,ea):
            if not fl: pts[s]+=p; nt[s]+=1; p2[s]+=p*p
    rank=sorted((s for s in nt if nt[s]>=50),key=lambda s:-pts[s]/nt[s]); N=len(rank)
    tier={}
    for r,s in enumerate(rank): tier[s]='top' if r<N*0.2 else ('weak' if r>=N*0.7 else 'mid')
    tier[you]='us'
    top=set([s for s in rank if s!=you][:5])
    m=pts[you]/nt[you]; se=math.sqrt(max(0,p2[you]/nt[you]-m*m)/nt[you])
    print(f"tables {len(rows)} teams {N} | US rank {rank.index(you)+1}/{N} pts {m:.2f}±{se:.2f} n={nt[you]}")
    print('top5:',[(name[s],round(pts[s]/nt[s],2)) for s in rank[:6]])
    print('tier cutoffs: top >=',round(pts[rank[int(N*0.2)-1]]/nt[rank[int(N*0.2)-1]],2),' weak <=',round(pts[rank[int(N*0.7)]]/nt[rank[int(N*0.7)]],2))
    print('weak-tier point spread:',[round(pts[s]/nt[s],1) for s in rank[int(N*0.7)::3]])
    C=collections.Counter()
    with Pool(8) as p:
        for c in p.imap_unordered(work,[(rows[i:i+40],tier,you,top) for i in range(0,len(rows),40)]): C.update(c)
    pickle.dump(C,open(sys.argv[2],'wb'))
    for g in('US','TOP5'):
        ntab=sum(C[(g,'byweak',w,'n')] for w in range(5))
        print(f'\n== {g} ({ntab} tables)')
        for lab,rng in(('byweak',range(5)),('bytop',range(5)),('byfill',range(4))):
            print(' ',lab,' | '.join(f"{w}: n={C[(g,lab,w,'n')]} pts {C[(g,lab,w,'pts')]/C[(g,lab,w,'n')]:.2f} 1st {C[(g,lab,w,'first')]/C[(g,lab,w,'n')]:.1%}" for w in rng if C[(g,lab,w,'n')]>=40))
        print('  net bb won per table from each tier:',' '.join(f"{t}: {C[(g,'flow',t)]/ntab:+.1f}" for t in('filler','weak','mid','top','us')))
        tb=sum(C[(g,'bustcredit',t)] for t in('filler','weak','mid','top','us'))
        print('  knockouts per table by victim tier:',' '.join(f"{t}: {C[(g,'bustcredit',t)]/ntab:.3f}" for t in('filler','weak','mid','top','us')),f'total {tb/ntab:.2f}')
    print('\n== first-in raise by tier of the big blind: P(all fold), eq, bb per attempt')
    for g in('US','TOP5','OTHER'):
        print(' ',g,' | '.join(f"BB={t}: n={C[(g,'steal',t,'n')]} allfold {C[(g,'steal',t,'allfold')]/max(1,C[(g,'steal',t,'n')]):.0%} eq {C[(g,'steal',t,'eq')]/max(1,C[(g,'steal',t,'n')]):+.3f} bb {C[(g,'steal',t,'bb')]/max(1,C[(g,'steal',t,'n')]):+.2f}" for t in('filler','weak','mid','top','us')))
    print('\n== BB response to a first-in raise, by BB tier')
    for t in('filler','weak','mid','top','us'):
        tot=sum(C[('BBresp',t,a)] for a in ACT); print(' ',t,' '.join(f"{a} {C[('BBresp',t,a)]/max(1,tot):.0%}" for a in('fold','call','raise')),f'n={tot}')
    print('\n== preflop profile by tier (first action)')
    for t in('filler','weak','mid','top','us'):
        for sit in('unopened','facing_raise'):
            tot=sum(C[('prof',t,sit,a)] for a in ACT); print(' ',t,sit,' '.join(f"{a} {C[('prof',t,sit,a)]/max(1,tot):.0%}" for a in('fold','check','call','raise')),f'n={tot}')
    busts=sum(C[('ALL','busts',t)] for t in('filler','weak','mid','top','us'))
    print('\nshare of all busts by tier:',' '.join(f"{t} {C[('ALL','busts',t)]/busts:.0%}" for t in('filler','weak','mid','top','us')))
