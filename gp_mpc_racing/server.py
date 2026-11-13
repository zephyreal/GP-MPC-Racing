"""Drop-in FastAPI course extension. Website stores source but NEVER imports student controllers."""
import hashlib,io,json,secrets,time,zipfile
from datetime import datetime,timedelta,timezone
from pathlib import Path
from fastapi import Depends,File,Form,HTTPException,Request,UploadFile
from fastapi.responses import FileResponse,StreamingResponse
from pydantic import BaseModel,Field
from typing import Literal
from .engine import VERSION,make_track,verify,rank_key,digest

ROOT=Path(__file__).parent
BJT=timezone(timedelta(hours=8))
def baseline_hash():return hashlib.sha256((ROOT/'engine.py').read_bytes()+(ROOT/'controllers.py').read_bytes()+(ROOT/'data/track02-original-v1.json').read_bytes()).hexdigest()
def validate_archive(content):
    if not content or len(content)>1_000_000:raise ValueError('代码ZIP必须小于1MB')
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        items=z.infolist()
        if len(items)>50 or sum(i.file_size for i in items)>5_000_000:raise ValueError('ZIP文件过多或解压体积过大')
        seen=set()
        for item in items:
            p=Path(item.filename)
            if p.is_absolute() or '..' in p.parts or '\\' in item.filename or ':' in item.filename or item.flag_bits&1 or ((item.external_attr>>16)&0o170000)==0o120000:raise ValueError('ZIP含危险路径或链接')
            if item.filename in seen:raise ValueError('ZIP含重复文件')
            seen.add(item.filename)
            if not item.is_dir() and p.suffix not in ('.py','.json','.md','.txt'):raise ValueError('只接受Python、JSON和说明文件')
        if 'agent.py' not in seen:raise ValueError('ZIP根目录须有agent.py，提供Controller.act方法')
    return content

class Competition(BaseModel):
    title:str=Field(min_length=2,max_length=100)
    track:Literal['track02-original-v1','oval','technical','reference']='track02-original-v1'
    laps:int=Field(default=10,ge=1,le=10)
    max_time:int=Field(default=1200,ge=30,le=1800)
    mode:Literal['practice','final']='practice'
    daily_limit:int=Field(default=2,ge=1,le=10)
    seed:int=Field(default=1,ge=1,le=10000)
    learn:bool=True
class Edit(BaseModel):
    close:bool=False
    published:bool|None=None
class Worker(BaseModel):
    fingerprint:str=Field(pattern='^[a-f0-9]{64}$')
class Lease(BaseModel):
    lease:str=Field(min_length=20,max_length=100)
class Result(Lease):
    fingerprint:str=Field(pattern='^[a-f0-9]{64}$')
    teacher:dict|None=None
    student:dict|None=None
    error:str=Field(default='',max_length=200)
class Reason(BaseModel):reason:str=Field(min_length=2,max_length=300)

class PayloadLimit:
    def __init__(self,app):self.app=app
    async def __call__(self,scope,receive,send):
        if scope['type']!='http' or scope.get('method') not in ('POST','PUT') or not scope.get('path','').startswith('/api/vehicle/'):
            return await self.app(scope,receive,send)
        limit=41_000_000 if scope['path'].startswith('/api/vehicle/worker/') and scope['path'].endswith('/result') else 1_100_000
        chunks=[];size=0
        while True:
            message=await receive()
            if message['type']=='http.disconnect':return
            size+=len(message.get('body',b''))
            if size>limit:
                from fastapi.responses import JSONResponse
                return await JSONResponse({'detail':'请求体超过上限'},status_code=413)(scope,receive,send)
            chunks.append(message)
            if not message.get('more_body'):break
        cursor=iter(chunks)
        async def replay():return next(cursor,{'type':'http.request','body':b'','more_body':False})
        return await self.app(scope,replay,send)

def register(app,env,*,demo=False):
    app.add_middleware(PayloadLimit)
    db=env['db'];current=env['current'];teacher=env['teacher'];folder=Path(env['DATA'])/'vehicle';folder.mkdir(exist_ok=True,parents=True,mode=0o700)
    with db() as c:
        c.executescript('''CREATE TABLE IF NOT EXISTS vehicle_settings(id INTEGER PRIMARY KEY,token_hash TEXT NOT NULL DEFAULT '',last_seen REAL NOT NULL DEFAULT 0);
        INSERT OR IGNORE INTO vehicle_settings(id) VALUES(1);
        CREATE TABLE IF NOT EXISTS vehicle_competitions(id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT NOT NULL,config TEXT NOT NULL,mode TEXT NOT NULL,state TEXT NOT NULL DEFAULT 'open',published INTEGER NOT NULL DEFAULT 0,baseline_hash TEXT NOT NULL,fingerprint TEXT NOT NULL DEFAULT '');
        CREATE TABLE IF NOT EXISTS vehicle_entries(id INTEGER PRIMARY KEY AUTOINCREMENT,competition_id INTEGER NOT NULL,user_id INTEGER NOT NULL,alias TEXT NOT NULL,note TEXT NOT NULL,path TEXT NOT NULL,sha TEXT NOT NULL,state TEXT NOT NULL,created REAL NOT NULL,error TEXT NOT NULL DEFAULT '',lease_hash TEXT NOT NULL DEFAULT '',lease_until REAL NOT NULL DEFAULT 0,result TEXT);
        CREATE TABLE IF NOT EXISTS vehicle_audit(id INTEGER PRIMARY KEY,user_id INTEGER,action TEXT,target TEXT,created REAL);
        CREATE TABLE IF NOT EXISTS vehicle_baselines(cache_key TEXT PRIMARY KEY,result TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS vehicle_queue ON vehicle_entries(state,id);''')
    def audit(c,u,what,target):c.execute('INSERT INTO vehicle_audit(user_id,action,target,created) VALUES(?,?,?,?)',(u['id'] if u else None,what,str(target),time.time()))
    def access(u=Depends(current)):
        if u['role']=='teacher':return u
        with db() as c:
            if not c.execute("SELECT 1 FROM course_memberships WHERE user_id=? AND course_id='design' AND active=1",(u['id'],)).fetchone():raise HTTPException(403,'请先加入智能制造课程设计')
        return u
    def active():
        if demo:raise HTTPException(403,'演示模式不接收参赛代码；正式比赛须安装课程平台扩展和独立评测机')
    def comp(c,cid):
        row=c.execute('SELECT * FROM vehicle_competitions WHERE id=?',(cid,)).fetchone()
        if not row:raise HTTPException(404,'比赛不存在')
        return dict(row)
    def maintain(c):
        c.execute("UPDATE vehicle_entries SET state='interrupted',lease_hash='',error='评测机失联，等待教师重试' WHERE state='running' AND lease_until<?",(time.time(),))
        if not demo:c.execute("UPDATE vehicle_entries SET state='cancelled',lease_hash='',error='账号或课程权限已取消' WHERE state IN ('waiting','pending','running') AND user_id NOT IN (SELECT u.id FROM users u JOIN course_memberships m ON m.user_id=u.id WHERE m.course_id='design' AND m.active=1 AND u.deleted_at='')")
    def summary(row):
        if not row:return None
        return {k:v for k,v in row.items() if k!='frames'}
    def entry(row,a,u):
        visible=u['role']=='teacher' or bool(a['published']);result=json.loads(row['result']) if row['result'] and visible else None
        return {'id':row['id'],'alias':row['alias'],'note':row['note'],'state':row['state'],'error':row['error'],'sha':row['sha'],'created':row['created'],'sealed':bool(row['result'] and not visible),'result':{k:summary(v) for k,v in result.items()} if result else None,'user_id':row['user_id'] if u['role']=='teacher' else None}
    def auth_worker(request:Request):
        active();value=request.headers.get('Authorization','')
        with db() as c:s=c.execute('SELECT * FROM vehicle_settings WHERE id=1').fetchone()
        if not value.startswith('Bearer ') or not s['token_hash'] or not secrets.compare_digest(s['token_hash'],hashlib.sha256(value[7:].encode()).hexdigest()):raise HTTPException(401,'评测机凭证无效')
    def leased(c,eid,token):
        maintain(c)
        r=c.execute('SELECT * FROM vehicle_entries WHERE id=?',(eid,)).fetchone()
        if not r or r['state']!='running' or r['lease_until']<time.time() or not secrets.compare_digest(r['lease_hash'],hashlib.sha256(token.encode()).hexdigest()):raise HTTPException(409,'评测租约已失效')
        return r
    def owned(c,eid,u):
        row=c.execute('SELECT * FROM vehicle_entries WHERE id=?',(eid,)).fetchone()
        if not row or (u['role']!='teacher' and row['user_id']!=u['id']):raise HTTPException(404,'版本不存在')
        return row
    @app.get('/courses/design/vehicle/')
    def page(u=Depends(access)):return FileResponse(ROOT/'static/index.html',headers={'Cache-Control':'no-store'})
    @app.get('/courses/design/vehicle/{name}')
    def asset(name:Literal['app.js','style.css','entry.js','replay-format.js','tutorial.html','teaching.html']):return FileResponse(ROOT/'static'/name,headers={'Cache-Control':'no-cache'})
    @app.get('/api/vehicle/teaching/v8/download')
    def teaching_project(u=Depends(access)):
        return FileResponse(ROOT/'teaching/GP_MPC_Desktop_V8.zip',filename='GP_MPC_Desktop_V8.zip',headers={'Cache-Control':'no-store'})
    @app.get('/api/vehicle/teaching/v8/python')
    def teaching_python(u=Depends(access)):
        return FileResponse(ROOT/'student/agent_v8_example.py',filename='agent.py',headers={'Cache-Control':'no-store'})
    @app.get('/api/vehicle/reference')
    def reference(u=Depends(access)):return make_track('track02-original-v1').public()
    @app.get('/api/vehicle/me')
    def me(u=Depends(access)):return {'id':u['id'],'role':u['role'],'name':u['name'],'demo':demo}
    @app.get('/api/vehicle/competitions')
    def competitions(u=Depends(access)):
        with db() as c:
            maintain(c);rows=c.execute('SELECT * FROM vehicle_competitions ORDER BY id DESC').fetchall();worker=c.execute('SELECT * FROM vehicle_settings WHERE id=1').fetchone()
            return {'competitions':[{**dict(a),'config':json.loads(a['config'])} for a in rows],'worker_online':worker['last_seen']>time.time()-60}
    @app.post('/api/vehicle/competitions')
    def create(x:Competition,u=Depends(teacher)):
        active();cfg=x.model_dump();cfg.update(controller_profile='python-port-v1',engine=VERSION,step_ms=2000,training_ms=20000,baseline_maxiter=12,baseline_hash=baseline_hash())
        with db() as c:
            cid=c.execute('INSERT INTO vehicle_competitions(title,config,mode,published,baseline_hash) VALUES(?,?,?,?,?)',(x.title,json.dumps(cfg),x.mode,int(x.mode=='practice'),cfg['baseline_hash'])).lastrowid;audit(c,u,'create',cid)
        return {'id':cid}
    @app.put('/api/vehicle/competitions/{cid}')
    def edit(cid:int,x:Edit,u=Depends(teacher)):
        active()
        with db() as c:
            c.execute('BEGIN IMMEDIATE');a=comp(c,cid);maintain(c)
            if x.close:
                c.execute("UPDATE vehicle_competitions SET state='closed' WHERE id=?",(cid,))
                if a['mode']=='final':
                    c.execute("UPDATE vehicle_entries SET state=CASE WHEN id IN (SELECT MAX(id) FROM vehicle_entries WHERE competition_id=? AND state='waiting' GROUP BY user_id) THEN 'pending' ELSE 'superseded' END WHERE competition_id=? AND state='waiting'",(cid,cid))
            if x.published is not None:
                if x.published and a['mode']=='final' and (not(x.close or a['state']=='closed') or c.execute("SELECT 1 FROM vehicle_entries WHERE competition_id=? AND state IN ('waiting','pending','running')",(cid,)).fetchone()):raise HTTPException(409,'先封存并完成评测，再发布成绩')
                c.execute('UPDATE vehicle_competitions SET published=? WHERE id=?',(int(x.published),cid))
            audit(c,u,'edit',cid)
        return {'ok':True}
    @app.post('/api/vehicle/worker-key')
    def key(u=Depends(teacher)):
        active();token=secrets.token_urlsafe(40)
        with db() as c:
            c.execute('UPDATE vehicle_settings SET token_hash=?,last_seen=0 WHERE id=1',(hashlib.sha256(token.encode()).hexdigest(),));c.execute("UPDATE vehicle_entries SET state='interrupted',lease_hash='',error='评测凭证已更换' WHERE state='running'");audit(c,u,'rotate-worker','key')
        return {'token':token}
    @app.get('/api/vehicle/starter')
    def starter(cid:int|None=None,u=Depends(access)):
        from .starter import build_starter
        cfg=Competition(title='本地入门训练',track='oval').model_dump()
        if cid is not None:
            with db() as c:cfg=json.loads(comp(c,cid)['config'])
        output=build_starter(cfg)
        return StreamingResponse(iter([output]),media_type='application/zip',headers={'Content-Disposition':'attachment; filename="vehicle-starter.zip"'})
    @app.post('/api/vehicle/competitions/{cid}/entries')
    async def upload(cid:int,file:UploadFile=File(...),alias:str=Form(''),note:str=Form(''),u=Depends(access)):
        active()
        if u['role']!='student':raise HTTPException(403,'请用学生账号参赛')
        alias=alias.strip() or ('同学'+str(u['id']))
        if not 1<=len(alias.strip())<=30 or len(note)>2000:raise HTTPException(400,'昵称1—30字，改进说明不超过2000字')
        content=await file.read(1_000_001)
        try:
            if (file.filename or '').lower() != 'agent.py':raise ValueError('只接受单个 agent.py 文件，不接受工程ZIP或JSON')
            if not content or len(content)>900_000:raise ValueError('Python文件须小于900KB')
            import ast
            try:tree=ast.parse(content.decode('utf-8-sig'))
            except (UnicodeError,SyntaxError) as e:raise ValueError('Python文件须为UTF-8编码且语法正确：'+str(e))
            functions=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='control']
            if len(functions)!=1:raise ValueError('请使用新版案例：定义 control(observation, reference, vehicle, memory) 函数')
            fn=functions[0]
            if len(fn.args.posonlyargs)+len(fn.args.args)!=4 or fn.args.kwonlyargs or fn.args.vararg or fn.args.kwarg:raise ValueError('control函数需要4个位置参数：observation, reference, vehicle, memory')
            output=io.BytesIO()
            with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
                info=zipfile.ZipInfo('agent.py');info.compress_type=zipfile.ZIP_DEFLATED
                z.writestr(info,content)
            content=output.getvalue()
            validate_archive(content)
        except (ValueError,zipfile.BadZipFile) as e:raise HTTPException(400,str(e))
        path=folder/(secrets.token_hex(20)+'.zip')
        try:
            path.write_bytes(content)
            with db() as c:
                c.execute('BEGIN IMMEDIATE');maintain(c);a=comp(c,cid);cfg=json.loads(a['config'])
                if a['state']!='open':raise HTTPException(409,'比赛已经封存')
                sha=hashlib.sha256(content).hexdigest()
                same=c.execute("SELECT id FROM vehicle_entries WHERE competition_id=? AND user_id=? AND sha=? AND state IN ('pending','running','completed','waiting') ORDER BY id DESC LIMIT 1",(cid,u['id'],sha)).fetchone()
                if same:
                    path.unlink(missing_ok=True)
                    return {'id':same['id'],'reused':True}
                midnight=datetime.now(BJT).replace(hour=0,minute=0,second=0,microsecond=0).timestamp()
                used=c.execute('SELECT COUNT(*) FROM vehicle_entries WHERE competition_id=? AND user_id=? AND created>=?',(cid,u['id'],midnight)).fetchone()[0]
                if used>=cfg['daily_limit']:raise HTTPException(429,'今天的提交次数已用完')
                if c.execute("SELECT COUNT(*) FROM vehicle_entries WHERE state IN ('waiting','pending','running')").fetchone()[0]>=300:raise HTTPException(429,'评测队列已满')
                c.execute("UPDATE vehicle_entries SET state='superseded' WHERE competition_id=? AND user_id=? AND state IN ('pending','waiting')",(cid,u['id']))
                eid=c.execute('INSERT INTO vehicle_entries(competition_id,user_id,alias,note,path,sha,state,created) VALUES(?,?,?,?,?,?,?,?)',(cid,u['id'],alias.strip(),note.strip(),str(path),hashlib.sha256(content).hexdigest(),'waiting' if a['mode']=='final' else 'pending',time.time())).lastrowid;audit(c,u,'submit',eid)
        except Exception:path.unlink(missing_ok=True);raise
        return {'id':eid}
    @app.get('/api/vehicle/competitions/{cid}/entries')
    def entries(cid:int,u=Depends(access)):
        with db() as c:
            maintain(c);a=comp(c,cid);rows=c.execute('SELECT * FROM vehicle_entries WHERE competition_id=? ORDER BY id DESC',(cid,)).fetchall()
            return [entry(r,a,u) for r in rows if r['user_id']==u['id'] or u['role']=='teacher']
    @app.get('/api/vehicle/competitions/{cid}/leaderboard')
    def leaderboard(cid:int,u=Depends(access)):
        with db() as c:
            maintain(c);a=comp(c,cid)
            if not a['published'] and u['role']!='teacher':return {'sealed':True,'rows':[]}
            rows=c.execute("SELECT e.* FROM vehicle_entries e JOIN users u ON u.id=e.user_id JOIN course_memberships m ON m.user_id=u.id AND m.course_id='design' AND m.active=1 WHERE competition_id=? AND u.deleted_at='' AND e.id IN (SELECT MAX(id) FROM vehicle_entries WHERE competition_id=? AND state IN ('completed','excluded') GROUP BY user_id)",(cid,cid)).fetchall()
            items=[entry(r,a,u) for r in rows if r['state']=='completed'];items.sort(key=lambda e:rank_key(e['result']['student']));previous=None;rank=0
            for i,e in enumerate(items,1):
                key=rank_key(e['result']['student'])
                if key!=previous:rank=i
                e['rank']=rank;previous=key
            return {'sealed':False,'rows':items}
    @app.get('/api/vehicle/entries/{eid}/replay')
    def replay(eid:int,u=Depends(access)):
        with db() as c:
            r=owned(c,eid,u);a=comp(c,r['competition_id'])
            if not a['published'] and u['role']!='teacher':raise HTTPException(403,'教师发布后开放回放')
            if not r['result']:raise HTTPException(409,'评测尚未完成')
            return {'entry':entry(r,a,u),'config':json.loads(a['config']),'track':make_track(json.loads(a['config'])['track']).public(),**json.loads(r['result'])}
    @app.get('/api/vehicle/entries/{eid}/source')
    def source(eid:int,u=Depends(access)):
        with db() as c:r=owned(c,eid,u)
        return FileResponse(r['path'],filename=f'vehicle-entry-{eid}.zip',headers={'Cache-Control':'no-store'})
    @app.post('/api/vehicle/entries/{eid}/{operation}')
    def manage(eid:int,operation:Literal['retry','exclude'],x:Reason,u=Depends(teacher)):
        active()
        with db() as c:
            c.execute('BEGIN IMMEDIATE');r=owned(c,eid,u);a=comp(c,r['competition_id'])
            if a['mode']=='final' and a['published']:raise HTTPException(409,'先撤回正式赛发布，再处理成绩')
            if operation=='retry' and r['state'] not in ('failed','interrupted'):raise HTTPException(409,'只有评测异常可重试')
            if operation=='exclude' and r['state']!='completed':raise HTTPException(409,'仅可撤销已有成绩')
            c.execute('UPDATE vehicle_entries SET state=?,error=?,result=?,lease_hash=? WHERE id=?',('pending' if operation=='retry' else 'excluded',x.reason,None if operation=='retry' else r['result'],'',eid));audit(c,u,operation,eid)
        return {'ok':True}
    @app.post('/api/vehicle/worker/claim')
    def claim(x:Worker,auth=Depends(auth_worker)):
        with db() as c:
            c.execute('BEGIN IMMEDIATE');maintain(c);c.execute('UPDATE vehicle_settings SET last_seen=? WHERE id=1',(time.time(),))
            if c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='arena_entries'").fetchone():
                if c.execute("SELECT 1 FROM arena_entries WHERE state='running' AND lease_until>?",(time.time(),)).fetchone():return {'job':None}
            if c.execute("SELECT 1 FROM vehicle_entries WHERE state='running'").fetchone():return {'job':None}
            rows=c.execute("SELECT e.* FROM vehicle_entries e WHERE e.state='pending' ORDER BY COALESCE((SELECT MAX(h.created) FROM vehicle_entries h WHERE h.user_id=e.user_id AND h.state IN ('completed','failed','interrupted','excluded')),0), e.id").fetchall()
            for r in rows:
                a=comp(c,r['competition_id'])
                if a['fingerprint'] and a['fingerprint']!=x.fingerprint:continue
                if not a['fingerprint']:c.execute('UPDATE vehicle_competitions SET fingerprint=? WHERE id=?',(x.fingerprint,a['id']))
                lease=secrets.token_urlsafe(32);c.execute("UPDATE vehicle_entries SET state='running',lease_hash=?,lease_until=? WHERE id=?",(hashlib.sha256(lease.encode()).hexdigest(),time.time()+90,r['id']))
                return {'job':{'id':r['id'],'config':json.loads(a['config']),'lease':lease,'sha':r['sha'],'teacher_cached':bool(c.execute('SELECT 1 FROM vehicle_baselines WHERE cache_key=?',(digest({'config':json.loads(a['config']),'fingerprint':x.fingerprint}),)).fetchone())}}
            return {'job':None}
    @app.post('/api/vehicle/worker/{eid}/heartbeat')
    def heartbeat(eid:int,x:Lease,auth=Depends(auth_worker)):
        with db() as c:
            c.execute('BEGIN IMMEDIATE');leased(c,eid,x.lease);c.execute('UPDATE vehicle_entries SET lease_until=? WHERE id=?',(time.time()+90,eid));c.execute('UPDATE vehicle_settings SET last_seen=? WHERE id=1',(time.time(),))
        return {'ok':True}
    @app.get('/api/vehicle/worker/{eid}/source')
    def worker_source(eid:int,request:Request,auth=Depends(auth_worker)):
        with db() as c:r=leased(c,eid,request.headers.get('X-Race-Lease',''))
        return FileResponse(r['path'],filename='entry.zip')
    @app.get('/api/vehicle/worker/{eid}/teacher')
    def cached_teacher(eid:int,request:Request,auth=Depends(auth_worker)):
        with db() as c:
            r=leased(c,eid,request.headers.get('X-Race-Lease',''));a=comp(c,r['competition_id'])
            key=digest({'config':json.loads(a['config']),'fingerprint':a['fingerprint']})
            cached=c.execute('SELECT result FROM vehicle_baselines WHERE cache_key=?',(key,)).fetchone()
            if not cached:raise HTTPException(404,'教师基准尚未计算')
            return json.loads(cached['result'])
    @app.post('/api/vehicle/worker/{eid}/result')
    def result(eid:int,x:Result,auth=Depends(auth_worker)):
        with db() as c:
            c.execute('BEGIN IMMEDIATE');r=leased(c,eid,x.lease);a=comp(c,r['competition_id']);cfg=json.loads(a['config'])
            if a['fingerprint']!=x.fingerprint:raise HTTPException(409,'评测环境已变化')
            if x.error:
                c.execute("UPDATE vehicle_entries SET state='failed',error=?,lease_hash='' WHERE id=?",(x.error,eid))
            else:
                try:
                    if len(json.dumps(x.teacher))+len(json.dumps(x.student))>40_000_000:raise ValueError('报告过大')
                    track=make_track(cfg['track']);cache_key=digest({'config':cfg,'fingerprint':x.fingerprint})
                    cached=c.execute('SELECT result FROM vehicle_baselines WHERE cache_key=?',(cache_key,)).fetchone()
                    teacher_result=json.loads(cached['result']) if cached else verify(track,cfg,x.teacher)
                    report={'teacher':teacher_result,'student':verify(track,cfg,x.student)}
                    if not cached and teacher_result['reason'] not in ('控制器超时','控制器输出无效','控制器中断'):
                        c.execute('INSERT OR IGNORE INTO vehicle_baselines VALUES(?,?)',(cache_key,json.dumps(teacher_result,separators=(',',':'))))
                except (ValueError,TypeError,KeyError,ArithmeticError) as e:raise HTTPException(400,str(e))
                c.execute("UPDATE vehicle_entries SET state='completed',result=?,error='',lease_hash='' WHERE id=?",(json.dumps(report,separators=(',',':')),eid))
            audit(c,None,'worker-result',eid)
        return {'ok':True}
    return {'folder':folder,'baseline_hash':baseline_hash()}
