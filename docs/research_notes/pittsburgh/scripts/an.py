import gzip, json, sys, collections, pickle
from multiprocessing import Pool
ACT=('fold','check','call','raise','bet')
def depth(bb):
    return 'd<=10' if bb<=10 else ('d10-20' if bb<=20 else 'd>20')
def hud(bb):
    return 'e<=10' if bb<=10 else ('e10-25' if bb<=25 else 'e>25')
def work(lines):
    C=collections.Counter()
    for line,yl in lines:
        t=json.loads(line); Y=json.loads(yl)['you'] if yl else None
        assert Y is None or (Y['table']==t['table'] and Y['iteration']==t['iteration'])
        seats=t['seats']; fil=t['fillers']; hands=t['hands']
        C[('_','tables')]+=1
        n=len(seats)
        # placement
        bust={}
        for k,h in enumerate(hands):
            sa=h['stacks_after']; sb=h['stacks_before']
            for i in range(n):
                if i not in bust and sb[i]>0 and sa[i]==0: bust[i]=(k,sb[i])
        last=hands[-1]; fa=last['stacks_after']
        key=lambda i: (bust[i][0],bust[i][1]) if i in bust else (10**6,fa[i])
        order=sorted([i for i in range(n) if hands[0]['stacks_before'][i]>0], key=key, reverse=True)
        for pl,i in enumerate(order):
            if fil[i]: continue
            T=seats[i]
            C[(T,'tables')]+=1; C[(T,'place',pl+1)]+=1
            p=last['equity_after'][i]; C[(T,'pts')]+=p; C[(T,'pts2')]+=p*p
            if i in bust:
                C[(T,'busthand',min(bust[i][0]//20,12))]+=1
        C[('_','nhands',min(len(hands)//25,10))]+=1
        prevalive=n
        for k,h in enumerate(hands):
            sb=h['stacks_before']; sa=h['stacks_after']; bbv=h['blinds'][1]
            alive=[i for i in range(n) if sb[i]>0]; na=len(alive)
            stage='HU' if na==2 else ('3-4' if na<=4 else '5-8')
            ev=h['events']; btn=h['button']
            blinds=[e for e in ev if e['kind']=='blind']
            for e in ev: C[('_','kind',e['kind'])]+=1
            if na==2:
                bbseat=[i for i in alive if i!=btn]
                bbseat=bbseat[0] if len(bbseat)==1 else None
                sbseat=btn if bbseat is not None else None
            else:
                full=[e['seat'] for e in blinds if e['amount']==bbv]
                bbseat=full[-1] if full else (max(blinds,key=lambda e:e['amount'])['seat'] if blinds else None)
                o=[e['seat'] for e in blinds if e['seat']!=bbseat]
                sbseat=o[0] if o else None
            # preflop walk
            inv=collections.Counter(); street=collections.Counter()
            for e in blinds: inv[e['seat']]+=e['amount']; street[e['seat']]+=e['amount']
            pre=[]; sawflop=False; post_agg=set(); post_call=set()
            cur='pre'
            for e in ev:
                kd=e['kind']
                if kd=='board':
                    if cur=='pre': cur='post'; street=collections.Counter()
                    continue
                if kd not in ACT: continue
                s=e['seat']
                if kd=='call': inv[s]+=e['amount']; street[s]+=e['amount']
                elif kd in('raise','bet'):
                    add=e['amount']-street[s]; inv[s]+=add; street[s]=e['amount']
                if cur=='pre': pre.append((s,kd,inv[s]>=sb[s]))
                else:
                    if kd in('raise','bet'): post_agg.add(s)
                    if kd=='call': post_call.add(s)
            sawflop = cur=='post'
            raises=0; calls=0; seen=set(); firstact={}; raiser=None
            pfa={}  # seat -> list of (kd, allin, raises_before)
            for (s,kd,ai) in pre:
                pfa.setdefault(s,[]).append((kd,ai,raises,calls))
                if kd=='raise': raises+=1; raiser=s
                elif kd=='call': calls+=1
            if na==2 and k>0 and prevalive>2 or (na==2 and k==0):
                pass
            for i in alive:
                if fil[i]: continue
                T=seats[i]
                pos='BTN' if (i==btn and na>2) else ('SB' if i==sbseat else ('BB' if i==bbseat else ('BTN' if i==btn else 'oth')))
                de=h['equity_after'][i]-h['equity_before'][i]; dc=sa[i]-sb[i]
                C[(T,'h',stage)]+=1; C[(T,'eq',stage)]+=de; C[(T,'chips_bb',stage)]+=dc/bbv
                C[(T,'hp',stage,pos)]+=1; C[(T,'eqp',stage,pos)]+=de
                a=pfa.get(i,[])
                d=depth(sb[i]/bbv)
                # outcome class
                vol=any(x[0] in('call','raise') for x in a)
                allin_pre = (not sawflop or True) and any(x[1] for x in a)
                if not vol: cls='novol'
                elif allin_pre: cls='allin_pre_shove' if [x for x in a if x[1]][0][0]=='raise' else 'allin_pre_call'
                elif not sawflop or (a and a[-1][0]=='fold'): cls='pre_only'
                else:
                    cls='post_agg' if i in post_agg else ('post_call' if i in post_call else 'post_passive')
                C[(T,'cls_h',stage,cls)]+=1; C[(T,'cls_eq',stage,cls)]+=de
                mine=None
                if Y is not None and i==Y['seat'] and k<len(Y['cards']) and Y['cards'][k]:
                    cc=Y['cards'][k]; r=sorted(('23456789TJQKA'.index(c[0]) for c in cc),reverse=True)
                    mine='pair' if len(set(r))<len(r) else ('A' if r[0]==12 else ('K' if r[0]==11 else ('Q' if r[0]==10 else 'J-')))
                    su=max(collections.Counter(c[1] for c in cc).values())
                if na==2:
                    opp=[j for j in alive if j!=i][0]; eff=hud(min(sb[i],sb[opp])/bbv)
                    if i==btn:
                        if a:
                            kd,ai,_,_=a[0]
                            lab='shove' if (kd=='raise' and ai) else ('limp' if kd=='call' else kd)
                            C[(T,'hu_btn',eff,lab)]+=1
                            C[(T,'hu_btn_eq',eff,lab)]+=de
                            if mine: C[('ME','hu_btn_cards',eff,mine,lab)]+=1
                    else:
                        ob=pfa.get(opp,[])
                        if ob and a:
                            okd,oai=ob[0][0],ob[0][1]
                            kd,ai,_,_=a[0]
                            lab='shove' if (kd=='raise' and ai) else kd
                            if mine: C[('ME','hu_bb_cards',okd+('_ai' if oai else ''),eff,mine,lab)]+=1
                            if okd=='raise':
                                C[(T,'hu_bb_vs_'+('shove' if oai else 'raise'),eff,lab)]+=1
                            elif okd=='call': C[(T,'hu_bb_vs_limp',eff,lab)]+=1
                else:
                    if a:
                        kd,ai,rb,cb=a[0]
                        if rb==0 and not (i==bbseat):
                            lab='shove' if (kd=='raise' and ai) else ('limp' if kd=='call' else kd)
                            C[(T,'open',stage,d,lab)]+=1
                            if cb==0: C[(T,'rfi',stage,d,pos,lab)]+=1
                        elif rb>=1:
                            lab='shove' if (kd=='raise' and ai) else kd
                            C[(T,'vsraise',stage,d,lab)]+=1
                            if rb==1: C[(T,'vs1raise',stage,d,lab)]+=1
                            if mine: C[('ME','vsraise_cards',d,mine,lab)]+=1
                    # cbet
                    if sawflop and raiser==i:
                        pass
                # bust mode
                if sa[i]==0:
                    C[(T,'bustmode',stage,cls)]+=1
                    C[(T,'bust_bb',stage,depth(sb[i]/bbv))]+=1
            # HU entry
            if na==2 and (k==0 or prevalive>2):
                tot=sum(sb)
                for i in alive:
                    if fil[i]: continue
                    T=seats[i]; C[(T,'hu_reach')]+=1; C[(T,'hu_share')]+=sb[i]/tot
                    C[(T,'hu_startbb')]+=min(sb[j] for j in alive)/bbv
                    j=[x for x in alive if x!=i][0]
                    won = (key(i)>key(j))
                    C[(T,'hu_won')]+=won
                    b='lead' if sb[i]*2>=tot else 'behind'
                    C[(T,'hu_n',b)]+=1; C[(T,'hu_w',b)]+=won
            prevalive=na
    return C
if __name__=='__main__':
    path,out=sys.argv[1],sys.argv[2]
    f=gzip.open(path,'rt'); hdr=json.loads(f.readline())
    def batches():
        b=[]; prev=None
        for line in f:
            if line.startswith('{"you"'):
                b.append((prev,line)); prev=None
            else:
                if prev is not None: b.append((prev,None))
                prev=line
            if len(b)>=40 and prev is None: yield b; b=[]
        if prev is not None: b.append((prev,None))
        if b: yield b
    C=collections.Counter()
    with Pool(8) as p:
        for c in p.imap_unordered(work,batches()): C.update(c)
    pickle.dump((hdr,C),open(out,'wb'))
    print('done',C[('_','tables')])
