import assert from 'node:assert/strict';
import {loadChallenger, validReport} from '../web/challenger-viz.mjs';

class Element {
  children=[];attributes={};textContent='';value='0';style={};
  append(...nodes){this.children.push(...nodes);}
  replaceChildren(...nodes){this.children=nodes;}
  setAttribute(k,v){this.attributes[k]=String(v);}
}
const elements=new Map();
const get=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id);};
globalThis.document={getElementById:get,createElement:()=>new Element(),createElementNS:()=>new Element()};
const all=e=>[e,...e.children.flatMap(all)];
get('challenger-metric').value='cpu_ms';
const point=(through, value=4)=>({from:through-1023,through,unseen_tasks:180,
  metrics:Object.fromEntries(['cpu_ms','curves','quotient_points','exact_tests'].map(k=>[k,{future_all:value,future_unseen_geometry:2}]))});
const oldURL='data/learning/archive-mg114-spatial-shadow-v1-aaaaaaaaaaaaaaaa.json';
let current={schema:'mg114-learning-visuals-v1',mode:'shadow',model_version:'mg114-spatial-shadow-v2',
  source_hash:'b'.repeat(64),model_count:1,completed_evaluations:0,through:2048,observed_tasks:2050,next_boundary:3072,
  baseline:'proof-aware context baseline',series:[],archives:[{source_hash:'a'.repeat(16),model_version:'mg114-spatial-shadow-v1',url:oldURL,evaluations:2}]};
const old={...current,source_hash:'a'.repeat(16),model_version:'mg114-spatial-shadow-v1',baseline:'context baseline',completed_evaluations:2,series:[point(1024),point(2048)]};
const fetchJSON=async path=>path===oldURL?old:current;
try {
  await loadChallenger(fetchJSON);
  assert.match(get('challenger-chart').children[0].textContent,/first evaluation/);
  assert.match(get('challenger-window-progress').textContent,/1,022 more verified tasks/);
  assert.equal(get('challenger-window').disabled,true);
  current={...current,model_count:2,completed_evaluations:1,series:[point(3072)],through:3072};
  await loadChallenger(fetchJSON);
  const svg=()=>all(get('challenger-chart'));
  assert.equal(svg().filter(n=>n.attributes.cx==='355').length,2);
  assert.equal(svg().filter(n=>n.textContent==='3,072').length,1);
  assert.match(get('challenger-status').textContent,/1 evaluation ·/);
  assert.match(get('challenger-selected').textContent,/trend pending/);
  assert.equal(get('challenger-window').disabled,true);
  get('challenger-version').value='a'.repeat(16);get('challenger-version').onchange();
  await new Promise(resolve=>setImmediate(resolve));
  assert.match(get('challenger-status').textContent,/Spatial model v1/);
  assert.match(get('challenger-detail').textContent,/context baseline/);
  get('challenger-window').value='0';get('challenger-window').oninput();
  await loadChallenger(fetchJSON);
  assert.equal(get('challenger-window').value,'0','refresh preserves historical selection');
  assert.match(get('challenger-window-progress').textContent,/Previous model version/);
  current={...current,source_hash:'c'.repeat(64),series:[],completed_evaluations:0,archives:[]};
  await loadChallenger(fetchJSON);
  assert.equal(svg().filter(n=>'viewBox' in n.attributes).length,0,'new empty version clears stale graph');
  assert.equal(validReport({...old,series:[{...point(1024),from:null}]}),false);
  console.log('Challenger UI: empty, first result, version selection, refresh, stale chart and malformed report checks passed.');
} finally {delete globalThis.document;}
