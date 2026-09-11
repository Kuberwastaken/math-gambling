// Exact accelerated kernel. Each worker owns its instance and its hit callback.
// Returning null means the optional artifact could not load; the BigInt engine
// remains available. Arithmetic traps after a task starts are never negatives.
import {validateTask, verifyTriple} from './engine.mjs?v=ec631fabe88d';
export async function createWasmKernel(bytesOrResponse) {
  let instance, onHit;
  const decode = (ptr, len) => JSON.parse(new TextDecoder().decode(new Uint8Array(instance.exports.memory.buffer, ptr, len)));
  const imports = {mg: {identity(ptr, len) {
    const hit = decode(ptr, len);
    if (!verifyTriple(hit?.xyz)) throw Error('WASM identity failed independent BigInt verification');
    onHit?.(hit);
  }}};
  const bytes = bytesOrResponse instanceof Response ? await bytesOrResponse.arrayBuffer() : bytesOrResponse;
  ({instance} = await WebAssembly.instantiate(bytes, imports));
  if (instance.exports.mg_self_test() !== 1) throw Error("WASM positive/negative self-test failed");
  return {runTask(task, options = {}) {
    task = validateTask(task);
    const input = new TextEncoder().encode(JSON.stringify(task));
    if (input.length > 2048) throw Error('Task exceeds WASM input limit');
    const api = instance.exports;
    new Uint8Array(api.memory.buffer, api.mg_input_ptr(), input.length).set(input);
    onHit = options.onHit;
    try {
      const len = api.mg_run(input.length, options.montgomery ? 1 : 0);
      const result = decode(api.mg_output_ptr(), len);
      if (result.error) throw Error(result.error);
      return result;
    } finally {onHit = null;}
  }};
}
export async function loadWasmKernel() {
  if (typeof WebAssembly === 'undefined') return null;
  try {
    const response = await fetch(new URL('./assets/kernel/math_gambling_kernel.wasm', import.meta.url), {signal: AbortSignal.timeout(10000)});
    if (!response.ok) return null;
    return await createWasmKernel(response);
  } catch { return null; }
}
