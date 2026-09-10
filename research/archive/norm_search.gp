\\ Selective norm/elliptic-curve search. This is NOT a complete height search.
\\ Uses the Grantham--Walsh norm idea with a signed pair sum and exact checks.
\\ Polynomial variable is q; number-field variable is x.

norm_candidates(k,a,b,c,mults) = {
  my(nn=a^3+k*b^3+k^2*c^3-3*k*a*b*c, bb=k*c^2-a*b, cc=b^2-a*c);
  my(out=List(),dd,rr);
  if(nn==0,return([]));
  for(i=1,#mults,
    if(nn%mults[i],next);
    dd=abs(nn)/mults[i];
    if(dd<2 || dd%3==0 || gcd(cc,dd)!=1,next);
    rr=lift(Mod(bb,dd)/Mod(cc,dd));
    if(lift(Mod(rr,dd)^3)!=k%dd,error("invalid norm root"));
    listput(out,[dd,rr,mults[i]]);
  );
  Vec(out);
};

curve_points(k,dd,rr,R,oldD,oldZ) = {
  my(eps=(k/3)%3,ss=if(dd%3==(2*eps)%3,dd,-dd),zz=rr+dd*q);
  my(pol=12*(k-zz^3)/ss-3*ss^2,pts,out=List(),zv,xv,yv,yy);
  my(qlo=-R-1,qhi=R+1,centre=0,H=R+1,zmin);
  if(oldZ>0,
    zmin=if(dd<=oldD,oldZ,10^17);
    \\ For large solutions z has the opposite sign to the pair sum ss.
    if(ss<0,
      qlo=floor((zmin-rr)/dd)+1;qhi=floor((R*dd-rr)/dd),
      qlo=ceil((-R*dd-rr)/dd);qhi=ceil((-zmin-rr)/dd)-1
    );
    if(qhi<qlo,return([]));
    centre=floor((qlo+qhi)/2);H=max(centre-qlo,qhi-centre);
    pol=subst(pol,q,q+centre);
  );
  if(H==0,
    my(vv=subst(pol,q,0),ww);
    pts=if(vv>=0 && issquare(vv,&ww),[[0,ww]],[]),
    pts=hyperellratpoints(pol,[H,1])
  );
  for(i=1,#pts,
    yy=pts[i][2];if(yy<0,next);
    if(denominator(pts[i][1])!=1 || denominator(yy)!=1,next);
    if((3*ss+yy)%6 || (3*ss-yy)%6,next);
    if(pts[i][1]+centre<qlo || pts[i][1]+centre>qhi,next);
    xv=(3*ss+yy)/6;yv=(3*ss-yy)/6;zv=rr+dd*(pts[i][1]+centre);
    if(abs(zv)>R*dd || abs(zv)>min(abs(xv),abs(yv)),next);
    if(xv^3+yv^3+zv^3!=k,error("cube identity failed"));
    if(oldZ>0 && (abs(zv)<=10^17 || (dd<=oldD && abs(zv)<=oldZ)),next);
    listput(out,vecsort([xv,yv,zv]));
  );
  Set(Vec(out));
};

\\ Samples uniformly in a coefficient cube, NOT uniformly in d or in solutions.
\\ Different coefficient triples and multipliers can describe the same curve.
run_batch(k,A,seed,count,R,oldD,oldZ,mults) = {
  my(seen=Map(),attempts=0,curves=0,duplicates=0,excluded=0,hits=0);
  my(a,b,c,cs,dd,rr,key,points,lo=0,hi=0,t0=getwalltime());
  setrand(seed);
  for(j=1,count,
    a=random(2*A+1)-A;b=random(2*A+1)-A;c=random(2*A+1)-A;
    cs=norm_candidates(k,a,b,c,mults);
    for(i=1,#cs,
      attempts++;dd=cs[i][1];rr=cs[i][2];
      if(oldZ>0 && (R*dd<=10^17 || (dd<=oldD && R*dd<=oldZ)),excluded++;next);
      key=[dd,rr];if(mapisdefined(seen,key),duplicates++;next);
      mapput(seen,key,1);curves++;if(lo==0 || dd<lo,lo=dd);hi=max(hi,dd);
      points=curve_points(k,dd,rr,R,oldD,oldZ);
      for(h=1,#points,hits++;print("HIT ",[k,points[h],dd,rr,[a,b,c],cs[i][3]]));
    );
  );
  print("STATS ",[seed,count,attempts,curves,duplicates,excluded,hits,getwalltime()-t0,lo,hi]);
};
