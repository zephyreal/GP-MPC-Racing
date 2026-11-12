import hashlib,json,math
from pathlib import Path
from gp_mpc_racing.engine import make_track,Race,Track
from tools.export_original_track import build

ROOT=Path(__file__).parents[1]

def test_all_original_files_are_byte_preserved():
    root=ROOT/'matlab_original';manifest=json.loads((root/'MANIFEST.json').read_text());assert len(manifest['files'])==36
    for entry in manifest['files']:
        data=(root/entry['path']).read_bytes()
        assert len(data)==entry['bytes'] and hashlib.sha256(data).hexdigest()==entry['sha256'],entry['path']
    assert manifest['archive_sha256']=='8c263b79260570887be39c1a7e5901660bb86a9b3c0ac2ad3eb1ed72f5b89e32'

def test_default_original_map_exact_sampling_and_boundaries():
    track=make_track();assert track.identifier=='track02-original-v1' and track.width==6 and len(track.points)==391
    assert track.points[0]==[.5,0] and track.points[27]==[14,0]
    angle=math.radians(5);p=track.points[28]
    assert abs(p[0]-(14+15*math.sin(angle)))<1e-12 and abs(p[1]-(-15+15*math.cos(angle)))<1e-12
    for center,left,right in zip(track.points,track.left,track.right):
        assert math.dist(left,right)==__import__('pytest').approx(6)
        assert max(abs(center[i]-(left[i]+right[i])/2) for i in (0,1))<1e-12
    assert track.closed is False
    race=Race(track);assert race.state==[5,0,0,10,0,0] and race.s>0
    roundtrip=Track.from_public(track.public());assert roundtrip.public()==track.public()

def test_map_generated_from_original_method_not_a_replacement():
    source=ROOT/'matlab_original/GP_MPC_Desktop_V3/classes/RaceTrack.m'
    rebuilt=build(source);checked=json.loads((ROOT/'gp_mpc_racing/data/track02-original-v1.json').read_text())
    assert rebuilt==checked and len(checked['source']['segments'])==20
    assert checked['source']['straight_step_m']==.5 and checked['source']['arc_step_degrees']==5
    assert make_track('oval').points!=make_track().points
    # v0.1 reference identifier remains the old reconstruction, so saved races do not silently change maps.
    assert make_track('reference').points!=make_track().points

def test_reference_api_defaults_and_parser_installed(tmp_path,monkeypatch):
    import sqlite3
    from contextlib import contextmanager
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from gp_mpc_racing.server import register,Competition
    @contextmanager
    def db():
        c=sqlite3.connect(tmp_path/'db');c.row_factory=sqlite3.Row
        try:yield c;c.commit()
        finally:c.close()
    app=FastAPI();user=lambda:{'id':1,'role':'teacher','name':'老师'}
    register(app,{'db':db,'current':user,'teacher':user,'DATA':tmp_path},demo=True)
    c=TestClient(app);ref=c.get('/api/vehicle/reference').json()
    assert ref['points']==make_track().points and len(ref['left'])==391
    assert c.get('/courses/design/vehicle/replay-format.js').status_code==200
    assert Competition(title='原地图').track=='track02-original-v1'
