import pickle,sys,collections
C=pickle.load(open(sys.argv[1],'rb'))
def row(key):
    n=C[key+('n',)]
    return n,(C[key+('eq',)]/n if n else 0),(C[key+('bb',)]/n if n else 0)
print('== chip share (x average stack) at stage entry, and reach rate per table')
T={'US':25003,'TOP5':None}
for g in('US','TOP5','FIELD'):
    print(g,' '.join(f"<= {m} left: n={C[(g,'reach',m,'n')]} share {C[(g,'reach',m,'share')]/max(1,C[(g,'reach',m,'n')]):.2f}" for m in(4,3,2)))
print('\n== steals: first-in raise; P(all fold), eq and bb per attempt')
for st in('5-8','3-4'):
  for pos in('EP','CO','BTN','SB'):
    for d in('>20','10-20','<=10'):
      for act in('raise','shove'):
        r=[]
        for g in('US','TOP5','FIELD'):
            n=C[(g,'steal',pos,st,d,act,'n')]
            if n<200: r.append(f'{g} n={n}'); continue
            r.append(f"{g} n={n} allfold {C[(g,'steal',pos,st,d,act,'allfold')]/n:.0%} eq {C[(g,'steal',pos,st,d,act,'eq')]/n:+.3f} bb {C[(g,'steal',pos,st,d,act,'bb')]/n:+.2f}")
        if any('allfold' in x for x in r): print(st,pos,d,act,' | '.join(r))
print('\n== open size (bb) distribution >20bb 5-8')
for g in('US','TOP5','FIELD'):
    d=collections.Counter({k[4]:v for k,v in C.items() if k[0]==g and k[1]=='size' and k[2]=='5-8' and k[3]=='>20'})
    tot=sum(d.values()); print(g,' '.join(f"{s}:{v/tot:.0%}" for s,v in sorted(d.items()) if v/tot>=0.03))
print('\n== group action results by situation: action share, eq/hand, bb/hand')
sits=sorted({k[2:-2] for k in C if k[0] in('US','TOP5','FIELD') and k[1]=='sit'})
for s in sits:
    for g in('US','TOP5','FIELD'):
        acts={k[-2] for k in C if k[0]==g and k[1]=='sit' and k[2:-2]==s}
        tot=sum(C[(g,'sit')+s+(a,'n')] for a in acts)
        if tot<300: continue
        te=sum(C[(g,'sit')+s+(a,'eq')] for a in acts)/tot
        print(' '.join(map(str,s)),g,f'ALL eq {te:+.3f} n={tot} |',' '.join(f"{a} {C[(g,'sit')+s+(a,'n')]/tot:.0%} eq {row((g,'sit')+s+(a,))[1]:+.3f}" for a in sorted(acts,key=lambda a:-C[(g,'sit')+s+(a,'n')]) if C[(g,'sit')+s+(a,'n')]/tot>=0.02))
print('\n== OUR hands by class: situation | class: action n eq/hand bb/hand')
ms=sorted({k[2:-3] for k in C if k[0]=='ME'})
for s in ms:
    tot=sum(v for k,v in C.items() if k[0]=='ME' and k[2:-3]==s and k[-1]=='n')
    if tot<1500: continue
    print(' '.join(map(str,s)),f'(n={tot})')
    for c in('pair_T+','pair_lo','A_T+','A_lo','K_T+','K_lo','Q_T+','Q_lo','J-hi'):
        acts={k[-2] for k in C if k[0]=='ME' and k[2:-3]==s and k[-3]==c}
        ct=sum(C[('ME','sit')+s+(c,a,'n')] for a in acts)
        if not ct: continue
        print(f'   {c:8s}',' | '.join(f"{a} {C[('ME','sit')+s+(c,a,'n')]/ct:.0%} n={C[('ME','sit')+s+(c,a,'n')]} eq {row(('ME','sit')+s+(c,a))[1]:+.3f} bb {row(('ME','sit')+s+(c,a))[2]:+.2f}" for a in sorted(acts,key=lambda a:-C[('ME','sit')+s+(c,a,'n')]) if C[('ME','sit')+s+(c,a,'n')]>=30))
