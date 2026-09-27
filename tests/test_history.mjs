import assert from 'node:assert/strict';
import test from 'node:test';
await import('../portal/history.js');
const now = Date.parse('2026-09-27T12:00:00Z');
const b = (minutes, seq, extras = {}) => ({created_at_utc: new Date(now - minutes*60000).toISOString(), first_sequence: seq, last_sequence: seq, boot_id: 1, temperature: {minimum: -2, average: 0, maximum: 2}, ...extras});
test('sorts, clips time window and keeps zero/negative values', () => {
 const s = RialoHistory.summarize([b(0,2), b(5,1), b(61,0), b(-1,3)],1,now);
 assert.equal(s.count,2); assert.equal(s.segments.length,1); assert.equal(s.minimum,-2);assert.equal(s.average,0);
});
test('breaks gaps, missing sequences, sessions and invalid values', () => {
 for (const next of [b(0,2), b(15,3), b(15,2,{boot_id:2}), b(15,2,{simulated:true})]) {
  assert.equal(RialoHistory.summarize([b(20,1), next],1,now).segments.length,2);
 }
 const s=RialoHistory.summarize([b(10,1),b(5,2,{temperature:{average:null}}),b(0,3)],1,now);
 assert.equal(s.count,2);assert.equal(s.segments.length,2);
});
test('empty period has no invented temperature',()=>{
 const s=RialoHistory.summarize([],24,now);assert.equal(s.average,null);assert.deepEqual(s.segments,[]);
});
