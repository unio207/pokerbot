import gzip, json, sys, collections, pickle
from multiprocessing import Pool
ACT=('fold','check','call','raise','bet')
def bk(fr,ai):
    if ai: return 'allin'
    return '<=33%' if fr<=.335 else ('34-50%' if fr<=.505 else ('51-75%' if fr<=.755 else ('76-100%' if fr<=1.005 else '>100%')))
def b3(m): return '<2.5x' if m<2.5 else ('2.5-3.5x' if m<3.5 else ('3.5-5x' if m<5 else '>5x'))
def bo(x): return '2.0' if x<=2.25 else ('2.5' if x<=2.75 else '3.0+')
def work(a):
    lines,top,you=a
    C=collections.Counter()
    for line,yl in lines:
        t=json.loads(line); seats=t['seats']; fil=t['fillers']; n=len(seats)
        grp=[None if fil[i] else ('US' if seats[i]==you else ('TOP5' if seats[i] in top else 'FIELD')) for i in range(n)]
        for h in t['hands']:
            sb=h['stacks_before']; sa=h['stacks_after']; bbv=h['blinds'][1]; btn=h['button']
            alive=[i for i in range(n) if sb[i]>0]; na=len(alive)
            if na<2: continue
            ev=h['events']; eqd=[h['equity_after'][i]-h['equity_before'][i] for i in range(n)]
            blinds=[e for e in ev if e['kind']=='blind']
            if na==2:
                bbs=[i for i in alive if i!=btn]; bbseat=bbs[0] if len(bbs)==1 else None; sbseat=btn
            else:
                full=[e['seat'] for e in blinds if e['amount']==bbv]
                bbseat=full[-1] if full else (max(blinds,key=lambda e:e['amount'])['seat'] if blinds else None)
                o=[e['seat'] for e in blinds if e['seat']!=bbseat]; sbseat=o[0] if o else None
            order=sorted(alive,key=lambda i:(i-btn-1)%n)
            co=order[-2] if (na>=4 and order[-1]==btn) else None
            def pos(i): return 'BB' if i==bbseat else ('SB' if i==sbseat else ('BTN' if i==btn else ('CO' if i==co else 'EP')))
            inv=collections.Counter(); street=collections.Counter(); pot=0
            for e in blinds: inv[e['seat']]+=e['amount']; street[e['seat']]+=e['amount']; pot+=e['amount']
            folded=set(); st=0; streetbet=False
            praises=0; pcalls=0; pfr=None; openamt=0
            pend=[]   # pending records needing 'allfold' resolution: (kind,key,seat,street,nonfolded_needed)
            cbet_done=False; three=None; opener=None; opener_resp_done=True
            facing={}  # seat-> (bucket, hu) for first response to opening bet this street
            curbet=None
            acts=[e for e in ev if e['kind'] in ACT or e['kind']=='board']
            # precompute per-street whether anyone called/raised after index
            for idx,e in enumerate(acts):
                kd=e['kind']
                if kd=='board':
                    if e.get('amount')==1:
                        st+=1; street=collections.Counter(); streetbet=False; facing={}; curbet=None
                    continue
                s=e['seat']; g=grp[s]
                inhand=[i for i in alive if i not in folded]
                if st==0:
                    d=sb[s]/bbv
                    if kd=='raise':
                        amt=e['amount']; add=amt-street[s]; ai=inv[s]+add>=sb[s]
                        later=[x for x in acts[idx+1:] ]
                        nxt=[]
                        for x in later:
                            if x['kind']=='board': break
                            nxt.append(x)
                        allfold=all(x['kind']=='fold' for x in nxt) and not any(x['kind']=='board' for x in later)
                        if praises==0:
                            if pcalls==0 and s!=bbseat and not ai and d>20 and na>2 and g:
                                k=(g,'open',pos(s),bo(amt/bbv))
                                C[k+('n',)]+=1; C[k+('af',)]+=allfold; C[k+('eq',)]+=eqd[s]
                            opener=s; openamt=amt
                        elif praises==1:
                            if not ai and d>20 and g and openamt>0:
                                b=b3(amt/openamt)
                                k=(g,'3bet',b); C[k+('n',)]+=1; C[k+('af',)]+=allfold; C[k+('eq',)]+=eqd[s]; C[k+('bb',)]+=(sa[s]-sb[s])/bbv
                                three=b; opener_resp_done=False
                            elif ai and g and d>20:
                                k=(g,'3bet','shove'); C[k+('n',)]+=1; C[k+('af',)]+=allfold; C[k+('eq',)]+=eqd[s]; C[k+('bb',)]+=(sa[s]-sb[s])/bbv
                        praises+=1; pfr=s
                        inv[s]+=add; street[s]=amt; pot+=add
                    elif kd=='call':
                        if praises==0: pcalls+=1
                        inv[s]+=e['amount']; street[s]+=e['amount']; pot+=e['amount']
                    elif kd=='fold': folded.add(s)
                    if three and not opener_resp_done and s==opener and praises==2 and kd in('fold','call') or (three and not opener_resp_done and s==opener and kd=='raise' and praises==3):
                        opener_resp_done=True
                        if g=='FIELD': C[('FIELD','vs3bet',three,kd)]+=1
                    continue
                # postflop
                sname=('flop','turn','river')[min(st,3)-1]
                hu='2' if len(inhand)==2 else '3+'
                if not streetbet and kd in('check','raise','bet'):
                    if g: C[(g,'opp',sname,hu,'n')]+=1
                    iscb = (st==1 and s==pfr and not cbet_done)
                    if iscb: cbet_done=True
                    if kd=='check':
                        if iscb and g: C[(g,'cb','check','n')]+=1; C[(g,'cb','check','eq')]+=eqd[s]
                    else:
                        amt=e['amount']; ai=inv[s]+amt>=sb[s]; fr=amt/pot if pot else 9; b=bk(fr,ai)
                        # resolve allfold: after this street no one else remains
                        rest=[]
                        for x in acts[idx+1:]:
                            if x['kind']=='board': break
                            rest.append(x)
                        others=[i for i in inhand if i!=s]
                        f2=set(x['seat'] for x in rest if x['kind']=='fold')
                        allfold=all(i in f2 for i in others)
                        if g:
                            k=(g,'bet',sname,hu,b)
                            C[(g,'opp',sname,hu,'bet')]+=1
                            C[k+('n',)]+=1; C[k+('af',)]+=allfold; C[k+('eq',)]+=eqd[s]; C[k+('bb',)]+=(sa[s]-sb[s])/bbv
                            if iscb:
                                C[(g,'cb','bet','n')]+=1; C[(g,'cb','bet','eq')]+=eqd[s]; C[(g,'cb','bet','af')]+=allfold; C[(g,'cb','size',b)]+=1
                        C[('ALL','betpop',sname,hu,b,'n')]+=1; C[('ALL','betpop',sname,hu,b,'af')]+=allfold; C[('ALL','betpop',sname,hu,b,'frsum')]+=min(fr,5)
                        streetbet=True; curbet=(b,hu,s); facing={}
                        inv[s]+=amt; street[s]=amt; pot+=amt
                    continue
                if streetbet:
                    if curbet and s!=curbet[2] and s not in facing:
                        facing[s]=1
                        if g=='FIELD': C[('FIELD','face',sname,curbet[1],curbet[0],kd)]+=1
                        if g=='US': C[('US','face',sname,curbet[1],curbet[0],kd)]+=1
                    if kd=='call': inv[s]+=e['amount']; street[s]+=e['amount']; pot+=e['amount']
                    elif kd in('raise','bet'):
                        add=e['amount']-street[s]; inv[s]+=add; street[s]=e['amount']; pot+=add
                    elif kd=='fold': folded.add(s)
                elif kd=='fold': folded.add(s)
    return C
if __name__=='__main__':
    out=sys.argv[1]; Ctot=collections.Counter()
    for path in sys.argv[2:]:
        f=gzip.open(path,'rt'); hdr=json.loads(f.readline()); you=hdr['you']
        pts=collections.Counter(); nt=collections.Counter(); rows=[]; prev=None
        for line in f:
            if line.startswith('{"you"'): rows.append((prev,line)); prev=None
            else:
                if prev is not None: rows.append((prev,None))
                prev=line
        if prev is not None: rows.append((prev,None))
        for tl,_ in rows:
            i=tl.find('"seats"'); seats=json.loads(tl[tl.find('[',i):tl.find(']',i)+1])
            j=tl.find('"fillers"'); fil=json.loads(tl[tl.find('[',j):tl.find(']',j)+1])
            k=tl.rfind('"equity_after"'); ea=json.loads(tl[tl.find('[',k):tl.find(']',k)+1])
            for s,fl,p in zip(seats,fil,ea):
                if not fl: pts[s]+=p; nt[s]+=1
        top=set(sorted((s for s in nt if s!=you and nt[s]>=100),key=lambda s:-pts[s]/nt[s])[:5])
        B=[(rows[i:i+40],top,you) for i in range(0,len(rows),40)]
        with Pool(8) as p:
            for c in p.imap_unordered(work,B): Ctot.update(c)
        print('done',len(rows),flush=True)
    pickle.dump(Ctot,open(out,'wb'))
    C=Ctot; BK=('<=33%','34-50%','51-75%','76-100%','>100%','allin')
    print('\n== 1. opening bets postflop: freq, then per size: share / P(allfold) / eq / bb (n)')
    for sn in('flop','turn','river'):
      for hu in('2','3+'):
        for g in('US','TOP5','FIELD'):
            o=C[(g,'opp',sn,hu,'n')]; nb=C[(g,'opp',sn,hu,'bet')]
            if not o: continue
            print(f"{sn} {hu}p {g}: bet {nb/o:.1%} of {o} | "+' ; '.join(f"{b} {C[(g,'bet',sn,hu,b,'n')]/max(1,nb):.0%} af {C[(g,'bet',sn,hu,b,'af')]/C[(g,'bet',sn,hu,b,'n')]:.0%} eq {C[(g,'bet',sn,hu,b,'eq')]/C[(g,'bet',sn,hu,b,'n')]:+.2f} (n={C[(g,'bet',sn,hu,b,'n')]})" for b in BK if C[(g,'bet',sn,hu,b,'n')]>=50))
    print('\n== 1b. population: P(all fold) by size vs break-even (avg size s -> s/(1+s))')
    for sn in('flop','turn','river'):
      for hu in('2','3+'):
        r=[]
        for b in BK:
            nn=C[('ALL','betpop',sn,hu,b,'n')]
            if nn<200: continue
            s=C[('ALL','betpop',sn,hu,b,'frsum')]/nn; af=C[('ALL','betpop',sn,hu,b,'af')]/nn; be=s/(1+s)
            r.append(f"{b} af {af:.0%} be {be:.0%} {'CLEARS' if af>be else 'no'} (n={nn})")
        print(sn,hu+'p',' ; '.join(r))
    print('\n== 1c. first response facing an opening bet: FIELD and US fold/call/raise')
    for sn in('flop','turn','river'):
      for hu in('2','3+'):
        for g in('FIELD','US'):
            r=[]
            for b in BK:
                tot=sum(C[(g,'face',sn,hu,b,k)] for k in('fold','call','raise'))
                if tot<200: continue
                r.append(f"{b} fold {C[(g,'face',sn,hu,b,'fold')]/tot:.0%} raise {C[(g,'face',sn,hu,b,'raise')]/tot:.0%} (n={tot})")
            print(sn,hu+'p',g,' ; '.join(r))
    print('\n== 2. flop c-bet')
    for g in('US','TOP5','FIELD'):
        nb=C[(g,'cb','bet','n')]; nc=C[(g,'cb','check','n')]
        print(g,f"cbet {nb/(nb+nc):.1%} of {nb+nc} | bet: allfold {C[(g,'cb','bet','af')]/nb:.0%} eq {C[(g,'cb','bet','eq')]/nb:+.3f} | check: eq {C[(g,'cb','check','eq')]/max(1,nc):+.3f} (n={nc}) | sizes "+' '.join(f"{b} {C[(g,'cb','size',b)]/nb:.0%}" for b in BK))
    print('\n== 3. 3-bets >20bb')
    for g in('US','TOP5','FIELD'):
        print(g,' ; '.join(f"{b} n={C[(g,'3bet',b,'n')]} af {C[(g,'3bet',b,'af')]/max(1,C[(g,'3bet',b,'n')]):.0%} eq {C[(g,'3bet',b,'eq')]/max(1,C[(g,'3bet',b,'n')]):+.3f} bb {C[(g,'3bet',b,'bb')]/max(1,C[(g,'3bet',b,'n')]):+.2f}" for b in('<2.5x','2.5-3.5x','3.5-5x','>5x','shove')))
    for b in('<2.5x','2.5-3.5x','3.5-5x','>5x'):
        tot=sum(C[('FIELD','vs3bet',b,k)] for k in('fold','call','raise'))
        print('FIELD opener vs 3bet',b,' '.join(f"{k} {C[('FIELD','vs3bet',b,k)]/max(1,tot):.0%}" for k in('fold','call','raise')),f'(n={tot})')
    print('\n== 4. open size >20bb non-HU')
    for p_ in('EP','CO','BTN','SB'):
        for g in('US','TOP5','FIELD'):
            print(p_,g,' ; '.join(f"{b}bb n={C[(g,'open',p_,b,'n')]} af {C[(g,'open',p_,b,'af')]/max(1,C[(g,'open',p_,b,'n')]):.0%} eq {C[(g,'open',p_,b,'eq')]/max(1,C[(g,'open',p_,b,'n')]):+.3f}" for b in('2.0','2.5','3.0+')))
