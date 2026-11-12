"""Trusted, dependency-free race physics and scoring. Controllers never supply positions or scores."""
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path

VERSION='singletrack-race-v1'
DT=.15
STEER=math.radians(20)
CAR_LENGTH=3.8
CAR_WIDTH=1.6

def wrap(x):return (x+math.pi)%(2*math.pi)-math.pi
def clamp(x,lo,hi):return max(lo,min(hi,x))

@dataclass
class Track:
    name:str
    points:list
    width:float=8.
    left:list|None=None
    right:list|None=None
    heading:list|None=None
    source:dict|None=None
    closed:bool=True
    initial_state:list|None=None
    identifier:str=''
    def __post_init__(self):
        self.lengths=[];self.dist=[0.]
        for i,p in enumerate(self.points):
            q=self.points[(i+1)%len(self.points)];length=math.hypot(q[0]-p[0],q[1]-p[1]);self.lengths.append(length);self.dist.append(self.dist[-1]+length)
        self.length=self.dist[-1]
    def point(self,s):
        import bisect
        s=s%self.length;i=min(len(self.points)-1,bisect.bisect_right(self.dist,s)-1)
        p=self.points[i];q=self.points[(i+1)%len(self.points)];t=(s-self.dist[i])/max(self.lengths[i],1e-9)
        return p[0]+t*(q[0]-p[0]),p[1]+t*(q[1]-p[1]),math.atan2(q[1]-p[1],q[0]-p[0])
    def project(self,x,y,previous=None):
        candidates=range(len(self.points)) if previous is None else [i for i in range(len(self.points)) if abs((self.dist[i]-previous+self.length/2)%self.length-self.length/2)<18]
        best=None
        for i in candidates:
            p=self.points[i];q=self.points[(i+1)%len(self.points)];dx=q[0]-p[0];dy=q[1]-p[1];t=clamp(((x-p[0])*dx+(y-p[1])*dy)/max(self.lengths[i]**2,1e-9),0,1)
            xx=p[0]+t*dx;yy=p[1]+t*dy;d=math.hypot(x-xx,y-yy)
            if best is None or d<best[0]:best=(d,(self.dist[i]+t*self.lengths[i])%self.length,math.atan2(dy,dx),((x-xx)*(-dy)+(y-yy)*dx)/max(self.lengths[i],1e-9))
        return best
    def public(self):
        result={'name':self.name,'points':self.points,'width':self.width,'length':self.length,'closed':self.closed}
        for key in ('left','right','heading','source','initial_state'):
            if getattr(self,key) is not None:result[key]=getattr(self,key)
        if self.identifier:result['id']=self.identifier
        return result
    @classmethod
    def from_public(cls,d):return cls(d['name'],d['points'],d['width'],**{k:d[k] for k in ('left','right','heading','source','closed','initial_state') if k in d},identifier=d.get('id',''))


def make_track(name='track02-original-v1',seed=1):
    if name=='track02-original-v1':
        return Track.from_public(json.loads((Path(__file__).parent/'data/track02-original-v1.json').read_text()))
    # Smooth public training tracks; fixed seed changes grip, never changes lap rules.
    if name=='reference':
        segments=[('s',14),('c',15,-90),('s',5),('c',4,90),('c',4,-90),('s',5),('c',3.5,-90),('s',16),('c',3.5,-120),('s',10),('c',10,120),('s',10),('c',5,90),('s',5),('c',5,90),('c',7,-180),('s',2.3),('c',10,-90),('s',14.6),('c',12,-90)]
        points=[];x=y=h=0.
        for item in segments:
            if item[0]=='s':
                n=math.ceil(item[1]/.5);ds=item[1]/n
                for _ in range(n):points.append([x,y]);x+=ds*math.cos(h);y+=ds*math.sin(h)
            else:
                radius,angle=item[1],math.radians(item[2]);n=math.ceil(abs(angle)/math.radians(3));da=angle/n;sign=1 if angle>0 else -1
                for _ in range(n):
                    points.append([x,y]);x+=sign*radius*(math.sin(h+da)-math.sin(h));y-=sign*radius*(math.cos(h+da)-math.cos(h));h+=da
        return Track('上传项目参考赛道（网页版重建）',points,6.)
    if name not in ('oval','technical'):raise ValueError('未知赛道')
    points=[]
    for i in range(360):
        a=2*math.pi*i/360
        radius=1+.10*math.cos(3*a) if name=='technical' else 1
        points.append([42*math.cos(a)*radius,25*math.sin(a)*radius])
    return Track('基础椭圆' if name=='oval' else '连续弯道',points,8.)


def derivative(x,u,nominal=False,grip=1.):
    px,py,psi,vx,vy,r=x;delta=clamp(u[0],-STEER,STEER);pedal=clamp(u[1],-1,1)
    mass,inertia=(750.,900.) if nominal else (500.,600.)
    ar=math.atan2(vy-1.5*r,max(vx,.5));af=math.atan2(vy+.9*r,max(vx,.5))-delta
    def pace(a,b,d):return -grip*d*math.sin(8*math.atan(b*a+.5*(b*a-math.atan(b*a))))
    fyf=-35000*af if nominal else pace(af,.4,4560.4)
    fyr=-35000*ar if nominal else pace(ar,.45,4000.)
    force=pedal*(4000 if pedal>=0 else 8000)
    # Standard body-frame Coriolis terms; unlike the MATLAB source these are outside /mass.
    ax=(force*.5+force*.5*math.cos(delta)-fyf*math.sin(delta))/mass+vy*r-.012*vx*vx
    ay=(fyr+force*.5*math.sin(delta)+fyf*math.cos(delta))/mass-vx*r
    rr=(.9*(fyf*math.cos(delta)+force*.5*math.sin(delta))-1.5*fyr)/inertia
    return [vx*math.cos(psi)-vy*math.sin(psi),vx*math.sin(psi)+vy*math.cos(psi),r,ax,ay,rr]

def step(x,u,dt=DT,nominal=False,grip=1.):
    y=list(x);h=dt/5
    for _ in range(5):
        a=derivative(y,u,nominal,grip);mid=[v+h*.5*d for v,d in zip(y,a)];b=derivative(mid,u,nominal,grip);y=[v+h*d for v,d in zip(y,b)]
    y[2]=wrap(y[2]);return y


def action(raw):
    if not isinstance(raw,dict):raise ValueError('控制器必须返回对象')
    values=[raw.get('steering'),raw.get('torque')]
    if any(type(v) not in (float,int) or not math.isfinite(v) for v in values):raise ValueError('转向与驱动力必须为有限数值')
    if abs(values[0])>1.000001 or abs(values[1])>1.000001:raise ValueError('控制量超出[-1,1]')
    return [clamp(values[0],-1,1)*STEER,clamp(values[1],-1,1)]

class Race:
    def __init__(self,track,laps=2,max_time=180,seed=1):
        self.track=track;self.target=laps;self.max_time=max_time;self.seed=seed;self.grip=1.-.03*(seed%3)
        x,y,h=track.point(0);self.state=list(track.initial_state) if track.initial_state else [x,y,h,6.,0.,0.];self.s=track.project(*self.state[:2])[1] if track.initial_state else 0.;self.progress=0.;self.t=0.;self.lap_times=[];self.last_cross=0.;self.next_gate=1;self.gates=24;self.status='running';self.reason='';self.frames=[];self.errors=[];self.last=None
        self.record([0,0],0,{})
    def observation(self):
        return {'state':self.state[:],'time':self.t,'dt':DT,'track':self.track.public(),'progress':self.progress,'lap':len(self.lap_times),'target_laps':self.target,'last_transition':self.last,'max_steering':STEER}
    def record(self,u,solve_ms,telemetry):
        safe={}
        if isinstance(telemetry,dict):
            for key in ('gp_active','gp_update','solver_ok','solve_ms','train_ms'):
                value=telemetry.get(key)
                if isinstance(value,(str,bool)) and (not isinstance(value,str) or len(value)<140):safe[key]=value
                elif type(value) in (int,float) and math.isfinite(value):safe[key]=value
            path=telemetry.get('prediction',[])
            if isinstance(path,list) and len(path)<=20 and all(isinstance(p,list) and len(p)==2 and all(type(v) in (int,float) and math.isfinite(v) for v in p) for p in path):safe['prediction']=path
        self.frames.append({'t':round(self.t,4),'state':[round(v,7) for v in self.state],'action':u,'progress':round(self.progress,5),'solve_ms':round(solve_ms,3),'telemetry':safe})
    def advance(self,raw,solve_ms=0):
        if self.status!='running':raise ValueError('比赛已结束')
        u=action(raw);before=self.state[:];previous=self.progress;self.state=step(before,u,grip=self.grip);self.t=round(self.t+DT,8)
        if any(not math.isfinite(v) or abs(v)>100000 for v in self.state):self.status='failed';self.reason='车辆状态异常';return
        distance,s,heading,lateral=self.track.project(*self.state[:2],self.s);ds=(s-self.s+self.track.length/2)%self.track.length-self.track.length/2
        if abs(ds)>max(5,DT*math.hypot(self.state[3],self.state[4])*2):self.status='failed';self.reason='沿程跳变';return
        self.s=s;self.progress+=ds;self.errors.append(lateral)
        # Ordered along-track gates, with local projection and a physical travel bound.
        while self.progress>=self.next_gate*self.track.length/self.gates:self.next_gate+=1
        finished=int(self.progress/self.track.length)
        if finished>len(self.lap_times) and self.next_gate>finished*self.gates:
            cross=self.t-DT+DT*(finished*self.track.length-previous)/max(ds,1e-9);self.lap_times.append(round(cross-self.last_cross,5));self.last_cross=cross
        outside=False
        for forward in (-CAR_LENGTH/2,CAR_LENGTH/2):
            for side in (-CAR_WIDTH/2,CAR_WIDTH/2):
                px=self.state[0]+forward*math.cos(self.state[2])-side*math.sin(self.state[2]);py=self.state[1]+forward*math.sin(self.state[2])+side*math.cos(self.state[2])
                if self.track.project(px,py,self.s)[0]>self.track.width/2:outside=True
        if outside:self.status='failed';self.reason='车身越界'
        elif self.state[3]<0 or abs(math.atan2(self.state[4],max(self.state[3],.01)))>math.radians(80):self.status='failed';self.reason='倒车或侧滑过大'
        elif len(self.lap_times)>=self.target:self.status='completed'
        elif self.t>=self.max_time:self.status='timeout';self.reason='达到最大模拟时长'
        self.last={'state':before,'action':u,'next_state':self.state[:],'lap_finished':len(self.lap_times)>int(previous/self.track.length)}
        self.record(u,solve_ms,raw.get('telemetry',{}))
    def stop(self,reason):self.status='failed';self.reason=reason
    def result(self):
        return {'status':self.status,'reason':self.reason,'completed_laps':len(self.lap_times),'lap_times':self.lap_times,'simulated_seconds':round(self.last_cross if self.status=='completed' else self.t,5),'progress':round(clamp(self.progress/(self.target*self.track.length),0,1),6),'lateral_rmse':round(math.sqrt(sum(x*x for x in self.errors)/max(1,len(self.errors))),5),'mean_solve_ms':round(sum(f['solve_ms'] for f in self.frames)/max(1,len(self.frames)-1),3),'frames':self.frames}

def verify(track,config,report):
    if not isinstance(report,dict) or not isinstance(report.get('frames'),list):raise ValueError('无有效轨迹')
    frames=report['frames'];race=Race(track,config['laps'],config['max_time'],config['seed'])
    if not 1<=len(frames)<=int(config['max_time']/DT)+2:raise ValueError('轨迹长度超限')
    for frame in frames[1:]:
        u=frame['action']
        if not isinstance(u,list) or len(u)!=2:raise ValueError('控制记录无效')
        ms=frame['solve_ms']
        if type(ms) not in (int,float) or not math.isfinite(ms) or not 0<=ms<=config['step_ms']+(config.get('training_ms',0) if race.last and race.last['lap_finished'] else 0)+50:raise ValueError('控制耗时不符')
        race.advance({'steering':u[0]/STEER,'torque':u[1],'telemetry':frame.get('telemetry',{})},ms)
        if len(frame['state'])!=6 or any(not math.isfinite(v) or abs(v-w)>1e-5 for v,w in zip(frame['state'],race.frames[-1]['state'])) or abs(frame['t']-race.t)>1e-5:raise ValueError('位置或时间不是裁判计算的轨迹')
    if race.status=='running':
        reason=report.get('reason')
        if report.get('status')!='failed' or reason not in ('控制器超时','控制器输出无效','控制器中断'):raise ValueError('不完整轨迹不可计分')
        race.stop(reason)
    return race.result()

def rank_key(result):return (result['status']!='completed',-result['progress'],result['simulated_seconds'])
def digest(data):return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':')).encode()).hexdigest()
