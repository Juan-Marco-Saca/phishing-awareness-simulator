const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const listeners = {}, timers = {}, requests = [];
let now = 0, focused = true, observer;
const document = {
    currentScript: {dataset: {token: 'test-token'}}, hidden: false,
    hasFocus: () => focused,
    querySelector: () => ({}), querySelectorAll: () => [],
    addEventListener: (name, fn) => {listeners[name] = fn;}
};
const window = {crypto: {randomUUID: () => '12345678-1234-1234-1234-123456789012'},
    addEventListener: (name, fn) => {listeners[name] = fn;}, IntersectionObserver: true};
const context = {window, document, crypto: window.crypto, performance: {now: () => now},
    setInterval: (fn, delay) => {timers[delay] = fn;},
    sessionStorage: {getItem: () => null, setItem: () => {}},
    IntersectionObserver: class {constructor(fn) {observer=fn;} observe() {}},
    fetch: async (url, options) => {
        if (url === '/fail') throw new Error('Offline');
        requests.push(JSON.parse(options.body)); return {ok:true, status:200};
    }};
vm.runInNewContext(fs.readFileSync('static/learning.js', 'utf8'), context);
function advance(to) {for (;now<to;) {now+=5000; timers[5000]();}}
(async () => {
    advance(20000);
    document.hidden=true; focused=false; listeners.visibilitychange();
    advance(40000);
    document.hidden=false; focused=true; listeners.focus();
    advance(120000);
    await timers[30000]();
    const activity = requests.filter(r => r.event === 'training_activity');
    assert.equal(activity.at(-1).active_seconds, 80, 'Hidden time and idle time must be excluded');
    observer([{isIntersecting:true, target:{dataset:{trainingSection:'warning_signs'}}}]);
    observer([{isIntersecting:true, target:{dataset:{trainingSection:'warning_signs'}}}]);
    assert.equal(requests.filter(r => r.event==='training_section_viewed').length, 1);
    await assert.rejects(window.telemetryFetch('quiz', '/fail', {}));
    await new Promise(resolve => setImmediate(resolve));
    assert.ok(requests.some(r => r.event==='client_request_failed' && r.operation==='quiz' && r.count===1));
    assert.ok(requests.every(r => Object.keys(r).every(k => ['event','section','session_id','active_seconds','operation','count'].includes(k))));
    console.log('Learning browser behavior passed: active-time pause, idle cutoff, section deduplication, failure reporting.');
})().catch(error => {console.error(error); process.exitCode=1;});
