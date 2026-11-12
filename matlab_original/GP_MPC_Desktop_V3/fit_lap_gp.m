function [candidate,score]=fit_lap_gp(X,Y,active,cfg)
% Candidate trained on early samples and screened on later held-out samples.
% No guarantee of improved closed-loop lap time follows from this test.
valid=all(isfinite(X),1)&all(isfinite(Y),2)';
X=X(:,valid);Y=Y(valid,:); count=size(X,2);
candidate=[];
score=struct('accepted',false,'oldError',NaN,'newError',NaN,'fitFlags',[], ...
    'reason','Too few samples','points',0);
if count<40,return;end
split=floor(0.8*count);
idx=unique(round(linspace(1,split,min(cfg.gpMaxPoints,split))));
Xt=X(:,idx);Yt=Y(idx,:);Xv=X(:,split+1:end);Yv=Y(split+1:end,:);
l=max(std(Xt,0,2),[0.1;0.1;0.01;0.01;0.05]);
M=zeros(5,5,3);vf=zeros(3,1);vn=zeros(3,1);flags=zeros(3,1);
options=optimoptions('fmincon','Algorithm','sqp','Display','off','MaxIterations',cfg.fitMaxiter);
for j=1:3
    signal=max(mean(Yt(:,j).^2),1e-6);
    initial=log([l;signal;max(0.01*signal,1e-8)]);
    lower=log([l*0.02;max(signal*1e-4,1e-10);1e-10]);
    upper=log([l*50;max(signal*1e4,1);max(signal*10,1)]);
    [theta,~,flags(j)]=fmincon(@(v) objective(v,Xt,Yt(:,j)),initial,[],[],[],[],lower,upper,[],options);
    M(:,:,j)=diag(exp(theta(1:5)).^2);vf(j)=exp(theta(6));vn(j)=exp(theta(7));
end
candidate=GP(5,3,vf,vn,M,numel(idx));candidate.add(Xt,Yt);
old=active.predict(Xv)';new=cfg.gpGain*candidate.eval(Xv)';
scale=max(mean(Yt.^2,1),1e-6);
oldChannels=mean((Yv-old).^2,1)./scale;
newChannels=mean((Yv-new).^2,1)./scale;
score.oldError=mean(oldChannels);score.newError=mean(newChannels);
score.fitFlags=flags;score.points=numel(idx);
score.accepted=all(flags>0) && all(isfinite(new(:))) && ...
    score.newError<(1-cfg.minGain)*score.oldError && all(newChannels<=1.05*oldChannels+1e-8);
if score.accepted,score.reason='Accepted by held-out prediction test';
elseif any(flags<=0),score.reason='Hyperparameter fit did not converge';
else,score.reason='Held-out improvement insufficient or one channel worsened';end
end
function value=objective(theta,X,y)
A=X./exp(theta(1:5));D=max(0,sum(A.^2,1)'+sum(A.^2,1)-2*A'*A);
K=exp(theta(6))*exp(-0.5*D)+exp(theta(7))*eye(numel(y));
[L,p]=chol(K,'lower');if p~=0,value=1e30;return;end
v=L\y;value=0.5*(v'*v)+sum(log(diag(L)))+numel(y)*log(2*pi)/2;
end
