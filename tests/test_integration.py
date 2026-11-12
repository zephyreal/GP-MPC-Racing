import importlib,sqlite3,sys,types
from contextlib import contextmanager
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

def test_extension_reuses_course_and_adds_navigation(tmp_path,monkeypatch):
    fake=types.ModuleType('app');fake.app=FastAPI();fake.DATA=tmp_path
    @contextmanager
    def db():
        c=sqlite3.connect(tmp_path/'db');c.row_factory=sqlite3.Row
        try:yield c;c.commit()
        except Exception:c.rollback();raise
        finally:c.close()
    fake.db=db;fake.current=lambda:{'id':1,'name':'老师','role':'teacher'};fake.teacher=fake.current
    @fake.app.get('/')
    def original_home():return HTMLResponse('<html><body>Original course</body></html>')
    monkeypatch.setitem(sys.modules,'app',fake);sys.modules.pop('gp_mpc_racing.integrated',None)
    extension=importlib.import_module('gp_mpc_racing.integrated');client=TestClient(extension.app)
    response=client.get('/');assert response.status_code==200 and 'Original course' in response.text and '/courses/design/vehicle/entry.js?v=' in response.text
    assert client.get('/api/vehicle/me').json()['name']=='老师'
    assert client.get('/courses/design/vehicle/entry.js').status_code==200
