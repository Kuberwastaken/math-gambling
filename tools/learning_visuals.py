#!/usr/bin/env python3
"""Small public learning series and a README figure from frozen evaluations."""
import json
import math
from pathlib import Path
from html import escape
from ingest import atomic_json
ROOT=Path(__file__).resolve().parents[1]
METRICS={'cpu_ms':'Server CPU cost','quotient_points':'Quotient positions','curves':'Curve intervals','exact_tests':'Exact square tests'}

def reduction(scores,metric):
    base=scores.get('proof_baseline',scores['context_baseline'])[metric];value=scores['spatial'][metric]
    if base is None or value is None or base<=0:return None
    result=100*(base-value)/base
    if not math.isfinite(result):raise ValueError('nonfinite prediction metric')
    return result

def read_series(folder):
    series=[]
    for p in sorted(folder.glob('eval-*.json')):
        e=json.loads(p.read_text());point={'through':e['through'],'from':e['from'],'model_hash':e['model_hash'],'metrics':{},'unseen_tasks':e['results']['future_unseen_geometry']['tasks']}
        for key in METRICS:
            point['metrics'][key]={group:reduction(e['results'][group]['mean_absolute_log1p_error'],key) for group in ('future_all','future_unseen_geometry')}
        series.append(point)
    return series

def generate(data=ROOT/'data'):
    data=Path(data);latest=json.loads((data/'learning/latest.json').read_text())
    folder=(data/latest['history']).resolve()
    if not folder.is_relative_to((data/'learning').resolve()):raise ValueError('invalid history path')
    series=read_series(folder)
    report={k:latest[k] for k in ['mode','through','observed_tasks','model_count','completed_evaluations','next_boundary','source_hash']}
    baseline='proof-aware context baseline' if latest.get('schema')=='mg114-spatial-shadow-v2' else 'context baseline'
    report.update(schema='mg114-learning-visuals-v1',series=series[-512:],metrics=METRICS,baseline=baseline)
    report.update(model_version=latest['schema'],first_training_boundary=latest.get('first_training_boundary'),archives=[])
    # Publish each previous source version separately. Never splice incomparable
    # baselines into the current curve or make the initial page fetch all history.
    for old in sorted((data/'learning').glob('mg114-spatial-shadow-v*/*')):
        if not old.is_dir() or old.resolve()==folder:continue
        if old.parent.name not in ('mg114-spatial-shadow-v1','mg114-spatial-shadow-v2'):continue
        if len(old.name)!=16 or any(c not in '0123456789abcdef' for c in old.name):continue
        points=read_series(old)
        if not points:continue
        models=sorted(old.glob('model-*.json'))
        name=f'archive-{old.parent.name}-{old.name}.json'
        old_baseline='proof-aware context baseline' if old.parent.name.endswith('v2') else 'context baseline'
        archived=dict(schema=report['schema'],mode='shadow',model_version=old.parent.name,source_hash=old.name,
                      model_count=len(models),completed_evaluations=len(points),through=int(models[-1].stem.split('-')[1]) if models else points[-1]['through'],
                      series=points[-512:],baseline=old_baseline,archived=True)
        atomic_json(data/'learning'/name,archived)
        report['archives'].append(dict(source_hash=old.name,model_version=old.parent.name,
                                       evaluations=len(points),url=f'data/learning/{name}'))
    atomic_json(data/'learning/visuals.json',report)
    svg=['<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="730" viewBox="0 0 1200 730" role="img" aria-labelledby="title desc">',
         '<title id="title">Spatial challenger: prediction error across frozen evaluations</title>',
         f'<desc id="desc">Percentage error reduction relative to the {baseline}. Positive is better. Black is later submitted tasks; red dashed is unseen geometry. This measures predictions, not discovery odds.</desc>',
         '<rect width="1200" height="730" fill="white"/>',
         '<g font-family="Arial,Helvetica,sans-serif" fill="#111">',
         '<text x="38" y="45" font-size="27">Is the challenger learning?</text>',
         f'<text x="38" y="76" font-size="16">{len(series)} frozen evaluations · {latest["through"]:,} training-boundary tasks · SHADOW: no production influence</text>',
         '<path d="M38 105h30" stroke="#111" stroke-width="3"/><text x="78" y="111" font-size="15">Later submitted tasks</text>',
         '<path d="M320 105h30" stroke="#b5222c" stroke-width="3" stroke-dasharray="6 4"/><text x="360" y="111" font-size="15">Unseen geometry</text>']
    for index,(metric,label) in enumerate(METRICS.items()):
        left=65+(index%2)*590;top=165+(index//2)*245;w=505;h=145
        values=[p['metrics'][metric][g] for p in series for g in ('future_all','future_unseen_geometry') if p['metrics'][metric][g] is not None]
        lo=min([0]+values);hi=max([1]+values);pad=(hi-lo)*.15;lo-=pad;hi+=pad
        x=lambda j:left+w/2 if len(series)==1 else left+j*w/max(1,len(series)-1)
        y=lambda v:top+h-(v-lo)/(hi-lo)*h
        svg.append(f'<text x="{left}" y="{top-20}" font-size="19">{escape(label)}</text>')
        for v in [lo,0,hi]:
            svg.append(f'<path d="M{left} {y(v):.2f}h{w}" stroke="#ddd"/><text x="{left-9}" y="{y(v)+5:.2f}" text-anchor="end" font-size="12">{v:.1f}%</text>')
        for group,color,dash in [('future_all','#111',''),('future_unseen_geometry','#b5222c','6 4')]:
            pen=False;segments=[]
            for j,p in enumerate(series):
                value=p['metrics'][metric][group]
                if value is None:pen=False;continue
                segments.append(f'{"L" if pen else "M"}{x(j):.2f},{y(value):.2f}');pen=True
                svg.append(f'<circle cx="{x(j):.2f}" cy="{y(value):.2f}" r="3" fill="{color}"/>')
            svg.append(f'<path d="{" ".join(segments)}" fill="none" stroke="{color}" stroke-width="2.5" stroke-dasharray="{dash}"/>')
        if series:
            for j in sorted({0,len(series)-1}):svg.append(f'<text x="{x(j):.2f}" y="{top+h+23}" text-anchor="middle" font-size="12">{series[j]["through"]:,}</text>')
        else:
            svg.append(f'<text x="{left+w/2}" y="{top+h/2}" text-anchor="middle" font-size="15">Awaiting the first complete evaluation window</text>')
        svg.append(f'<text x="{left+w/2}" y="{top+h+43}" text-anchor="middle" font-size="12">Verified tasks at evaluation end</text>')
    svg+=[f'<text x="38" y="679" font-size="15">Y: reduction in mean absolute log1p error versus {baseline}. Above zero = lower error.</text>',
          '<text x="38" y="706" font-size="15">Historical backfills are retrospective. Better predictions do not establish better discovery odds.</text></g></svg>']
    (data/'learning/evolution.svg').write_text('\n'.join(svg),encoding='utf-8',newline='\n')
    pilot_path=data/'learning/pilots/2026-09-11/results.json'
    if pilot_path.exists():
        pilot=json.loads(pilot_path.read_text());rates={}
        for arm in pilot['arms']:
            runs=[r for r in pilot['runs'] if r['arm']==arm]
            cpu=sum(r['cpu_ms'] for r in runs)
            if cpu>0:rates[arm]=sum(r['counters']['quotient_points'] for r in runs)/cpu
        if rates.get('current',0)>0:
            arms=[('uniform','Uniform'),('current','Legacy scheduler (pilot)'),('spatial_q','Spatial challenger')]
            report['pilot']=[{'label':label,'ratio':rates[arm]/rates['current']} for arm,label in arms]
            atomic_json(data/'learning/visuals.json',report)
            chart=['<svg xmlns="http://www.w3.org/2000/svg" width="900" height="300" viewBox="0 0 900 300" role="img" aria-label="Exploratory pilot quotient exposure per CPU relative to legacy scheduler">',
                   '<rect width="900" height="300" fill="white"/><g font-family="Arial,Helvetica,sans-serif" fill="#111">',
                   '<text x="25" y="35" font-size="22">A small performance pilot</text>']
            for j,(arm,label) in enumerate(arms):
                ratio=rates[arm]/rates['current'];y=70+j*52
                chart.append(f'<text x="25" y="{y+21}" font-size="17">{label}</text><rect x="215" y="{y}" width="{ratio*360:.2f}" height="30" fill="{["#999","#111","#b5222c"][j]}"/><text x="{225+ratio*360:.2f}" y="{y+21}" font-size="17">{ratio:.2f}×</text>')
            chart+=['<text x="25" y="253" font-size="15">Quotient exposure per CPU · four seeds · about 8.35 CPU-seconds across all four tested arms</text>',
                    '<text x="25" y="279" font-size="15">Exploratory, not sufficient for promotion. This is not a multiplier on discovery odds.</text></g></svg>']
            (data/'learning/pilot.svg').write_text('\n'.join(chart),encoding='utf-8',newline='\n')
    return report
if __name__=='__main__':generate()
