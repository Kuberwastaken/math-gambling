import {runTask, verifyTriple, ENGINE} from './engine.mjs?v=027258560b2e';

// A worker accepts one task at a time. The page decides when to queue the next.
// Stop is a task-boundary instruction; terminating a worker discards only its
// unfinished task, which must never be submitted as completed coverage.
import {loadWasmKernel} from './wasm-kernel.mjs?v=027258560b2e';
const accelerated = await loadWasmKernel();
let busy = false;
self.onmessage = async ({data}) => {
  if (data?.type === 'stop') {
    self.postMessage({type: 'stopped', atTaskBoundary: !busy});
    return;
  }
  if (data?.type !== 'start') return;
  if (busy) { self.postMessage({type: 'error', message: 'worker already running a task'}); return; }
  busy = true;
  const started = performance.now();
  try {
    const result = await (accelerated?.runTask || runTask)(data.task, {onHit(hit) {
      if (verifyTriple(hit?.xyz))
        self.postMessage({type: 'identity', hit, task: data.task});
    }});
    self.postMessage({type: 'result', result, elapsedMs: performance.now() - started});
  } catch (error) {
    self.postMessage({type: 'error', message: String(error?.message || error)});
  } finally { busy = false; }
};
self.postMessage({type: 'ready', engine: ENGINE, kernel: accelerated ? 'rust-wasm' : 'javascript-bigint'});
