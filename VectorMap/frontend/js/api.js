// ─── MODAL HELPERS ────────────────────────────────────────────────────
function openModal(id)  { document.getElementById(id).classList.remove('hidden'); }
function closeModal(id) { document.getElementById(id).classList.add('hidden'); }

function toggleSection(id) {
    const el = document.getElementById(id);
    if (el) el.classList.toggle('hidden');
}

// ─── PAGE ROUTER ─────────────────────────────────────────────────────
function switchPage(n) {
    for (let i = 1; i <= 5; i++) {
        document.getElementById('page-' + i).classList.add('hidden');
        document.getElementById('nav-' + i).classList.remove('active');
    }
    document.getElementById('page-' + n).classList.remove('hidden');
    document.getElementById('nav-' + n).classList.add('active');
    if (n === 2) { loadQueryHistory(); loadConfig(); loadModelList(); loadTemplates(); loadHallucinations(); }
    if (n === 4) { loadVaultHealth(); loadVaultDrift(); }
    if (n === 5) { renderTokenDeepDive(); }
}

// ─── QUERY HISTORY ────────────────────────────────────────────────────
async function loadQueryHistory(mode) {
    try {
        const url = (mode === 'session' && _currentSessionId)
            ? `/api/query_history?n=50&session=${encodeURIComponent(_currentSessionId)}`
            : '/api/query_history?n=50';
        const d = await fetch(url).then(r => r.json());
        const tbody = document.getElementById('query-history-tbody');
        if (!d.history || d.history.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-slate-600 italic py-4 text-center text-[8px]">No queries yet.</td></tr>';
            return;
        }
        tbody.innerHTML = d.history.map(e => {
            const ph   = e.phases || {};
            const retr = ph.retrieve || 0, gen = ph.generate || 0, tot = e.total_ms || 0;
            const delta = e.rss_delta_mb || 0;
            const q = (e.query || '').substring(0, 38) + (e.query?.length > 38 ? '…' : '');
            const dColor = delta > 10 ? 'text-red-400' : delta > 0 ? 'text-yellow-400' : 'text-emerald-400';
            const sid = (e.session_id || '').replace('session_', '').substring(0, 12);
            return `<tr class="border-b border-slate-800/30 hover:bg-slate-800/20 cursor-pointer transition text-[9px]" onclick="openQueryDetail(${e.id})">
                <td class="py-1.5 pr-2 text-slate-600">${e.query_id || e.id || '?'}</td>
                <td class="py-1.5 pr-2 text-slate-700 text-[7px]">${sid}</td>
                <td class="py-1.5 pr-3 text-slate-400 max-w-[180px] truncate" title="${e.query || ''}">${q}</td>
                <td class="py-1.5 pr-2 text-right text-slate-500">${_ms(retr)}</td>
                <td class="py-1.5 pr-2 text-right ${gen > 5000 ? 'text-warning' : 'text-slate-400'}">${_ms(gen)}</td>
                <td class="py-1.5 pr-2 text-right font-bold text-white">${_ms(tot)}</td>
                <td class="py-1.5 text-right ${dColor}">${delta > 0 ? '+' : ''}${delta.toFixed(0)}MB</td>
            </tr>`;
        }).join('');
        const last = d.history[0];
        if (last) updateLastTrace(last);
    } catch (e) {}
}

async function openQueryDetail(id) {
    try {
        const d = await fetch(`/api/query_history/${id}`).then(r => r.json());
        if (!d.query) return;
        const q = d.query;
        document.getElementById('qd-meta').textContent = `ID ${q.id} · ${(q.timestamp || '').substring(0, 19)} · ${_ms(q.total_ms || 0)}`;
        document.getElementById('qd-query').textContent = q.query || '';
        const respEl = document.getElementById('qd-response');
        try { respEl.innerHTML = marked.parse(q.response || ''); } catch { respEl.textContent = q.response || ''; }
        const ph = q.phases || {};
        document.getElementById('qd-phases').innerHTML = Object.entries(ph).map(([k, v]) =>
            `<div class="flex justify-between"><span class="text-slate-600">${k}</span><span class="text-slate-300">${_ms(v)}</span></div>`
        ).join('') || '<span class="text-slate-700">—</span>';
        const srcs = q.sources || [];
        document.getElementById('qd-sources').innerHTML = srcs.map(s =>
            `<div class="text-slate-400 truncate" title="${s.filename || s}"><i class="fa-solid fa-file-code mr-1 text-accent text-[7px]"></i>${s.filename || s}</div>`
        ).join('') || '<span class="text-slate-700">—</span>';
        openModal('query-modal');
    } catch (e) { console.error(e); }
}

function updateLastTrace(e) {
    const el = document.getElementById('last-trace');
    if (!el || !e) return;
    const ph  = e.phases || {};
    const tot = e.total_ms || 1;
    const items = [
        { label: 'retrieve', ms: ph.retrieve || 0, color: 'bg-cyan-500'   },
        { label: 'generate', ms: ph.generate || 0, color: 'bg-amber-500'  },
        { label: 'validate', ms: ph.validate || 0, color: 'bg-green-500'  },
    ];
    el.innerHTML = `<div class="text-slate-600 text-[8px] mb-2 truncate" title="${e.query || ''}">"${(e.query || '').substring(0, 40)}"</div>`
        + items.map(i => `<div>
            <div class="flex justify-between mb-0.5 text-[8px]"><span class="text-slate-500 uppercase">${i.label}</span><span class="text-slate-400">${_ms(i.ms)}</span></div>
            <div class="w-full bg-slate-800 h-1 rounded-full overflow-hidden"><div class="${i.color} h-full rounded-full" style="width:${Math.min((i.ms / tot) * 100, 100).toFixed(1)}%"></div></div>
        </div>`).join('')
        + `<div class="border-t border-slate-800 pt-2 mt-2 flex justify-between text-[8px] font-mono"><span class="text-slate-600">Total</span><span class="text-white font-bold">${_ms(tot)}</span></div>`;
}

// ─── AGENT CONFIGURATION ──────────────────────────────────────────────
async function loadConfig() {
    try {
        const d = await fetch('/api/config').then(r => r.json());
        if (!d.config) return;
        const c = d.config;
        document.getElementById('cfg-model').value = c.model;
        document.getElementById('cfg-temp').value  = c.temperature;
        document.getElementById('cfg-k').value     = c.retrieval_k;
        document.getElementById('cfg-attempts').value = c.max_attempts;
        document.getElementById('cfg-budget').value   = c.context_budget;
        const sp = document.getElementById('cfg-sysprompt');
        if (sp) sp.value = c.system_prompt || '';
        const mt = document.getElementById('cfg-memory-turns');
        if (mt && c.memory_turns !== undefined) mt.value = c.memory_turns;
        const ws = document.getElementById('cfg-web-search');
        if (ws && c.web_search !== undefined) ws.checked = c.web_search;
    } catch (e) {}
}

async function loadModelList() {
    try {
        const d = await fetch('/api/ollama/models').then(r => r.json());
        const sel = document.getElementById('cfg-model');
        sel.innerHTML = (d.available || []).map(m =>
            `<option value="${m.name}">${m.name} (${m.size_gb}G)${m.loaded ? ' ◉' : ''}</option>`
        ).join('');
    } catch (e) {}
}

async function saveConfig() {
    const sp  = document.getElementById('cfg-sysprompt');
    const mt  = document.getElementById('cfg-memory-turns');
    const ws  = document.getElementById('cfg-web-search');
    const body = {
        model:          document.getElementById('cfg-model').value,
        temperature:    parseFloat(document.getElementById('cfg-temp').value),
        retrieval_k:    parseInt(document.getElementById('cfg-k').value),
        max_attempts:   parseInt(document.getElementById('cfg-attempts').value),
        context_budget: parseInt(document.getElementById('cfg-budget').value),
        system_prompt:  sp ? sp.value : '',
        memory_turns:   mt ? parseInt(mt.value) : 5,
        web_search:     ws ? ws.checked : false,
    };
    try {
        const d = await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        }).then(r => r.json());
        const st = document.getElementById('cfg-status');
        if (d.status === 'ok') {
            st.textContent = '✓ Applied: ' + body.model;
            st.className = 'text-[8px] text-emerald-400 font-mono text-center h-3';
            document.getElementById('p1-active-model').textContent = body.model;
            const badge = document.getElementById('p1-model-applied');
            if (badge) { badge.classList.remove('hidden'); setTimeout(() => badge.classList.add('hidden'), 3000); }
        } else {
            st.textContent = 'Error: ' + d.message;
            st.className = 'text-[8px] text-red-400 font-mono text-center h-3';
        }
        setTimeout(() => { if (st) st.textContent = ''; }, 4000);
    } catch (e) { document.getElementById('cfg-status').textContent = 'Connection error'; }
}
