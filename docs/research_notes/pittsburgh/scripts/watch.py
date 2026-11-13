import subprocess, json, sys, time
known=set(sys.argv[1:])
while True:
    try:
        t=subprocess.run(['python3.12','skills/sequoia-launch/scripts/portal.py'],capture_output=True,text=True,timeout=60).stdout
        j=t.find('== rounds'); obj,_=json.JSONDecoder().raw_decode(t[t.find('{',j):])
        new=[x for x in obj['items'] if x['id'] not in known]
        done=[x for x in new if x.get('completed_at')]
        if done:
            for x in done: print('FINISHED',x['id'],x['kind'],'weight',x['weight'],'iterations',x['iterations'],x['completed_at'])
            break
    except Exception as e:
        print('poll error',type(e).__name__,flush=True)
    time.sleep(45)
