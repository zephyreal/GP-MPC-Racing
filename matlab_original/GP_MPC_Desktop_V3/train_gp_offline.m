function metrics=train_gp_offline(dataFile,maxPoints)
% Offline GP hyperparameter fit. Last 20% of time samples are held out.
% This is a screening split, not independent real-vehicle validation.
root=fileparts(mfilename('fullpath'));
addpath(fullfile(root,'classes'));
if nargin<1, dataFile=fullfile(root,'results','collect_latest.mat'); end
if nargin<2, maxPoints=100; end
assert(maxPoints>=2 && maxPoints==floor(maxPoints));
s=load(dataFile,'out'); o=s.out;
valid=all(isfinite(o.z),1)&all(isfinite(o.residual),2)';
X=o.z(:,valid); Y=o.residual(valid,:);
count=size(X,2); assert(count>=25,'Collect at least 25 valid steps.');
split=floor(0.8*count);
idx=unique(round(linspace(1,split,min(maxPoints,split))));
Xt=X(:,idx); Yt=Y(idx,:); Xv=X(:,split+1:end); Yv=Y(split+1:end,:);
lengths=max(std(Xt,0,2),[0.1;0.1;0.01;0.01;0.05]);
M=zeros(5,5,3); vf=zeros(3,1); vn=zeros(3,1);
exitflags=zeros(3,1);
opts=optimoptions('fmincon','Display','off','Algorithm','sqp','MaxIterations',100);
for j=1:3
    signal=max(mean(Yt(:,j).^2),1e-6);
    theta0=log([lengths;signal;max(0.01*signal,1e-8)]);
    lower=log([lengths*0.02;max(signal*1e-4,1e-10);1e-10]);
    upper=log([lengths*50;max(signal*1e4,1);max(signal*10,1)]);
    theta0=min(max(theta0,lower),upper);
    [theta,~,exitflags(j)]=fmincon(@(v) nll(v,Xt,Yt(:,j)),theta0,[],[],[],[],lower,upper,[],opts);
    M(:,:,j)=diag(exp(theta(1:5)).^2); vf(j)=exp(theta(6)); vn(j)=exp(theta(7));
end
gp=GP(5,3,vf,vn,M,numel(idx)); gp.add(Xt,Yt);
pred=gp.eval(Xv)';
metrics=struct('nominal_residual_rmse',sqrt(mean(Yv.^2,1)), ...
    'gp_residual_rmse',sqrt(mean((Yv-pred).^2,1)), ...
    'training_points',numel(idx),'holdout_points',size(Xv,2),'fit_exitflags',exitflags);
disp(metrics);
if any(exitflags<=0), warning('V2:Fit','Some hyperparameter fits did not converge. Inspect metrics.');end
gpData=struct('X',Xt,'Y',Yt,'M',M,'var_f',vf,'var_n',vn);
metadata=struct('dt',o.cfg.dt,'source',dataFile,'metrics',metrics,'model','original_singletrack');
d=fullfile(root,'results'); if ~isfolder(d),mkdir(d);end
save(fullfile(d,'gp_model.mat'),'gpData','metadata');
fprintf('Saved fixed GP model. Compare held-out errors before running gp mode.\n');
end
function value=nll(theta,X,y)
l=exp(theta(1:5)); A=X./l;
D=max(0,sum(A.^2,1)'+sum(A.^2,1)-2*(A'*A));
K=exp(theta(6))*exp(-0.5*D)+exp(theta(7))*eye(size(X,2));
[L,p]=chol(K,'lower');
if p~=0, value=1e30; return; end
v=L\y; value=0.5*(v'*v)+sum(log(diag(L)))+0.5*numel(y)*log(2*pi);
end
