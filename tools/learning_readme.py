"""README-only learning report; never injected into website copy."""
import json
from pathlib import Path
from readme_snapshot import ROOT

def render(data):
    path=Path(data)/'learning/latest.json'
    if not path.exists():return 'Learning report unavailable. Production remains on the established cost scheduler.'
    r=json.loads(path.read_text())
    cluster=Path(data)/'cluster.json'
    current=json.loads(cluster.read_text()).get('totals',{}).get('verified_unique_tasks',0) if cluster.exists() else 0
    stale=current>r['observed_tasks']
    lines=['## Experimental task learning','',
           f"Frozen through **{r['through']:,} verified tasks**; **{r['model_count']} models** and **{r['completed_evaluations']} completed forward-window evaluations**. Mode: **shadow**, with no production influence.",'',
           'The challenger predicts server CPU, quotient positions, curves and exact-test counts from context and coarse coefficient/block geometry. Shrinkage keeps sparse regions close to their context baseline. These are arithmetic and cost predictions, not winning probabilities.','',
           '```mermaid','flowchart TD','    Receipts[Independently replayed receipts] --> Ledger[Canonical ledger]',
           '    Ledger --> Production[Existing cost policy: 40 percent exploration]',
           '    Ledger --> Freeze[Freeze each 1024 task boundary]',
           '    Freeze --> Spatial[Train spatial challenger excluding held-out geometry]',
           '    Spatial --> Future[Score next 1024 accepted tasks]',
           '    Future --> Report[Publish errors and immutable model hashes]',
           '    Report --> Gate[Controlled policy benchmark still required]',
           '    Gate --> NoPromotion[No automatic discovery-policy promotion]','```','']
    if stale: lines += ['', '**Learning report is behind the ledger; inspect the latest Action before interpreting freshness.**']
    e=r.get('latest_evaluation')
    if e:
        lines += [f"Latest evaluation: tasks {e['from']:,}–{e['through']:,}. Lower mean absolute log1p prediction error is better.",'',
                  '| Quantity | Context baseline | Spatial challenger |','| --- | ---: | ---: |']
        scores=e['results']['future_all']['mean_absolute_log1p_error']
        for t in ('cpu_ms','quotient_points','curves','exact_tests'):
            lines.append(f"| {t} | {scores['context_baseline'][t]:.4f} | {scores['spatial'][t]:.4f} |")
        lines += ['',f"Unseen-geometry evaluation: {e['results']['future_unseen_geometry']['tasks']:,} tasks. Full errors and nonzero-count support are in the report."]
    lines += ['', 'Historical backfills are retrospective chronological tests, not a randomized A/B experiment. New snapshots remain frozen while later arrivals are evaluated. Arrival time is not computation time; submitted work is selection-biased. Improved prediction error alone cannot promote a search policy.', '',
              '[Latest report](data/learning/latest.json) · [Frozen model and evaluation records](data/'+r['history']+'/) · [Design and promotion protocol](docs/LEARNING.md)']
    return '\n'.join(lines)

def update(data=ROOT/'data',readme=ROOT/'README.md'):
    p=Path(readme);s=p.read_text();a='<!-- LEARNING:START -->';b='<!-- LEARNING:END -->'
    block=a+'\n\n'+render(data)+'\n\n'+b
    if a in s:
        start=s.index(a);end=s.index(b,start)+len(b);s=s[:start]+block+s[end:]
    else:s+='\n\n'+block+'\n'
    p.write_text(s,encoding='utf-8',newline='\n')
if __name__=='__main__':update()
