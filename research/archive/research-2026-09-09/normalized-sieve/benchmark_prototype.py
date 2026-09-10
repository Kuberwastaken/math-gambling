from pathlib import Path
import json,random,sqlite3,subprocess,time,statistics
HERE=Path(__file__).resolve().parent
LAB=HERE.parents[1]
OUT=LAB/'research-2026-09-09'
def main():
    db=sqlite3.connect('file:'+str(LAB/'phase3/runs/campaign/campaign.sqlite3')+'?mode=ro',uri=True)
    contexts=dict(db.execute('select key,spec from contexts'))
    samples=[]
    for key,spec in contexts.items():
        row=db.execute('select id,start,count,policy,stats from jobs where context=? and status="complete" order by id desc limit 1',(key,)).fetchone()
        if row:
            jid,start,count,policy,stats=row
            samples.append((key,json.loads(spec),jid,start,max(32,count//10),policy))
    rng=random.Random(11420260909);rng.shuffle(samples)
    records=[]
    for key,spec,jid,start,count,policy in samples:
        args=['tile',*[str(spec[k]) for k in ('ell','radius','tlo','thi','dlo','dhi')],str(start),str(count),str(spec['high']),str(spec['low']),policy,'inversion','1142']
        versions=['old','new'];rng.shuffle(versions);pair={}
        for name in versions:
            binary=LAB/'phase3/bin/offset_worker' if name=='old' else HERE/'offset_worker'
            begin=time.monotonic();run=subprocess.run([str(binary),*args],text=True,capture_output=True,check=True,timeout=30)
            assert not run.stderr
            data=[json.loads(x) for x in run.stdout.splitlines()];stats=data[-1]
            assert stats['complete'] and stats['quotient_points']==stats['rejected_mod243']+stats['rejected_parity']+stats['exact_tests']+sum(x['rejected'] for x in stats['filters'])
            pair[name]=dict(elapsed=time.monotonic()-begin,cpu=stats['cpu_seconds'],exact=stats['exact_tests'],stats=stats,hits=[x for x in data if x['type']=='hit'])
        for k in ('candidates','curves','quotient_points','rejected_mod243','rejected_parity','hits','norm_evaluations'):
            assert pair['old']['stats'][k]==pair['new']['stats'][k],(key,k)
        assert pair['old']['hits']==pair['new']['hits']
        assert pair['new']['exact']<=pair['old']['exact']
        for p in pair.values():p.pop('stats');p.pop('hits')
        records.append(dict(context=key,source_job=jid,args=args,order=versions,**pair))
    groups={}
    for low,high in [(0,64),(64,256),(256,4096)]:
        group=[r for r in records if r['context'].endswith(f':{low}:{high}')]
        groups[f'{low}:{high}']={name:sum(r[name]['cpu'] for r in group) for name in ('old','new')}
        groups[f'{low}:{high}']['speedup']=groups[f'{low}:{high}']['old']/groups[f'{low}:{high}']['new']
    result=dict(status='passed',design='81 production contexts; one tenth latest completed tile; randomized paired order; one extra worker while production runs; exploratory timing subject to contention',pairs=len(records),groups=groups,total_cpu={name:sum(r[name]['cpu'] for r in records) for name in ('old','new')},total_exact={name:sum(r[name]['exact'] for r in records) for name in ('old','new')},records=records)
    (OUT/'normalized-sieve-benchmark.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='records'},indent=2))
if __name__=='__main__':main()
