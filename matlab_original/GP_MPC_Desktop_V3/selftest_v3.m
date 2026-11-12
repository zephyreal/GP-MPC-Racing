function selftest_v3()
selftest_v2;
a=GPBlend;
[mu,V]=a.predict(zeros(5,4));
assert(isequal(size(mu),[3,4]) && ~any(mu(:)) && isequal(size(V),[3,3,4]));
g=GP(5,3,ones(3,1),0.01*ones(3,1),repmat(eye(5),[1,1,3]),10);
g.add(zeros(5,1),[1 2 3]);a.model=g;
assert(norm(a.predict(ones(5,1))-a.gain*g.eval(ones(5,1)))<1e-12);
L=100; start=91; distance=0:3:303; s=mod(start+distance,L);
progress=0; crossings=[];dt=0.15;
for k=1:numel(s)-1
    ds=mod(s(k+1)-s(k)+L/2,L)-L/2;
    previous=progress;progress=progress+ds;
    if progress>=(numel(crossings)+1)*L && ds>0
        crossings(end+1)=(k-1)*dt+dt*((numel(crossings)+1)*L-previous)/ds; %#ok<AGROW>
    end
end
assert(numel(crossings)==3 && max(abs(diff([0,crossings])-5))<1e-10);
s=[1 99 1];delta=mod(diff(s)+L/2,L)-L/2;assert(isequal(delta,[-2 2]));
fprintf('V3 numerical self-tests passed; GUI and closed-loop learning still require run_learning.\n');
end
