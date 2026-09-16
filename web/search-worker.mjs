import {runTask, verifyTriple, ENGINE, ENGINES} from './engine.mjs';

// A worker accepts one task at a time. The page decides when to queue the next.
// Stop is a task-boundary instruction; terminating a worker discards only its
// unfinished task, which must never be submitted as completed coverage.
import {loadWasmKernel} from './wasm-kernel.mjs';
const accelerated = await loadWasmKernel();
// An accelerated kernel that predates engine v2 rejects a version-2 task before
// computing anything. Falling back to the audited BigInt engine keeps the page
// working, and is only taken when the kernel produced no output at all, so a
// published identity can never be emitted twice.
let acceleratedVersions = accelerated ? new Set(Object.keys(ENGINES).map(Number)) : new Set();
let busy = false;
async function compute(task, options) {
  if (accelerated && acceleratedVersions.has(task?.version)) {
    let emitted = 0;
    try {
      return await accelerated.runTask(task, {...options, onHit(hit) { emitted++; options.onHit(hit); }});
    } catch (error) {
      if (emitted || task.version === 1) throw error;
      acceleratedVersions.delete(task.version);
      self.postMessage({type: 'kernel', kernel: 'javascript-bigint',
        message: `Accelerated kernel does not support engine ${ENGINES[task.version]}: ${String(error?.message || error)}`});
    }
  }
  return runTask(task, options);
}
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
    const result = await compute(data.task, {onHit(hit) {
      if (verifyTriple(hit?.xyz))
        self.postMessage({type: 'identity', hit, task: data.task});
    }});
    self.postMessage({type: 'result', result, elapsedMs: performance.now() - started});
  } catch (error) {
    self.postMessage({type: 'error', message: String(error?.message || error)});
  } finally { busy = false; }
};
self.postMessage({type: 'ready', engine: ENGINE, kernel: accelerated ? 'rust-wasm' : 'javascript-bigint'});
