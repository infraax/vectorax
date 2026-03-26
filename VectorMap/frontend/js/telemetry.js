// ─── TELEMETRY POLL ───────────────────────────────────────────────────

async function fetchStatus() {
    try {
        const d = await fetch('/status').then(r => r.json());
        if (d.status !== 'online') return;
        const s  = d.stats;
        const h  = s.hardware;
        const mb = h.mem_breakdown || {};
        const cpu = h.cpu_percent;

        // Page 1 CPU
        document.getElementById('p1-cpu-pct').textContent = cpu + '%';
        document.getElementById('p1-cpu-pct').className = `font-bold text-[10px] ${_col(cpu)}`;
        document.getElementById('p1-cpu-bar').style.width = cpu + '%';
        document.getElementById('p1-cpu-bar').className = `${_bg(cpu)} h-full transition-all duration-500`;

        // RAM
        document.getElementById('p1-ram-pct').textContent = h.ram_percent + '%';
        document.getElementById('p1-ram-pct').className = `font-bold text-[10px] ${_col(h.ram_percent)}`;
        document.getElementById('p1-ram-gb').textContent = `${h.ram_used_gb}/${h.ram_total_gb}GB`;

        // Memory breakdown bars
        const tot = h.ram_total_gb || 24;
        ['active', 'wired', 'inactive', 'free'].forEach(k => {
            const gb = mb[k + '_gb'] || 0;
            const el = document.getElementById('bar-' + k);
            if (el) el.style.width = Math.min((gb / tot) * 100, 100).toFixed(1) + '%';
        });
        if (mb.active_gb   !== undefined) document.getElementById('p1-mem-active').textContent   = mb.active_gb + 'G';
        if (mb.wired_gb    !== undefined) document.getElementById('p1-mem-wired').textContent    = mb.wired_gb + 'G';
        if (mb.inactive_gb !== undefined) document.getElementById('p1-mem-inactive').textContent = mb.inactive_gb + 'G';
        if (mb.free_gb     !== undefined) document.getElementById('p1-mem-free').textContent     = mb.free_gb + 'G';

        // Guardrail bar
        const avail = mb.available_gb || 0;
        const gp = Math.min((avail / tot) * 100, 100);
        const gc = avail > 4 ? 'bg-emerald-500' : avail > 1.5 ? 'bg-yellow-500' : 'bg-red-500';
        const gt = avail > 4 ? 'text-emerald-400' : avail > 1.5 ? 'text-yellow-400' : 'text-red-400';
        const gb2 = document.getElementById('p1-guardrail-bar');
        const gt2 = document.getElementById('p1-guardrail-txt');
        if (gb2) { gb2.style.width = gp.toFixed(1) + '%'; gb2.className = `${gc} h-full transition-all duration-500`; }
        if (gt2) { gt2.textContent = avail.toFixed(1) + 'GB avail'; gt2.className = `${gt} w-16 text-right text-[8px] font-mono`; }

        // RSS labels
        if (mb.my_procs_rss_gb    !== undefined) document.getElementById('p1-my-rss').textContent  = mb.my_procs_rss_gb;
        if (mb.other_procs_rss_gb !== undefined) document.getElementById('p1-other-rss').textContent = mb.other_procs_rss_gb;
        if (h.server_rss_mb       !== undefined) document.getElementById('p1-srv-rss').textContent  = h.server_rss_mb;

        // Process table
        _lastProc = { my_ram: h.top_ram || [], my_cpu: h.top_cpu || [], other_ram: h.other_ram || [], other_cpu: h.other_cpu || [] };
        renderProcTable();

        // Port bindings
        if (s.ports) {
            const _ph = p => p.status === 'ONLINE'
                ? `<span class="text-emerald-400 font-bold">● ONLINE</span> <span class="text-slate-600 text-[8px]">pid ${p.pid}${p.ram_mb && p.ram_mb !== '—' ? ' · ' + p.ram_mb + 'MB' : ''}</span>`
                : '<span class="text-danger">● OFFLINE</span>';
            document.getElementById('port-fastapi').innerHTML  = _ph(s.ports.fastapi);
            document.getElementById('port-ollama').innerHTML   = _ph(s.ports.ollama);
            document.getElementById('port-obsidian').innerHTML = _ph(s.ports.obsidian);
        }

        // Chunk counts
        document.getElementById('p1-chunks').textContent = (s.indexed_chunks_total || 0).toLocaleString() + ' Chunks';
        document.getElementById('p3-chunk-count').textContent = (s.indexed_chunks_total || 0).toLocaleString();

        // Agent config display
        if (s.agent_config) {
            document.getElementById('p1-active-model').textContent = s.agent_config.model;
            document.getElementById('p1-cfg-temp').textContent     = s.agent_config.temperature;
            document.getElementById('p1-cfg-k').textContent        = s.agent_config.retrieval_k;
            document.getElementById('p1-cfg-ctx').textContent      = Math.round((s.agent_config.context_budget || 20000) / 1000) + 'k';
        }

        updateIndexingUI(s, h, mb);

        if (s.current_node) {
            highlightNode(s.current_node);
            if (_queryActive) updateTypingStatus(s.current_node);
        } else if (!_queryActive) highlightNode(null);

        updatePage2(h, mb, s);

        const svcChroma = document.getElementById('svc-chroma');
        if (svcChroma) svcChroma.textContent = (s.indexed_chunks_total || 0).toLocaleString() + ' chunks';
        const svcLlm = document.getElementById('svc-llm');
        if (svcLlm && s.agent_config) svcLlm.textContent = s.agent_config.model;

        // Memory turns badge
        if (s.memory_turns !== undefined) {
            const badge = document.getElementById('p1-mem-turns-badge');
            if (badge) { badge.textContent = s.memory_turns + ' turns'; badge.classList.toggle('hidden', s.memory_turns === 0); }
        }

        // Web search status
        if (s.web_search !== undefined) {
            const wt = document.getElementById('web-search-toggle');
            const ws = document.getElementById('web-search-status');
            if (wt) wt.checked = s.web_search;
            if (ws) { ws.textContent = s.web_search ? 'ON' : 'OFF'; ws.className = s.web_search ? 'text-emerald-400 font-bold' : 'text-danger font-bold'; }
        }
        if (s.last_web_search) {
            const el = document.getElementById('web-last-search');
            if (el) el.textContent = s.last_web_search;
        }

        // Resources tab (p2r)
        const p2rCpu = document.getElementById('p2r-cpu');
        if (p2rCpu) { p2rCpu.textContent = cpu + '%'; p2rCpu.className = _col(cpu) + ' font-bold'; }
        const p2rBar = document.getElementById('p2r-cpu-bar');
        if (p2rBar) { p2rBar.style.width = cpu + '%'; p2rBar.className = _bg(cpu) + ' h-full transition-all'; }
        const p2rRam = document.getElementById('p2r-ram');
        if (p2rRam) { p2rRam.textContent = h.ram_percent + '%'; p2rRam.className = _col(h.ram_percent) + ' font-bold'; }
        const p2rRamBar = document.getElementById('p2r-ram-bar');
        if (p2rRamBar) p2rRamBar.style.width = h.ram_percent + '%';
        if (h.server_rss_mb    !== undefined) { const e = document.getElementById('p2r-vb-rss');    if (e) e.textContent = h.server_rss_mb + 'MB'; }
        if (mb.wired_gb        !== undefined) { const e = document.getElementById('p2r-gpu-wired'); if (e) e.textContent = mb.wired_gb + 'GB'; }
        if (mb.other_procs_rss_gb !== undefined) { const e = document.getElementById('p2r-other'); if (e) e.textContent = mb.other_procs_rss_gb + 'GB'; }
    } catch (e) {}
}

// ─── INDEXING UI UPDATE ───────────────────────────────────────────────
function updateIndexingUI(s, h, mb) {
    const isIdx  = s.is_indexing;
    const stopBtn = document.getElementById('p1-btn-stop');
    const idxBtn  = document.getElementById('p1-btn-index');
    const adiv    = document.getElementById('p1-active-idx');
    if (isIdx) {
        adiv.classList.remove('hidden');
        stopBtn.classList.remove('hidden');
        idxBtn.disabled = true;
        idxBtn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin mr-1 text-accent"></i> INDEXING...';
        idxBtn.classList.add('opacity-50', 'cursor-not-allowed');
        document.getElementById('p1-idx-file').textContent  = s.current_file || '—';
        document.getElementById('p1-idx-count').textContent = `${s.processed_files || 0}/${s.total_files_to_index || 0}`;
        const pct = s.total_files_to_index > 0 ? (s.processed_files / s.total_files_to_index) * 100 : 0;
        document.getElementById('p1-idx-progress').style.width = pct.toFixed(1) + '%';
        const msg  = s.status_msg || '';
        const dot  = document.getElementById('p1-dot');
        const stEl = document.getElementById('p1-idx-status');
        stEl.textContent = msg;
        if (msg.includes('PAUSED') || msg.includes('Stopped')) {
            stEl.className = 'text-[9px] text-danger uppercase font-bold tracking-widest flex-1';
            dot.className  = 'w-1.5 h-1.5 rounded-full bg-danger flash-warning';
        } else {
            stEl.className = 'text-[9px] text-accent uppercase font-bold tracking-widest flex-1';
            dot.className  = 'w-1.5 h-1.5 rounded-full bg-accent flash-warning';
        }
        document.getElementById('idx-cpu-draw').textContent  = h.cpu_percent + '%';
        document.getElementById('idx-avail-draw').textContent = (mb || {}).available_gb?.toFixed(1) || 0;
        document.getElementById('idx-fps').textContent = (s.files_per_sec || 0).toFixed(2);
        document.getElementById('idx-eta').textContent = _fmtEta(s.est_remaining_sec || 0);
    } else {
        adiv.classList.add('hidden');
        stopBtn.classList.add('hidden');
        idxBtn.disabled = false;
        idxBtn.innerHTML = '<i class="fa-solid fa-bolt mr-1 text-accent"></i> UPDATE VAULT CACHE';
        idxBtn.classList.remove('opacity-50', 'cursor-not-allowed');
    }
}

// ─── PAGE 2 RESOURCE PANEL UPDATE ────────────────────────────────────
function updatePage2(h, mb, s) {
    const cpu   = h.cpu_percent;
    const avail = (mb || {}).available_gb || 0;
    const tot   = h.ram_total_gb || 24;
    document.getElementById('p2-cpu').textContent = cpu + '%';
    document.getElementById('p2-cpu').className   = _col(cpu) + ' font-bold';
    document.getElementById('p2-cpu-bar').style.width = cpu + '%';
    document.getElementById('p2-cpu-bar').className   = _bg(cpu) + ' h-full transition-all';
    document.getElementById('p2-avail').textContent   = avail.toFixed(1) + 'GB';
    document.getElementById('p2-avail-bar').style.width = Math.min((avail / tot) * 100, 100).toFixed(1) + '%';
    if (h.server_rss_mb !== undefined)           document.getElementById('p2-vb-rss').textContent     = h.server_rss_mb + 'MB';
    const wiredGb = (mb || {}).wired_gb;
    if (wiredGb !== undefined)                   document.getElementById('p2-gpu-wired').textContent   = wiredGb + 'GB';
    if ((mb || {}).other_procs_rss_gb !== undefined) document.getElementById('p2-other-rss').textContent = mb.other_procs_rss_gb + 'GB';
    const gs = (mb || {}).guardrail_state || 'ok';
    const gt = document.getElementById('p2-guard-txt');
    if (gt) {
        gt.textContent = gs.toUpperCase();
        gt.className   = gs === 'ok' ? 'text-emerald-400 font-bold' : gs === 'warn' ? 'text-yellow-400 font-bold' : 'text-red-400 font-bold';
    }
}

// ─── PROCESS TABLE ────────────────────────────────────────────────────
function showProcTab(t) {
    _procTab = t;
    document.getElementById('tab-my').className    = 'tab-btn ' + (t === 'my'    ? 'active' : '');
    document.getElementById('tab-other').className = 'tab-btn ' + (t === 'other' ? 'active' : '');
    renderProcTable();
}

function renderProcTable() {
    const d   = _lastProc;
    const ram = _procTab === 'my' ? d.my_ram    : d.other_ram;
    const cpu = _procTab === 'my' ? d.my_cpu    : d.other_cpu;
    let rh = '', ch = '';
    (ram || []).forEach(p => { rh += `<div class="flex justify-between gap-1"><span class="truncate text-slate-500">${p.name}</span><span class="text-white font-bold flex-shrink-0">${p.gb}G</span></div>`; });
    (cpu || []).forEach(p => { ch += `<div class="flex justify-between gap-1"><span class="truncate text-slate-500">${p.name}</span><span class="${_col(p.pct)} font-bold flex-shrink-0">${p.pct}%</span></div>`; });
    document.getElementById('p1-top-ram').innerHTML = rh || '<span class="text-slate-700">—</span>';
    document.getElementById('p1-top-cpu').innerHTML = ch || '<span class="text-slate-700">—</span>';
}

// ─── LANGGRAPH NODE HIGHLIGHT ─────────────────────────────────────────
function highlightNode(name) {
    ['retrieve', 'generate', 'validate'].forEach(n => {
        const r  = document.getElementById('node-' + n);
        const l  = document.getElementById('label-' + n);
        const el = document.getElementById('node-elapsed-' + n);
        if (!r) return;
        r.classList.remove('active', 'done');
        l.classList.remove('active');
        if (el) el.setAttribute('opacity', '0');
        if (n === name) {
            r.classList.add('active');
            l.classList.add('active');
            if (!_nodeStartTs[n]) _nodeStartTs[n] = Date.now();
            if (el) { el.setAttribute('opacity', '1'); el.textContent = Math.round(Date.now() - _nodeStartTs[n]) + 'ms'; }
        }
    });
    const edges = { retrieve: 'edge-r-g', generate: 'edge-g-v', validate: 'edge-v-end' };
    Object.values(edges).forEach(id => {
        const e = document.getElementById(id);
        if (e) { e.classList.remove('active', 'traversing'); }
    });
    if (name && edges[name]) {
        const e = document.getElementById(edges[name]);
        if (e) e.classList.add('traversing');
    }
    const lbl = document.getElementById('lg-active-label');
    if (lbl) {
        lbl.textContent = name ? name.toUpperCase() : 'IDLE';
        lbl.className   = name
            ? 'ml-auto text-[8px] font-mono px-1.5 py-0.5 rounded bg-sky-900/40 text-accent'
            : 'ml-auto text-[8px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-500';
    }
    if (!name) _nodeStartTs = {};
    const sub = document.getElementById('sub-generate');
    if (sub && name === 'generate') {
        const m = document.getElementById('p1-active-model')?.textContent || 'Ollama';
        sub.textContent = m + ' · SQLite cache';
    }
}
