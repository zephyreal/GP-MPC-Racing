function selftest_v2()
% Numerical checks, without solving a closed-loop optimization.
root=fileparts(mfilename('fullpath'));
addpath(fullfile(root,'classes'),fullfile(root,'CODEGEN'));
validate_fast_paths;
rng(17);
gp=GP(5,3,ones(3,1),0.01*ones(3,1),repmat(eye(5),[1,1,3]),30);
X=randn(5,20); Y=randn(20,3); gp.add(X,Y); Q=randn(5,7);
[mu,V]=gp.eval(Q);
for j=1:3
    D=pdist2(Q',X','mahalanobis',gp.M(:,:,j)).^2;
    K=exp(-0.5*D); expected=(K*gp.alpha(:,j))';
    assert(norm(mu(j,:)-expected)<1e-10);
    W=gp.L(:,:,j)\K'; expectedVar=1-sum(W.^2,1);
    assert(norm(reshape(V(j,j,:),1,[])-expectedVar)<1e-10);
end
model=MotionModelGP_SingleTrack_nominal([],[]);
x=[5;0;0;10;0.1;0.01;0];u=[0.01;0.1;10];
model.fastMidpoint=false; a=model.xkp1Mean(x,u,0.15);
model.fastMidpoint=true; b=model.xkp1Mean(x,u,0.15);
assert(norm(a-b)<1e-12);
[td,p0,h,w]=RaceTrack.loadTrack_02(); track=RaceTrack(td,p0,h,w);
query=linspace(0,2*max(track.dist),77);
track.useCachedInterpolation=false; [a,b,c]=track.getTrackInfo(query);
track.useCachedInterpolation=true; [d,e,f]=track.getTrackInfo(query);
assert(norm(a-d,'fro')<1e-9 && norm(b-e)<1e-9 && c==f);
mpc=NMPC(@(x,P,u) model.xkp1Mean(x,u,0.15),@(x,u,e) [],@(x,u,e) [], ...
    [-1;-1;5],[1;1;30],7,3,0,@(t,x,P,u,e,r) x'*x+u'*u,@(t,x,P,e,r) x'*x,10,0.15);
mpc.meanOnlyPrediction=true;
U=repmat(u,1,10); costFull=mpc.costfun(U(:),0,0,x);
mpc.configureBlocking([1 1 1 1 2 4]);
assert(mpc.optSize()==18);
blocks=repmat(u,1,6); [expanded,~]=mpc.splitvariables(blocks(:));
assert(isequal(expanded,U));
assert(abs(mpc.costfun(blocks(:),0,0,x)-costFull)<1e-8);
mpc.configureBlocking(ones(1,10)); assert(mpc.optSize()==30);
fprintf('V2 numerical self-tests passed. Run benchmark_v2 for closed-loop timing.\n');
end
