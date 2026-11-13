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
    assert c.post('/api/vehicle/worker/9/result',content=b'x'*41_000_001).status_code==413
    assert c.post('/api/vehicle/competitions',headers={'X-User':'2'},json={'title':'wrong'}).status_code==403

def test_single_file_upload_deduplicates_without_execution(setup):
    c,db=setup;cid=create(c)
    files={'file':('agent.py',b'raise RuntimeError("website must never run this")')}
    url=f'/api/vehicle/competitions/{cid}/entries'
    first=c.post(url,headers={'X-User':'2'},files=files);assert first.status_code==200,first.text
    second=c.post(url,headers={'X-User':'2'},files=files)
    assert second.json()['id']==first.json()['id'] and second.json()['reused']
    bad=c.post(url,headers={'X-User':'2'},files={'file':('agent.py',b'def broken(:')})
    assert bad.status_code==400
    changed=c.post(url,headers={'X-User':'2'},files={'file':('agent.py',b'pass')})
    assert changed.status_code==200
    with db() as d:assert d.execute('SELECT state FROM vehicle_entries WHERE id=?',(first.json()['id'],)).fetchone()[0]=='superseded'

def test_shared_compute_slot_blocks_vehicle_and_expires(setup):
    c,db=setup;cid=create(c);submit(c,cid);w=worker(c)
    import time
    with db() as d:
        d.execute('CREATE TABLE arena_entries(state TEXT,lease_until REAL)')
        d.execute('INSERT INTO arena_entries VALUES(?,?)',('running',time.time()+90))
    assert claim(c,w) is None
    with db() as d:d.execute('UPDATE arena_entries SET lease_until=0')
    assert claim(c,w) is not None

def test_teacher_cache_reused_only_for_frozen_environment(setup,trusted_reports):
    c,db=setup;cid=create(c);submit(c,cid);w=worker(c);job=claim(c,w)
    assert not job['teacher_cached'];finish(c,w,job,trusted_reports)
    submit(c,cid,uid=3);job=claim(c,w);assert job['teacher_cached']
    finish(c,w,job,{'student':trusted_reports['student']})
    with db() as d:assert d.execute('SELECT COUNT(*) FROM vehicle_baselines').fetchone()[0]==1
    cid2=create(c);submit(c,cid2)
    job=c.post('/api/vehicle/worker/claim',headers=w,json={'fingerprint':'b'*64}).json()['job']
    assert not job['teacher_cached']

def test_downloaded_starter_runs_outside_repository(setup,tmp_path):
    import subprocess,sys
    c,db=setup;cid=create(c)
    response=c.get(f'/api/vehicle/starter?cid={cid}',headers={'X-User':'2'})
    assert response.status_code==200
    target=tmp_path/'download';target.mkdir()
    with zipfile.ZipFile(io.BytesIO(response.content)) as z:
        assert {'agent.py','local_test.py','track.json','map.html','01_setup.bat','03_test_official.bat'}<=set(z.namelist())
        z.extractall(target)
    run=subprocess.run([sys.executable,'local_test.py','--official'],cwd=target,capture_output=True,text=True,timeout=60)
    assert run.returncode==0,run.stdout+run.stderr
    result=json.loads((target/'output/local_result.json').read_text())
    assert result['student']['status']=='completed'
    assert (target/'output/report.html').exists()

def test_ten_lap_configuration(setup):
    c,db=setup
    r=c.post('/api/vehicle/competitions',headers={'X-User':'1'},json={'title':'十圈比赛','laps':10,'max_time':1200})
    assert r.status_code==200,r.text
    assert c.post('/api/vehicle/competitions',headers={'X-User':'1'},json={'title':'超限比赛','laps':11}).status_code==422

def test_beginner_tutorial_and_single_launcher(setup,tmp_path):
    import subprocess,sys
    c,db=setup
    response=c.get('/courses/design/vehicle/tutorial.html')
    assert response.status_code==200 and 'SPEED = 7.0' in response.text
    response=c.get('/api/vehicle/starter',headers={'X-User':'2'})
    target=tmp_path/'beginner';target.mkdir()
    with zipfile.ZipFile(io.BytesIO(response.content)) as z:
        assert {'START.bat','launch.py','START_HERE.html'}<=set(z.namelist())
        z.extractall(target)
    script="import launch,sys; from pathlib import Path; launch.prepare=lambda:Path(sys.executable); launch.open_file=lambda p:None; choices=iter(['1','0']); launch.input=lambda _:next(choices); launch.main()"
    run=subprocess.run([sys.executable,'-c',script],cwd=target,capture_output=True,text=True,timeout=60)
    assert run.returncode==0,run.stdout+run.stderr
    result=json.loads((target/'output/local_result.json').read_text())
    assert result['student']['completed_laps']==1
    assert result['config']['laps']==1 and result['config']['track']=='oval'
    history=[p for p in (target/'output').iterdir() if p.is_dir()]
    assert len(history)==1 and (history[0]/'agent.py').read_bytes()==(target/'agent.py').read_bytes()
