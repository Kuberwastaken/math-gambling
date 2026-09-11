import {test} from 'node:test';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {CONTEXTS,makeTask,runTask} from '../web/engine.mjs';
import {normBounds,certifiedEmpty} from '../web/proposal-proof.mjs';
test('outward tile proof agrees exactly across Python and JS',async()=>{
 const tasks=CONTEXTS.flatMap(c=>[0n,(BigInt(c.totalRows)-1n)/128n*128n,BigInt(c.totalRows)/7n/128n*128n].map(row=>makeTask(c.id,row,c.blocks-1)));
 const p=spawnSync(process.env.PYTHON || 'python3',['-c',"import sys,json;sys.path.insert(0,'tools');from search_features import norm_bounds;print(json.dumps([[str(x) for x in norm_bounds(t)] for t in json.load(sys.stdin)]))"],{input:JSON.stringify(tasks),encoding:'utf8'});
 assert.equal(p.status,0,p.stderr);const expected=JSON.parse(p.stdout);
 for(let i=0;i<tasks.length;i++){
  assert.deepEqual(normBounds(tasks[i]).map(String),expected[i]);
  if(certifiedEmpty(tasks[i])){const r=await runTask(tasks[i]);assert.equal(r.counters.outside_shell,r.counters.generators);}
 }
});
