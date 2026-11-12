const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert');
const root=path.join(__dirname,'..'),context=vm.createContext({console});vm.runInContext(fs.readFileSync(path.join(root,'gp_mpc_racing/static/replay-format.js'),'utf8'),context);
const reference=JSON.parse(fs.readFileSync(path.join(root,'gp_mpc_racing/data/track02-original-v1.json'),'utf8'));
reference.length=200;
const run={status:'timeout',reason:'本地原记录',progress:.01,simulated_seconds:.15,lap_times:[],frames:[{t:0,state:[5,0,0,10,0,0],original_state:[5,0,0,10,0,0,5],original_control:[0,0,0],action:[0,0],progress:0,solve_ms:0},{t:.15,state:[6.5,0,0,10,0,0],original_state:[6.5,0,0,10,0,0,6.5],original_control:[0,.1,10],action:[0,.1],progress:1.5,solve_ms:100}]};
const fixture={schema:'matlab-original-dual-replay-v1',recording_only:true,track:structuredClone(reference),config:{engine:'matlab-original-v3-replay',laps:5},teacher:structuredClone(run),student:structuredClone(run)};
function parse(data){context.data=data;context.reference=reference;return vm.runInContext('parseOriginalReplay(data,reference)',context)}
const result=parse(structuredClone(fixture));assert(result.teacher.frames[1].original_control[2]===10&&result.recording_only===true);
let bad=structuredClone(fixture);bad.track.left[30][0]+=.1;assert.throws(()=>parse(bad),/逐点坐标/);
bad=structuredClone(fixture);bad.teacher.frames[1].original_state.pop();assert.throws(()=>parse(bad),/7维状态/);
bad=structuredClone(fixture);bad.student.frames[1].t=0;assert.throws(()=>parse(bad),/有效时间/);
bad=structuredClone(fixture);bad.track.source.sha256='x';assert.throws(()=>parse(bad),/源码版本/);
bad=structuredClone(fixture);bad.recording_only=false;assert.throws(()=>parse(bad),/原版适配器/);
bad=structuredClone(fixture);bad.teacher.lap_times=1.5;assert.deepStrictEqual(Array.from(parse(bad).teacher.lap_times),[1.5]);
const script=fs.readFileSync(path.join(root,'gp_mpc_racing/static/app.js'),'utf8');assert(script.includes('map.left')&&script.includes('map.right')&&script.includes('parseOriginalReplay'));assert(!script.includes('Array.from({length:180}'));
console.log('Original replay validation, raw state/control retention, geometry checks and no-ellipse fallback passed');
