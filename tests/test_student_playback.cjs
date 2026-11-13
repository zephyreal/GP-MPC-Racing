const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('gp_mpc_racing/static/app.js','utf8');
const ctx=vm.createContext({});vm.runInContext(source.slice(source.indexOf('function frameAt('),source.indexOf('function duration(')),ctx);
const frames=[{t:0,state:[0,0,Math.PI-.1,4,0,0],progress:0},{t:1,state:[10,20,-Math.PI+.1,6,0,0],progress:10}];
const mid=ctx.frameAt({frames},.5);assert.equal(mid.frame.state[0],5);assert.equal(mid.frame.state[1],10);assert.ok(Math.abs(mid.frame.state[2]-Math.PI)<1e-9);assert.equal(mid.frame.progress,5);
assert.equal(ctx.frameAt({frames},20).frame,frames[1]);assert.equal(ctx.frameAt({frames},0).frame,frames[0]);assert.equal(frames[0].state[0],0);
console.log('Playback interpolation and heading wrap passed');
