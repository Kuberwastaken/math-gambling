/* Native selective three-cubes experiment. No exhaustive-coverage claim.
 * Candidate norms are the Grantham--Walsh idea, specialized to k=114.
 * All modular filters are necessary conditions. Final checks use PARI integers.
 * Compile with the bundled PARI headers/library as described in README.md.
 */
#include <pari/pari.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <inttypes.h>
#include <time.h>

typedef __int128 i128;
typedef unsigned __int128 u128;
static const int sieve_primes[] = {5,7,11,13,17,19,23,31,37,41,43,47,53,59,61};
#define NP (sizeof(sieve_primes)/sizeof(sieve_primes[0]))
static unsigned char qr[NP][64], cubes[NP][64], ok27[27][27];
static uint64_t rng_state;
static uint64_t root_count, covered, curves, residue_survivors, hits, overflowed;
static uint64_t class_curves[3];

static int mod128(i128 a,int p) {int r=(int)(a%p);return r<0?r+p:r;}
static i128 abs128(i128 a) {return a<0?-a:a;}
static uint64_t rand64(void) {
  uint64_t z=(rng_state+=UINT64_C(0x9e3779b97f4a7c15));
  z=(z^(z>>30))*UINT64_C(0xbf58476d1ce4e5b9);
  z=(z^(z>>27))*UINT64_C(0x94d049bb133111eb);
  return z^(z>>31);
}
static uint64_t uniform(uint64_t n) {
  uint64_t v,threshold=-n%n;
  do {v=rand64();} while(v<threshold);
  return v%n;
}
static uint64_t inverse(uint64_t a,uint64_t m) {
  i128 t=0,nt=1;
  uint64_t r=m,nr=a;
  while(nr){uint64_t q=r/nr,rr=r-q*nr;r=nr;nr=rr;i128 tt=t-(i128)q*nt;t=nt;nt=tt;}
  if(r!=1)return 0;
  t%=(i128)m;if(t<0)t+=m;return (uint64_t)t;
}
static uint64_t mulmod(uint64_t a,uint64_t b,uint64_t m) {return (uint64_t)((u128)a*b%m);}
static i128 floordiv(i128 a,i128 b) {i128 q=a/b,r=a%b;return q-(r<0);}
static i128 ceildiv(i128 a,i128 b) {return -floordiv(-a,b);}
static GEN integer128(i128 v) {
  int neg=v<0;u128 a=neg?(u128)(-v):(u128)v;
  GEN x=addii(shifti(utoi((ulong)(a>>64)),64),utoi((ulong)a));
  return neg?negi(x):x;
}
static void init_filters(long k) {
  memset(ok27,0,sizeof(ok27));
  for(int s=0;s<27;s++)for(int x=0;x<27;x++)for(int z=0;z<27;z++){
    int y=(s-x+27)%27;
    if((x*x*x+y*y*y+z*z*z)%27==k%27)ok27[s][z]=1;
  }
  for(size_t j=0;j<NP;j++)for(int a=0;a<sieve_primes[j];a++){
    int p=sieve_primes[j];qr[j][a*a%p]=1;cubes[j][a]=a*a*a%p;
  }
}
static void exact_check(long k,i128 s,i128 z) {
  pari_sp av=avma;
  GEN sg=integer128(s),zg=integer128(z),rem,v;
  GEN top=subii(mulsi(4,subii(stoi(k),powiu(zg,3))),powiu(sg,3));
  GEN square=dvmdii(top,mulsi(3,sg),&rem);
  if(signe(rem)==0 && signe(square)>=0 && Z_issquareall(square,&v)){
    GEN xp=addii(sg,v),yp=subii(sg,v);
    if(!mpodd(xp) && !mpodd(yp)){
      GEN x=shifti(xp,-1),y=shifti(yp,-1);
      if(cmpii(absi(zg),absi(x))<=0 && cmpii(absi(zg),absi(y))<=0){
        GEN sum=addii(addii(powiu(x,3),powiu(y,3)),powiu(zg,3));
        if(cmpis(sum,k)){fprintf(stderr,"Exact verification failed\n");exit(3);}
        hits++;pari_printf("HIT [%ld,[%Ps,%Ps,%Ps]]\n",k,x,y,zg);fflush(stdout);
      }
    }
  }
  avma=av;
}
static void check_curve(long k,uint64_t d,uint64_t r,long R,uint64_t oldD,i128 oldZ) {
  int eps=(k/3)%3;
  i128 s=(d%3==(uint64_t)((2*eps)%3))?(i128)d:-(i128)d;
  i128 zmin=oldZ>0?(d<=oldD?oldZ:(i128)100000000000000000LL):0;
  i128 zmax=(i128)R*d;
  if(zmax<=zmin){covered++;return;}
  i128 lo,hi;
  if(s<0){lo=floordiv(zmin-r,d)+1;hi=floordiv(zmax-r,d);}
  else {lo=ceildiv(-zmax-r,d);hi=ceildiv(-zmin-r,d)-1;}
  if(lo>hi){covered++;return;}
  curves++;
  int aa[NP],bb[NP],dp[NP],rp[NP];
  for(size_t j=0;j<NP;j++){
    int p=sieve_primes[j],sm=mod128(s,p);
    aa[j]=3*sm%p;bb[j]=mod128(4*k-sm*sm*sm,p);
    dp[j]=d%p;rp[j]=r%p;
  }
  int sm27=mod128(s,27);
  for(i128 q=lo;q<=hi;q++){
    i128 z=(i128)r+(i128)d*q;
    if(!ok27[sm27][mod128(z,27)] || mod128(k-s-z,2))continue;
    int pass=1;
    for(size_t j=0;j<NP;j++){
      int p=sieve_primes[j],zm=mod128(rp[j]+(i128)dp[j]*q,p);
      int disc=mod128(aa[j]*(bb[j]-4*cubes[j][zm]),p);
      if(!qr[j][disc]){pass=0;break;}
    }
    if(pass){residue_survivors++;exact_check(k,s,z);}
  }
}
static void scan(uint64_t seed,uint64_t count,long A,long R) {
  const long k=114;const uint64_t mults[]={1,5,25};
  const i128 oldZ=(i128)1000000000000000000LL*10;
  const uint64_t oldD=(uint64_t)(oldZ/54);
  rng_state=seed;
  for(uint64_t j=0;j<count;j++){
    i128 a=(i128)uniform(2*A+1)-A,b=(i128)uniform(2*A+1)-A,c=(i128)uniform(2*A+1)-A;
    i128 n=a*a*a+k*b*b*b+k*k*c*c*c-3*k*a*b*c;
    i128 B=k*c*c-a*b,C=b*b-a*c;
    if(!n)continue;
    for(int t=0;t<3;t++){
      if(n%mults[t])continue;
      i128 dd=abs128(n)/mults[t];
      if(dd<2 || dd%3==0)continue;
      if(dd>INT64_MAX){overflowed++;continue;}
      uint64_t d=(uint64_t)dd;
      if((i128)R*d<=100000000000000000LL || (d<=oldD && (i128)R*d<=oldZ)){covered++;continue;}
      i128 cm=C%d;if(cm<0)cm+=d;
      uint64_t inv=inverse((uint64_t)cm,d);if(!inv)continue;
      i128 bm=B%d;if(bm<0)bm+=d;
      uint64_t r=mulmod((uint64_t)bm,inv,d);
      if(mulmod(mulmod(r,r,d),r,d)!=k%d){fprintf(stderr,"Invalid modular root\n");exit(3);}
      root_count++;check_curve(k,d,r,R,oldD,oldZ);
    }
  }
}
/* J=(5,alpha-4) generates Cl(K)=C3; J^2=(25,alpha-4).
 * Pick gamma directly in J^j, so N(gamma) is divisible by 5^j.
 * Scale each coefficient box by cbrt(5^j) to target comparable D ranges.
 * This samples ideal classes evenly, not solutions or distinct curves evenly.
 */
static void class_scan(uint64_t seed,uint64_t count,long A,long R) {
  const uint64_t mults[]={1,5,25};
  const i128 oldZ=(i128)1000000000000000000LL*10;
  const uint64_t oldD=(uint64_t)(oldZ/54);
  long radii[3]={A,0,0};
  for(int j=1;j<3;j++){
    long h=A;
    while((i128)h*h*h<(i128)A*A*A*mults[j])h++;
    radii[j]=h;
  }
  rng_state=seed;
  for(uint64_t j=0;j<count;j++){
    int t=j%3;uint64_t ell=mults[t];long h=radii[t];
    i128 b=(i128)uniform(2*h+1)-h,c=(i128)uniform(2*h+1)-h;
    i128 a0=mod128(-4*b-16*c,ell);
    i128 qlo=ceildiv(-h-a0,ell),qhi=floordiv(h-a0,ell);
    i128 a=a0+(qlo+uniform((uint64_t)(qhi-qlo+1)))*ell;
    i128 n=a*a*a+114*b*b*b+12996*c*c*c-342*a*b*c;
    if(n%ell){fprintf(stderr,"Class lattice norm divisibility failed\n");exit(3);}
    i128 dd=abs128(n)/ell;
    if(dd<2 || dd%3==0)continue;
    if(dd>INT64_MAX){overflowed++;continue;}
    uint64_t d=(uint64_t)dd;
    if((i128)R*d<=100000000000000000LL || (d<=oldD && (i128)R*d<=oldZ)){covered++;continue;}
    i128 B=114*c*c-a*b,C=b*b-a*c,cm=C%d;
    if(cm<0)cm+=d;
    uint64_t inv=inverse((uint64_t)cm,d);if(!inv)continue;
    i128 bm=B%d;if(bm<0)bm+=d;
    uint64_t r=mulmod((uint64_t)bm,inv,d);
    if(mulmod(mulmod(r,r,d),r,d)!=114%d){fprintf(stderr,"Invalid modular root\n");exit(3);}
    uint64_t before=curves;
    root_count++;check_curve(114,d,r,R,oldD,oldZ);
    class_curves[t]+=curves-before;
  }
}

int main(int argc,char **argv) {
  pari_init(16000000,500000);
  struct timespec ts;clock_gettime(CLOCK_MONOTONIC,&ts);double start=ts.tv_sec+ts.tv_nsec*1e-9;
  if(argc==6 && (!strcmp(argv[1],"scan") || !strcmp(argv[1],"class-scan"))){
    uint64_t seed=strtoull(argv[2],0,10),n=strtoull(argv[3],0,10);
    long A=strtol(argv[4],0,10),R=strtol(argv[5],0,10);
    if(A<1 || A>80000 || R<4 || R>1000000){fprintf(stderr,"radius 1..80000, ratio 4..1000000 required\n");return 2;}
    init_filters(114);
    if(!strcmp(argv[1],"class-scan"))class_scan(seed,n,A,R);else scan(seed,n,A,R);
  } else if(argc==6 && !strcmp(argv[1],"curve")){
    long k=strtol(argv[2],0,10),R=strtol(argv[5],0,10);
    uint64_t d=strtoull(argv[3],0,10),r=strtoull(argv[4],0,10);
    if(k<3 || k>1000 || (k%9!=3 && k%9!=6) || d<2 || d>INT64_MAX || d%3==0 || r>=d || R<4 || R>10000000){fprintf(stderr,"Invalid curve parameters\n");return 2;}
    if(mulmod(mulmod(r,r,d),r,d)!=k%d){fprintf(stderr,"Not a modular root\n");return 2;}
    init_filters(k);check_curve(k,d,r,R,0,0);
  } else {fprintf(stderr,"Usage: %s scan/class-scan SEED COUNT RADIUS RATIO | curve K D ROOT RATIO\n",argv[0]);return 2;}
  clock_gettime(CLOCK_MONOTONIC,&ts);double elapsed=ts.tv_sec+ts.tv_nsec*1e-9-start;
  printf("STATS {\"curves\":%"PRIu64",\"covered\":%"PRIu64",\"exact_tests\":%"PRIu64",\"hits\":%"PRIu64",\"overflowed\":%"PRIu64",\"seconds\":%.6f}\n",curves,covered,residue_survivors,hits,overflowed,elapsed);
  printf("CLASSES [%"PRIu64",%"PRIu64",%"PRIu64"]\n",class_curves[0],class_curves[1],class_curves[2]);
  pari_close();return 0;
}
