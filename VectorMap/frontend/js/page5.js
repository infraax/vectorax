// ─── PAGE 5: INTELLIGENCE TOOLS ──────────────────────────────────────

// ─── PAGE 5 TABS ─────────────────────────────────────────────────────
const P5_TABS = ['refactor', 'arch', 'web', 'log', 'token'];

function switchP5Tab(tab) {
    P5_TABS.forEach(t => {
        const el  = document.getElementById('p5-tab-' + t);
        const btn = document.getElementById('p5t-' + t);
        if (el)  el.classList.toggle('hidden', t !== tab);
        if (btn) { btn.classList.toggle('active', t === tab); }
    });
    if (tab === 'token')   renderTokenDeepDive();
    if (tab === 'refactor') loadRefactorFileBrowser();
    if (tab === 'arch')     loadArchFileBrowser();
}

// ─── FILE BROWSER (shared by Refactor + Arch Graph) ───────────────────
let _vaultFilesCache = null;

async function _loadVaultFiles() {
    if (_vaultFilesCache) return _vaultFilesCache;
    try {
        const d = await fetch('/api/chunks/stats').then(r => r.json());
        _vaultFilesCache = (d.top_files || []).map(f => f.source || '');
        return _vaultFilesCache;
    } catch (e) { return []; }
}

async function loadRefactorFileBrowser() {
    const sel = document.getElementById('refactor-file-sel');
    if (!sel || sel.dataset.loaded) return;
    sel.dataset.loaded = '1';
    sel.innerHTML = '<option value="">Loading vault files…</option>';
    const files = await _loadVaultFiles();
    if (!files.length) {
        sel.innerHTML = '<option value="">No indexed files found</option>';
        return;
    }
    sel.innerHTML = '<option value="">— Browse indexed files —</option>'
        + files.map(f => {
            const short = f.split('__').pop() || f;
            return `<option value="${f}">${short}</option>`;
        }).join('');
    sel.addEventListener('change', () => {
        const pathEl = document.getElementById('refactor-path');
        if (pathEl) pathEl.value = sel.value;
    });
}

async function loadArchFileBrowser() {
    const sel = document.getElementById('arch-file-sel');
    if (!sel || sel.dataset.loaded) return;
    sel.dataset.loaded = '1';
    sel.innerHTML = '<option value="">Loading vault files…</option>';
    const files = await _loadVaultFiles();
    if (!files.length) {
        sel.innerHTML = '<option value="">No indexed files found</option>';
        return;
    }
    sel.innerHTML = '<option value="">— Browse indexed files —</option>'
        + files.map(f => {
            const short = f.split('__').pop() || f;
            return `<option value="${f}">${short}</option>`;
        }).join('');
}

function addArchFileFromBrowser() {
    const sel = document.getElementById('arch-file-sel');
    if (!sel || !sel.value) return;
    const container = document.getElementById('arch-file-inputs');
    const count     = container.querySelectorAll('.arch-file-input').length;
    if (count >= 5) { alert('Maximum 5 files'); return; }
    const file = sel.value;
    const short = file.split('__').pop() || file;
    const div = document.createElement('div'); div.className = 'flex gap-2';
    div.innerHTML = `<input type="text" class="arch-file-input flex-1 bg-slate-800 border border-slate-700 rounded px-3 py-1.5 text-[10px] font-mono outline-none focus:border-accent text-white" value="${file}" placeholder="${short}">
    <button onclick="this.parentElement.remove()" class="text-[8px] bg-slate-800 hover:bg-red-900/30 text-slate-500 hover:text-danger px-2 py-1 rounded border border-slate-700 transition"><i class="fa-solid fa-xmark"></i></button>`;
    container.appendChild(div);
    sel.value = '';
}

// ─── REFACTOR AGENT ───────────────────────────────────────────────────
async function runRefactor() {
    const path = document.getElementById('refactor-path').value.trim();
    const mode = document.querySelector('input[name="refactor-mode"]:checked')?.value || 'refactor';
    if (!path) { alert('Select or enter a file'); return; }
    document.getElementById('refactor-spinner').classList.remove('hidden');
    document.getElementById('refactor-result').classList.add('hidden');
    try {
        const d = await fetch('/api/tools/refactor', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filepath: path, mode })
        }).then(r => r.json());
        _refactorData = d;
        document.getElementById('refactor-original').textContent   = d.original   || '—';
        document.getElementById('refactor-refactored').textContent = d.refactored || d.result || '—';
        if (d.tests) {
            document.getElementById('refactor-tests-section').classList.remove('hidden');
            document.getElementById('refactor-tests-body').textContent = d.tests;
        } else {
            document.getElementById('refactor-tests-section').classList.add('hidden');
        }
        if (d.status === 'error') {
            document.getElementById('refactor-original').textContent = d.message || 'Error';
        }
        document.getElementById('refactor-result').classList.remove('hidden');
    } catch (e) { alert('Refactor error: ' + e.message); }
    document.getElementById('refactor-spinner').classList.add('hidden');
}

function approveRefactor() {
    const content  = document.getElementById('refactor-refactored').textContent;
    const path     = document.getElementById('refactor-path').value.trim();
    const filename = path.split('/').pop() || 'refactored.py';
    const blob     = new Blob([content], { type: 'text/plain' });
    const url      = URL.createObjectURL(blob);
    const a        = document.createElement('a'); a.href = url; a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
}

// ─── ARCH GRAPH ───────────────────────────────────────────────────────
function addArchFile() {
    const container = document.getElementById('arch-file-inputs');
    const count     = container.querySelectorAll('.arch-file-input').length;
    if (count >= 5) { alert('Maximum 5 files'); return; }
    const div = document.createElement('div'); div.className = 'flex gap-2';
    div.innerHTML = `<input type="text" class="arch-file-input flex-1 bg-slate-800 border border-slate-700 rounded px-3 py-1.5 text-[10px] font-mono outline-none focus:border-accent text-white" placeholder="source name or file path">
    <button onclick="this.parentElement.remove()" class="text-[8px] bg-slate-800 hover:bg-red-900/30 text-slate-500 hover:text-danger px-2 py-1 rounded border border-slate-700 transition"><i class="fa-solid fa-xmark"></i></button>`;
    container.appendChild(div);
}

async function generateArchGraph() {
    const inputs = Array.from(document.querySelectorAll('.arch-file-input')).map(i => i.value.trim()).filter(Boolean);
    if (!inputs.length) { alert('Add at least one file (use the browser above or type a source name)'); return; }
    const container = document.getElementById('arch-network');
    container.innerHTML = '<div class="h-full flex items-center justify-center"><i class="fa-solid fa-circle-notch fa-spin text-2xl text-accent"></i></div>';
    try {
        const d = await fetch('/api/tools/arch_graph', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ files: inputs })
        }).then(r => r.json());
        if (d.status === 'error') {
            container.innerHTML = `<div class="h-full flex items-center justify-center text-red-400 text-[10px] font-mono">${d.message || 'Error'}</div>`;
            return;
        }
        const nodes = new vis.DataSet((d.nodes || d.graph?.nodes || []).map(n => ({
            id: n.id, label: n.label || n.id,
            color: { background: '#0f172a', border: '#334155' },
            font: { color: '#94a3b8', size: 11 }, shape: 'box'
        })));
        const edges = new vis.DataSet((d.edges || d.graph?.edges || []).map(e => ({
            from: e.from || e.source, to: e.to || e.target,
            color: { color: '#334155' }, arrows: 'to'
        })));
        container.innerHTML = '';
        _archNetwork = new vis.Network(container, { nodes, edges }, {
            physics: { enabled: document.getElementById('arch-physics')?.checked ?? true, solver: 'forceAtlas2Based' },
            interaction: { hover: true },
            nodes:  { borderWidth: 1, borderWidthSelected: 2 },
            edges:  { smooth: { type: 'dynamic' } }
        });
        _archNetwork.on('selectNode', function (params) {
            if (params.nodes.length) {
                const n = nodes.get(params.nodes[0]);
                document.getElementById('arch-node-detail').classList.remove('hidden');
                document.getElementById('arch-node-label').textContent = n ? n.label : '—';
            }
        });
    } catch (e) {
        container.innerHTML = '<div class="h-full flex items-center justify-center text-red-400 text-[10px] font-mono">Error: ' + e.message + '</div>';
    }
}

function toggleArchPhysics(on) {
    if (_archNetwork) _archNetwork.setOptions({ physics: { enabled: on } });
}

// ─── WEB GROUNDING ────────────────────────────────────────────────────
async function toggleWebSearch(on) {
    try {
        const d = await fetch('/api/config', {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ web_search: on })
        }).then(r => r.json());
        const ws = document.getElementById('web-search-status');
        if (ws) { ws.textContent = on ? 'ON' : 'OFF'; ws.className = on ? 'text-emerald-400 font-bold' : 'text-danger font-bold'; }
    } catch (e) {}
}

// ─── ROBOT LOG SNIFFER ────────────────────────────────────────────────
async function connectRobotLog() {
    const path = document.getElementById('robot-log-path').value.trim();
    if (!path) { alert('Enter a log file path'); return; }
    document.getElementById('robot-log-connect').classList.add('hidden');
    document.getElementById('robot-log-disconnect').classList.remove('hidden');
    const view = document.getElementById('robot-log-view');
    view.innerHTML = '';
    _robotLogInterval = setInterval(async () => {
        try {
            const d = await fetch(`/api/robot/log/stream?path=${encodeURIComponent(path)}`).then(r => r.json());
            if (d.status === 'error') {
                const div = document.createElement('div');
                div.className = 'text-red-400 text-[8px] font-mono';
                div.textContent = '⚠ ' + (d.message || 'Error reading log');
                view.appendChild(div);
                disconnectRobotLog();
                return;
            }
            (d.lines || []).forEach(line => {
                const div   = document.createElement('div');
                const isErr = line.includes('ERROR') || line.includes('error');
                div.className = (isErr ? 'text-red-400' : 'text-slate-400') + ' text-[9px] font-mono leading-relaxed';
                div.textContent = line;
                view.appendChild(div);
            });
            // Keep last 200 lines
            while (view.children.length > 200) view.removeChild(view.firstChild);
            view.scrollTop = view.scrollHeight;
        } catch (e) {}
    }, 1000);
}

function disconnectRobotLog() {
    clearInterval(_robotLogInterval); _robotLogInterval = null;
    document.getElementById('robot-log-connect').classList.remove('hidden');
    document.getElementById('robot-log-disconnect').classList.add('hidden');
}

async function analyseRobotLog() {
    const path = document.getElementById('robot-log-path').value.trim();
    if (!path) { alert('Connect to a log file first'); return; }
    try {
        const d = await fetch('/api/robot/log/analyse', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path })
        }).then(r => r.json());
        const section = document.getElementById('robot-log-analysis');
        const content = document.getElementById('robot-log-analysis-content');
        section.classList.remove('hidden');
        try { content.innerHTML = marked.parse(d.analysis || 'No analysis returned'); }
        catch { content.textContent = d.analysis || '—'; }
    } catch (e) { alert('Analysis error: ' + e.message); }
}

// ─── TOKEN DEEP DIVE ──────────────────────────────────────────────────
function renderTokenDeepDive() {
    const u     = _lastTokenUsage || {};
    const limit = 32768;
    const sys   = u.system || 0, ctx = u.context || 0, pmt = u.chat_history || 0, mem = u.memory || 0;
    const free  = Math.max(0, limit - sys - ctx - pmt - mem);
    const setW  = (id, w) => { const e = document.getElementById(id); if (e) e.style.width = w; };
    setW('p5-tok-bar-sys',  ((sys  / limit) * 100).toFixed(1) + '%');
    setW('p5-tok-bar-ctx',  ((ctx  / limit) * 100).toFixed(1) + '%');
    setW('p5-tok-bar-pmt',  ((pmt  / limit) * 100).toFixed(1) + '%');
    setW('p5-tok-bar-mem',  ((mem  / limit) * 100).toFixed(1) + '%');
    setW('p5-tok-bar-free', ((free / limit) * 100).toFixed(1) + '%');

    const segments = [
        { name: 'System Prompt',      tokens: sys,  color: '#64748b' },
        { name: 'Retrieved Context',  tokens: ctx,  color: '#38bdf8' },
        { name: 'Chat History',       tokens: pmt,  color: '#fbbf24' },
        { name: 'Memory Turns',       tokens: mem,  color: '#818cf8' },
        { name: 'Available',          tokens: free, color: '#10b981' },
    ];
    const tbody = document.getElementById('token-breakdown-tbody');
    if (tbody) {
        tbody.innerHTML = segments.map(s => `
            <tr class="border-b border-slate-800/30">
                <td class="py-1.5 pr-3 text-slate-300">${s.name}</td>
                <td class="py-1.5 pr-3 text-right text-slate-200 font-mono">${s.tokens >= 1000 ? (s.tokens / 1000).toFixed(1) + 'k' : s.tokens}</td>
                <td class="py-1.5 pr-3 text-right text-slate-500">${Math.round((s.tokens / limit) * 100)}%</td>
                <td class="py-1.5"><div class="w-3 h-3 rounded" style="background:${s.color}"></div></td>
            </tr>`
        ).join('');
    }

    if (u.chunks && u.chunks.length) {
        document.getElementById('token-chunks-section').classList.remove('hidden');
        const cl = document.getElementById('token-chunks-list');
        if (cl) cl.innerHTML = u.chunks.map(c => `
            <div class="flex items-center gap-2 text-[8px] font-mono bg-slate-800/40 p-1.5 rounded mb-1">
                <span class="truncate flex-1 text-slate-400">${(c.source || '').split('/').pop()}</span>
                <span class="text-sky-400 flex-shrink-0">${c.tokens || 0} tok</span>
            </div>`
        ).join('');
    } else {
        const s = document.getElementById('token-chunks-section');
        if (s) s.classList.add('hidden');
    }

    const used    = sys + ctx + pmt + mem;
    const usedPct = Math.round((used / limit) * 100);
    const rec     = document.getElementById('token-recommendation');
    const recTxt  = document.getElementById('token-rec-text');
    if (rec && recTxt) {
        if (!used) {
            rec.classList.add('hidden');
        } else if (usedPct > 80) {
            rec.classList.remove('hidden');
            recTxt.textContent = `Context is ${usedPct}% of budget — consider reducing retrieval_k or context_budget`;
            rec.className = 'mt-3 bg-slate-800/60 p-3 rounded border border-slate-700/50 text-[9px] font-mono text-warning';
        } else {
            rec.classList.remove('hidden');
            recTxt.textContent = `Context is ${usedPct}% of budget — headroom looks healthy`;
            rec.className = 'mt-3 bg-slate-800/60 p-3 rounded border border-slate-700/50 text-[9px] font-mono text-emerald-400';
        }
    }
}

// ─── MASTER INIT ──────────────────────────────────────────────────────
function initApp() {
    _currentSessionId = sessionStorage.getItem('vb_session_id') || null;

    fetchStatus();
    setInterval(fetchStatus, 4000);

    _logInterval = setInterval(pollLogStream, 2000);

    fetchOllamaModels();
    setInterval(fetchOllamaModels, 10000);

    loadQueryHistory();
}
