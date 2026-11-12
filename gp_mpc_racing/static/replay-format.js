'use strict';
// Original recordings are local display data only; this parser never posts scores or runs code.
function parseOriginalReplay(data,reference){
 if(!data||data.schema!=='matlab-original-dual-replay-v1'||data.recording_only!==true||data.config?.engine!=='matlab-original-v3-replay')throw Error('请选择原版适配器导出的双车JSON，不接受代码或普通成绩文件');
 const finite=v=>typeof v==='number'&&Number.isFinite(v),matrix=(a,n,cols)=>Array.isArray(a)&&a.length===n&&a.every(row=>Array.isArray(row)&&row.length===cols&&row.every(v=>finite(v)&&Math.abs(v)<1e7));
 const map=data.track,n=reference.points.length;
 if(!map||map.width!==reference.width||!finite(map.length)||map.length<=0)throw Error('原地图宽度或长度无效');
 for(const key of ['points','left','right']){
  if(!matrix(map[key],n,2))throw Error('原地图坐标维度不符');
  if(map[key].some((p,i)=>p.some((v,j)=>Math.abs(v-reference[key][i][j])>1e-6)))throw Error('地图与原Track02逐点坐标不一致，请导出同一份原地图');
 }
 if(map.source?.sha256&&map.source.sha256!==reference.source.sha256)throw Error('RaceTrack.m源码版本不符，请先核对原始地图文件');
 if(!Number.isInteger(data.config.laps)||data.config.laps<1||data.config.laps>100)throw Error('圈数无效');
 for(const key of ['teacher','student']){
  const run=data[key];if(!run||!Array.isArray(run.frames)||run.frames.length<2||run.frames.length>20000)throw Error('轨迹帧数无效');
  let previous=-1;
  for(const frame of run.frames){
   if(!finite(frame.t)||frame.t<0||frame.t<=previous||frame.t>86400||!matrix([frame.state],1,6)||!matrix([frame.original_state],1,7)||!matrix([frame.original_control],1,3)||!matrix([frame.action],1,2)||!finite(frame.progress)||!finite(frame.solve_ms)||frame.solve_ms<0)throw Error('轨迹缺少原7维状态、3维控制或有效时间记录');
   if(frame.state.some((v,i)=>Math.abs(v-frame.original_state[i])>1e-9))throw Error('显示状态与原始状态不一致');
   previous=frame.t;
  }
  if(!['completed','failed','timeout'].includes(run.status)||!finite(run.progress)||!finite(run.simulated_seconds))throw Error('原结果摘要无效');
  if(typeof run.lap_times==='number')run.lap_times=[run.lap_times];
  if(!Array.isArray(run.lap_times)||run.lap_times.some(t=>!finite(t)||t<=0))throw Error('原圈速记录无效');
 }
 map.closed=false;return data;
}
