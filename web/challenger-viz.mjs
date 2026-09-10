const METRICS = {cpu_ms: 'Server CPU cost', quotient_points: 'Quotient positions', curves: 'Curve intervals', exact_tests: 'Exact square tests'};
const NS = 'http://www.w3.org/2000/svg';
export function validReport(report) {
  return report?.schema === 'mg114-learning-visuals-v1' && report.mode === 'shadow' &&
    Array.isArray(report.series) && report.series.length <= 10000 &&
    report.series.every(p => Number.isSafeInteger(p.through) && Object.keys(METRICS).every(k =>
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
  try {
    const r = await fetchJSON('data/learning/visuals.json');
    if (!validReport(r)) throw Error('Invalid report');
    status.textContent = `${r.model_count} frozen models · ${r.completed_evaluations} evaluations · ${Number(r.through).toLocaleString()} tasks at the latest training boundary`;
    const pilot = document.getElementById('challenger-pilot-bars');
    if (pilot && Array.isArray(r.pilot) && r.pilot.length === 3 && r.pilot.every(p => typeof p.label === 'string' && Number.isFinite(p.ratio) && p.ratio >= 0 && p.ratio < 10)) {
      pilot.replaceChildren();
      for (const p of r.pilot) {
        const row=document.createElement('div'), label=document.createElement('span'), track=document.createElement('span'), bar=document.createElement('i'), value=document.createElement('strong');
        label.textContent=p.label;value.textContent=`${p.ratio.toFixed(2)}×`;
        track.className='pilot-track';bar.style.width=`${p.ratio/Math.max(...r.pilot.map(p=>p.ratio))*100}%`;
        track.append(bar);row.append(label,track,value);pilot.append(row);
      }
    }
    const select = document.getElementById('challenger-metric'), range = document.getElementById('challenger-window');
    range.max = Math.max(0,r.series.length-1);range.value=range.max;range.disabled=!r.series.length;
    select.disabled=!r.series.length;
    if (!r.series.length) { document.getElementById('challenger-detail').textContent='Waiting for the first complete evaluation window.'; return; }
    function draw() {
      const key=select.value, chosen=Number(range.value), plot=document.getElementById('challenger-chart');
      const vals=r.series.flatMap(p=>Object.values(p.metrics[key])).filter(Number.isFinite);
      const low=Math.min(0,...vals), high=Math.max(1,...vals), pad=(high-low)*.15, lo=low-pad, hi=high+pad;
      const x=i=>55+i*600/Math.max(1,r.series.length-1), y=v=>210-(v-lo)*160/(hi-lo);
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
      for(const i of [0,r.series.length-1]) svg.append(node('text',{x:x(i),y:240,'text-anchor':'middle',fill:'#555','font-size':13},r.series[i].through.toLocaleString()));
      plot.replaceChildren(svg);
      const p=r.series[chosen], m=p.metrics[key];
      const describe=v=>v===null?'unavailable':`${Math.abs(v).toFixed(2)}% ${v>=0?'lower':'higher'} error`;
      document.getElementById('challenger-selected').textContent=`Evaluation ${chosen+1} of ${r.series.length}`;
      document.getElementById('challenger-detail').textContent=`Tasks ${p.from.toLocaleString()}–${p.through.toLocaleString()}: ${describe(m.future_all)} on later submissions; ${describe(m.future_unseen_geometry)} on ${p.unseen_tasks} tasks in held-out geometry. Compared with the context-only predictor.`;
    }
    select.onchange=draw;range.oninput=draw;draw();
  } catch {
    status.textContent='Challenger report unavailable. The production scheduler remains active.';
  }
}
