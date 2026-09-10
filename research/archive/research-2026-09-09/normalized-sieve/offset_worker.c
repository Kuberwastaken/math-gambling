/* Phase3 deterministic positive cancellation offsets. Prior phases remain read-only.
 * All decisions that remove candidates use exact integer arithmetic. Exposure
 * and timings are floating-point measurement proxies, never exclusion rules.
 */
#define main frozen_campaign_main
#include "checker.c"
#undef main
#include <sys/resource.h>

static const i128 offset_den=(i128)1000000000000000000LL;
static const i128 offset_alpha=(i128)4848807585839879338LL;
static const i128 offset_alpha2=(i128)23*1000000000000000000LL+510935004498358840LL;
static const uint64_t historical_D0=UINT64_C(185185185185185185);
typedef struct {i128 lo,hi;} offset_range;
typedef struct {i128 b,c,base,p,q;uint64_t ell;} offset_row;
static uint64_t offset_Dlo,offset_Dhi,offset_tlo,offset_thi,offset_ratio,offset_min_ratio;
static uint64_t outside_shell,eligible_inputs,rows_done,empty_rows,norm_evaluations,recurrence_steps;
static uint64_t rejected_signed,rejected_signed8,rejected_signed361;
static unsigned char bad8[8],bad361[361];
static double exposure_sum;

static uint64_t offset_sqrt64(uint64_t n){
  if(!n)return 0;
  uint64_t x=UINT64_C(1)<<((64-__builtin_clzll(n)+1)/2);
  for(;;){uint64_t y=(x+n/x)/2;if(y>=x)return x;x=y;}
}
static i128 offset_base(uint64_t ell,i128 b,i128 c){
  i128 residue=mod128(-4*b-16*c,(int)ell);
  i128 n=-offset_alpha*b-offset_alpha2*c-residue*offset_den,d=ell*offset_den;
  return residue+ell*floordiv(2*n+d,2*d);
}
static offset_row make_offset_row(uint64_t ell,i128 b,i128 c){
  offset_row r={b,c,offset_base(ell,b,c),-342*b*c,114*b*b*b+12996*c*c*c,ell};return r;
}
static i128 offset_norm(const offset_row *row,i128 t){
  norm_evaluations++;i128 a=row->base+row->ell*t;return a*a*a+row->p*a+row->q;
}
static i128 first_offset_ge(const offset_row *row,i128 lo,i128 hi,i128 target,int direction){
  hi++;
  while(lo<hi){i128 mid=lo+(hi-lo)/2;if(direction*offset_norm(row,mid)<target)lo=mid+1;else hi=mid;}
  return lo;
}
static int offset_range_compare(const void *aa,const void *bb){
  const offset_range *a=aa,*b=bb;return a->lo<b->lo?-1:a->lo>b->lo;
}
/* Integer derivative partition covers every lattice t, including rounding and
 * turning-point boundaries. Positive offsets imply N>0; negative norm branches
 * are outside this explicitly positive-real-embedding generator domain. */
static int offset_ranges(const offset_row *row,offset_range out[3]){
  i128 tmin=offset_tlo,tmax=offset_thi;offset_range pieces[3];int dir[3],np=0,n=0;
  if(row->b*row->c<=0){pieces[np]=(offset_range){tmin,tmax};dir[np++]=1;}
  else{
    i128 h=offset_sqrt64((uint64_t)(114*row->b*row->c));
    i128 l=ceildiv(-h-row->base,row->ell),u=floordiv(h-row->base,row->ell);
    pieces[np]=(offset_range){tmin,l-1<tmax?l-1:tmax};dir[np++]=1;
    pieces[np]=(offset_range){l>tmin?l:tmin,u<tmax?u:tmax};dir[np++]=-1;
    pieces[np]=(offset_range){u+1>tmin?u+1:tmin,tmax};dir[np++]=1;
  }
  i128 lower=(i128)row->ell*(offset_Dlo+1),upper=(i128)row->ell*offset_Dhi;
  for(int j=0;j<np;j++){
    i128 lo=pieces[j].lo,hi=pieces[j].hi;if(lo>hi)continue;
    int s=dir[j];i128 left=s*offset_norm(row,lo),right=s*offset_norm(row,hi);
    if(left>right)fail("Offset monotone segment failed");
    i128 low=lower,high=upper;if(s<0){low=-upper;high=-lower;}
    if(high<left || low>right)continue;
    i128 first=low<=left?lo:first_offset_ge(row,lo,hi,low,s);
    i128 last=high>=right?hi:first_offset_ge(row,lo,hi,high+1,s)-1;
    if(first<=last)out[n++]=(offset_range){first,last};
  }
  qsort(out,n,sizeof(*out),offset_range_compare);
  int kept=0;
  for(int j=0;j<n;j++){
    if(kept && out[j].lo<=out[kept-1].hi+1){if(out[j].hi>out[kept-1].hi)out[kept-1].hi=out[j].hi;}
    else out[kept++]=out[j];
  }
  return kept;
}
static void init_signed_filters(void){
  const int f8[]={0,4,6},f361[]={0,19,76,95,114,133,171,209,304,323};
  for(size_t i=0;i<sizeof(f8)/sizeof(*f8);i++)bad8[f8[i]]=1;
  for(size_t i=0;i<sizeof(f361)/sizeof(*f361);i++)bad361[f361[i]]=1;
}
static int signed_reject(uint64_t d){
  i128 s=d%3==1?(i128)d:-(i128)d;
  if(bad8[mod128(s,8)]){rejected_signed++;rejected_signed8++;return 1;}
  if(bad361[mod128(s,361)]){rejected_signed++;rejected_signed361++;return 1;}
  return 0;
}
static void check_offset_D(const offset_row *row,uint64_t index,i128 t,i128 dd,int prefiltered){
  if(!prefiltered)eligible_inputs++;
  if(dd<=offset_Dlo || dd>offset_Dhi)fail("Offset shell endpoint failed");
  current_index=index;current_ell=row->ell;current_a=row->base+row->ell*t;current_b=row->b;current_c=row->c;
#ifdef OFFSET_TRACE_CANDIDATE
  OFFSET_TRACE_CANDIDATE(index,t,current_a,current_b,current_c,dd);
#endif
  if(!prefiltered){
    if(dd<2 || dd%3==0){invalid_d++;return;}
    if(dd>INT64_MAX){unsupported_d++;return;}
    if(signed_reject((uint64_t)dd))return;
  }
  uint64_t d=(uint64_t)dd;
  i128 a=current_a,b=row->b,c=row->c,B=114*c*c-a*b,C=b*b-a*c,cm=C%d,bm=B%d;
  if(cm<0)cm+=d;if(bm<0)bm+=d;
  uint64_t inv=inverse((uint64_t)cm,d);if(!inv){noninvertible++;return;}
  uint64_t r=mulmod((uint64_t)bm,inv,d);
  if(mulmod(mulmod(r,r,d),r,d)!=114%d)fail("Offset modular root identity failed");
#ifdef OFFSET_TRACE_ROOT
  OFFSET_TRACE_ROOT(index,t,d,r);
#endif
  uint64_t before=curves;
  frontier_curve(d,r,offset_ratio,offset_min_ratio);
  if(curves>before)exposure_sum+=(double)historical_D0/(double)d;
}
/* D(t)=N(base+ell*t)/ell is an integral cubic. The period456 wheel
 * exactly batches the existing checks, preserving their precedence. N mod19
 * is a^3, and at19|a, D mod361=19*(6*ell^-1*b^3 mod19). The sign
 * depends on t mod3, so the361 gate has period57; lcm(24,57)=456. */
#define ROW_PERIOD 456
typedef struct {uint16_t prefix[4][ROW_PERIOD+1],good[ROW_PERIOD],n;} offset_wheel;
static void make_offset_wheel(const offset_row *row,offset_wheel *w){
  memset(w,0,sizeof(*w));
  i128 ell=row->ell,a=row->base,n=a*a*a+row->p*a+row->q;
  if(n%ell)fail("Offset wheel lattice divisibility failed");
  int d=mod128(n/ell,24),d1=mod128(3*a*a+3*ell*a+ell*ell+row->p,24);
  int d2=mod128(6*ell*(a+ell),24),d3=mod128(6*ell*ell,24),d24[24];
  for(int j=0;j<24;j++){d24[j]=d;d=(d+d1)%24;d1=(d1+d2)%24;d2=(d2+d3)%24;}
  int inv=row->ell==1?1:row->ell==5?4:16,b19=mod128(row->b,19);
  int a19=mod128(row->base,19),special=(19-a19)*inv%19;
  int at19=19*(6*inv*b19*b19*b19%19);
  for(int j=0;j<ROW_PERIOD;j++){
    int dm=d24[j%24],sign=dm%3==1?1:-1,category=0;
    if(dm%3==0)category=1;
    else if(bad8[(sign*dm+24)%8])category=2;
    else if(j%19==special && bad361[(sign*at19+361)%361])category=3;
    for(int c=0;c<4;c++)w->prefix[c][j+1]=w->prefix[c][j]+(category==c);
    if(!category)w->good[w->n++]=j;
  }
}
static uint64_t wheel_prefix(const offset_wheel *w,int category,uint64_t end){
  return (end/ROW_PERIOD)*w->prefix[category][ROW_PERIOD]+w->prefix[category][end%ROW_PERIOD];
}
/* Skips must advance all forward differences by the actual h, not one step.
 * With domain t<=8191, |a|<171 million and ell<=25, every jump product is
 * safely below signed128 limits, including when initialization t=0 is used. */
static void offset_jump(i128 h,i128 *d,i128 *d1,i128 *d2,i128 d3){
  i128 h2=h*(h-1)/2,h3=h*(h-1)*(h-2)/6;
  *d+=h*(*d1)+h2*(*d2)+h3*d3;*d1+=h*(*d2)+h2*d3;*d2+=h*d3;
}
static void visit_offset_range(const offset_row *row,uint64_t index,i128 lo,i128 hi,int test_membership,const offset_wheel *wheel){
  if(lo>hi)return;
  i128 ell=row->ell,a=row->base+ell*lo,norm=offset_norm(row,lo);
  if(norm<=0 || norm%ell)fail("Positive offset norm/lattice identity failed");
  i128 d=norm/ell,d1=3*a*a+3*ell*a+ell*ell+row->p,d2=6*ell*(a+ell),d3=6*ell*ell;
  recurrence_steps+=(uint64_t)(hi-lo); /* Logical t distance, including skipped positions. */
  if(wheel){
    uint64_t l=(uint64_t)lo,h=(uint64_t)hi;
    eligible_inputs+=h-l+1;
    invalid_d+=wheel_prefix(wheel,1,h+1)-wheel_prefix(wheel,1,l);
    uint64_t s8=wheel_prefix(wheel,2,h+1)-wheel_prefix(wheel,2,l);
    uint64_t s361=wheel_prefix(wheel,3,h+1)-wheel_prefix(wheel,3,l);
    rejected_signed8+=s8;rejected_signed361+=s361;rejected_signed+=s8+s361;
    if(!wheel->n)return;
    uint64_t cycle=(l/ROW_PERIOD)*ROW_PERIOD;int j=0;
    while(j<wheel->n && wheel->good[j]<l%ROW_PERIOD)j++;
    if(j==wheel->n){j=0;cycle+=ROW_PERIOD;}
    i128 t=cycle+wheel->good[j];if(t>hi)return;
    offset_jump(t-lo,&d,&d1,&d2,d3);
    for(;;){
      check_offset_D(row,index,t,d,1);
      if(++j==wheel->n){j=0;cycle+=ROW_PERIOD;}
      i128 next=cycle+wheel->good[j];if(next>hi)break;
      offset_jump(next-t,&d,&d1,&d2,d3);t=next;
    }
  }else{
    for(i128 t=lo;t<=hi;t++){
      if(!test_membership || (d>(i128)offset_Dlo && d<=(i128)offset_Dhi))check_offset_D(row,index,t,d,0);
      if(t<hi){d+=d1;d1+=d2;d2+=d3;}
    }
  }
}
static void offset_tile(uint64_t ell,uint64_t radius,uint64_t start,uint64_t count,uint64_t total,int direct,int probe){
  setup_permutation(total,ell,radius);uint64_t width=2*radius+1;
  candidates=count*(offset_thi-offset_tlo+1);
  for(uint64_t index=start;index<start+count;index++){
    rows_done++;
    uint64_t v=(uint64_t)(((u128)index*perm_stride+perm_offset)%total);
    offset_row row=make_offset_row(ell,(i128)(v%width)-radius,(i128)(v/width)-radius);
    uint64_t before=eligible_inputs;
    if(direct)visit_offset_range(&row,index,offset_tlo,offset_thi,1,0);
    else{
      offset_range ranges[3];int n=offset_ranges(&row,ranges);
      if(probe){
        printf("{\"type\":\"row\",\"index\":%"PRIu64",\"b\":",index);quoted128(row.b);
        printf(",\"c\":");quoted128(row.c);printf(",\"base\":");quoted128(row.base);printf(",\"intervals\":[");
        for(int j=0;j<n;j++){if(j)putchar(',');putchar('[');quoted128(ranges[j].lo);putchar(',');quoted128(ranges[j].hi);putchar(']');}
        printf("]}\n");
      }
      offset_wheel wheel;const offset_wheel *wp=0;uint64_t length=0;
      for(int j=0;j<n;j++)length+=(uint64_t)(ranges[j].hi-ranges[j].lo+1);
      /* Keep tiny rows scalar: setup is not automatically amortized. Trace
       * candidate builds retain every eligible-position callback; root traces
       * remain available with the actual wheel path. Dlo>=1 handles D<2. */
#ifndef OFFSET_TRACE_CANDIDATE
      if(length>=256 && offset_Dlo>=1){make_offset_wheel(&row,&wheel);wp=&wheel;}
#endif
      for(int j=0;j<n;j++)visit_offset_range(&row,index,ranges[j].lo,ranges[j].hi,0,wp);
    }
    empty_rows+=before==eligible_inputs;
  }
  outside_shell=candidates-eligible_inputs;
}
static double offset_cpu(void){struct rusage r;getrusage(RUSAGE_SELF,&r);return r.ru_utime.tv_sec+r.ru_utime.tv_usec*1e-6+r.ru_stime.tv_sec+r.ru_stime.tv_usec*1e-6;}
static void offset_stats(uint64_t ell,uint64_t radius,uint64_t start,uint64_t count,uint64_t total,const char *policy,const char *method,double cpu,double wall){
  printf("{\"type\":\"stats\",\"version\":2,\"complete\":true,\"kind\":\"offset\",\"mode\":\"row_tile\",\"k\":114,\"ell\":%"PRIu64",\"radius\":%"PRIu64",\"tlo\":%"PRIu64",\"thi\":%"PRIu64",\"Dlo\":%"PRIu64",\"Dhi\":%"PRIu64",\"start\":%"PRIu64",\"count\":%"PRIu64",\"end\":%"PRIu64",\"total\":%"PRIu64",\"ratio\":%"PRIu64",\"min_ratio\":%"PRIu64",\"policy\":\"%s\",\"method\":\"%s\",\"permutation_seed\":%"PRIu64",\"permutation_stride\":%"PRIu64",\"permutation_offset\":%"PRIu64",",ell,radius,offset_tlo,offset_thi,offset_Dlo,offset_Dhi,start,count,start+count,total,offset_ratio,offset_min_ratio,policy,method,perm_seed,perm_stride,perm_offset);
  printf("\"rows\":%"PRIu64",\"empty_rows\":%"PRIu64",\"candidates\":%"PRIu64",\"eligible_inputs\":%"PRIu64",\"outside_shell\":%"PRIu64",\"rejected_signed\":%"PRIu64",\"rejected_signed8\":%"PRIu64",\"rejected_signed361\":%"PRIu64",\"invalid_d\":%"PRIu64",\"noninvertible_C\":%"PRIu64",\"unsupported_D\":%"PRIu64",\"covered\":%"PRIu64",\"curves\":%"PRIu64",\"zero_norm\":%"PRIu64",\"symmetry_rejected\":0,",rows_done,empty_rows,candidates,eligible_inputs,outside_shell,rejected_signed,rejected_signed8,rejected_signed361,invalid_d,noninvertible,unsupported_d,covered,curves,zero_norm);
  printf("\"quotient_points\":%"PRIu64",\"rejected_mod243\":%"PRIu64",\"rejected_parity\":%"PRIu64",\"exact_tests\":%"PRIu64",\"hits\":%"PRIu64",\"reorders\":%"PRIu64",\"calibration_samples\":%"PRIu64",\"direct_curves\":%"PRIu64",\"wheel_curves\":%"PRIu64",\"norm_evaluations\":%"PRIu64",\"recurrence_steps\":%"PRIu64",\"exposure_sum\":%.17g,\"cpu_seconds\":%.6f,\"wall_seconds\":%.6f,\"final_order\":[",quotient_points,rejected81,rejected_parity,exact_tests,hit_count,reorders,calibration_samples,direct_curves,wheel_curves,norm_evaluations,recurrence_steps,exposure_sum,cpu,wall);
  for(int j=0;j<NP;j++)printf("%s%d",j?",":"",sieve_primes[order[j]]);
  printf("],\"filters\":[");
  for(int j=0;j<NP;j++)printf("%s{\"prime\":%d,\"tested\":%"PRIu64",\"rejected\":%"PRIu64",\"calibrated\":%"PRIu64",\"calibration_rejected\":%"PRIu64"}",j?",":"",sieve_primes[j],tested[j],rejected[j],calibrated[j],calibration_reject[j]);
  printf("]}\n");
}
int main(int argc,char **argv){
  if(argc>=2 && (!strcmp(argv[1],"curve") || !strcmp(argv[1],"interval")))return frozen_campaign_main(argc,argv);
  if(argc!=15 || strcmp(argv[1],"tile"))fail("Usage: offset_worker tile ELL RADIUS TLO THI DLO DHI START ROWS RATIO MIN_RATIO POLICY METHOD SEED");
  uint64_t ell=parse(argv[2]),radius=parse(argv[3]);offset_tlo=parse(argv[4]);offset_thi=parse(argv[5]);
  offset_Dlo=parse(argv[6]);offset_Dhi=parse(argv[7]);uint64_t start=parse(argv[8]),count=parse(argv[9]);
  offset_ratio=parse(argv[10]);offset_min_ratio=parse(argv[11]);const char *policy=argv[12],*method=argv[13];perm_seed=parse(argv[14]);
  int direct=!strcmp(method,"direct"),probe=!strcmp(method,"probe");
  if(!direct && !probe && strcmp(method,"inversion"))fail("Unknown offset method");
  if((ell!=1 && ell!=5 && ell!=25) || !radius || radius>6000000 || offset_tlo<8 || offset_tlo>offset_thi || offset_thi>8191 || offset_Dlo>=offset_Dhi || offset_Dhi>INT64_MAX || offset_ratio<4 || offset_ratio>1000000 || offset_min_ratio>=offset_ratio || count>1000000)fail("Invalid offset bounds");
  uint64_t total=(2*radius+1)*(2*radius+1);if(start>total || count>total-start)fail("Offset row tile outside domain");
  if(probe && count>2000)fail("Probe limited to2000rows");
  struct timespec ts;clock_gettime(CLOCK_MONOTONIC,&ts);double begun=ts.tv_sec+ts.tv_nsec*1e-9,cpu=offset_cpu();
  tile_mode=1;set_policy(policy);init_filters(114);init_signed_filters();pari_init(16000000,500000);
  offset_tile(ell,radius,start,count,total,direct,probe);
  if(candidates!=outside_shell+rejected_signed+invalid_d+noninvertible+unsupported_d+covered+curves)fail("Offset candidate conservation failed");
  if(quotient_points!=rejected81+rejected_parity+exact_tests+rejected[0]+rejected[1]+rejected[2]+rejected[3]+rejected[4]+rejected[5]+rejected[6]+rejected[7]+rejected[8]+rejected[9]+rejected[10]+rejected[11]+rejected[12]+rejected[13]+rejected[14])fail("Offset quotient conservation failed");
  clock_gettime(CLOCK_MONOTONIC,&ts);double wall=ts.tv_sec+ts.tv_nsec*1e-9-begun;
  offset_stats(ell,radius,start,count,total,policy,method,offset_cpu()-cpu,wall);
  if(fflush(stdout)==EOF)fail("Worker stdout flush failed");pari_close();return 0;
}
