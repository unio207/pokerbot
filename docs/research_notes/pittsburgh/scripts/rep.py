import pickle,sys,collections,math
hdr,C=pickle.load(open(sys.argv[1],'rb')); you=hdr['you']; name={e['entry_id']:e['team_name'] for e in hdr['entries']}
teams=[t for t in name if C[(t,'tables')]>0]
st=[]
for t in teams:
    n=C[(t,'tables')]; m=C[(t,'pts')]/n; sd=math.sqrt(max(0,C[(t,'pts2')]/n-m*m)); st.append((m,sd/math.sqrt(n),n,t))
st.sort(reverse=True)
print('tables',C[('_','tables')],'teams seen',len(teams))
print({k[2]:v for k,v in C.items() if k[0]=='_' and k[1]=='kind'})
rank=[x[3] for x in st].index(you)+1
print(f'OUR RANK (among teams at our tables) {rank}/{len(st)}')
for i,(m,se,n,t) in enumerate(st):
    if i<12 or t==you or i>=len(st)-3:
        pl=[C[(t,'place',p)]/n for p in range(1,9)]
        print(f"{i+1:3d} {name[t][:22]:22s} n={n:5d} pts={m:6.2f}±{se:.2f} places "+' '.join(f'{x:.1%}' for x in pl))
top=[x[3] for x in st[:5] if x[3]!=you][:5]
G={'US':[you],'TOP5':top,'FIELD':[t for t in teams if t!=you]}
def g(grp,*k): return sum(C[(t,)+k] for t in G[grp])
def keys(prefix):
    return sorted({k[1:] for k in C if k[0] in teams and k[1]==prefix})
print('\n== equity points per table by stage (sum = pts - 12.5), and per 100 hands')
for grp in G:
    nt=g(grp,'tables')
    print(grp, 'pts/table', round(g(grp,'pts')/nt,2), 'hands/table',round(sum(g(grp,'h',s) for s in('5-8','3-4','HU'))/nt,1))
    for s in('5-8','3-4','HU'):
        h=g(grp,'h',s); print(f"   {s:4s} hands/tbl {h/nt:6.1f} eq/tbl {g(grp,'eq',s)/nt:+6.2f} eq/100h {100*g(grp,'eq',s)/h:+6.2f} bb/100 {100*g(grp,'chips_bb',s)/h:+7.1f}")
        for pos in('BTN','SB','BB','oth'):
            hp=g(grp,'hp',s,pos)
            if hp: print(f"        {pos:3s} n={hp:7d} eq/tbl {g(grp,'eqp',s,pos)/nt:+6.2f} eq/100h {100*g(grp,'eqp',s,pos)/hp:+6.2f}")
print('\n== outcome classes: eq/table (share of hands)')
for s in('5-8','3-4','HU'):
    for cls in('novol','pre_only','allin_pre_shove','allin_pre_call','post_agg','post_call','post_passive'):
        row=[]
        for grp in G:
            nt=g(grp,'tables'); h=g(grp,'h',s); n=g(grp,'cls_h',s,cls)
            row.append(f"{grp} {n/h:6.1%} {g(grp,'cls_eq',s,cls)/nt:+6.2f}/tbl {100*g(grp,'cls_eq',s,cls)/max(1,n):+7.1f}/100h")
        print(f"{s:4s} {cls:16s} "+' | '.join(row))
def dist(grp,prefix,*mid,labs):
    tot=sum(g(grp,prefix,*mid,l) for l in labs)
    return ' '.join(f"{l} {g(grp,prefix,*mid,l)/max(1,tot):5.1%}" for l in labs)+f" (n={tot})"
print('\n== HU')
for grp in G:
    r=g(grp,'hu_reach'); nt=g(grp,'tables')
    print(grp,f"reach {r/nt:.1%} won {g(grp,'hu_won')/r:.1%} avg share {g(grp,'hu_share')/r:.2f} effbb {g(grp,'hu_startbb')/r:.1f} | lead win {g(grp,'hu_w','lead')/max(1,g(grp,'hu_n','lead')):.1%} n={g(grp,'hu_n','lead')} behind win {g(grp,'hu_w','behind')/max(1,g(grp,'hu_n','behind')):.1%} n={g(grp,'hu_n','behind')}")
    for e in('e<=10','e10-25','e>25'):
        print('   btn',e,dist(grp,'hu_btn',e,labs=('fold','limp','raise','shove')))
        print('   bb vs raise',e,dist(grp,'hu_bb_vs_raise',e,labs=('fold','call','raise','shove')))
        print('   bb vs shove',e,dist(grp,'hu_bb_vs_shove',e,labs=('fold','call')))
        print('   bb vs limp ',e,dist(grp,'hu_bb_vs_limp',e,labs=('check','raise','shove')))
print('\n== non-HU preflop')
for s in('5-8','3-4'):
  for d in('d<=10','d10-20','d>20'):
    for grp in G:
        print(f"{s} {d:7s} {grp:5s} unopened: {dist(grp,'open',s,d,labs=('fold','limp','raise','shove'))}")
        print(f"{s} {d:7s} {grp:5s} vs raise: {dist(grp,'vsraise',s,d,labs=('fold','call','raise','shove'))}")
print('\n== RFI by position (us vs top5), raise+shove %')
for s in('5-8','3-4'):
  for d in('d<=10','d10-20','d>20'):
    for pos in('oth','BTN','SB'):
        row=[]
        for grp in('US','TOP5'):
            tot=sum(g(grp,'rfi',s,d,pos,l) for l in('fold','limp','raise','shove'))
            row.append(f"{grp} {(g(grp,'rfi',s,d,pos,'raise')+g(grp,'rfi',s,d,pos,'shove'))/max(1,tot):5.1%} limp {g(grp,'rfi',s,d,pos,'limp')/max(1,tot):5.1%} n={tot}")
        print(s,d,pos,' | '.join(row))
print('\n== bust')
for grp in G:
    nt=g(grp,'tables')
    print(grp,'bust by hand/20:',' '.join(f"{b*20}:{g(grp,'busthand',b)/nt:.1%}" for b in range(13)))
    tot=sum(v for k,v in C.items() if k[0] in G[grp] and k[1]=='bustmode')
    d=collections.Counter()
    for k,v in C.items():
        if k[0] in G[grp] and k[1]=='bustmode': d[k[2:]]+=v
    print('   mode:',' '.join(f"{a}/{b} {v/tot:.1%}" for (a,b),v in sorted(d.items(),key=lambda x:-x[1])[:12]))
print('\n== our cards')
for k in sorted(k for k in C if k[0]=='ME'): pass
def metab(prefix,dims):
    d=collections.defaultdict(collections.Counter)
    for k,v in C.items():
        if k[0]=='ME' and k[1]==prefix: d[k[2:-1]][k[-1]]+=v
    for kk in sorted(d):
        tot=sum(d[kk].values()); print('  ',prefix,kk,' '.join(f"{a} {v/tot:.0%}" for a,v in d[kk].most_common()),f"(n={tot})")
metab('hu_btn_cards',0); metab('hu_bb_cards',0); metab('vsraise_cards',0)
