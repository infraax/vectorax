// ─── CHAT ─────────────────────────────────────────────────────────────

async function sendMsg() {
    const input = document.getElementById('user-input');
    const text  = input.value.trim();
    if (!text) return;
    input.value = '';
    const hist = document.getElementById('chat-history');
    const wrap = document.createElement('div'); wrap.className = 'flex justify-end w-full';
    const uDiv = document.createElement('div');
    uDiv.className = 'bg-slate-800 p-5 rounded-2xl rounded-tr-sm user-msg shadow-lg max-w-3xl text-sm text-slate-200 border border-slate-700/50';
    uDiv.textContent = text;
    wrap.appendChild(uDiv);
    hist.appendChild(wrap);
    hist.scrollTop = hist.scrollHeight;

    // Show typing indicator with node-aware status
    const typingEl = document.getElementById('typing-indicator');
    const typingTxt = document.getElementById('typing-status-txt');
    typingEl.classList.remove('hidden');
    if (typingTxt) typingTxt.textContent = 'Connecting to agent…';

    document.getElementById('context-container').innerHTML = '';
    _queryActive = true;
    _queryStartTs = Date.now();

    try {
        let body = { message: text };
        if (_useInjected && _injectedDocs.length) body.injected_docs = _injectedDocs;
        const r = await fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        typingEl.classList.add('hidden');
        _queryActive = false;
        highlightNode(null);
        const elapsed = ((Date.now() - _queryStartTs) / 1000).toFixed(1);

        if (r.status === 503 || r.status === 500) {
            const d = await r.json();
            appendAI('⚠️ **Blocked**: ' + (d.error || 'Server error'));
            return;
        }
        const d = await r.json();
        if (d.error) { appendAI('⚠️ **Error**: ' + d.error); return; }
        if (d.system_logs?.length) appendTrace(d.system_logs);
        if (d.token_usage) {
            const u = d.token_usage;
            _lastTokenUsage = u;
            updateTokenBar(u.system || 2000, u.context || 0, u.chat_history || 0, 32768);
        }
        appendAI(d.response, elapsed);
        updateContextPanel(d.sources);
        highlightMinimapSources(d.sources);
        setTimeout(() => loadQueryHistory(), 500);
    } catch (e) {
        typingEl.classList.add('hidden');
        _queryActive = false;
        appendAI('🛑 **Connection Refused**: FastAPI backend offline.');
    }
}

function appendAI(md, elapsed) {
    const hist = document.getElementById('chat-history');
    const wrap = document.createElement('div'); wrap.className = 'flex justify-start w-full';
    const d    = document.createElement('div');
    d.className = 'bg-slate-900 p-6 rounded-2xl rounded-tl-sm ai-msg shadow-lg max-w-4xl text-sm leading-relaxed text-slate-300 markdown-body w-full border border-slate-800/50';
    const c = document.createElement('div');
    c.innerHTML = marked.parse(md);
    d.appendChild(c);
    // Timing badge
    if (elapsed !== undefined) {
        const badge = document.createElement('div');
        badge.className = 'mt-3 pt-2 border-t border-slate-800/60 flex items-center gap-2';
        badge.innerHTML = `<i class="fa-solid fa-clock text-slate-600 text-[9px]"></i><span class="text-[9px] font-mono text-slate-600">Completed in ${elapsed}s</span>`;
        d.appendChild(badge);
    }
    wrap.appendChild(d);
    hist.appendChild(wrap);
    hist.scrollTop = hist.scrollHeight;
}

function appendUser(txt) {
    const hist = document.getElementById('chat-history');
    const wrap = document.createElement('div'); wrap.className = 'flex justify-end w-full';
    const d    = document.createElement('div');
    d.className = 'bg-slate-800 p-5 rounded-2xl rounded-tr-sm user-msg shadow-lg max-w-3xl text-sm text-slate-200 border border-slate-700/50';
    d.textContent = txt;
    wrap.appendChild(d);
    hist.appendChild(wrap);
    hist.scrollTop = hist.scrollHeight;
}

function appendTrace(logs) {
    const hist = document.getElementById('chat-history');
    const wrap = document.createElement('div'); wrap.className = 'flex justify-start w-full opacity-75 mb-[-1rem]';
    const d    = document.createElement('div');
    d.className = 'system-trace p-4 rounded-xl shadow-md max-w-4xl text-xs leading-relaxed text-slate-400 markdown-body w-full';
    d.innerHTML = `<strong class="text-slate-300 uppercase tracking-widest text-[9px] mb-2 block"><i class="fa-solid fa-code-branch mr-2"></i>LangGraph Trace</strong><ul class="space-y-1">`
        + logs.map(l => `<li class="-ml-3 py-0.5 border-b border-slate-700/20">${marked.parseInline(l)}</li>`).join('')
        + '</ul>';
    wrap.appendChild(d);
    hist.appendChild(wrap);
    hist.scrollTop = hist.scrollHeight;
}

// ─── Update typing indicator text from node status ────────────────────
function updateTypingStatus(nodeName) {
    if (!_queryActive) return;
    const el = document.getElementById('typing-status-txt');
    if (!el) return;
    const labels = {
        retrieve: '🔍 Retrieving from ChromaDB…',
        generate: '🧠 Generating with LLM…',
        validate: '✅ Validating sources…',
    };
    el.textContent = labels[nodeName] || 'Processing…';
}

function updateContextPanel(sources) {
    const c = document.getElementById('context-container');
    if (!sources || !sources.length) {
        c.innerHTML = '<div class="text-center text-slate-600 font-mono text-[10px] italic mt-10">Context query yielded 0 nodes.</div>';
        return;
    }
    c.innerHTML = '';
    sources.forEach(s => {
        const score      = s.score || 0;
        const scoreColor = score >= 0.7 ? '#10b981' : score >= 0.5 ? '#fbbf24' : '#f43f5e';
        const card       = document.createElement('div');
        card.className   = 'bg-[#030712] border border-slate-700/50 rounded-xl p-2.5 shadow-md';
        const shortName  = s.filename.split('__').pop() || s.filename;
        card.innerHTML = `<div class="flex items-center gap-2 mb-1.5 border-b border-slate-800 pb-1.5">
            <i class="fa-solid fa-file-code text-accent text-[9px]"></i>
            <span class="text-[9px] font-bold text-slate-300 font-mono truncate flex-1" title="${s.filename}">${shortName}</span>
            <span class="text-[8px] font-mono flex-shrink-0" style="color:${scoreColor}">${Math.round(score * 100)}%</span>
        </div>
        <div class="h-1 rounded mb-1.5 overflow-hidden bg-slate-800"><div class="h-full rounded" style="width:${score * 100}%;background:${scoreColor}"></div></div>
        <div class="text-[8px] text-slate-500 leading-relaxed font-mono max-h-20 overflow-hidden">${s.snippet || ''}</div>`;
        c.appendChild(card);
    });
}

// ─── TOKEN BAR ────────────────────────────────────────────────────────
function updateTokenBar(sys, ctx, pmt, total) {
    const limit = 32768;
    const free  = Math.max(0, limit - sys - ctx - pmt);
    document.getElementById('tok-bar-sys').style.width  = ((sys  / limit) * 100).toFixed(1) + '%';
    document.getElementById('tok-bar-ctx').style.width  = ((ctx  / limit) * 100).toFixed(1) + '%';
    document.getElementById('tok-bar-pmt').style.width  = ((pmt  / limit) * 100).toFixed(1) + '%';
    document.getElementById('tok-bar-free').style.width = ((free / limit) * 100).toFixed(1) + '%';
    document.getElementById('tok-sys').textContent  = sys  >= 1000 ? (sys  / 1000).toFixed(1) + 'k' : sys;
    document.getElementById('tok-ctx').textContent  = ctx  >= 1000 ? (ctx  / 1000).toFixed(1) + 'k' : ctx;
    document.getElementById('tok-pmt').textContent  = pmt  >= 1000 ? (pmt  / 1000).toFixed(1) + 'k' : pmt;
    document.getElementById('tok-free').textContent = free >= 1000 ? (free / 1000).toFixed(1) + 'k' : free;
    document.getElementById('tok-used-pct').textContent = Math.round(((sys + ctx + pmt) / limit) * 100) + '%';
}

// ─── MEMORY / EXPORT ─────────────────────────────────────────────────
async function clearMemory() {
    // Clears only the in-memory conversation buffer — no database entries are affected
    try {
        await fetch('/api/memory', { method: 'DELETE' });
        const badge = document.getElementById('p1-mem-turns-badge');
        if (badge) { badge.textContent = '0 turns'; badge.classList.add('hidden'); }
        // Show user-friendly confirmation in chat
        const hist = document.getElementById('chat-history');
        const note = document.createElement('div');
        note.className = 'flex justify-center w-full my-1';
        note.innerHTML = '<span class="text-[9px] font-mono text-slate-600 bg-slate-900 px-3 py-1 rounded-full border border-slate-800">Conversation memory cleared — query history & database unchanged</span>';
        hist.appendChild(note);
        hist.scrollTop = hist.scrollHeight;
    } catch (e) {}
}

async function exportToObsidian() {
    const title = prompt('Export session title:');
    if (!title) return;
    try {
        // Get the current session id from the most recent history entry
        let sid = _currentSessionId;
        if (!sid) {
            const hist = await fetch('/api/query_history?n=1').then(r => r.json());
            sid = (hist.entries || [])[0]?.session_id || '';
        }
        if (!sid) { alert('No session to export — send a query first.'); return; }
        const r = await fetch('/api/export/obsidian', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: sid, title })
        });
        const d = await r.json();
        if (d.status === 'ok') alert('Exported to Vault:\n' + d.path);
        else alert('Export failed: ' + (d.message || 'Unknown error'));
    } catch (e) { alert('Export error: ' + e.message); }
}

// ─── LOG STREAM POLL ─────────────────────────────────────────────────
function pollLogStream() {
    fetch(`/api/log/stream?since=${_lastLogTs}`)
        .then(r => r.json())
        .then(d => {
            // Backend returns "entries", not "events"
            const evts = d.entries || d.events || [];
            if (!evts.length) return;
            const feed = document.getElementById('p1-log-feed');
            if (!feed) return;
            evts.forEach(ev => {
                _lastLogTs = ev.ts || _lastLogTs;
                const evType = (ev.event || '').toLowerCase();
                let cls = 'text-slate-500';
                if (evType.includes('node') || evType.includes('retrieve') || evType.includes('generate') || evType.includes('validate')) cls = 'log-node';
                else if (evType.includes('startup') || evType.includes('start')) cls = 'log-startup';
                else if (evType.includes('pca'))   cls = 'log-pca';
                else if (evType.includes('query')) cls = 'log-query';
                else if (evType.includes('error')) cls = 'log-error';
                const row = document.createElement('div');
                row.className = cls + ' font-mono text-[9px] leading-relaxed';
                const tsStr = ev.ts != null ? `[${(ev.ts).toFixed(1)}s]` : '';
                row.textContent = `${tsStr} ${ev.event || ''}`;
                feed.appendChild(row);
            });
            while (feed.children.length > 30) feed.removeChild(feed.firstChild);
            feed.scrollTop = feed.scrollHeight;
        }).catch(() => {});
}

// ─── MINIMAP HIGHLIGHT ────────────────────────────────────────────────
function highlightMinimapSources(sources) {
    if (!_pcaPoints || !sources || !sources.length) return;
    renderP1Minimap(sources);
}
