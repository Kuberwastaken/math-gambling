const METRICS = {cpu_ms: 'Server CPU cost', quotient_points: 'Quotient positions', curves: 'Curve intervals', exact_tests: 'Exact square tests'};
const NS = 'http://www.w3.org/2000/svg';
let revision = 0, selectedVersion = null, selectedThrough = null, followLatest = true;
const count = n => Number.isSafeInteger(n) && n >= 0;
const modelName = r => r.model_version?.endsWith('v2') ? 'Shared features v2' : 'Spatial model v1';
const archives = r => (r.archives || []).filter(a =>
  typeof a.source_hash === 'string' && /^data\/learning\/archive-mg114-spatial-shadow-v[12]-[a-f0-9]{16}\.json$/.test(a.url));
export function validReport(report) {
  return report?.schema === 'mg114-learning-visuals-v1' && report.mode === 'shadow' &&
    count(report.model_count) && count(report.completed_evaluations) && count(report.through) &&
    Array.isArray(report.series) && report.series.length <= 10000 &&
    report.series.every(p => count(p.through) && count(p.from) && p.from <= p.through && count(p.unseen_tasks) && Object.keys(METRICS).every(k =>
      ['future_all', 'future_unseen_geometry'].every(g => p.metrics?.[k]?.[g] === null || Number.isFinite(p.metrics?.[k]?.[g]))));
}
function node(tag, attrs, text) {
  const el = document.createElementNS(NS, tag);
  for (const [k,v] of Object.entries(attrs)) el.setAttribute(k, String(v));
  if (text !== undefined) el.textContent = text;
  return el;
}
export async function loadChallenger(fetchJSON) {
  const root = document.getElementById('challenger');
  if (!root) return;
  const status = document.getElementById('challenger-status');
  const currentRequest = ++revision;
  try {
    const current = await fetchJSON('data/learning/visuals.json');
    if (!validReport(current)) throw Error('Invalid report');
    const versions = document.getElementById('challenger-version'), previous = selectedVersion;
    const available = archives(current);
    const archived = available.find(a => a.source_hash === previous);
    let r = current;
    if (archived) r = await fetchJSON(archived.url);
    if (currentRequest !== revision) return;
    if (!validReport(r)) throw Error('Invalid archived report');
    selectedVersion = archived ? archived.source_hash : current.source_hash;
    if (versions) {
      versions.replaceChildren();
      for (const item of [{...current, label:`Current: ${modelName(current)}`},
        ...available.map(a => ({...a,label:`Previous: ${modelName(a)} · ${a.source_hash.slice(0,8)} (${a.evaluations} evaluations)`}))]) {
        const option=document.createElement('option');option.value=item.source_hash;option.textContent=item.label;versions.append(option);
      }
      versions.value=selectedVersion;versions.disabled=!available.length;
      versions.onchange=()=>{selectedVersion=versions.value;selectedThrough=null;followLatest=true;void loadChallenger(fetchJSON);};
    }
    status.textContent = `${modelName(r)} · ${r.model_count.toLocaleString()} frozen model${r.model_count===1?'':'s'} · ${r.completed_evaluations.toLocaleString()} evaluation${r.completed_evaluations===1?'':'s'} · ${r.through.toLocaleString()} tasks at the latest training boundary`;
    const progress = document.getElementById('challenger-window-progress');
    if (progress) progress.textContent = archived
      ? 'Previous model version. Its baseline and evaluations are kept separate from the current model.'
      : count(current.next_boundary) && count(current.observed_tasks)
        ? `${Math.max(0,current.next_boundary-current.observed_tasks).toLocaleString()} more verified tasks until the next evaluation boundary (${current.next_boundary.toLocaleString()}).${available.length?' Earlier model results are available in the Model selector.':''}` : '';

    const pilot = document.getElementById('challenger-pilot-bars');
    if (pilot && Array.isArray(current.pilot) && current.pilot.length === 3 && current.pilot.some(p=>p.ratio>0) && current.pilot.every(p => typeof p.label === 'string' && Number.isFinite(p.ratio) && p.ratio >= 0 && p.ratio < 10)) {
      pilot.replaceChildren();
      for (const p of current.pilot) {
        const row=document.createElement('div'), label=document.createElement('span'), track=document.createElement('span'), bar=document.createElement('i'), value=document.createElement('strong');
        label.textContent=p.label;value.textContent=`${p.ratio.toFixed(2)}×`;
        track.className='pilot-track';bar.style.width=`${p.ratio/Math.max(...current.pilot.map(p=>p.ratio))*100}%`;
        track.append(bar);row.append(label,track,value);pilot.append(row);
      }
    }
    const select = document.getElementById('challenger-metric'), range = document.getElementById('challenger-window');
    const oldIndex=r.series.findIndex(p=>p.through===selectedThrough);
    range.max = String(Math.max(0,r.series.length-1));
    range.value=String(followLatest || oldIndex<0 ? Math.max(0,r.series.length-1) : oldIndex);
    range.disabled=r.series.length<2;
    select.disabled=!r.series.length;
    if (!r.series.length) {
      const message=document.createElement('p');message.textContent='This model has been trained. Its first evaluation is still collecting verified tasks.';
      document.getElementById('challenger-chart').replaceChildren(message);
      document.getElementById('challenger-selected').textContent='Awaiting first evaluation';
      document.getElementById('challenger-detail').textContent='No prediction-error statistics exist yet for this model version.';
      return;
    }
    function draw() {
      const key=select.value, chosen=Number(range.value), plot=document.getElementById('challenger-chart');
      const vals=r.series.flatMap(p=>Object.values(p.metrics[key])).filter(Number.isFinite);
      const low=Math.min(0,...vals), high=Math.max(1,...vals), pad=(high-low)*.15, lo=low-pad, hi=high+pad;
      const x=i=>r.series.length===1?355:55+i*600/(r.series.length-1), y=v=>210-(v-lo)*160/(hi-lo);
      const svg=node('svg',{viewBox:'0 0 710 260',role:'img','aria-label':`${METRICS[key]} prediction error reduction across ${r.series.length} evaluation windows. Positive values are better.`});
      svg.append(node('rect',{width:710,height:260,fill:'#fff'}));
      for (const v of [lo,0,hi]) {
        svg.append(node('path',{d:`M55 ${y(v)}H655`,stroke:'#ddd'}));
        svg.append(node('text',{x:48,y:y(v)+4,'text-anchor':'end',fill:'#555','font-size':13},`${v.toFixed(1)}%`));
      }
      for (const [g,color,dash] of [['future_all','#111',''],['future_unseen_geometry','#b5222c','6 4']]) {
        // Missing values break the line rather than implying an observation.
        let d='',pen=false;
        r.series.forEach((p,i)=>{const v=p.metrics[key][g];if(v===null){pen=false;return;}d+=`${pen?'L':'M'}${x(i)} ${y(v)} `;pen=true;});
        svg.append(node('path',{d,fill:'none',stroke:color,'stroke-width':2.5,'stroke-dasharray':dash}));
        const v=r.series[chosen].metrics[key][g];
        if(v!==null)svg.append(node('circle',{cx:x(chosen),cy:y(v),r:4,fill:color}));
      }
      svg.append(node('path',{d:`M${x(chosen)} 45V214`,stroke:'#888','stroke-dasharray':'2 4'}));
      for(const i of new Set([0,r.series.length-1])) svg.append(node('text',{x:x(i),y:240,'text-anchor':'middle',fill:'#555','font-size':13},r.series[i].through.toLocaleString()));
      plot.replaceChildren(svg);
      const p=r.series[chosen], m=p.metrics[key];
      selectedThrough=p.through;
      const describe=v=>v===null?'unavailable':`${Math.abs(v).toFixed(2)}% ${v>=0?'lower':'higher'} error`;
      document.getElementById('challenger-selected').textContent=`Evaluation ${chosen+1} of ${r.series.length}${r.series.length===1?' · first result; trend pending':''}`;
      document.getElementById('challenger-detail').textContent=`Tasks ${p.from.toLocaleString()}–${p.through.toLocaleString()}: ${describe(m.future_all)} on later submissions; ${describe(m.future_unseen_geometry)} on ${p.unseen_tasks} tasks in held-out geometry. Compared with the ${r.baseline || 'context-only predictor'}.`;
    }
    select.onchange=draw;range.oninput=()=>{followLatest=Number(range.value)===Number(range.max);draw();};draw();
  } catch {
    if(currentRequest !== revision)return;
    status.textContent='Challenger report unavailable. The production scheduler remains active.';
  }
}
