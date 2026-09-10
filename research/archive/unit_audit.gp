K=bnfinit(x^3-114,1);ee=K.fu[1];le=log(abs(nfeltembed(K,ee,1)));ratios=List();
for(dd=2,1000,if(dd%3==0,next);for(rr=0,dd-1,if(rr^3%dd!=114%dd,next);ii=idealhnf(K,dd,x-rr);cl=bnfisprincipal(K,ii,0)[1];j=(-cl)%3;gg=bnfisprincipal(K,idealmul(K,ii,idealpow(K,K.gen[1],j)));gg=nfbasistoalg(K,gg[2]);nn=dd*5^j;tt=round(log(nn^(1/3)/abs(nfeltembed(K,gg,1)))/le);best=10^100;for(vv=tt-2,tt+2,aa=nfalgtobasis(K,gg*ee^vv);best=min(best,vecmax(abs(aa))));listput(ratios,best/nn^(1/3))));
r=vecsort(Vec(ratios));print("SHAPE ",[#r,r[1],r[ceil(#r/2)],r[ceil(9*#r/10)],r[#r]]);
quit;
