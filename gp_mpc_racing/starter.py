"""Downloadable local workspace; no student code is executed while packaging."""
import io,json,zipfile,html
from pathlib import Path
from .engine import make_track

def build_starter(config):
    root=Path(__file__).parent;output=io.BytesIO();track=make_track(config['track']).public()
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted((root/'student').iterdir()):
            if p.is_file():z.writestr(p.name,p.read_bytes())
        for name in ('__init__.py','engine.py','controllers.py','function_adapter.py','data/track02-original-v1.json'):
            z.writestr('gp_mpc_racing/'+name,(root/name).read_bytes())
        import re
        lesson=(root/'static/teaching.html').read_text()
        lesson=re.sub(r'<a href="/api/vehicle/teaching/v8/[^"]+">(.*?)</a>',r'\1（请回到课程网站下载）',lesson)
        z.writestr('teaching.html',lesson)
        z.writestr('START_HERE.html',(root/'static/tutorial.html').read_bytes())
        z.writestr('competition.json',json.dumps(config,ensure_ascii=False,indent=2))
        z.writestr('track.json',json.dumps(track,ensure_ascii=False,indent=2))
        pts=track['points'];xs=[p[0] for p in pts];ys=[p[1] for p in pts]
        x,y=min(xs)-10,min(ys)-10;w,h=max(xs)-x+10,max(ys)-y+10
        points=' '.join(f'{p[0]},{-p[1]}' for p in pts+[pts[0]])
        z.writestr('map.html',f'<meta charset="utf-8"><title>比赛地图</title><h1>{html.escape(track["name"])}</h1><p>单位：米；x向右，y向上；红点为参考起点，沿数据点顺序行驶。车辆宽1.6m、长3.8m。完整数据见track.json。</p><svg style="width:95vw;height:75vh" viewBox="{x} {-y-h} {w} {h}"><polyline points="{points}" fill="none" stroke="#aabcad" stroke-width="{track["width"]}"/><circle cx="{pts[0][0]}" cy="{-pts[0][1]}" r="1" fill="red"/></svg>')
    return output.getvalue()
