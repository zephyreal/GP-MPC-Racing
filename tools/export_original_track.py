"""Translate only original Track02 geometry instructions, with MATLAB colon sampling semantics.
No dynamics or controller is executed. MATLAB export_original_track.m is the native reference path.
"""
import hashlib,json,math,re
from pathlib import Path

def build(source):
    text=Path(source).read_text();section=text.split('function [trackdata, x0, th0, w] = loadTrack_02()',1)[1].split('function [track_l,track_r,psi_c]',1)[0]
    width=float(re.search(r'\bw\s*=\s*([0-9.]+)',section).group(1));pattern=r"'s'\s*,\s*([0-9.]+)|'c'\s*,\s*\{\s*([0-9.]+)\s*,\s*(-?[0-9.]+)\s*\}"
    segments=[['s',float(a)] if a else ['c',float(b),float(c)] for a,b,c in re.findall(pattern,section)]
    center=[];left=[];right=[];headings=[];x=y=h=0.
    def append(cx,cy,heading):
        center.append([cx,cy]);left.append([cx-width/2*math.sin(heading),cy+width/2*math.cos(heading)]);right.append([cx+width/2*math.sin(heading),cy-width/2*math.cos(heading)]);headings.append(heading)
    for item in segments:
        if item[0]=='s':
            length=item[1]
            for i in range(1,math.floor(length/.5+1e-12)+1):append(x+i*.5*math.cos(h),y+i*.5*math.sin(h),h)
            x+=length*math.cos(h);y+=length*math.sin(h)
        else:
            radius,degrees=item[1:];sign=1 if degrees>0 else -1
            for i in range(1,math.floor(abs(degrees)/5+1e-12)+1):
                angle=math.radians(sign*i*5);dx=sign*radius*math.sin(angle);dy=sign*radius*(1-math.cos(angle));append(x+dx*math.cos(h)-dy*math.sin(h),y+dx*math.sin(h)+dy*math.cos(h),h+angle)
            angle=math.radians(degrees);dx=sign*radius*math.sin(angle);dy=sign*radius*(1-math.cos(angle));x+=dx*math.cos(h)-dy*math.sin(h);y+=dx*math.sin(h)+dy*math.cos(h);h+=angle
    return {'schema':'original-track-v1','id':'track02-original-v1','name':'原项目 Track02','points':center,'left':left,'right':right,'heading':headings,'width':width,'closed':False,'initial_state':[5,0,0,10,0,0],
        'source':{'kind':'original-matlab-geometry-translation','file':'matlab_original/GP_MPC_Desktop_V3/classes/RaceTrack.m','sha256':hashlib.sha256(Path(source).read_bytes()).hexdigest(),'method':'loadTrack_02 + generateTrackPoints','straight_step_m':.5,'arc_step_degrees':5,'segments':segments,'note':'Geometry translated from unchanged MATLAB source; native export available for numerical cross-check.'}}
if __name__=='__main__':
    root=Path(__file__).resolve().parents[1];data=build(root/'matlab_original/GP_MPC_Desktop_V3/classes/RaceTrack.m');output=root/'gp_mpc_racing/data/track02-original-v1.json';output.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':'))+'\n');print(str(len(data['points']))+' original-sampling points, width '+str(data['width'])+' m')
