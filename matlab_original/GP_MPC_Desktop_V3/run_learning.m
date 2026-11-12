function out=run_learning(usercfg)
% Multi-lap compact MPC, live visualization and optional lap-boundary GP fit.
if nargin<1,usercfg=struct();end
root=fileparts(mfilename('fullpath'));
addpath(fullfile(root,'classes'),fullfile(root,'CODEGEN'),fullfile(root,'functions'));
cfg=struct('laps',5,'maxSimTime',600,'dt',0.15,'maxiter',30, ...
    'algorithm','interior-point','learn',true,'live',true,'drawEvery',2, ...
    'gpMaxPoints',80,'fitMaxiter',60,'gpGain',0.3,'minGain',0.02, ...
    'saveResults',true,'seed',1);
keys=fieldnames(usercfg);
for i=1:numel(keys),assert(isfield(cfg,keys{i}),'Unknown option: %s',keys{i});cfg.(keys{i})=usercfg.(keys{i});end
assert(cfg.laps>=1 && cfg.laps==floor(cfg.laps));
assert(cfg.dt>0 && cfg.maxSimTime>=cfg.dt && cfg.drawEvery>=1 && cfg.drawEvery==floor(cfg.drawEvery));
assert(cfg.gpMaxPoints>=2 && cfg.gpMaxPoints==floor(cfg.gpMaxPoints));
assert(cfg.gpGain>0 && cfg.gpGain<=1 && cfg.minGain>=0 && cfg.minGain<1);
rng(cfg.seed);
noise=diag([(1/3)^2,(1/3)^2,(deg2rad(3)/3)^2]);
truth=MotionModelGP_SingleTrack_true([],noise);nominal=MotionModelGP_SingleTrack_nominal([],[]);
active=GPBlend;active.gain=cfg.gpGain;
model=MotionModelGP_SingleTrack_nominal(@active.predict,noise);
[td,p0,h,w]=RaceTrack.loadTrack_02();track=RaceTrack(td,p0,h,w);L=max(track.dist);
mpc=NMPC(@(x,P,u) model.xkp1Mean(x,u,cfg.dt),@(x,u,e) [],@(x,u,e) [], ...
    [-deg2rad(20);-1;5],[deg2rad(20);1;30],7,3,0, ...
    @(t,x,P,u,e,r) race_cost(x,P,u,track),@(t,x,P,e,r) 2*race_cost(x,P,zeros(3,1),track),10,cfg.dt);
mpc.meanOnlyPrediction=true;mpc.maxiter=cfg.maxiter;mpc.solverAlgorithm=cfg.algorithm;
mpc.configureBlocking([1 1 1 1 2 4]);mpc.uguess(3,:)=20;
K=floor(cfg.maxSimTime/cfg.dt);
out=struct('cfg',cfg,'mode','learning','t',(0:K)*cfg.dt,'x',NaN(7,K+1),'u',NaN(3,K), ...
    'solve_seconds',NaN(1,K),'core_seconds',NaN(1,K),'loop_seconds',NaN(1,K), ...
    'train_seconds',zeros(1,K),'exitflag',NaN(1,K),'solver_message',{cell(1,K)}, ...
    'z',NaN(5,K),'residual',NaN(K,3),'contour_error',NaN(1,K),'outside',false(1,K), ...
    'progress',zeros(1,K+1),'steps',0,'stopped_reason','', ...
    'track_c',track.track_c,'track_l',track.track_l,'track_r',track.track_r,'laps',struct([]));
x=[5;0;0;10;0;0;0];x(7)=track.getTrackDistance(x(1:2));out.x(:,1)=x;
ui=[];if cfg.live,ui=live_dashboard('init',track);end
lapStartStep=1;lastCrossTime=0;total=0;wall=tic;
lastSafeModel=[];trial=false;usedGP=false;
fprintf('Target %d laps, dt %.3fs, live=%d, learning=%d. Lap time uses SIMULATION time.\n',cfg.laps,cfg.dt,cfg.live,cfg.learn);
for k=1:K
    if cfg.live && (~isgraphics(ui.fig) || getappdata(ui.fig,'stopRequested'))
        out.stopped_reason='Stopped by user';break;
    end
    loopClock=tic;
    [U,~,info]=mpc.optimize(x,out.t(k),0,false);
    out.solve_seconds(k)=info.seconds;out.exitflag(k)=info.exitflag;out.solver_message{k}=info.output.message;
    u=U(:,1);out.u(:,k)=u;next=truth.xkp1Mean(x,u,cfg.dt);
    reason='';
    if any(~isfinite(next)),reason='Nonfinite vehicle state';
    elseif next(4)<0,reason='Negative longitudinal velocity';
    elseif abs(atan2(next(5),next(4)))>deg2rad(80),reason='Sideslip angle exceeded 80 degrees';end
    if isempty(reason),next(7)=track.getTrackDistance(next(1:2),x(7));end
    out.x(:,k+1)=next;out.steps=k;
    out.z(:,k)=model.z(x,u);
    out.residual(k,:)=(model.Bd\(next-nominal.xkp1Mean(x,u,cfg.dt)))';
    if all(isfinite(next))
        [~,ec,~,~]=track.getVehicleDeviation(next(1:2),next(3),next(7));
        out.contour_error(k)=ec*w/2;out.outside(k)=abs(ec)>1;
    end
    out.core_seconds(k)=toc(loopClock);
    if ~isempty(reason)
        if trial,active.model=lastSafeModel;end
        out.stopped_reason=reason;out.loop_seconds(k)=toc(loopClock);break;
    end
    ds=mod(next(7)-x(7)+L/2,L)-L/2;
    previous=total;total=total+ds;out.progress(k+1)=total;
    completed=numel(out.laps);
    if total>=(completed+1)*L && ds>0
        crossing=out.t(k)+cfg.dt*((completed+1)*L-previous)/ds;
        span=lapStartStep:k;
        lap=struct('index',completed+1,'seconds',crossing-lastCrossTime, ...
            'meanSpeed',mean(hypot(out.x(4,span+1),out.x(5,span+1))), ...
            'lateralRMSE',sqrt(mean(out.contour_error(span).^2)), ...
            'outsideSamples',sum(out.outside(span)), ...
            'nonconverged',sum(out.exitflag(span)<=0),'samples',numel(span), ...
            'usedGP',usedGP,'acceptedNext',false,'reverted',false,'trainingSeconds',0, ...
            'screenOld',NaN,'screenNew',NaN,'updateReason','No update requested');
        % A candidate is provisional until one full lap has no detected exit.
        if trial && lap.outsideSamples>0
            active.model=lastSafeModel;trial=false;lap.reverted=true;
            lap.updateReason='Reverted candidate after detected track-width violation';
        elseif trial
            lastSafeModel=active.model;trial=false;
        end
        if cfg.learn && lap.index<cfg.laps && lap.outsideSamples==0 && ~lap.reverted
            if cfg.live,live_dashboard('message',ui,sprintf('Lap %d finished (%.2fs). Fitting candidate GP; simulation paused...',lap.index,lap.seconds));end
            fitClock=tic;
            try
                [candidate,screen]=fit_lap_gp(out.z(:,span),out.residual(span,:),active,cfg);
                lap.screenOld=screen.oldError;lap.screenNew=screen.newError;lap.updateReason=screen.reason;
                if screen.accepted
                    lastSafeModel=active.model;active.model=candidate;trial=true;lap.acceptedNext=true;
                end
            catch exception
                lap.updateReason=['Fit failed; old model retained: ',exception.message];
                warning('V3:Training','%s',lap.updateReason);
            end
            lap.trainingSeconds=toc(fitClock);out.train_seconds(k)=lap.trainingSeconds;
        elseif cfg.learn && lap.outsideSamples>0 && ~lap.reverted
            lap.updateReason='No training promotion from a lap with detected width violation';
        end
        out.laps(end+1)=lap;lastCrossTime=crossing;lapStartStep=k+1;usedGP=~isempty(active.model);
        fprintf('Lap %d: %.2fs, RMSE %.3fm, outside %d, unconverged %d/%d, GP used %d, next update %d\n', ...
            lap.index,lap.seconds,lap.lateralRMSE,lap.outsideSamples,lap.nonconverged,lap.samples,lap.usedGP,lap.acceptedNext);
        fprintf('  %s\n',lap.updateReason);
    end
    if cfg.live && (mod(k,cfg.drawEvery)==0 || numel(out.laps)>=cfg.laps)
        [prediction,~]=mpc.predictStateSequence(x,zeros(7),U);
        status=sprintf('t %.1fs | wall %.1fs | lap %d/%d | v %.2f m/s (%.1f km/h) | solve %.3fs | exit %d | GP %d', ...
            out.t(k+1),toc(wall),min(numel(out.laps)+1,cfg.laps),cfg.laps,hypot(next(4),next(5)), ...
            3.6*hypot(next(4),next(5)),info.seconds,info.exitflag,~isempty(active.model));
        live_dashboard('update',ui,out,k,prediction,status);
    end
    out.loop_seconds(k)=toc(loopClock);x=next;
    if numel(out.laps)>=cfg.laps,out.stopped_reason='Requested laps completed';break;end
end
if isempty(out.stopped_reason),out.stopped_reason='Maximum simulation time reached';end
out.wall_seconds=toc(wall);out.gpData=[];
if ~isempty(active.model)
    g=active.model;out.gpData=struct('X',g.X,'Y',g.Y,'M',g.M,'var_f',g.var_f,'var_n',g.var_n,'gain',active.gain);
end
fprintf('Finished: %s; %d laps; wall %.1fs\n',out.stopped_reason,numel(out.laps),out.wall_seconds);
if cfg.live && isgraphics(ui.fig),live_dashboard('message',ui,['Finished: ',out.stopped_reason]);end
if cfg.saveResults
    d=fullfile(root,'results');if ~isfolder(d),mkdir(d);end
    if cfg.learn,name='learning_latest';else,name='baseline_laps_latest';end
    save(fullfile(d,[name,'.mat']),'out');
    if ~isempty(out.laps),writetable(struct2table(out.laps),fullfile(d,[name,'_laps.csv']));end
    fprintf('Saved %s\n',fullfile(d,[name,'.mat']));
end
end
