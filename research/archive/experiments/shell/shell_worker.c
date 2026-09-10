/* Experimental exact D-shell generator. This file does not change production.
 * Shared integer checking code is included read-only from the frozen worker.
 */
#define main frozen_campaign_main
#include "../../campaign_worker.c"
#undef main
#include <sys/resource.h>

typedef struct {i128 lo,hi;} shell_range;
typedef struct {i128 b,c,a0,p,q;uint64_t ell;} shell_row;
static uint64_t shell_norm_evaluations, shell_recurrence_steps, shell_empty_rows;
static uint64_t shell_eligible, shell_positions, shell_rows;
static uint64_t shell_D0,shell_radius,shell_twidth,shell_ratio,shell_min_ratio;

static uint64_t exact_sqrt64(uint64_t n){
  if(!n)return 0;
  uint64_t x=UINT64_C(1)<<((64-__builtin_clzll(n)+1)/2);
  for(;;){uint64_t y=(x+n/x)/2;if(y>=x)return x;x=y;}
}
static shell_row make_row(uint64_t ell,i128 b,i128 c){
  shell_row r={b,c,mod128(-4*b-16*c,(int)ell),-342*b*c,
               114*b*b*b+12996*c*c*c,ell};
  return r;
}
static i128 row_norm(const shell_row *row,i128 t){
  shell_norm_evaluations++;
  i128 a=row->a0+row->ell*t;return a*a*a+row->p*a+row->q;
}
static i128 first_norm_ge(const shell_row *row,i128 lo,i128 hi,i128 target,int direction){
  hi++;
  while(lo<hi){
    i128 mid=lo+(hi-lo)/2;
    if(direction*row_norm(row,mid)<target)lo=mid+1;else hi=mid;
  }
  return lo;
}
static int range_compare(const void *aa,const void *bb){
  const shell_range *a=aa,*b=bb;return a->lo<b->lo?-1:a->lo>b->lo;
}
/* For bc>0, the derivative vanishes at ±sqrt(114bc). If h is its
 * integer floor, all integer a split without gaps into a<=-h-1,
 * -h<=a<=h, a>=h+1. N is increasing/decreasing/increasing there.
 * No floating-point turning point or endpoint enters an exclusion.
 */
static int shell_ranges(const shell_row *row,uint64_t radius,uint64_t D0,shell_range out[6]){
  i128 tmin=-(i128)(radius/row->ell),tmax=radius/row->ell;
  shell_range pieces[3];int direction[3],np=0,n=0;
  if(row->b*row->c<=0){pieces[np]=(shell_range){tmin,tmax};direction[np++]=1;}
  else{
    i128 h=exact_sqrt64((uint64_t)(114*row->b*row->c));
    i128 l=ceildiv(-h-row->a0,row->ell),u=floordiv(h-row->a0,row->ell);
    pieces[np]=(shell_range){tmin,l-1<tmax?l-1:tmax};direction[np++]=1;
    pieces[np]=(shell_range){l>tmin?l:tmin,u<tmax?u:tmax};direction[np++]=-1;
    pieces[np]=(shell_range){u+1>tmin?u+1:tmin,tmax};direction[np++]=1;
  }
  i128 lower=(i128)row->ell*(D0+1),upper=(i128)row->ell*2*D0;
  for(int j=0;j<np;j++){
    i128 lo=pieces[j].lo,hi=pieces[j].hi;if(lo>hi)continue;
    int sign=direction[j];
    i128 val_lo=sign*row_norm(row,lo),val_hi=sign*row_norm(row,hi);
    if(val_lo>val_hi)fail("Internal monotone segment failure");
    for(int side=0;side<2;side++){
      i128 a=side?-upper:lower,b=side?-lower:upper;
      if(sign<0){i128 t=-b;b=-a;a=t;}
      if(b<val_lo || a>val_hi)continue;
      i128 first=a<=val_lo?lo:first_norm_ge(row,lo,hi,a,sign);
      i128 last=b>=val_hi?hi:first_norm_ge(row,lo,hi,b+1,sign)-1;
      if(first<=last)out[n++]=(shell_range){first,last};
    }
  }
  qsort(out,n,sizeof(*out),range_compare);
  int kept=0;
  for(int j=0;j<n;j++){
    if(kept && out[j].lo<=out[kept-1].hi+1){
      if(out[j].hi>out[kept-1].hi)out[kept-1].hi=out[j].hi;
    }else out[kept++]=out[j];
  }
  return kept;
}
static void check_shell_candidate(const shell_row *row,uint64_t row_index,i128 t,i128 norm){
  candidates++;shell_eligible++;
  i128 a=row->a0+row->ell*t,b=row->b,c=row->c;
  current_a=a;current_b=b;current_c=c;current_ell=row->ell;
  current_index=row_index*shell_twidth+(uint64_t)(t+shell_radius/row->ell);
  if(box_symmetry_duplicate(row->ell,shell_radius,a,b,c)){symmetry_rejected++;return;}
  if(norm%row->ell)fail("Internal norm lattice divisibility failure");
  i128 dd=abs128(norm)/row->ell;
  if(dd<=shell_D0 || dd>(i128)2*shell_D0)fail("Internal shell interval failure");
  if(dd<2 || dd%3==0){invalid_d++;return;}
  if(dd>INT64_MAX){unsupported_d++;return;}
  uint64_t d=(uint64_t)dd;
  i128 C=b*b-a*c,B=114*c*c-a*b,cm=C%d,bm=B%d;
  if(cm<0)cm+=d;if(bm<0)bm+=d;
  uint64_t inv=inverse((uint64_t)cm,d);
  if(!inv){noninvertible++;return;}
  uint64_t r=mulmod((uint64_t)bm,inv,d);
  if(mulmod(mulmod(r,r,d),r,d)!=114%d)fail("Internal modular root failure");
#ifdef SHELL_TRACE_ROOT
  SHELL_TRACE_ROOT(row_index,t,d,r);
#endif
  frontier_curve(d,r,shell_ratio,shell_min_ratio);
}
/* Both methods use the same exact finite-difference recurrence. The direct
 * reference still visits every lattice coefficient and tests shell membership.
 * The inversion method enters only the proved eligible t intervals. */
static void visit_range(const shell_row *row,uint64_t index,i128 lo,i128 hi,int membership_test){
  if(lo>hi)return;
  /* In a negative (c,b) row, the opposite t is -t when a0=0 and
   * -t-1 otherwise. Only the latter row's t=T endpoint can lack an
   * opposite inside [-T,T]. Count proved duplicate ranges in bulk. */
  if(!membership_test && (row->c<0 || (!row->c && row->b<0))){
    i128 T=shell_radius/row->ell;
    int retain_boundary=row->a0!=0 && lo<=T && T<=hi;
    uint64_t skipped=(uint64_t)(hi-lo)+1-retain_boundary;
    candidates+=skipped;shell_eligible+=skipped;symmetry_rejected+=skipped;
    if(!retain_boundary)return;
    lo=hi=T;
  }
  i128 ell=row->ell,a=row->a0+ell*lo;
  i128 norm=row_norm(row,lo);
  i128 delta=ell*(3*a*a+3*ell*a+ell*ell+row->p);
  i128 delta2=6*ell*ell*(a+ell),delta3=6*ell*ell*ell;
  i128 lower=ell*(shell_D0+1),upper=ell*2*shell_D0;
  for(i128 t=lo;t<=hi;t++){
    if(!membership_test || (abs128(norm)>=lower && abs128(norm)<=upper))
      check_shell_candidate(row,index,t,norm);
    if(t<hi){norm+=delta;delta+=delta2;delta2+=delta3;shell_recurrence_steps++;}
  }
}
static void run_shell(uint64_t ell,uint64_t radius,uint64_t start,uint64_t count,int direct,int probe){
  uint64_t width=2*radius+1,total=width*width;
  setup_permutation(total,ell,radius);
  shell_twidth=2*(radius/ell)+1;
  shell_positions=count*shell_twidth;
  for(uint64_t i=start;i<start+count;i++){
    shell_rows++;
    uint64_t v=(uint64_t)(((u128)i*perm_stride+perm_offset)%total);
    shell_row row=make_row(ell,(i128)(v%width)-radius,(i128)(v/width)-radius);
    if(direct){
      uint64_t before=shell_eligible;
      visit_range(&row,i,-(i128)(radius/ell),radius/ell,1);
      shell_empty_rows+=shell_eligible==before;
    }else{
      shell_range ranges[6];int n=shell_ranges(&row,radius,shell_D0,ranges);
      shell_empty_rows+=n==0;
      if(probe){
        printf("{\"type\":\"row\",\"row_index\":%"PRIu64",\"b\":",i);quoted128(row.b);
        printf(",\"c\":");quoted128(row.c);printf(",\"a0\":");quoted128(row.a0);printf(",\"intervals\":[");
        for(int j=0;j<n;j++){
          if(j)putchar(',');putchar('[');quoted128(ranges[j].lo);putchar(',');quoted128(ranges[j].hi);putchar(']');
          shell_eligible+=(uint64_t)(ranges[j].hi-ranges[j].lo)+1;
        }
        printf("]}\n");
      }else for(int j=0;j<n;j++)visit_range(&row,i,ranges[j].lo,ranges[j].hi,0);
    }
  }
}
static double process_cpu(void){struct rusage r;getrusage(RUSAGE_SELF,&r);return r.ru_utime.tv_sec+r.ru_utime.tv_usec*1e-6+r.ru_stime.tv_sec+r.ru_stime.tv_usec*1e-6;}
int main(int argc,char **argv){
  if(argc<10 || argc>12 || strcmp(argv[1],"tile"))fail("Usage: shell_worker tile ELL RADIUS D0 START ROWS RATIO POLICY inversion|direct|probe [MIN_RATIO [SEED]]");
  uint64_t ell=parse(argv[2]),A=parse(argv[3]);shell_D0=parse(argv[4]);
  uint64_t start=parse(argv[5]),count=parse(argv[6]);shell_ratio=parse(argv[7]);
  const char *policy=argv[8],*method=argv[9];
  if(argc>=11)shell_min_ratio=parse(argv[10]);if(argc>=12)perm_seed=parse(argv[11]);
  int direct=!strcmp(method,"direct"),probe=!strcmp(method,"probe");
  if(!direct && !probe && strcmp(method,"inversion"))fail("Unknown shell method");
  if((ell!=1 && ell!=5 && ell!=25) || A<1 || A>1000000 || !shell_D0 || shell_D0>INT64_MAX/2 || shell_ratio<4 || shell_ratio>1000000 || shell_min_ratio>=shell_ratio || count>1000000)fail("Invalid experimental bounds");
  uint64_t total=(2*A+1)*(2*A+1);
  if(start>total || count>total-start)fail("Row tile outside domain");
  if(probe && count>20000)fail("Probe output limited to20000rows");
  shell_radius=A;tile_mode=1;
  struct timespec ts;clock_gettime(CLOCK_MONOTONIC,&ts);double begun=ts.tv_sec+ts.tv_nsec*1e-9,cpu=process_cpu();
  set_policy(policy);init_filters(114);pari_init(16000000,500000);
  run_shell(ell,A,start,count,direct,probe);
  clock_gettime(CLOCK_MONOTONIC,&ts);double elapsed=ts.tv_sec+ts.tv_nsec*1e-9-begun;
  /* Keep the exact checker accounting in its existing schema as a separate
   * record; experimental row geometry is explicitly recorded below. */
  print_stats("experimental_shell",114,ell,A,start,count,shell_ratio,shell_min_ratio,total,policy,elapsed);
  printf("{\"type\":\"shell_stats\",\"complete\":true,\"method\":\"%s\",\"D0\":\"%"PRIu64"\",\"D1\":\"%"PRIu64"\",\"row_start\":%"PRIu64",\"row_end\":%"PRIu64",\"rows\":%"PRIu64",\"empty_rows\":%"PRIu64",\"lattice_positions\":%"PRIu64",\"eligible_inputs\":%"PRIu64",\"outside_shell\":%"PRIu64",\"norm_evaluations\":%"PRIu64",\"recurrence_steps\":%"PRIu64",\"cpu_seconds\":%.6f,\"wall_seconds\":%.6f}\n",method,shell_D0,2*shell_D0,start,start+count,shell_rows,shell_empty_rows,shell_positions,shell_eligible,shell_positions-shell_eligible,shell_norm_evaluations,shell_recurrence_steps,process_cpu()-cpu,elapsed);
  pari_close();return 0;
}
