/* Only fixed event names, section identifiers, counters and timings leave this file. */
(() => {
    const token = document.currentScript.dataset.token;
    if (!token) return;
    const endpoint = '/learning-event?token=' + encodeURIComponent(token);
    const storageKey = 'telemetry-failures:' + token;
    const operations = ['interaction', 'quiz', 'training_progress', 'page_load'];
    let pending = {};
    try {
        const saved = JSON.parse(sessionStorage.getItem(storageKey) || '{}');
        for (const key of operations) if (Number.isInteger(saved[key]) && saved[key] > 0) pending[key] = Math.min(100, saved[key]);
    } catch (_) {}
    function persist() {try {sessionStorage.setItem(storageKey, JSON.stringify(pending));} catch (_) {}}
    function failed(operation) {
        if (!operations.includes(operation)) return;
        pending[operation] = Math.min(100, (pending[operation] || 0) + 1);
        persist();
    }
    async function post(data) {
        const response = await fetch(endpoint, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data), keepalive:true});
        if (!response.ok) throw new Error('Telemetry unavailable');
    }
    let flushing = false;
    async function flushFailures() {
        if (flushing) return;
        flushing = true;
        try {
            for (const operation of Object.keys(pending)) {
                const count = pending[operation];
                await post({event:'client_request_failed', operation, count});
                pending[operation] -= count;
                if (!pending[operation]) delete pending[operation];
                persist();
            }
        } catch (_) {/* Retain counters until the connection recovers; no recursive reporting. */}
        finally {flushing = false;}
    }
    window.telemetryFetch = async (operation, url, options) => {
        let response;
        try {response = await fetch(url, options);}
        catch (error) {failed(operation); void flushFailures(); throw error;}
        if (response.status >= 500) {failed(operation); void flushFailures();}
        return response;
    };
    window.addEventListener('error', () => failed('page_load'));
    window.addEventListener('online', flushFailures);
    setInterval(flushFailures, 20000);
    void flushFailures();

    if (!document.querySelector('[data-training-section]')) return;
    const seen = new Set();
    if ('IntersectionObserver' in window) {
        const observer = new IntersectionObserver(entries => {
            for (const entry of entries) {
                const section = entry.target.dataset.trainingSection;
                if (entry.isIntersecting && !document.hidden && !seen.has(section)) {
                    seen.add(section);
                    post({event:'training_section_viewed', section}).catch(() => {seen.delete(section); failed('training_progress');});
                }
            }
        }, {threshold:0.5});
        document.querySelectorAll('[data-training-section]').forEach(node => observer.observe(node));
    }
    if (!window.crypto || !crypto.randomUUID) return;
    const sessionId = crypto.randomUUID();
    let activeMs = 0, previous = performance.now(), lastInteraction = previous;
    let wasActive = !document.hidden && document.hasFocus();
    function tick() {
        const current = performance.now();
        if (wasActive && previous-lastInteraction < 60000) activeMs += Math.min(5000, current-previous);
        previous = current;
        wasActive = !document.hidden && document.hasFocus();
    }
    for (const name of ['pointerdown', 'keydown', 'scroll', 'touchstart']) {
        window.addEventListener(name, () => {lastInteraction=performance.now();}, {passive:true});
    }
    async function checkpoint() {
        tick();
        try {await post({event:'training_activity', session_id:sessionId, active_seconds:Math.min(86400, Math.floor(activeMs/1000))});}
        catch (_) {failed('training_progress');}
    }
    document.addEventListener('visibilitychange', () => {tick(); if (document.hidden) void checkpoint();});
    window.addEventListener('blur', tick);
    window.addEventListener('focus', () => {lastInteraction=performance.now(); tick();});
    window.addEventListener('pagehide', checkpoint);
    setInterval(tick, 5000);
    setInterval(checkpoint, 30000);
})();
