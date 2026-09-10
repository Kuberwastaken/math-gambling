/* A finite deterministic search of a thin real-embedding plane.
 * This specializes the Grantham--Walsh cancellation-plane idea. It does not
 * certify a height box, all ideals, or a predictive advantage over other arms.
 * Every coefficient triple in this explicitly defined finite domain has a
 * unique index. Mathematical rejection and exact checks reuse campaign_worker.
 */
#define main campaign_common_main
#include "campaign_worker.c"
#undef main

static const i128 plane_den = (i128)1000000000000000000LL;
/* Nearest integers to 10^18 * 114^(1/3) and 10^18 * 114^(2/3).
 * Constants specify the domain exactly; no floating point is used at runtime.
 */
static const i128 plane_alpha_num = (i128)4848807585839879338LL;
static const i128 plane_alpha2_num = (i128)23*1000000000000000000LL + 510935004498358840LL;
static uint64_t plane_v;

static i128 plane_base_for(uint64_t ell,i128 b,i128 c,i128 p,i128 q,i128 den){
  i128 residue=mod128(-4*b-16*c,(int)ell);
  i128 numerator=-p*b-q*c-residue*den,denominator=ell*den;
  return residue+ell*floordiv(2*numerator+denominator,2*denominator);
}
static int plane_duplicate_for(uint64_t ell,i128 a,i128 b,i128 c,i128 p,i128 q,i128 den){
  if(!(c<0 || (c==0 && (b<0 || (b==0 && a<0)))))return 0;
  i128 opposite_base=plane_base_for(ell,-b,-c,p,q,den),delta=-a-opposite_base;
  return delta%(i128)ell==0 && delta/(i128)ell>=-2 && delta/(i128)ell<=2;
}
static int plane_duplicate(uint64_t ell){
  return plane_duplicate_for(ell,current_a,current_b,current_c,plane_alpha_num,plane_alpha2_num,plane_den);
}

static uint64_t plane_total(uint64_t radius){
  u128 w=(u128)2*radius+1,n=5*w*w;
  if(n>UINT64_MAX)fail("Plane domain exceeds uint64");return (uint64_t)n;
}
static i128 plane_generator(uint64_t ell,uint64_t radius,uint64_t index,uint64_t total){
  uint64_t w=2*radius+1;
  current_index=index;current_ell=ell;
  plane_v=(uint64_t)(((u128)index*perm_stride+perm_offset)%total);
  uint64_t v=plane_v;
  i128 t=(i128)(v%5)-2;v/=5;
  i128 b=(i128)(v%w)-(i128)radius,c=(i128)(v/w)-(i128)radius;
  /* floor(n/d+1/2): nearest lattice point, exact half ties toward +infinity. */
  i128 a=plane_base_for(ell,b,c,plane_alpha_num,plane_alpha2_num,plane_den)+ell*t;
  current_a=a;current_b=b;current_c=c;
  i128 norm=a*a*a+114*b*b*b+12996*c*c*c-342*a*b*c;
  if(norm%ell || mod128(a+4*b+16*c,(int)ell))fail("Plane lattice identity failed");
  return norm;
}
static int plane_root(i128 norm,uint64_t ell,uint64_t *d,uint64_t *r){
  if(!norm){zero_norm++;return 0;}
  i128 dd=abs128(norm)/ell;
  if(dd<2 || dd%3==0){invalid_d++;return 0;}
  if(dd>INT64_MAX){unsupported_d++;return 0;}
  *d=(uint64_t)dd;
  i128 a=current_a,b=current_b,c=current_c;
  i128 C=b*b-a*c,B=114*c*c-a*b,cm=C%*d,bm=B%*d;
  if(cm<0)cm+=*d;if(bm<0)bm+=*d;
  uint64_t inv=inverse((uint64_t)cm,*d);
  if(!inv){noninvertible++;return 0;}
  *r=mulmod((uint64_t)bm,inv,*d);
  if(mulmod(mulmod(*r,*r,*d),*r,*d)!=114%*d)fail("Plane modular root identity failed");
  return 1;
}
static void plane_tile(uint64_t ell,uint64_t radius,uint64_t start,uint64_t count,uint64_t ratio,uint64_t min_ratio,uint64_t total,int dump){
  setup_permutation(total,ell,radius);
  for(uint64_t n=0;n<count;n++){
    candidates++;
    i128 norm=plane_generator(ell,radius,start+n,total);
    if(dump){
      uint64_t d=0,r=0;int usable=plane_root(norm,ell,&d,&r);
      printf("{\"type\":\"candidate\",\"kind\":\"plane\",\"index\":%"PRIu64",\"permuted_index\":%"PRIu64",\"ell\":%"PRIu64",\"abc\":[",current_index,plane_v,ell);
      quoted128(current_a);putchar(',');quoted128(current_b);putchar(',');quoted128(current_c);
      printf("],\"symmetry_duplicate\":%s,\"norm\":",plane_duplicate(ell)?"true":"false");quoted128(norm);
      printf(",\"root_usable\":%s,\"D\":",usable?"true":"false");
      if(d)printf("\"%"PRIu64"\"",d);else printf("null");
      printf(",\"r\":");if(usable)printf("\"%"PRIu64"\"",r);else printf("null");
      printf("}\n");continue;
    }
    if(plane_duplicate(ell)){symmetry_rejected++;continue;}
    /* Early coverage check is identical to the box worker. The root test is
     * deferred until a curve has a possible interval outside prior coverage. */
    if(norm){
      i128 dd=abs128(norm)/ell;
      if(dd>=2 && dd%3 && dd<=INT64_MAX){
        const i128 oldZ=(i128)1000000000000000000LL*10;
        if((i128)ratio*dd<=(dd<=oldZ/54?oldZ:(i128)100000000000000000LL)){covered++;continue;}
      }
    }
    uint64_t d=0,r=0;
    if(plane_root(norm,ell,&d,&r))frontier_curve(d,r,ratio,min_ratio);
  }
}
static void plane_stats(const char *mode,uint64_t ell,uint64_t radius,uint64_t start,uint64_t count,uint64_t ratio,uint64_t min_ratio,uint64_t total,const char *policy,double seconds){
  printf("{\"type\":\"stats\",\"version\":1,\"complete\":true,\"kind\":\"plane\",\"mode\":\"%s\",\"k\":114,\"ell\":%"PRIu64",\"radius\":%"PRIu64",\"start\":%"PRIu64",\"count\":%"PRIu64",\"end\":%"PRIu64",\"total\":%"PRIu64",\"ratio\":%"PRIu64",\"min_ratio\":%"PRIu64",\"policy\":\"%s\",\"permutation_seed\":%"PRIu64",\"permutation_stride\":%"PRIu64",\"permutation_offset\":%"PRIu64",",mode,ell,radius,start,count,start+count,total,ratio,min_ratio,policy,perm_seed,perm_stride,perm_offset);
  printf("\"candidates\":%"PRIu64",\"curves\":%"PRIu64",\"quotient_points\":%"PRIu64",\"exact_tests\":%"PRIu64",\"hits\":%"PRIu64",\"zero_norm\":%"PRIu64",\"invalid_d\":%"PRIu64",\"unsupported_D\":%"PRIu64",\"noninvertible_C\":%"PRIu64",\"symmetry_rejected\":%"PRIu64",\"covered\":%"PRIu64",\"rejected_mod243\":%"PRIu64",\"rejected_parity\":%"PRIu64",\"reorders\":%"PRIu64",\"calibration_samples\":%"PRIu64",\"wall_seconds\":%.6f,\"final_order\":[",candidates,curves,quotient_points,exact_tests,hit_count,zero_norm,invalid_d,unsupported_d,noninvertible,symmetry_rejected,covered,rejected81,rejected_parity,reorders,calibration_samples,seconds);
  for(int j=0;j<NP;j++)printf("%s%d",j?",":"",sieve_primes[order[j]]);
  printf("],\"direct_curves\":%"PRIu64",\"wheel_curves\":%"PRIu64",\"filters\":[",direct_curves,wheel_curves);
  for(int j=0;j<NP;j++)printf("%s{\"prime\":%d,\"tested\":%"PRIu64",\"rejected\":%"PRIu64",\"calibrated\":%"PRIu64",\"calibration_rejected\":%"PRIu64"}",j?",":"",sieve_primes[j],tested[j],rejected[j],calibrated[j],calibration_reject[j]);
  printf("]}\n");
}
int main(int argc,char **argv){
  if(argc==2 && !strcmp(argv[1],"tie_selftest")){
    /* Synthetic rational plane a≈-b/2 produces exact half ties. Return its
     * entire small domain so Python can independently check set preservation. */
    for(uint64_t ell=1;ell<=25;ell*=5)for(i128 b=-3;b<=3;b++)for(i128 c=-3;c<=3;c++)for(i128 t=-2;t<=2;t++){
      i128 a=plane_base_for(ell,b,c,1,0,2)+ell*t;
      printf("{\"ell\":%"PRIu64",\"a\":",ell);print128(a);
      printf(",\"b\":");print128(b);printf(",\"c\":");print128(c);
      printf(",\"symmetry_duplicate\":%s}\n",plane_duplicate_for(ell,a,b,c,1,0,2)?"true":"false");
    }
    return 0;
  }
  if(argc>=2 && (!strcmp(argv[1],"curve") || !strcmp(argv[1],"interval")))return campaign_common_main(argc,argv);
  struct timespec ts;clock_gettime(CLOCK_MONOTONIC,&ts);double begun=ts.tv_sec+ts.tv_nsec*1e-9;
  uint64_t ell=0,radius=0,start=0,count=0,ratio=64,min_ratio=0;const char *policy="fixed";
  int dump=argc>=2 && !strcmp(argv[1],"dump");
  if(dump && argc>=6 && argc<=7){
    ell=parse(argv[2]);radius=parse(argv[3]);start=parse(argv[4]);count=parse(argv[5]);
    if(argc==7)perm_seed=parse(argv[6]);
  }else if(argc>=8 && argc<=10 && !strcmp(argv[1],"tile")){
    ell=parse(argv[2]);radius=parse(argv[3]);start=parse(argv[4]);count=parse(argv[5]);ratio=parse(argv[6]);policy=argv[7];
    if(argc>=9)min_ratio=parse(argv[8]);if(argc==10)perm_seed=parse(argv[9]);
  }else fail("Usage: plane_worker tile ELL RADIUS START COUNT RATIO POLICY [MIN_RATIO [PERM_SEED]] | dump ELL RADIUS START COUNT [PERM_SEED] | curve ... | interval ...");
  if((ell!=1 && ell!=5 && ell!=25) || radius<1 || radius>100000000 || ratio<4 || ratio>1000000 || min_ratio>=ratio)fail("Invalid plane bounds");
  uint64_t total=plane_total(radius);
  if(start>total || count>total-start)fail("Plane tile outside finite index domain");
  tile_mode=1;set_policy(policy);init_filters(114);pari_init(16000000,500000);
  plane_tile(ell,radius,start,count,ratio,min_ratio,total,dump);
  clock_gettime(CLOCK_MONOTONIC,&ts);double seconds=ts.tv_sec+ts.tv_nsec*1e-9-begun;
  plane_stats(dump?"dump":"tile",ell,radius,start,count,ratio,min_ratio,total,policy,seconds);
  pari_close();return 0;
}
