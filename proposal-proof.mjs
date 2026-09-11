// Outward integer bounds only. Shared derivation: tools/search_features.py.
import {CONTEXTS, validateTask} from './engine.mjs?v=eee5288cd1a6';
const S=10n**18n,A=4848807585839879338n,A2=23510935004498358839n;
if (!(A**3n<=114n*S**3n && (A+1n)**3n>114n*S**3n &&
      A2**3n<=12996n*S**3n && (A2+1n)**3n>12996n*S**3n)) throw Error('Invalid outward root bounds');
const abs=x=>x<0n?-x:x, min=(a,b)=>a<b?a:b,max=(a,b)=>a>b?a:b;
const add=(a,b)=>[a[0]+b[0],a[1]+b[1]];
const mul=(a,b)=>{const v=[a[0]*b[0],a[0]*b[1],a[1]*b[0],a[1]*b[1]];return [v.reduce(min),v.reduce(max)];};
const scale=(a,n)=>mul(a,[n,n]);
const square=a=>[a[0]<=0n&&a[1]>=0n?0n:min(a[0]**2n,a[1]**2n),max(a[0]**2n,a[1]**2n)];
export function normBounds(input) {
 const task=validateTask(input),c=CONTEXTS.find(c=>c.id===task.context),r=BigInt(c.radius),w=2n*r+1n;
 let start=BigInt(task.row);const end=min(start+128n,BigInt(c.totalRows));
 const t0=BigInt(c.tlo+16*task.block),t1=min(t0+15n,BigInt(c.thi)),ell=BigInt(c.ell);const bounds=[];
 while(start<end){
  const stop=min(end,(start/w+1n)*w),b=[start%w-r,(stop-1n)%w-r],cc=start/w-r;
  const error=max(abs(b[0]),abs(b[1]))+abs(cc),u=[ell*t0*S-ell*S/2n-error,ell*t1*S+ell*S/2n+error];
  const v=add(mul([A,A+1n],b),scale([A2,A2+1n],cc));
  const wt=add(add(mul([A2,A2+1n],square(b)),scale(b,114n*cc*S)),scale([A,A+1n],114n*cc*cc));
  bounds.push(mul(u,add(add(square(u),scale(mul(v,u),-3n)),scale(wt,3n*S))));start=stop;
 }
 return [bounds.map(x=>x[0]).reduce(min),bounds.map(x=>x[1]).reduce(max)];
}
export function certifiedEmpty(task){
 const [lo,hi]=normBounds(task),c=CONTEXTS.find(c=>c.id===task.context),ell=BigInt(c.ell);
 return hi<=ell*BigInt(c.dlo)*S**3n || lo>ell*BigInt(c.dhi)*S**3n;
}
