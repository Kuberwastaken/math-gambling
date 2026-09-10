#include <unistd.h>
#include <sys/stat.h>
/* Deterministic, bounded selective search for x^3+y^3+z^3=114.
 * Norm parametrization: Grantham--Walsh; arithmetic checks use PARI.
 * A tile exhausts generator indices, NOT distinct ideals/curves or a height box.
 * No statistical rule removes candidates. Adaptive ordering changes only cost.
 */
#include <pari/pari.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <inttypes.h>
#include <time.h>
#include <errno.h>
#include <limits.h>

typedef __int128 i128;
typedef unsigned __int128 u128;
enum { NP=15 };
static const int sieve_primes[NP]={5,7,11,13,17,19,23,31,37,41,43,47,53,59,61};
static uint64_t masks[NP][64], qr_masks[NP];
static i128 normalized_h;
static int normalized_ready;
/* 243-bit base mask plus a duplicate prefix permits any64-bit cyclic window. */
static uint64_t short_q_masks[162][5];
enum { MOD3=243 };
static unsigned char ok81[MOD3][MOD3];
static uint16_t allowed_z[MOD3][MOD3],allowed_z_count[MOD3],inv243[MOD3];
static int order[NP], adaptive;
static int interval_engine; /* -1 direct, 0 automatic, +1 residue wheel */
static uint64_t direct_curves,wheel_curves;
static uint64_t tested[NP], rejected[NP], calibrated[NP], calibration_reject[NP];
static uint64_t candidates, curves, quotient_points, exact_tests, hit_count;
static uint64_t zero_norm, invalid_d, unsupported_d, noninvertible, covered;
static uint64_t symmetry_rejected;
static uint64_t rejected81, rejected_parity, reorders, calibration_samples;
static uint64_t current_index, current_ell, perm_seed=114, perm_stride, perm_offset;
static i128 current_a,current_b,current_c;
static int tile_mode;

static void fail(const char *s){fprintf(stderr,"%s\n",s);exit(2);}
static uint64_t parse(const char *s) {
  if(!s[0] || s[0]=='-')fail("Expected unsigned decimal integer");
  char *end;errno=0;unsigned long long v=strtoull(s,&end,10);
  if(errno || *end)fail("Invalid unsigned decimal integer");return (uint64_t)v;
}
static i128 signed_parse(const char *s) {
  int neg=*s=='-';if(neg)s++;
  uint64_t v=parse(s);if(v>INT64_MAX)fail("Signed quotient exceeds INT64_MAX");
  return neg?-(i128)v:(i128)v;
}
static void print128(i128 x) {
  char buf[48];int i=0;u128 n=x<0?(u128)(-x):(u128)x;
  do{buf[i++]=(char)('0'+n%10);n/=10;}while(n);
  if(x<0)putchar('-');while(i)putchar(buf[--i]);
}
static void quoted128(i128 x){putchar('"');print128(x);putchar('"');}
static int mod128(i128 x,int p){int r=(int)(x%p);return r<0?r+p:r;}
static i128 abs128(i128 x){return x<0?-x:x;}
static i128 floordiv(i128 a,i128 b){i128 q=a/b,r=a%b;return q-(r<0);}
static i128 ceildiv(i128 a,i128 b){return -floordiv(-a,b);}
static uint64_t gcd64(uint64_t a,uint64_t b){while(b){uint64_t c=a%b;a=b;b=c;}return a;}
static uint64_t mix64(uint64_t v){v=(v^(v>>30))*UINT64_C(0xbf58476d1ce4e5b9);v=(v^(v>>27))*UINT64_C(0x94d049bb133111eb);return v^(v>>31);}
static uint64_t mulmod(uint64_t a,uint64_t b,uint64_t m){return (uint64_t)((u128)a*b%m);}
static uint64_t inverse(uint64_t a,uint64_t m){
  i128 t=0,nt=1;uint64_t r=m,nr=a;
  while(nr){uint64_t q=r/nr,rr=r-q*nr;r=nr;nr=rr;i128 tt=t-(i128)q*nt;t=nt;nt=tt;}
  if(r!=1)return 0;t%=(i128)m;if(t<0)t+=m;return (uint64_t)t;
}
static GEN integer128(i128 v){
  int neg=v<0;u128 a=neg?(u128)(-v):(u128)v;
  GEN z=addii(shifti(utoi((ulong)(a>>64)),64),utoi((ulong)a));return neg?negi(z):z;
}
static void init_filters(long k){
  memset(masks,0,sizeof(masks));
  memset(allowed_z_count,0,sizeof(allowed_z_count));
  unsigned char pair[MOD3][MOD3]={0};int cube[MOD3];
  for(int x=0;x<MOD3;x++)cube[x]=x*x*x%MOD3;
  for(int x=0;x<MOD3;x++)for(int y=0;y<MOD3;y++)pair[(x+y)%MOD3][(cube[x]+cube[y])%MOD3]=1;
  for(int s=0;s<MOD3;s++)for(int z=0;z<MOD3;z++){
    ok81[s][z]=pair[s][mod128(k-cube[z],MOD3)];
    if(ok81[s][z])allowed_z[s][allowed_z_count[s]++]=(uint16_t)z;
  }
  for(int v=1;v<MOD3;v++)if(v%3)inv243[v]=(uint16_t)inverse(v,MOD3);
  memset(short_q_masks,0,sizeof(short_q_masks));
  for(int d=1;d<MOD3;d++)if(d%3){
    int eps=(k/3)%3,sm=d%3==(2*eps)%3?d:MOD3-d,slot=d-1-d/3;
    for(int u=0;u<307;u++)if(ok81[sm][d*(u%MOD3)%MOD3])
      short_q_masks[slot][u/64]|=UINT64_C(1)<<(u%64);
  }
  for(int j=0;j<NP;j++){
    int p=sieve_primes[j];unsigned char qr[64]={0};
    qr_masks[j]=0;
    for(int v=0;v<p;v++){qr[v*v%p]=1;qr_masks[j]|=UINT64_C(1)<<(v*v%p);}
    for(int s=0;s<p;s++)for(int z=0;z<p;z++){
      int disc=mod128((i128)3*s*(4*k-4*z*z*z-s*s*s),p);
      if(qr[disc])masks[j][s]|=UINT64_C(1)<<z;
    }
  }
}
static void set_policy(const char *s){
  if(!strncmp(s,"direct:",7)){interval_engine=-1;s+=7;}
  else if(!strncmp(s,"wheel:",6)){interval_engine=1;s+=6;}
  for(int j=0;j<NP;j++)order[j]=j;
  if(!strcmp(s,"fixed"))return;
  if(!strcmp(s,"adaptive")){adaptive=1;return;}
  char *copy=strdup(s);if(!copy)fail("Allocation failed");
  char *save=0,*tok=strtok_r(copy,",",&save);int seen[NP]={0},n=0;
  while(tok){
    uint64_t p=parse(tok);int j;for(j=0;j<NP && (uint64_t)sieve_primes[j]!=p;j++);
    if(j==NP || seen[j] || n==NP)fail("Policy must list every sieve prime exactly once");
    order[n++]=j;seen[j]=1;tok=strtok_r(0,",",&save);
  }
  free(copy);if(n!=NP)fail("Policy must list every sieve prime exactly once");
}
/* Every calibration sample tests every prime, preventing the censoring bias
 * from measuring a late filter only on candidates that survived earlier ones.
 * Samples are deterministic, periodic observations, not independent draws.
 * Sorting unconditional rejection rates is a heuristic, not claimed optimal.
 */
static void reorder(void){
  for(int i=1;i<NP;i++){
    int j=i,t=order[i];
    while(j && calibration_reject[t]>calibration_reject[order[j-1]]){order[j]=order[j-1];j--;}
    order[j]=t;
  }
  reorders++;
}
static void exact_check(long k,i128 s,i128 z,uint64_t d,uint64_t r,i128 q){
  pari_sp av=avma;GEN sg=integer128(s),zg=integer128(z),rem,v;
  GEN top=subii(mulsi(4,subii(stoi(k),powiu(zg,3))),powiu(sg,3));
  GEN square=dvmdii(top,mulsi(3,sg),&rem);
  if(signe(rem)==0 && signe(square)>=0 && Z_issquareall(square,&v)){
    GEN xp=addii(sg,v),yp=subii(sg,v);
    if(!mpodd(xp) && !mpodd(yp)){
      GEN x=shifti(xp,-1),y=shifti(yp,-1);
      if(cmpii(absi(zg),absi(x))<=0 && cmpii(absi(zg),absi(y))<=0){
        GEN sum=addii(addii(powiu(x,3),powiu(y,3)),powiu(zg,3));
        if(cmpis(sum,k))fail("Internal exact verification failed");
        hit_count++;
        printf("{\"type\":\"hit\",\"k\":%ld,\"index\":",k);
        if(tile_mode)printf("%"PRIu64,current_index);else printf("null");
        printf(",\"ell\":%"PRIu64",\"abc\":[",current_ell);
        quoted128(current_a);putchar(',');quoted128(current_b);putchar(',');quoted128(current_c);
        printf("],\"D\":\"%"PRIu64"\",\"r\":\"%"PRIu64"\",\"q\":",d,r);quoted128(q);
        pari_printf(",\"xyz\":[\"%Ps\",\"%Ps\",\"%Ps\"]}\n",x,y,zg);
        if(fflush(stdout)==EOF)fail("Hit stdout flush failed");
        struct stat hit_stat;int hit_fd=fileno(stdout);
        if(hit_fd<0 || fstat(hit_fd,&hit_stat))fail("Hit stdout metadata failed");
        if(S_ISREG(hit_stat.st_mode) && fsync(hit_fd))fail("Hit stdout sync failed");
      }
    }
  }
  avma=av;
}
static void prepare_prime(long k,int j,i128 s,uint64_t d,uint64_t r,int *rp,int *dp,uint64_t *allowed,uint16_t *ready){
  if(!(*ready&(1U<<j))){
    int p=sieve_primes[j];dp[j]=d%p;rp[j]=r%p;
    int sm=s>0?dp[j]:(dp[j]?p-dp[j]:0);allowed[j]=masks[j][sm];
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
    *ready|=1U<<j;
  }
}
static void sieve_quotient(long k,i128 s,uint64_t d,uint64_t r,i128 q,
                           int *rp,int *dp,uint64_t *allowed,uint16_t *ready,
                           uint64_t ordinal){
#ifdef CAMPAIGN_TRACE_Q
    CAMPAIGN_TRACE_Q(q); /* Compile-time test hook; absent from normal builds. */
#endif
    int pass=1;
    if((ordinal&1023)==0){
      for(int j=0;j<NP;j++){
        prepare_prime(k,j,s,d,r,rp,dp,allowed,ready);
        int zm=mod128(rp[j]+(i128)dp[j]*q,sieve_primes[j]);
        calibrated[j]++;calibration_reject[j]+=!((allowed[j]>>zm)&1);
      }
      calibration_samples++;
      if(adaptive && calibration_samples%64==0)reorder();
    }
    for(int n=0;n<NP;n++){
      int j=order[n];prepare_prime(k,j,s,d,r,rp,dp,allowed,ready);
      int zm=mod128(rp[j]+(i128)dp[j]*q,sieve_primes[j]);
      tested[j]++;if(!((allowed[j]>>zm)&1)){rejected[j]++;pass=0;break;}
    }
    if(pass){exact_tests++;exact_check(k,s,(i128)r+(i128)d*q,d,r,q);}
}
static i128 first_congruent(i128 lo,int residue,int modulus){
  return lo+mod128((i128)residue-mod128(lo,modulus),modulus);
}
static uint64_t residue_count(i128 first,i128 hi,int period){
  return first>hi?0:(uint64_t)((hi-first)/period)+1;
}
static void interval(long k,uint64_t d,uint64_t r,i128 lo,i128 hi){
  if(lo>hi){covered++;return;}
  if(hi-lo>20000002)fail("Quotient interval too large");
  int eps=(k/3)%3;
  i128 s=d%3==(uint64_t)((2*eps)%3)?(i128)d:-(i128)d;
  curves++;normalized_ready=0;
  int sm81=mod128(s,MOD3),rp[NP],dp[NP];uint64_t allowed[NP];uint16_t prepared=0;
  uint64_t base=quotient_points,length=(uint64_t)(hi-lo)+1;
  quotient_points+=length;
  if(interval_engine<0){
    direct_curves++;
    int z81=mod128((i128)r+(i128)d*lo,MOD3),delta81=d%MOD3;
    for(i128 q=lo;q<=hi;q++){
      int valid81=ok81[sm81][z81];z81+=delta81;if(z81>=MOD3)z81-=MOD3;
      if(!valid81){rejected81++;continue;}
      i128 z=(i128)r+(i128)d*q;
      if(mod128(k-s-z,2)){rejected_parity++;continue;}
      sieve_quotient(k,s,d,r,q,rp,dp,allowed,&prepared,base+(uint64_t)(q-lo)+1);
    }
  }else if(!interval_engine && length<1024){
    wheel_curves++;
    int dm=d%MOD3,slot=dm-1-dm/3;
    int position=(mod128(lo,MOD3)+inv243[dm]*(r%MOD3))%MOD3;
    int odd=d%2,required=mod128(k-s-r,2),parity=mod128(lo,2);
    const uint64_t *mask=short_q_masks[slot];
    for(uint64_t off=0;off<length;){
      int width=length-off<64?(int)(length-off):64,bit=position%64,word=position/64;
      uint64_t valid=mask[word]>>bit;if(bit)valid|=mask[word+1]<<(64-bit);
      if(width<64)valid&=(UINT64_C(1)<<width)-1;
      uint64_t kept=valid;
      if(odd)kept&=parity==required?UINT64_C(0x5555555555555555):UINT64_C(0xaaaaaaaaaaaaaaaa);
      else if(required)kept=0;
      rejected81+=width-__builtin_popcountll(valid);
      rejected_parity+=__builtin_popcountll(valid)-__builtin_popcountll(kept);
      while(kept){int b=__builtin_ctzll(kept);kept&=kept-1;
        i128 q=lo+off+b;sieve_quotient(k,s,d,r,q,rp,dp,allowed,&prepared,base+off+b+1);
      }
      off+=width;position+=width;if(position>=MOD3)position-=MOD3;parity^=width&1;
    }
  }else{
    wheel_curves++;
    /* Since gcd(D,243)=1, each allowed z residue corresponds bijectively
     * to q=(z-r)/D modulo243. If D is odd, parity picks exactly one of
     * its two lifts modulo486. If D is even, parity is fixed for the curve.
     * Count both rejection stages exactly using arithmetic progressions. */
    int inv=inv243[d%MOD3],rm=r%MOD3,odd=d%2;
    if(!inv)fail("Internal noninvertible quotient wheel D");
    int required_parity=mod128(k-s-r,2),period=odd?486:243;
    uint64_t passed243=0,passed_parity=0;
    for(int j=0;j<allowed_z_count[sm81];j++){
      int q243=mod128((allowed_z[sm81][j]-rm)*inv,MOD3);
      i128 first243=first_congruent(lo,q243,243);
      passed243+=residue_count(first243,hi,243);
      if(!odd && required_parity)continue;
      int residue=q243;
      if(odd && residue%2!=required_parity)residue+=243;
      i128 first=first_congruent(lo,residue,period);
      passed_parity+=residue_count(first,hi,period);
      for(i128 q=first;q<=hi;q+=period)
        sieve_quotient(k,s,d,r,q,rp,dp,allowed,&prepared,base+(uint64_t)(q-lo)+1);
    }
    rejected81+=length-passed243;
    rejected_parity+=passed243-passed_parity;
  }
}
static void frontier_curve(uint64_t d,uint64_t r,uint64_t ratio,uint64_t min_ratio){
  const i128 oldZ=(i128)1000000000000000000LL*10;
  const uint64_t oldD=(uint64_t)(oldZ/54);
  i128 zmin=d<=oldD?oldZ:(i128)100000000000000000LL;
  if((i128)min_ratio*d>zmin)zmin=(i128)min_ratio*d;
  i128 zmax=(i128)ratio*d;
  if(zmax<=zmin){covered++;return;}
  /* k=114 forces x,y,z=2 mod3; S=x+y=1 mod3. At these
   * heights the minimal coordinate z has the opposite sign from S. */
  if(d%3!=1)interval(114,d,r,floordiv(zmin-r,d)+1,floordiv(zmax-r,d));
  else interval(114,d,r,ceildiv(-zmax-r,d),ceildiv(-zmin-r,d)-1);
}
static uint64_t domain_total(uint64_t ell,uint64_t radius){
  uint64_t w=2*radius+1,t=2*(radius/ell)+1;
  u128 n=(u128)w*w*t;if(n>UINT64_MAX)fail("Domain exceeds uint64");return (uint64_t)n;
}
static void setup_permutation(uint64_t total,uint64_t ell,uint64_t radius){
  uint64_t v=mix64(perm_seed^mix64(ell)^mix64(radius));
  perm_offset=v%total;perm_stride=mix64(v+UINT64_C(0x9e3779b97f4a7c15))%total;
  if(!perm_stride)perm_stride=1;
  while(gcd64(perm_stride,total)!=1){perm_stride++;if(perm_stride==total)perm_stride=1;}
}
/* gamma and -gamma have the same |norm| and adjoint coefficients B,C.
 * Therefore they give exactly the same (D,r) and quotient interval. The
 * asymmetric a-residue boundary means -gamma is not always in this domain;
 * prune only when the opposite lattice t coordinate also lies in range.
 */
static int box_symmetry_duplicate(uint64_t ell,uint64_t radius,i128 a,i128 b,i128 c){
  if(!(c<0 || (c==0 && (b<0 || (b==0 && a<0)))))return 0;
  i128 opposite_a0=mod128(4*b+16*c,(int)ell);
  i128 numerator=-a-opposite_a0;
  if(numerator%ell)fail("Internal opposite lattice membership failed");
  i128 opposite_t=numerator/ell,h=radius/ell;
  return opposite_t>=-h && opposite_t<=h;
}
static void tile(uint64_t ell,uint64_t radius,uint64_t start,uint64_t count,uint64_t ratio,uint64_t min_ratio,uint64_t total){
  uint64_t w=2*radius+1,t=2*(radius/ell)+1;
  setup_permutation(total,ell,radius);current_ell=ell;
  for(uint64_t n=0;n<count;n++){
    candidates++;current_index=start+n;
    uint64_t v=(uint64_t)(((u128)current_index*perm_stride+perm_offset)%total);
    i128 tt=(i128)(v%t)-(i128)(radius/ell);v/=t;
    i128 b=(i128)(v%w)-(i128)radius,c=(i128)(v/w)-(i128)radius;
    i128 a=ell*tt+mod128(-4*b-16*c,(int)ell);
    current_a=a;current_b=b;current_c=c;
    if(box_symmetry_duplicate(ell,radius,a,b,c)){symmetry_rejected++;continue;}
    i128 norm=a*a*a+114*b*b*b+12996*c*c*c-342*a*b*c;
    if(norm%ell)fail("Internal lattice divisibility failed");
    if(!norm){zero_norm++;continue;}
    i128 dd=abs128(norm)/ell;
    if(dd<2 || dd%3==0){invalid_d++;continue;}
    if(dd>INT64_MAX){unsupported_d++;continue;}
    uint64_t d=(uint64_t)dd;
    const i128 oldZ=(i128)1000000000000000000LL*10;
    if((i128)ratio*d<=(d<=(uint64_t)(oldZ/54)?oldZ:(i128)100000000000000000LL)){covered++;continue;}
    i128 C=b*b-a*c,B=114*c*c-a*b,cm=C%d,bm=B%d;
    if(cm<0)cm+=d;if(bm<0)bm+=d;
    uint64_t inv=inverse((uint64_t)cm,d);
    if(!inv){noninvertible++;continue;}
    uint64_t r=mulmod((uint64_t)bm,inv,d);
    if(mulmod(mulmod(r,r,d),r,d)!=114%d)fail("Internal modular root identity failed");
    frontier_curve(d,r,ratio,min_ratio);
  }
}
static void print_stats(const char *mode,long k,uint64_t ell,uint64_t radius,uint64_t start,uint64_t count,uint64_t ratio,uint64_t min_ratio,uint64_t total,const char *policy,double seconds){
  printf("{\"type\":\"stats\",\"version\":1,\"complete\":true,\"mode\":\"%s\",\"k\":%ld,\"ell\":%"PRIu64",\"radius\":%"PRIu64",\"start\":%"PRIu64",\"count\":%"PRIu64",\"end\":%"PRIu64",\"total\":%"PRIu64",\"ratio\":%"PRIu64",\"min_ratio\":%"PRIu64",\"policy\":\"%s\",\"permutation_seed\":%"PRIu64",\"permutation_stride\":%"PRIu64",\"permutation_offset\":%"PRIu64",",mode,k,ell,radius,start,count,start+count,total,ratio,min_ratio,policy,perm_seed,perm_stride,perm_offset);
  printf("\"candidates\":%"PRIu64",\"curves\":%"PRIu64",\"quotient_points\":%"PRIu64",\"exact_tests\":%"PRIu64",\"hits\":%"PRIu64",\"zero_norm\":%"PRIu64",\"invalid_d\":%"PRIu64",\"unsupported_D\":%"PRIu64",\"noninvertible_C\":%"PRIu64",\"covered\":%"PRIu64",\"rejected_mod243\":%"PRIu64",\"rejected_parity\":%"PRIu64",\"reorders\":%"PRIu64",\"calibration_samples\":%"PRIu64",\"wall_seconds\":%.6f,\"final_order\":[",candidates,curves,quotient_points,exact_tests,hit_count,zero_norm,invalid_d,unsupported_d,noninvertible,covered,rejected81,rejected_parity,reorders,calibration_samples,seconds);
  for(int j=0;j<NP;j++)printf("%s%d",j?",":"",sieve_primes[order[j]]);
  printf("],\"filters\":[");
  for(int j=0;j<NP;j++)printf("%s{\"prime\":%d,\"tested\":%"PRIu64",\"rejected\":%"PRIu64",\"calibrated\":%"PRIu64",\"calibration_rejected\":%"PRIu64"}",j?",":"",sieve_primes[j],tested[j],rejected[j],calibrated[j],calibration_reject[j]);
  printf("],\"symmetry_rejected\":%"PRIu64",\"direct_curves\":%"PRIu64",\"wheel_curves\":%"PRIu64"}\n",symmetry_rejected,direct_curves,wheel_curves);
}
int main(int argc,char **argv){
  struct timespec ts;clock_gettime(CLOCK_MONOTONIC,&ts);double begun=ts.tv_sec+ts.tv_nsec*1e-9;
  long k=114;uint64_t ell=0,radius=0,start=0,count=0,ratio=0,min_ratio=0,total=0;
  uint64_t d=0,r=0;i128 lo=0,hi=0;const char *policy=0,*mode=0;
  if(argc>=8 && argc<=10 && !strcmp(argv[1],"tile")){
    mode="tile";tile_mode=1;ell=parse(argv[2]);radius=parse(argv[3]);start=parse(argv[4]);count=parse(argv[5]);ratio=parse(argv[6]);policy=argv[7];
    if(argc>=9)min_ratio=parse(argv[8]);if(argc>=10)perm_seed=parse(argv[9]);
    if((ell!=1 && ell!=5 && ell!=25) || radius<1 || radius>1000000 || ratio<4 || ratio>1000000 || min_ratio>=ratio)fail("Invalid tile bounds");
    total=domain_total(ell,radius);if(start>total || count>total-start)fail("Tile outside finite index domain");
    if(count>1000000000)fail("At most one billion inputs per tile (counter overflow guard)");
  }else if(argc==7 && !strcmp(argv[1],"curve")){
    mode="curve";k=(long)parse(argv[2]);d=parse(argv[3]);r=parse(argv[4]);ratio=parse(argv[5]);policy=argv[6];
    if(ratio<4 || ratio>10000000)fail("Invalid curve ratio");lo=-(i128)ratio;hi=r?(i128)ratio-1:(i128)ratio;
  }else if(argc==8 && !strcmp(argv[1],"interval")){
    mode="interval";k=(long)parse(argv[2]);d=parse(argv[3]);r=parse(argv[4]);lo=signed_parse(argv[5]);hi=signed_parse(argv[6]);policy=argv[7];
  }else fail("Usage: campaign_worker tile ELL RADIUS START COUNT RATIO POLICY [MIN_RATIO [PERM_SEED]] | curve K D ROOT RATIO POLICY | interval K D ROOT QLO QHI POLICY");
  if(!tile_mode && (k<3 || k>1000 || (k%9!=3 && k%9!=6) || d<2 || d>INT64_MAX || d%3==0 || r>=d || lo>hi || hi-lo>20000002))fail("Invalid curve parameters");
  if(!tile_mode && mulmod(mulmod(r,r,d),r,d)!=k%d)fail("Not a modular root");
  set_policy(policy);init_filters(k);pari_init(16000000,500000);
  if(tile_mode)tile(ell,radius,start,count,ratio,min_ratio,total);else interval(k,d,r,lo,hi);
  clock_gettime(CLOCK_MONOTONIC,&ts);double seconds=ts.tv_sec+ts.tv_nsec*1e-9-begun;
  print_stats(mode,k,ell,radius,start,count,ratio,min_ratio,total,policy,seconds);
  if(fflush(stdout)==EOF)fail("Worker stdout flush failed");pari_close();return 0;
}
