import assert from 'node:assert/strict';
import test from 'node:test';
import {createHash, webcrypto} from 'node:crypto';
import {CONTEXTS, ENGINE, makeTask, taskId} from '../web/engine.mjs';
import {newSeed, seededRandom, createCoverageClient, validateManifest} from '../web/search-session.mjs';
if (!globalThis.crypto) globalThis.crypto = webcrypto;
const digest = bytes => createHash('sha256').update(bytes).digest('hex');
function fixture(ids = {}) {
  const files = new Map(), shards = {};
  let count = 0;
  for (const c of CONTEXTS) {
    const tasks = [...(ids[c.id] || [])].sort();
    const bytes = JSON.stringify({schema:'math-gambling-coverage-shard-v1', engine:ENGINE, context:c.id, tasks},null,2)+'\n';
    const sha256 = digest(bytes), file = `${c.id}-${sha256}.json`;
    files.set(file, bytes); shards[c.id] = {file,sha256,count:tasks.length}; count += tasks.length;
  }
  const index = {schema:'math-gambling-coverage-v1',engine:ENGINE,revision:count,verified_task_count:count,updated_at:'2026-09-10T00:00:00Z',shards};
  files.set('index.json',JSON.stringify(index));
  return {files,index};
}
function clientHost(start) {
  let current = start, clock = 1;
  const calls = [];
  const client = createCoverageClient(new URL('https://example.test/math-gambling/'),{
    now:()=>clock,
    fetcher:async url => {
      const name = url.pathname.split('/').at(-1); calls.push(name);
      return new Response(current.files.get(name) ?? 'missing', {status:current.files.has(name)?200:404});
    },
  });
  return {client,calls,set(next,elapsed=61000){current=next;clock+=elapsed;}};
}
test('random 256-bit seeds and stable unbiased bounded SHA-256 streams',async()=>{
  assert.match(newSeed(), /^[0-9a-f]{64}$/);
  assert.notEqual(newSeed(),newSeed());
  const seed='12'.repeat(32), a=seededRandom(seed),b=seededRandom(seed);
  const input=Buffer.concat([Buffer.from(seed,'hex'),Buffer.alloc(8)]);
  const reference=createHash('sha256').update(input).digest().readBigUInt64BE(0);
  assert.equal(await a.below(1n<<64n),reference);
  assert.equal(await b.below(1n<<64n),reference);
  for(let i=0;i<80;i++) {
    const x=await a.below(128n),y=await b.below(128n);
    assert.equal(x,y); assert.ok(x>=0n&&x<128n);
  }
  await assert.rejects(a.below(0n));
  await assert.rejects(a.below((1n<<64n)+1n));
});
test('exact membership skips published IDs, keeps unsearched neighbors, refreshes new work',async()=>{
  const first=makeTask('c00',0),neighbor=makeTask('c00',128);
  const h=clientHost(fixture({c00:[taskId(first)]}));
  assert.equal(await h.client.has(first),true);
  assert.equal(await h.client.has(neighbor),false);
  assert.equal(h.calls.length,2,'index plus one cached context shard');
  h.set(fixture({c00:[taskId(first),taskId(neighbor)]}));
  assert.equal(await h.client.has(neighbor),true);
  assert.equal(h.client.revision,2);
});
test('corrupt, missing and regressed coverage fail closed',async()=>{
  const task=makeTask('c00',0),good=fixture({c00:[taskId(task)]});
  const corrupt=fixture({c00:[taskId(task)]});
  corrupt.files.set(corrupt.index.shards.c00.file,'{}');
  await assert.rejects(clientHost(corrupt).client.has(task),/checksum/);
  const missing=fixture(); missing.files.delete(missing.index.shards.c00.file);
  await assert.rejects(clientHost(missing).client.has(task),/unavailable/);
  const h=clientHost(good); await h.client.has(task); h.set(fixture());
  await assert.rejects(h.client.has(task),/backwards/);
  const invalid=fixture();invalid.index.shards.c00.file='../outside.json';
  assert.throws(()=>validateManifest(invalid.index),/descriptor/);
});
test('even correctly hashed shards cannot erase old IDs or contain duplicate IDs',async()=>{
  const a=taskId(makeTask('c00',0)),b=taskId(makeTask('c00',128)),c=taskId(makeTask('c00',256));
  const h=clientHost(fixture({c00:[a]}));await h.client.has(makeTask('c00',0));
  h.set(fixture({c00:[b,c]}));
  await assert.rejects(h.client.has(makeTask('c00',0)),/removed/);
  await assert.rejects(clientHost(fixture({c00:[a,a]})).client.has(makeTask('c00',0)),/duplicate/);
});

test('Python-published v2 chunks support browser membership, extension and missing-file failure',async()=>{
  const {execFileSync} = await import('node:child_process');
  const build = (rows) => {
    const script = `import sys,json,tempfile\nfrom pathlib import Path\nsys.path.insert(0,'tools')\nfrom coverage_index import publish_coverage\nfrom search_core import make_task,task_id\nwith tempfile.TemporaryDirectory() as tmp:\n tasks=[]\n for i,row in enumerate(json.loads(sys.argv[1])):\n  t=make_task('c00',row);tasks.append(dict(schema='math-gambling-verified-task-v1',sequence=i+1,result=dict(task=t,id=task_id(t))))\n manifest=publish_coverage(Path(tmp),tasks)\n print(json.dumps({'index':manifest,'files':{p.name:p.read_text() for p in (Path(tmp)/'coverage').glob('*.json')}}))`;
    const result = JSON.parse(execFileSync('python3',['-c',script,JSON.stringify(rows)],{encoding:'utf8'}));
    return {index:result.index,files:new Map(Object.entries(result.files))};
  };
  const first=build([0]), next=build([0,128]);
  const h=clientHost(first);
  assert.equal(await h.client.has(makeTask('c00',0)),true);
  assert.equal(await h.client.has(makeTask('c00',128)),false);
  h.set(next);
  assert.equal(await h.client.has(makeTask('c00',128)),true);
  assert.equal(await h.client.has(makeTask('c00',256)),false);
  const broken=build([0]);
  for(const name of broken.files.keys()) if(name.startsWith('c00-b')) broken.files.delete(name);
  await assert.rejects(clientHost(broken).client.has(makeTask('c00',0)),/unavailable/);
  const oldClient=clientHost(fixture({c00:[taskId(makeTask('c00',0))]}));
  assert.equal(await oldClient.client.has(makeTask('c00',0)),true);
  oldClient.set(first);
  assert.equal(await oldClient.client.has(makeTask('c00',0)),true,'same-count v1 to v2 upgrade');
});

function chunkedFixture(tasks) {
  const files = new Map(), shards = {};
  const write = (prefix, payload, count) => {
    const bytes = JSON.stringify(payload, null, 2) + '\n', sha256 = digest(bytes);
    const file = `${prefix}-${sha256}.json`;
    files.set(file, bytes);
    return {file, sha256, count};
  };
  for (const context of CONTEXTS) {
    const buckets = {};
    for (const task of tasks.filter(task => task.context === context.id)) {
      const id = taskId(task), bucket = digest(id).slice(0, 2);
      (buckets[bucket] ||= []).push(id);
    }
    for (const [bucket, ids] of Object.entries(buckets)) {
      buckets[bucket] = [write(`${context.id}-b${bucket}`, {
        schema: 'math-gambling-coverage-chunk-v2', engine: ENGINE,
        context: context.id, bucket, tasks: ids.sort(),
      }, ids.length)];
    }
    shards[context.id] = write(context.id, {
      schema: 'math-gambling-coverage-context-v2', engine: ENGINE, context: context.id, buckets,
    }, tasks.filter(task => task.context === context.id).length);
  }
  const index = {schema: 'math-gambling-coverage-v2', engine: ENGINE, revision: tasks.length,
    verified_task_count: tasks.length, updated_at: '2026-09-10T00:00:00Z', shards};
  files.set('index.json', JSON.stringify(index));
  return {index, files};
}

test('suspended v2 readers resume after retired tails disappear, while cached membership stays guarded', async () => {
  const first = makeTask('c00', 0), same = [first], bucket = digest(taskId(first)).slice(0, 2);
  let other;
  for (let row = 128; row < 128 * 10000 && same.length < 3; row += 128) {
    const task = makeTask('c00', row);
    if (digest(taskId(task)).slice(0, 2) === bucket) same.push(task);
    else other ||= task;
  }
  assert.equal(same.length, 3);
  const original = chunkedFixture(same.slice(0, 1)), updated = chunkedFixture(same.slice(0, 2));
  const oldTail = [...original.files.keys()].find(file => file.startsWith('c00-b'));
  const h = clientHost(original);
  assert.equal(await h.client.has(other), false, 'load the old context without caching its tail');
  assert.equal(h.calls.includes(oldTail), false);
  h.set(updated, 25 * 3600 * 1000);
  assert.equal(updated.files.has(oldTail), false, 'retired files are absent from the current host');
  assert.equal(await h.client.has(same[0]), true);
  assert.equal(await h.client.has(same[1]), true);
  assert.equal(await h.client.has(same[2]), false);
  assert.equal(h.calls.includes(oldTail), false, 'a fresh manifest cannot require a retired download');

  const cached = clientHost(original);
  assert.equal(await cached.client.has(first), true);
  cached.set(chunkedFixture(same.slice(1)), 25 * 3600 * 1000);
  await assert.rejects(cached.client.has(same[1]), /removed completed work/);
});
