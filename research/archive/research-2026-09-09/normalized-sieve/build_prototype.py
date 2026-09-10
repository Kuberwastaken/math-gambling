from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
LAB=HERE.parents[1]
PROJECT=LAB.parents[1]
SOURCE=LAB/'phase3'
s=(SOURCE/'checker.c').read_text()
s=s.replace('static uint64_t masks[NP][64];','static uint64_t masks[NP][64], qr_masks[NP];\nstatic i128 normalized_h;\nstatic int normalized_ready;')
s=s.replace('for(int v=0;v<p;v++)qr[v*v%p]=1;','qr_masks[j]=0;\n    for(int v=0;v<p;v++){qr[v*v%p]=1;qr_masks[j]|=UINT64_C(1)<<(v*v%p);}')
s=s.replace('static void prepare_prime(int j,','static void prepare_prime(long k,int j,')
old='int sm=s>0?dp[j]:(dp[j]?p-dp[j]:0);allowed[j]=masks[j][sm];*ready|=1U<<j;'
new='''int sm=s>0?dp[j]:(dp[j]?p-dp[j]:0);allowed[j]=masks[j][sm];
    if(!dp[j]){
      /* For r<D<=INT64_MAX, both products are below 2^126. Long
       * division computes (k-r^3)/D without forming the cubic. */
      if(!normalized_ready){
        u128 square=(u128)r*r,u=square/d,v=square%d,vr=v*r;
        u128 w=vr/d,t=vr%d;
        i128 delta=(i128)k-(i128)t;
        if(delta%(i128)d)fail("Normalized sieve received a non-root");
        normalized_h=delta/(i128)d-(i128)(u*r)-(i128)w;
        normalized_ready=1;
      }
      int sign=s>0?1:-1,rm=rp[j];
      rp[j]=mod128(4*sign*(i128)mod128(normalized_h,p)*inverse(3,p),p);
      dp[j]=mod128(-4*sign*rm*rm,p);
      allowed[j]=qr_masks[j];
    }
    *ready|=1U<<j;'''
assert old in s
s=s.replace(old,new).replace('prepare_prime(j,s,d,r,','prepare_prime(k,j,s,d,r,')
s=s.replace('curves++;\n  int sm81=', 'curves++;normalized_ready=0;\n  int sm81=')
(HERE/'checker.c').write_text(s)
(HERE/'offset_worker.c').write_text((SOURCE/'offset_worker.c').read_text())
link=HERE/'libpari.dylib'
if not link.exists(): link.symlink_to(LAB/'bin/libpari.dylib')
subprocess.run(['clang','-O3','-Wall','-Wextra','-I',str(PROJECT/'work/pari-include'),str(HERE/'offset_worker.c'),'-L',str(LAB/'bin'),'-lpari','-o',str(HERE/'offset_worker')],check=True)
print(HERE/'offset_worker')
