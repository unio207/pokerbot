import gzip, json, sys, collections, pickle
from multiprocessing import Pool
ACT=('fold','check','call','raise','bet')
RK='23456789TJQKA'
def cls(cc):
    r=sorted((RK.index(c[0]) for c in cc),reverse=True)
    if len(set(r))<3:
        pr=[x for x in r if r.count(x)>=2][0]
        return 'pair_T+' if pr>=8 else 'pair_lo'
    h,k=r[0],r[1]
    n={12:'A',11:'K',10:'Q'}.get(h)
    if n is None: return 'J-hi'
    return n+('_T+' if k>=8 else '_lo')
def dep(x): return '<=10' if x<=10 else ('10-20' if x<=20 else '>20')
def work(a):
    lines,top,you=a
    C=collections.Counter()
    def add(key,de,dbb):
        C[key+('n',)]+=1; C[key+('eq',)]+=de; C[key+('bb',)]+=dbb
    for line,yl in lines:
        t=json.loads(line); Y=json.loads(yl)['you'] if yl else None
        seats=t['seats']; fil=t['fillers']; n=len(seats); hands=t['hands']
        grp=[None if fil[i] else ('US' if seats[i]==you else ('TOP5' if seats[i] in top else 'FIELD')) for i in range(n)]
        marks={4:False,3:False,2:False}
        for k,h in enumerate(hands):
            sb=h['stacks_before']; sa=h['stacks_after']; bbv=h['blinds'][1]
            alive=[i for i in range(n) if sb[i]>0]; na=len(alive); btn=h['button']; tot=sum(sb)
            for m in (4,3,2):
                if na<=m and not marks[m]:
                    marks[m]=True
                    for i in alive:
                        if grp[i]: C[(grp[i],'reach',m,'n')]+=1; C[(grp[i],'reach',m,'share')]+=sb[i]/tot*na
            ev=h['events']; blinds=[e for e in ev if e['kind']=='blind']
            if na==2:
                bbs=[i for i in alive if i!=btn]; bbseat=bbs[0] if len(bbs)==1 else None; sbseat=btn
            else:
                full=[e['seat'] for e in blinds if e['amount']==bbv]
                bbseat=full[-1] if full else (max(blinds,key=lambda e:e['amount'])['seat'] if blinds else None)
                o=[e['seat'] for e in blinds if e['seat']!=bbseat]; sbseat=o[0] if o else None
            order=sorted(alive,key=lambda i:(i-btn-1)%n)
            co=order[-2] if (na>=4 and order[-1]==btn) else None
            street=collections.Counter(); inv=collections.Counter()
            for e in blinds: street[e['seat']]+=e['amount']; inv[e['seat']]+=e['amount']
            pre=[]
            for e in ev:
                kd=e['kind']
                if kd=='board': break
                if kd not in ACT: continue
                s=e['seat']
                if kd=='call': inv[s]+=e['amount']; street[s]+=e['amount']
                elif kd in('raise','bet'):
                    add_=e['amount']-street[s]; inv[s]+=add_; street[s]=e['amount']
                pre.append((s,kd,inv[s]>=sb[s],e.get('amount',0)))
            raises=calls=0; first={}
            for idx,(s,kd,ai,amt) in enumerate(pre):
                if s not in first: first[s]=(idx,kd,ai,amt,raises,calls)
                if kd=='raise': raises+=1
                elif kd=='call': calls+=1
            for i in alive:
                g=grp[i]
                if not g or i not in first: continue
                idx,kd,ai,amt,rb,cb=first[i]
                de=h['equity_after'][i]-h['equity_before'][i]; dbb=(sa[i]-sb[i])/bbv
                d=dep(sb[i]/bbv)
                pos='BB' if i==bbseat else ('SB' if i==sbseat else ('BTN' if i==btn else ('CO' if i==co else 'EP')))
                act='shove' if (kd=='raise' and ai) else kd
                mine=cls(Y['cards'][k]) if (Y and g=='US' and i==Y['seat'] and k<len(Y['cards']) and len(Y['cards'][k])==3) else None
                if na==2:
                    opp=[j for j in alive if j!=i][0]; e_=dep(min(sb[i],sb[opp])/bbv)
                    if i==btn: sit=('HU_btn',e_)
                    else:
                        o=first.get(opp)
                        if not o: continue
                        sit=('HU_bb_vs_'+('shove' if (o[1]=='raise' and o[2]) else ('raise' if o[1]=='raise' else 'limp')),e_)
                else:
                    st='5-8' if na>=5 else '3-4'
                    if rb==0 and cb==0 and i!=bbseat:
                        sit=('RFI_'+pos,st,d)
                        if kd=='raise':
                            allfold=all(x[1]=='fold' for x in pre[idx+1:])
                            C[(g,'steal',pos,st,d,act,'n')]+=1; C[(g,'steal',pos,st,d,act,'allfold')]+=allfold
                            C[(g,'steal',pos,st,d,act,'eq')]+=de; C[(g,'steal',pos,st,d,act,'bb')]+=dbb
                            if not ai: C[(g,'size',st,d,round(amt/bbv*2)/2)]+=1
                    elif rb==1:
                        sit=(('BB' if i==bbseat else 'nonBB')+'_vs_1raise',st,d)
                    else: continue
                add((g,'sit')+sit+(act,),de,dbb)
                if mine: add(('ME','sit')+sit+(mine,act),de,dbb)
    return C
if __name__=='__main__':
    out=sys.argv[1]; files=sys.argv[2:]
    Ctot=collections.Counter()
    for path in files:
        # pass 0: top5 from the agg of rep? compute quickly from header-less scan is slow; take from file's own points via a light pass
        f=gzip.open(path,'rt'); hdr=json.loads(f.readline()); you=hdr['you']
        pts=collections.Counter(); nt=collections.Counter(); rows=[]; prev=None
        for line in f:
            if line.startswith('{"you"'): rows.append((prev,line)); prev=None
            else:
                if prev is not None: rows.append((prev,None))
                prev=line
        if prev is not None: rows.append((prev,None))
        import re
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
        print('done',path[-40:],len(rows),flush=True)
    pickle.dump(Ctot,open(out,'wb'))
