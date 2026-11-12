"""Local trusted-controller demonstration. Never imports uploaded code; no official leaderboard."""
import json,sqlite3,tempfile,threading,time
from contextlib import contextmanager
from pathlib import Path
from fastapi import FastAPI,HTTPException,Request
from pydantic import BaseModel,Field
from .server import register
from .engine import make_track,Race
from .controllers import MPCController,PursuitController

app=FastAPI(title='GP-MPC Racing — local demonstration');state={'status':'idle','phase':'','result':None};lock=threading.Lock()
folder=Path(tempfile.mkdtemp(prefix='gp-mpc-demo-'));database=folder/'demo.db'
@contextmanager
def db():
    c=sqlite3.connect(database);c.row_factory=sqlite3.Row
    try:yield c;c.commit()
    except Exception:c.rollback();raise
    finally:c.close()
def user():return {'id':0,'role':'teacher','name':'本地演示'}
register(app,{'db':db,'current':user,'teacher':user,'DATA':folder},demo=True)
@app.get('/')
def root():
    from fastapi.responses import RedirectResponse
    return RedirectResponse('/courses/design/vehicle/')
class Demo(BaseModel):
    speed:float=Field(default=8,ge=4,le=12)
    lookahead:float=Field(default=7,ge=4,le=12)
    laps:int=Field(default=2,ge=1,le=3)
    learn:bool=True
@app.post('/api/vehicle/demo')
def start(x:Demo,request:Request):
    origin=request.headers.get('origin')
    if origin and origin.rstrip('/')!=str(request.base_url).rstrip('/'):raise HTTPException(403,'来源不匹配')
    if request.headers.get('X-App-Request')!='1':raise HTTPException(403,'请求头缺失')
    with lock:
        if state['status']=='running':raise HTTPException(409,'当前演示正在计算，请稍候')
        state.update(status='running',phase='准备可信控制器',result=None)
    def run():
        try:
            results={};track=make_track()
            for key,controller in [('teacher',MPCController(learn=x.learn)),('student',PursuitController(x.speed,x.lookahead))]:
                race=Race(track,x.laps,180)
                while race.status=='running':
                    started=time.monotonic();raw=controller.act(race.observation());race.advance(raw,(time.monotonic()-started)*1000)
                    with lock:state['phase']=('教师GP-MPC' if key=='teacher' else '学生入门策略')+' · 模拟 '+str(round(race.t,1))+' 秒'
                results[key]=race.result()
            with lock:state.update(status='completed',phase='可信示例已计算，可播放对照',result={'track':track.public(),'config':{'laps':x.laps,'learn':x.learn,'track':'oval','engine':'singletrack-race-v1'},**results})
        except Exception:
            with lock:state.update(status='failed',phase='演示计算失败，请检查后台日志')
            import traceback;traceback.print_exc()
    threading.Thread(target=run,daemon=True).start();return {'ok':True}
@app.get('/api/vehicle/demo')
def demo_status():
    with lock:return dict(state)
if __name__=='__main__':
    import uvicorn
    uvicorn.run(app,host='127.0.0.1',port=8020)
