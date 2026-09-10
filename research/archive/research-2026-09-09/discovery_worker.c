/* Bounded blind-discovery experiment. Frozen checker is included read-only.
 * Coefficient shapes use floating point only to propose integer candidates.
 * Norms, modular roots, all rejection rules and final solutions are exact.
 */
#define main frozen_checker_main
#include "../phase3/checker.c"
#undef main
#include <math.h>
#include <sys/resource.h>

static uint64_t random_state;
static double cpu_now(void){struct timespec ts;clock_gettime(CLOCK_PROCESS_CPUTIME_ID,&ts);return ts.tv_sec+ts.tv_nsec*1e-9;}
static uint64_t random64(void){random_state+=UINT64_C(0x9e3779b97f4a7c15);return mix64(random_state);}
static uint64_t uniform_n(uint64_t n){uint64_t x,threshold=-n%n;do{x=random64();}while(x<threshold);return x%n;}
static i128 centered(long a){return (i128)uniform_n(2*a+1)-a;}
enum { MAP_SIZE=1<<19 };
typedef struct {uint64_t d,r;} curve_key;
static curve_key *seen;
static uint64_t seen_count;
static int insert_curve(uint64_t d,uint64_t r){
  uint64_t slot=mix64(d^mix64(r))&(MAP_SIZE-1);
  for(;;){if(!seen[slot].d){seen[slot]=(curve_key){d,r};seen_count++;return 1;}
    if(seen[slot].d==d && seen[slot].r==r)return 0;
    slot=(slot+1)&(MAP_SIZE-1);}
}
int main(int argc,char **argv){
  if(argc!=14)fail("Usage: discovery_worker K A DLO DHI R CPU_SECONDS MAX_ATTEMPTS SEED W0 W1 W2 W3 TRACE");
  double started=cpu_now(),budget=strtod(argv[6],0);
  long k=parse(argv[1]),A=parse(argv[2]),R=parse(argv[5]);
  uint64_t dlo=parse(argv[3]),dhi=parse(argv[4]),maximum=parse(argv[7]);random_state=parse(argv[8]);
  uint64_t weights[4],wsum=0,attempts=0,outside=0,invalid=0,duplicates=0,by_arm[4]={0};
  for(int i=0;i<4;i++){weights[i]=parse(argv[9+i]);wsum+=weights[i];}
  int trace=parse(argv[13]);
  if(k<3||k>1000||(k%9!=3&&k%9!=6)||A<1||A>128||dlo>=dhi||dhi>1000000000||R<4||R>512||budget<=0||budget>1||!maximum||maximum>10000000||wsum!=1000000)fail("Invalid experiment bound");
  seen=calloc(MAP_SIZE,sizeof(*seen));if(!seen)fail("Allocation failed");
  long double alpha=cbrtl((long double)k),alpha2=alpha*alpha;
  long ab=(long)ceill(A*alpha2),bb=(long)ceill(A*alpha),width=A/4?A/4:1;
  tile_mode=1;current_ell=1;set_policy("fixed");init_filters(k);pari_init(16000000,500000);
  for(uint64_t j=0;j<maximum;j++){
    if(j && !(j&255) && cpu_now()-started>=budget)break;
    if(seen_count>=MAP_SIZE/2)break;
    uint64_t pick=uniform_n(wsum);int arm=0;
    while(arm<3 && pick>=weights[arm]){pick-=weights[arm];arm++;}
    i128 a,b,c;
    if(arm==0){a=centered(A);b=centered(A);c=centered(A);}
    else if(arm==1){a=centered(ab);b=centered(bb);c=centered(A);}
    else if(arm==2){b=centered(A);c=centered(A);a=-(i128)roundl(alpha*b+alpha2*c)+centered(width);}
    else {c=centered(A);b=(i128)roundl(alpha*c)+centered(width);a=(i128)roundl(alpha2*c)+centered(width);}
    attempts++;by_arm[arm]++;
    i128 n=a*a*a+k*b*b*b+k*k*c*c*c-3*k*a*b*c,dd=abs128(n),B=k*c*c-a*b,C=b*b-a*c;
    if(trace && j<64){printf("{\"type\":\"sample\",\"index\":%"PRIu64",\"arm\":%d,\"abc\":[",j,arm);quoted128(a);putchar(',');quoted128(b);putchar(',');quoted128(c);printf("],\"norm\":");quoted128(n);puts("}");}
    if(dd<=dlo||dd>dhi){outside++;continue;}
    if(dd<2||dd%3==0){invalid++;continue;}
    uint64_t d=(uint64_t)dd,cm=(uint64_t)((C%d+d)%d),bm=(uint64_t)((B%d+d)%d),inv=inverse(cm,d);
    if(!inv){invalid++;continue;}
    uint64_t r=mulmod(bm,inv,d);
    if(mulmod(mulmod(r,r,d),r,d)!=(uint64_t)k%d)fail("Invalid generated modular root");
    if(!insert_curve(d,r)){duplicates++;continue;}
    current_index=j;current_a=a;current_b=b;current_c=c;
    uint64_t before=hit_count;
    interval(k,d,r,-R-1,R+1);
    if(hit_count>before)printf("{\"type\":\"hit_time\",\"cpu_seconds\":%.9f,\"index\":%"PRIu64"}\n",cpu_now()-started,j);
  }
  double cpu=cpu_now()-started;
  printf("{\"type\":\"discovery_stats\",\"k\":%ld,\"radius\":%ld,\"attempts\":%"PRIu64",\"outside_shell\":%"PRIu64",\"invalid\":%"PRIu64",\"duplicates\":%"PRIu64",\"unique_curves\":%"PRIu64",\"quotient_points\":%"PRIu64",\"exact_tests\":%"PRIu64",\"raw_hits\":%"PRIu64",\"cpu_seconds\":%.9f,\"attempts_by_family\":[%"PRIu64",%"PRIu64",%"PRIu64",%"PRIu64"]}\n",k,A,attempts,outside,invalid,duplicates,seen_count,quotient_points,exact_tests,hit_count,cpu,by_arm[0],by_arm[1],by_arm[2],by_arm[3]);
  pari_close();free(seen);return 0;
}
