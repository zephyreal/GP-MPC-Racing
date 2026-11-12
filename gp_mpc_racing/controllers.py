"""Blocked NMPC and screened between-lap GP learning. Python engineering adaptation, not MATLAB equivalence."""
import math,time
import numpy as np
from scipy.optimize import minimize
from scipy.linalg import cho_factor,cho_solve
from .engine import Track,step,wrap,STEER,clamp

class ResidualGP:
    def __init__(self,x,y):
        self.x=np.asarray(x);self.y=np.asarray(y);self.scale=np.maximum(np.std(self.x,axis=0),[.1,.1,.01,.01,.05]);self.fits=[]
        for j in range(3):
            target=self.y[:,j];signal=max(float(np.mean(target**2)),1e-6)
            def kernel(theta,a,b):
                a=a/(self.scale*np.exp(theta[0]));b=b/(self.scale*np.exp(theta[0]));d=np.maximum(0,(a*a).sum(1)[:,None]+(b*b).sum(1)[None,:]-2*a@b.T)
                return np.exp(theta[1])*np.exp(-.5*d)
            def objective(theta):
                try:
                    k=kernel(theta,self.x,self.x)+np.exp(theta[2])*np.eye(len(self.x));factor=cho_factor(k,lower=True);alpha=cho_solve(factor,target)
                    return .5*target@alpha+np.log(np.diag(factor[0])).sum()+len(target)*.5*np.log(2*np.pi)
                except np.linalg.LinAlgError:return 1e20
            result=minimize(objective,[0,math.log(signal),math.log(signal*.01+1e-8)],method='L-BFGS-B',bounds=[(-3,3),(math.log(signal)-6,math.log(signal)+6),(-23,math.log(max(signal*10,1)))],options={'maxiter':25})
            if not result.success:raise ValueError('GP超参数未收敛')
            k=kernel(result.x,self.x,self.x)+np.exp(result.x[2])*np.eye(len(self.x));alpha=cho_solve(cho_factor(k,lower=True),target);self.fits.append((result.x,alpha))
    def predict(self,x):
        x=np.atleast_2d(x);values=[]
        for theta,alpha in self.fits:
            a=x/(self.scale*np.exp(theta[0]));b=self.x/(self.scale*np.exp(theta[0]));d=np.maximum(0,(a*a).sum(1)[:,None]+(b*b).sum(1)[None,:]-2*a@b.T);values.append(np.exp(theta[1])*np.exp(-.5*d)@alpha)
        return np.stack(values,axis=1)

class MPCController:
    def __init__(self,learn=True,maxiter=12):
        self.learn=learn;self.maxiter=maxiter;self.track=None;self.warm=None;self.gp=None;self.samples=[];self.last_t=None;self.gp_message='首圈使用名义模型';self.training_ms=0
        self.blocks=[0,1,2,3,4,4,5,5,5,5]
    def update(self,obs):
        last=obs.get('last_transition');self.training_ms=0
        if not last or obs['time']==self.last_t:return
        self.last_t=obs['time'];x=last['state'];u=last['action'];nom=step(x,u,nominal=True);res=np.array(last['next_state'][3:6])-np.array(nom[3:6]);self.samples.append((x[3:6]+u,res))
        if not last['lap_finished']:return
        if not self.learn:self.samples=[];self.gp_message='学习已关闭';return
        if len(self.samples)<40:self.samples=[];self.gp_message='样本不足，保留原模型';return
        start=time.monotonic()
        try:
            x=np.array([p[0] for p in self.samples]);y=np.array([p[1] for p in self.samples]);split=int(len(x)*.8);idx=np.unique(np.linspace(0,split-1,min(80,split)).astype(int));candidate=ResidualGP(x[idx],y[idx]);scale=np.maximum(np.mean(y[idx]**2,axis=0),1e-6)
            old=np.zeros_like(y[split:]) if self.gp is None else .3*self.gp.predict(x[split:]);new=.3*candidate.predict(x[split:]);a=np.mean((y[split:]-old)**2,axis=0)/scale;b=np.mean((y[split:]-new)**2,axis=0)/scale
            if b.mean()<.98*a.mean() and np.all(b<=1.05*a+1e-8):self.gp=candidate;self.gp_message='留出预测改善，下一圈试用GP'
            else:self.gp_message='留出改善不足，保留原模型'
        except (ValueError,np.linalg.LinAlgError):self.gp_message='GP拟合未通过，保留原模型'
        finally:self.samples=[];self.training_ms=(time.monotonic()-start)*1000
    def act(self,obs):
        start=time.monotonic()
        if self.track is None:self.track=Track.from_public(obs['track'])
        self.update(obs);x=obs['state'];s=self.track.project(*x[:2])[1];width=self.track.width/2;pred=[]
        if self.warm is None:self.warm=np.tile([0,.15,8.],(6,1))
        def evaluate(flat,save=False):
            u=flat.reshape(6,3);state=list(x);ref=s;cost=0;path=[]
            for i,block in enumerate(self.blocks):
                control=u[block];feature=state[3:6]+list(control[:2]);state=step(state,control[:2],nominal=True)
                if self.gp is not None:
                    correction=.3*self.gp.predict(feature)[0]
                    for j in range(3):state[3+j]+=float(correction[j])
                ref+=obs['dt']*control[2];rx,ry,h=self.track.point(ref);dx=state[0]-rx;dy=state[1]-ry;lag=(dx*math.cos(h)+dy*math.sin(h))/width;contour=(-dx*math.sin(h)+dy*math.cos(h))/width
                h0=self.track.point(ref-2)[2];h1=self.track.point(ref+2)[2];curvature=abs(wrap(h1-h0))/4;safe_speed=min(11.,math.sqrt(3.2/max(curvature,.004)))
                stage=50*lag*lag+20*contour*contour+5*wrap(state[2]-h)**2+8*state[5]**2-3*control[2]+1000*max(0,abs(contour)-.72)**2+20*max(0,state[3]-safe_speed)**2
                if not math.isfinite(stage) or abs(stage)>1e12:return 1e15
                cost+=(3 if i==9 else 1)*stage;path.append(state[:2])
            if save:pred.extend(path)
            return cost
        bounds=[b for _ in range(6) for b in [(-STEER,STEER),(-1,1),(5,30)]]
        result=minimize(evaluate,self.warm.ravel(),method='SLSQP',bounds=bounds,options={'maxiter':self.maxiter,'ftol':.05})
        if np.all(np.isfinite(result.x)) and evaluate(result.x)<1e14:self.warm=result.x.reshape(6,3)
        evaluate(self.warm.ravel(),True);control=self.warm[0].copy();self.warm=np.vstack([self.warm[1:],self.warm[-1]])
        return {'steering':float(clamp(control[0]/STEER,-1,1)),'torque':float(clamp(control[1],-1,1)),'telemetry':{'prediction':pred,'gp_active':self.gp is not None,'gp_update':self.gp_message,'solver_ok':bool(result.success),'solve_ms':(time.monotonic()-start)*1000,'train_ms':self.training_ms}}

class PursuitController:
    """Simple student starter; this is not the GP-MPC teacher controller."""
    def __init__(self,speed=8.,lookahead=7.):self.speed=speed;self.lookahead=lookahead;self.track=None
    def act(self,obs):
        if self.track is None:self.track=Track.from_public(obs['track'])
        x,y,h,v,vy,r=obs['state'];s=self.track.project(x,y)[1];tx,ty,_=self.track.point(s+self.lookahead);alpha=wrap(math.atan2(ty-y,tx-x)-h);steering=math.atan2(2*2.4*math.sin(alpha),self.lookahead)
        return {'steering':clamp(steering/STEER,-1,1),'torque':clamp(.25*(self.speed-v)+.1,-1,1),'telemetry':{'prediction':[[tx,ty]],'gp_active':False}}
