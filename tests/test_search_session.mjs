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
  return {client,calls,set(next){current=next;clock+=61000;}};
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
