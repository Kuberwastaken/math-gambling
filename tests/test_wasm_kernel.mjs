import assert from 'node:assert/strict';
import {readFileSync, existsSync} from 'node:fs';
import {test} from 'node:test';
import {createWasmKernel} from '../web/wasm-kernel.mjs';
import {CONTEXTS,makeTask,runTask,canonicalJSON} from '../web/engine.mjs';
const path=new URL('../web/assets/kernel/math_gambling_kernel.wasm',import.meta.url);
test('WASM matches independent BigInt engine over all context boundaries', {skip: !existsSync(path)},async()=>{
 const kernel=await createWasmKernel(readFileSync(path));
 for(const c of CONTEXTS)for(const [row,block]of [[0,0],[(BigInt(c.totalRows)-1n)/128n*128n,c.blocks-1],[BigInt(c.totalRows)/7n/128n*128n,Math.floor(c.blocks/2)]]){
  const task=makeTask(c.id,row,block),expected=await runTask(task);
  for(const montgomery of [false,true])assert.equal(canonicalJSON(kernel.runTask(task,{montgomery})),canonicalJSON(expected));
 }
});
