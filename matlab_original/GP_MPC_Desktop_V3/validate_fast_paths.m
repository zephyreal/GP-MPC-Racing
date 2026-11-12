function validate_fast_paths()
% Run from a COPY of the original project after applying the patch.
% Requires MATLAB + Statistics and Machine Learning Toolbox.
root = fileparts(mfilename('fullpath'));
cd(root); addpath(fullfile(root,'classes'),fullfile(root,'CODEGEN'));
rng(7);
gp = GP(5,3,ones(3,1)*0.01,ones(3,1)*1e-5,repmat(eye(5),[1,1,3]),40);
gp.add(randn(5,30),0.01*randn(30,3));
z = randn(5,5);
[mu,varY] = gp.eval(z);
muFast = gp.eval(z);
assert(norm(mu-muFast,'fro') < 1e-12);
assert(all(isfinite(varY(:))));
model = MotionModelGP_SingleTrack_nominal(@gp.eval,zeros(3));
for active = [false true]
    gp.isActive = active;
    for j=1:20
        x = [randn(3,1);10+rand();0.05*randn(2,1);1];
        u = [0.02*randn();0.2;10];
        [muFull,~] = model.xkp1(x,0.001*eye(7),u,0.15);
        muFast = model.xkp1Mean(x,u,0.15);
        assert(norm(muFull-muFast) < 1e-10);
    end
end
gp.isActive = true;
cost = @(t,x,P,u,e,r) x'*x+u'*u;
terminal = @(t,x,P,e,r) x'*x;
mpc = NMPC(@(x,P,u) model.xkp1(x,P,u,0.15), ...
    @(x,u,e) [],@(x,u,e) [],[],[],7,3,0,cost,terminal,10,0.15);
x = [5;0;0;10;0;0;0];
inputs = repmat([0.01;0.1;10],1,10);
assert(mpc.optSize()==30,'Default constructor must initialize 30 decisions.');
[expanded,~] = mpc.splitvariables(inputs(:));
assert(isequal(size(expanded),[3,10]) && isequal(expanded,inputs), ...
    'Default unblocked control sequence must retain all 10 columns.');
[fullTrajectory,~] = mpc.predictStateSequence(x,zeros(7),inputs);
cFull = mpc.costfun(inputs(:),0,0,x);
mpc.meanOnlyPrediction = true;
mpc.f = @(x,P,u) model.xkp1Mean(x,u,0.15);
[fastTrajectory,~] = mpc.predictStateSequence(x,zeros(7),inputs);
cFast = mpc.costfun(inputs(:),0,0,x);
assert(norm(fullTrajectory-fastTrajectory,'fro') < 1e-9);
assert(abs(cFull-cFast) < 1e-9*max(1,abs(cFull)));
fprintf('Mean, rollout and mean-only objective equivalence checks passed.\n');
fprintf('This does not validate real-time performance or closed-loop stability.\n');
end
