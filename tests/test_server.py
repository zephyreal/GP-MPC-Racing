import copy,hashlib,io,json,sqlite3,zipfile
from contextlib import contextmanager
from pathlib import Path
import pytest
from fastapi import FastAPI,Header,HTTPException
from fastapi.testclient import TestClient
from gp_mpc_racing.server import register,validate_archive
from test_engine import trusted_reports,CFG

@pytest.fixture
def setup(tmp_path):
    @contextmanager
    def db():
        c=sqlite3.connect(tmp_path/'course.db');c.row_factory=sqlite3.Row
        try:yield c;c.commit()
        except Exception:c.rollback();raise
        finally:c.close()
    with db() as c:
        c.executescript("CREATE TABLE users(id INTEGER PRIMARY KEY,name TEXT,role TEXT,deleted_at TEXT DEFAULT '');CREATE TABLE course_memberships(user_id INTEGER,course_id TEXT,active INTEGER DEFAULT 1);")
        c.executemany('INSERT INTO users(id,name,role) VALUES(?,?,?)',[(1,'教师','teacher'),(2,'甲','student'),(3,'乙','student'),(4,'无权','student')]);c.executemany('INSERT INTO course_memberships(user_id,course_id) VALUES(?,?)',[(2,'design'),(3,'design')])
    def current(x_user:int=Header(default=0)):
        with db() as c:r=c.execute('SELECT * FROM users WHERE id=? AND deleted_at=?',(x_user,'')).fetchone()
        if not r:raise HTTPException(401,'请登录')
        return dict(r)
    def teacher(x_user:int=Header(default=0)):
        u=current(x_user)
        if u['role']!='teacher':raise HTTPException(403,'需要教师账号')
        return u
    app=FastAPI();register(app,{'db':db,'current':current,'teacher':teacher,'DATA':tmp_path});client=TestClient(app)
    return client,db

def code():
    data=io.BytesIO()
    with zipfile.ZipFile(data,'w') as z:z.writestr('agent.py','raise RuntimeError("Must never execute on website")')
    return data.getvalue()
def create(c,mode='practice'):
    r=c.post('/api/vehicle/competitions',headers={'X-User':'1'},json={'title':'无人车比赛','track':'oval','mode':mode,'laps':1,'max_time':90,'learn':False});assert r.status_code==200,r.text
    return r.json()['id']
def submit(c,cid,uid=2):
    r=c.post(f'/api/vehicle/competitions/{cid}/entries',headers={'X-User':str(uid)},data={'alias':'<script>同学','note':'test'},files={'file':('agent.zip',code())});assert r.status_code==200,r.text
    return r.json()['id']
def worker(c):return {'Authorization':'Bearer '+c.post('/api/vehicle/worker-key',headers={'X-User':'1'}).json()['token']}
def claim(c,w):return c.post('/api/vehicle/worker/claim',headers=w,json={'fingerprint':'a'*64}).json()['job']
def finish(c,w,job,reports):
    payload={'lease':job['lease'],'fingerprint':'a'*64,**reports};r=c.post(f'/api/vehicle/worker/{job["id"]}/result',headers=w,json=payload);assert r.status_code==200,r.text

def test_full_submission_leases_recompute_private_files(setup,trusted_reports):
    c,db=setup;cid=create(c);eid=submit(c,cid);w=worker(c);job=claim(c,w)
    assert job['id']==eid and len(job['config']['baseline_hash'])==64
    r=c.get(f'/api/vehicle/worker/{eid}/source',headers={**w,'X-Race-Lease':job['lease']});assert r.status_code==200 and hashlib.sha256(r.content).hexdigest()==job['sha']
    assert c.get(f'/api/vehicle/entries/{eid}/source',headers={'X-User':'3'}).status_code==404
    assert c.get('/api/vehicle/me',headers={'X-User':'4'}).status_code==403
    bad=copy.deepcopy(trusted_reports);bad['student']['frames'][5]['state'][1]+=3
    r=c.post(f'/api/vehicle/worker/{eid}/result',headers=w,json={'lease':job['lease'],'fingerprint':'a'*64,**bad});assert r.status_code==400
    finish(c,w,job,trusted_reports)
    board=c.get(f'/api/vehicle/competitions/{cid}/leaderboard',headers={'X-User':'2'}).json();assert board['rows'][0]['rank']==1 and board['rows'][0]['result']['student']['progress']==1
    assert c.get(f'/api/vehicle/entries/{eid}/replay',headers={'X-User':'2'}).status_code==200
    assert c.get(f'/api/vehicle/entries/{eid}/replay',headers={'X-User':'3'}).status_code==404
    assert c.post(f'/api/vehicle/worker/{eid}/heartbeat',headers=w,json={'lease':job['lease']}).status_code==409

def test_final_sealing_latest_and_publish(setup,trusted_reports):
    c,db=setup;cid=create(c,'final');old=submit(c,cid);eid=submit(c,cid);w=worker(c)
    assert claim(c,w) is None
    assert c.put(f'/api/vehicle/competitions/{cid}',headers={'X-User':'1'},json={'published':True}).status_code==409
    assert c.put(f'/api/vehicle/competitions/{cid}',headers={'X-User':'1'},json={'close':True}).status_code==200
    job=claim(c,w);assert job['id']==eid;finish(c,w,job,trusted_reports)
    assert c.get(f'/api/vehicle/entries/{eid}/replay',headers={'X-User':'2'}).status_code==403
    assert c.put(f'/api/vehicle/competitions/{cid}',headers={'X-User':'1'},json={'published':True}).status_code==200
    assert c.get(f'/api/vehicle/entries/{eid}/replay',headers={'X-User':'2'}).status_code==200
    assert c.post(f'/api/vehicle/entries/{eid}/exclude',headers={'X-User':'1'},json={'reason':'test'}).status_code==409
    c.put(f'/api/vehicle/competitions/{cid}',headers={'X-User':'1'},json={'published':False})
    assert c.get(f'/api/vehicle/entries/{eid}/replay',headers={'X-User':'2'}).status_code==403

def test_rotation_and_removed_student_cancel_jobs(setup):
    c,db=setup;cid=create(c);eid=submit(c,cid);w=worker(c);job=claim(c,w);new=worker(c)
    assert c.post(f'/api/vehicle/worker/{eid}/heartbeat',headers=w,json={'lease':job['lease']}).status_code==401
    assert c.post(f'/api/vehicle/worker/{eid}/heartbeat',headers=new,json={'lease':job['lease']}).status_code==409
    c.post(f'/api/vehicle/entries/{eid}/retry',headers={'X-User':'1'},json={'reason':'恢复运行'})
    job=claim(c,new)
    with db() as d:d.execute('UPDATE course_memberships SET active=0 WHERE user_id=2')
    assert c.post(f'/api/vehicle/worker/{eid}/heartbeat',headers=new,json={'lease':job['lease']}).status_code==409

def test_archive_and_transport_limits(setup):
    c,db=setup
    for name in ('../agent.py','/agent.py','agent.py\\x'):
        data=io.BytesIO()
        with zipfile.ZipFile(data,'w') as z:z.writestr(name,'x')
        with pytest.raises(ValueError):validate_archive(data.getvalue())
    assert c.post('/api/vehicle/worker/9/result',content=b'x'*11_000_001).status_code==413
    assert c.post('/api/vehicle/competitions',headers={'X-User':'2'},json={'title':'wrong'}).status_code==403
