"""Reproduce a labelled historical development test from verified records."""
import argparse,json
from pathlib import Path
from strategy_model import observations,fit,evaluate,digest

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--data',type=Path,default=Path('data'))
    p.add_argument('--through',type=int,default=28543)
    p.add_argument('--train',type=int,default=16384)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if not 0<a.train<a.through<=100000:p.error('require 0<train<through<=100000')
    if a.output.exists():p.error('refusing to overwrite an experiment')
    rows=observations(a.data,through=a.through)
    if len(rows)!=a.through:p.error('verified ledger does not reach requested boundary')
    model=fit(rows[:a.train])
    result={'schema':'mg114-historical-development-v1','training':a.train,'test':a.through-a.train,
            'status':'historical development evaluation, not an untouched promotion test',
            'input_hash':digest([r['hash'] for r in rows]),'model_hash':digest(model),
            'results':evaluate(model,rows[a.train:])}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(a.output)

if __name__=='__main__':main()
