import hashlib,io,zipfile,json,subprocess,sys
from pathlib import Path
from gp_mpc_racing.starter import build_starter
from test_server import setup

ROOT=Path(__file__).resolve().parents[1]/'gp_mpc_racing'

def test_original_v8_archive_and_teacher_separation():
    manifest=json.loads((ROOT/'teaching/V8_SOURCE.json').read_text())
    content=(ROOT/'teaching/GP_MPC_Desktop_V8.zip').read_bytes()
    assert hashlib.sha256(content).hexdigest()==manifest['archive_sha256']
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        for name,sha in manifest['files'].items():
            assert hashlib.sha256(z.read('GP_MPC_Desktop_V8/'+name)).hexdigest()==sha
    assert 'Racing Car · 无人车竞赛' not in (ROOT/'static/entry.js').read_text()


def test_teaching_download_permissions(setup):
    client,db=setup
    url='/api/vehicle/teaching/v8/download'
    assert client.get(url).status_code==401
    assert client.get(url,headers={'X-User':'4'}).status_code==403
    response=client.get(url,headers={'X-User':'2'})
    assert response.status_code==200 and response.content==(ROOT/'teaching/GP_MPC_Desktop_V8.zip').read_bytes()
    assert client.get('/courses/design/vehicle/teaching.html').status_code==200
    assert client.get('/api/vehicle/teaching/v8/python',headers={'X-User':'2'}).status_code==200


def test_enable_student_example_preserves_code_and_runs(tmp_path):
    cfg={'track':'oval','laps':1,'max_time':180,'seed':1}
    with zipfile.ZipFile(io.BytesIO(build_starter(cfg))) as z:z.extractall(tmp_path)
    original=(tmp_path/'agent.py').read_bytes()
    script="import launch,sys;from pathlib import Path;launch.prepare=lambda:Path(sys.executable);launch.open_file=lambda p:None;choices=iter(['6','1','0']);launch.input=lambda _:next(choices);launch.main()"
    run=subprocess.run([sys.executable,'-c',script],cwd=tmp_path,capture_output=True,text=True,timeout=120)
    assert run.returncode==0,run.stdout+run.stderr
    assert next((tmp_path/'output').glob('code-backup-*/agent.py')).read_bytes()==original
    report=json.loads((tmp_path/'output/local_result.json').read_text())
    assert report['student']['completed_laps']==1 and report['student']['status']=='completed'
    assert (tmp_path/'teaching.html').exists()
