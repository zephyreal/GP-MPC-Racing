function [out,d_GP] = run_demo(mode,usercfg)
% RUN_DEMO Standalone desktop GP-NMPC. See README_CN.md.
% out = run_demo('fast');
% out = run_demo('compact',struct('tf',30));
if nargin<1, mode='fast'; end
if nargin<2, usercfg=struct(); end
root=fileparts(mfilename('fullpath'));
addpath(fullfile(root,'classes'),fullfile(root,'functions'),fullfile(root,'CODEGEN'));
assert(exist('fmincon','file')==2,'Optimization Toolbox is required.');
cfg=struct('dt',0.15,'tf',15,'N',10,'maxiter',30, ...
    'algorithm','interior-point','useParallel',false,'gpFile',fullfile(root,'results','gp_model.mat'), ...
    'gpMaxPoints',100,'saveResults',true,'plotResults',true,'progressEvery',20,'seed',1);
keys=fieldnames(usercfg);
for i=1:numel(keys)
    assert(isfield(cfg,keys{i}),'Unknown configuration field: %s',keys{i});
    cfg.(keys{i})=usercfg.(keys{i});
end
mode=validatestring(mode,{'fast','compact','reference','collect','gp','gp_compact'});
assert(cfg.dt>0 && cfg.tf>=cfg.dt && cfg.N>=1 && cfg.N==floor(cfg.N));
assert(cfg.gpMaxPoints>=1 && cfg.gpMaxPoints==floor(cfg.gpMaxPoints));
rng(cfg.seed);
useGP=any(strcmp(mode,{'gp','gp_compact'}));
compact=any(strcmp(mode,{'compact','gp_compact'}));
reference=strcmp(mode,'reference');
noise=diag([(1/3)^2,(1/3)^2,(deg2rad(3)/3)^2]);
trueModel=MotionModelGP_SingleTrack_true([],noise);
nomModel=MotionModelGP_SingleTrack_nominal([],[]);
d_GP=GP(5,3,0.01*ones(3,1),diag(noise/3),repmat(eye(5),[1,1,3]),cfg.gpMaxPoints);
if useGP
    assert(isfile(cfg.gpFile),'No trained GP. Run collect, then train_gp_offline first.');
    loaded=load(cfg.gpFile,'gpData','metadata');
    assert(isfield(loaded,'gpData') && isfield(loaded,'metadata'),'Not a V2 GP data file.');
    assert(abs(loaded.metadata.dt-cfg.dt)<1e-12,'GP sample interval differs from cfg.dt. Retrain.');
    q=loaded.gpData;
    d_GP=GP(5,3,q.var_f,q.var_n,q.M,max(size(q.X,2),1));
    d_GP.add(q.X,q.Y);
end
d_GP.isActive=useGP;
estModel=MotionModelGP_SingleTrack_nominal(@d_GP.eval,noise);
trueModel.fastMidpoint=~reference;
nomModel.fastMidpoint=~reference;
estModel.fastMidpoint=~reference;
[td,p0,heading,width]=RaceTrack.loadTrack_02();
track=RaceTrack(td,p0,heading,width);
track.useCachedInterpolation=~reference;
if reference
    f=@(x,P,u) estModel.xkp1(x,P,u,cfg.dt);
else
    f=@(x,P,u) estModel.xkp1Mean(x,u,cfg.dt);
end
stage=@(t,x,P,u,e,r) race_cost(x,P,u,track);
terminal=@(t,x,P,e,r) 2*race_cost(x,P,zeros(3,1),track);
mpc=NMPC(f,@(x,u,e) [],@(x,u,e) [],[-deg2rad(20);-1;5], ...
    [deg2rad(20);1;30],7,3,0,stage,terminal,cfg.N,cfg.dt);
mpc.meanOnlyPrediction=~reference;
mpc.maxiter=cfg.maxiter;
mpc.solverAlgorithm=cfg.algorithm;
if compact
    assert(cfg.N==10,'Compact preset uses N=10. Edit configureBlocking for other horizons.');
    mpc.configureBlocking([1 1 1 1 2 4]);
end
K=floor(cfg.tf/cfg.dt);
x0=[5;0;0;10;0;0;0];
x0(7)=track.getTrackDistance(x0(1:2));
mpc.uguess(3,:)=20;
out=struct('cfg',cfg,'mode',mode,'t',(0:K)*cfg.dt,'x',NaN(7,K+1), ...
    'u',NaN(3,K),'solve_seconds',NaN(1,K),'step_seconds',NaN(1,K), ...
    'exitflag',NaN(1,K),'iterations',NaN(1,K),'function_evaluations',NaN(1,K), ...
    'contour_error',NaN(1,K),'outside',false(1,K),'z',NaN(5,K),'residual',NaN(K,3), ...
    'track_c',track.track_c,'track_l',track.track_l,'track_r',track.track_r, ...
    'stopped_reason','','steps',0,'decision_variables',mpc.optSize());
out.x(:,1)=x0;
fprintf('Mode=%s | N=%d | variables=%d | GP=%d | steps=%d\n',mode,cfg.N,mpc.optSize(),useGP,K);
for k=1:K
    totalClock=tic;
    x=out.x(:,k);
    [U,~,info]=mpc.optimize(x,out.t(k),0,cfg.useParallel);
    out.solve_seconds(k)=info.seconds;
    out.exitflag(k)=info.exitflag;
    out.iterations(k)=info.output.iterations;
    out.function_evaluations(k)=info.output.funcCount;
    % A finite iterate at an iteration limit is retained for simulation,
    % but recorded as non-converged. This is not a real-vehicle fallback.
    u=U(:,1); out.u(:,k)=u;
    [~,ec,~,~]=track.getVehicleDeviation(x(1:2),x(3),x(7));
    out.contour_error(k)=ec*width/2;
    out.outside(k)=abs(ec)>1;
    next=trueModel.xkp1Mean(x,u,cfg.dt);
    % Preserve original observer/projection convention for comparison.
    next(7)=track.getTrackDistance(next(1:2),x(7));
    out.x(:,k+1)=next;
    out.z(:,k)=estModel.z(x,u);
    out.residual(k,:)=(estModel.Bd\(next-nomModel.xkp1Mean(x,u,cfg.dt)))';
    out.steps=k;
    out.step_seconds(k)=toc(totalClock);
    if cfg.progressEvery>0 && (mod(k,cfg.progressEvery)==0 || k==K)
        fprintf('%d/%d | solve %.3fs | exit %d | lateral %.3fm\n',k,K,info.seconds,info.exitflag,out.contour_error(k));
    end
    if any(~isfinite(next)) || next(4)<0 || abs(atan2(next(5),next(4)))>deg2rad(80)
        out.stopped_reason='Nonfinite state, backwards motion, or excessive sideslip.';
        warning('V2:Stopped','Simulation stopped at step %d: %s',k,out.stopped_reason);
        break
    end
end
n=out.steps; timings=sort(out.solve_seconds(1:n));
out.summary=struct('median_s',median(timings),'p95_s',timings(max(1,ceil(0.95*n))), ...
    'max_s',max(timings),'step_median_s',median(out.step_seconds(1:n)), ...
    'deadline_miss_fraction',mean(out.step_seconds(1:n)>cfg.dt), ...
    'lateral_rmse_m',sqrt(mean(out.contour_error(1:n).^2)), ...
    'outside_samples',sum(out.outside(1:n)), ...
    'nonpositive_exitflags',sum(out.exitflag(1:n)<=0));
disp(out.summary);
if cfg.saveResults
    resultDir=fullfile(root,'results'); if ~isfolder(resultDir), mkdir(resultDir); end
    path=fullfile(resultDir,[mode,'_latest.mat']); save(path,'out');
    fprintf('Saved %s\n',path);
end
if cfg.plotResults, plot_result(out); end
end
