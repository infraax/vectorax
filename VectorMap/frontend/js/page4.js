// ─── PAGE 4: VAULT MANAGEMENT ─────────────────────────────────────────

function switchP4Tab(tab) {
    // Reserved for future tab expansion on page 4
}

// ─── VAULT HEALTH ─────────────────────────────────────────────────────
async function loadVaultHealth() {
    try {
        const d = await fetch('/api/vault/health').then(r => r.json());
        renderHealthScore(d);
    } catch (e) {}
}

function renderHealthScore(d) {
    const score   = d.score || 0;
    const scoreEl = document.getElementById('vault-health-score');
    if (scoreEl) {
        scoreEl.textContent = score;
        scoreEl.className   = 'text-4xl font-black ' + (score >= 75 ? 'text-emerald-400' : score >= 50 ? 'text-yellow-400' : 'text-red-400');
    }
    const barsEl = document.getElementById('vault-health-bars');
    if (barsEl && d.dimensions) {
        barsEl.innerHTML = (d.dimensions || []).map(dim => `
            <div>
                <div class="flex justify-between text-[8px] font-mono mb-0.5">
                    <span class="text-slate-500">${dim.name || '—'}</span>
                    <span class="${dim.value >= 75 ? 'text-emerald-400' : dim.value >= 50 ? 'text-yellow-400' : 'text-red-400'}">${dim.value || 0}</span>
                </div>
                <div class="w-full bg-slate-800 h-1 rounded overflow-hidden">
                    <div class="h-full rounded ${dim.value >= 75 ? 'bg-emerald-500' : dim.value >= 50 ? 'bg-yellow-500' : 'bg-red-500'}" style="width:${dim.value || 0}%"></div>
                </div>
            </div>`
        ).join('');
    }
}

// ─── VAULT DRIFT ──────────────────────────────────────────────────────
async function loadVaultDrift() {
    const setEl = (id, val) => { const e = document.getElementById(id); if (e) e.textContent = val; };
    setEl('drift-total',   '…'); setEl('drift-indexed', '…');
    setEl('drift-never',   '…'); setEl('drift-stale',   '…');
    try {
        const d = await fetch('/api/vault/drift').then(r => r.json());
        _driftData = d;

        // Backend field names: total_vault_files, total_indexed_sources, drifted (not stale), never_indexed
        const staleArr = d.drifted        || d.stale        || [];
        const neverArr = d.never_indexed  || [];
        setEl('drift-total',       d.total_vault_files     || d.total_files  || 0);
        setEl('drift-indexed',     d.total_indexed_sources || d.indexed      || 0);
        setEl('drift-never',       neverArr.length);
        setEl('drift-stale',       staleArr.length);
        setEl('drift-stale-count', staleArr.length);
        setEl('drift-never-count', neverArr.length);

        // Stale files list
        const staleList = document.getElementById('drift-stale-list');
        if (staleList) {
            staleList.innerHTML = staleArr.length ? staleArr
                .sort((a, b) => (b.delta_days || 0) - (a.delta_days || 0))
                .map(f => {
                    const fname = (f.file || '').split('/').pop() || f.file || '—';
                    return `<div class="flex items-center gap-2 text-[8px] font-mono bg-slate-800/40 p-1.5 rounded">
                        <span class="truncate flex-1 text-slate-400">${fname}</span>
                        <span class="text-orange-400 flex-shrink-0">+${(f.delta_days || 0).toFixed(1)}d</span>
                        <button onclick="reindexFile('${f.file || ''}')" class="text-[7px] bg-accent/10 hover:bg-accent/20 text-accent px-1.5 py-0.5 rounded border border-accent/20 transition flex-shrink-0">Reindex</button>
                    </div>`;
                }).join('')
                : '<div class="text-[8px] text-slate-700 italic">No stale files.</div>';
        }

        // Never indexed list
        const neverList = document.getElementById('drift-never-list');
        if (neverList) {
            neverList.innerHTML = neverArr.length ? neverArr.map(f => {
                const fval  = f.file || f;
                const fname = fval.split('/').pop() || fval;
                return `<div class="flex items-center gap-2 text-[8px] font-mono bg-slate-800/40 p-1.5 rounded">
                    <input type="checkbox" class="backfill-checkbox flex-shrink-0 accent-accent" value="${fval}" id="bf-${CSS.escape(fval)}">
                    <span class="truncate flex-1 text-slate-400">${fname}</span>
                </div>`;
            }).join('')
                : '<div class="text-[8px] text-slate-700 italic">All files indexed.</div>';
        }

        // Normalise _driftData so renderBackfillQueue() works regardless of which field was used
        _driftData.stale         = staleArr;
        _driftData.never_indexed = neverArr;
        renderBackfillQueue();
    } catch (e) {
        ['drift-total','drift-indexed','drift-never','drift-stale'].forEach(id => setEl(id, 'err'));
    }
}

function toggleDriftSection(type) {
    const list = document.getElementById('drift-' + type + '-list');
    const icon = document.getElementById('drift-' + type + '-icon');
    if (list) { list.classList.toggle('hidden'); }
    if (icon) { icon.className = list && !list.classList.contains('hidden') ? 'fa-solid fa-chevron-down text-[7px]' : 'fa-solid fa-chevron-right text-[7px]'; }
}

// ─── CHROMA CRUD EXPLORER ─────────────────────────────────────────────
async function chromaSearch() { return loadChromaSearch(); }

async function loadChromaSearch() {
    const q = document.getElementById('chroma-search-q').value.trim();
    if (!q) return;
    try {
        const d = await fetch(`/api/chroma/search?q=${encodeURIComponent(q)}`).then(r => r.json());
        // Backend returns "chunks" not "results"
        renderChromaResults(d.chunks || d.results || []);
    } catch (e) {
        document.getElementById('chroma-results').innerHTML = '<div class="text-red-400 text-[8px]">Search error: ' + e.message + '</div>';
    }
}

async function loadChromaFile(source) {
    // Backend endpoint uses ?source= not ?file=
    const sel  = document.getElementById('chroma-file-sel');
    const file = source || (sel ? sel.value : '');
    if (!file) return;
    try {
        const d = await fetch(`/api/chroma/file?source=${encodeURIComponent(file)}`).then(r => r.json());
        renderChromaResults(d.chunks || d.results || []);
    } catch (e) {
        document.getElementById('chroma-results').innerHTML = '<div class="text-red-400 text-[8px]">Load error: ' + e.message + '</div>';
    }
}

function renderChromaResults(results) {
    const el = document.getElementById('chroma-results');
    if (!results.length) { el.innerHTML = '<div class="text-[8px] text-slate-700 italic">No results.</div>'; return; }
    el.innerHTML = `<div class="text-[7px] text-slate-600 mb-2">${results.length} chunks</div>
        <table class="w-full text-[8px] font-mono">
        <thead><tr class="border-b border-slate-800 text-slate-500 uppercase tracking-widest">
            <td class="pb-1 pr-2">ID</td><td class="pb-1 pr-2">Source</td><td class="pb-1 pr-3">Snippet</td><td class="pb-1"></td>
        </tr></thead>
        <tbody>`
        + results.map(r => `
        <tr class="border-b border-slate-800/30 hover:bg-slate-800/20 transition">
            <td class="py-1.5 pr-2 text-slate-600 max-w-[60px] truncate" title="${r.id || ''}">${(r.id || '—').substring(0, 12)}…</td>
            <td class="py-1.5 pr-2 text-slate-400 max-w-[80px] truncate" title="${r.source || ''}">${(r.source || '—').split('__').pop()}</td>
            <td class="py-1.5 pr-3 text-slate-500 max-w-[160px] truncate" title="${r.snippet || ''}">${(r.snippet || '—').substring(0, 40)}</td>
            <td class="py-1.5 whitespace-nowrap">
                <button onclick="deleteChunk('${r.id || ''}')" class="text-[7px] bg-red-900/20 hover:bg-red-800/40 text-red-400 px-1.5 py-0.5 rounded border border-red-900/30 transition mr-1">Del</button>
                ${r.source ? `<button onclick="reindexChunk('${r.source}')" class="text-[7px] bg-accent/10 hover:bg-accent/20 text-accent px-1.5 py-0.5 rounded border border-accent/20 transition">Reindex</button>` : ''}
            </td>
        </tr>`
        ).join('') + '</tbody></table>';
}

function deleteChunk(id) {
    document.getElementById('delete-confirm-msg').textContent = `Delete chunk ID: ${id}?`;
    document.getElementById('delete-confirm-yes').onclick = async () => {
        closeModal('delete-confirm-modal');
        try {
            const d = await fetch(`/api/chroma/chunk/${encodeURIComponent(id)}`, { method: 'DELETE' }).then(r => r.json());
            if (d.status === 'ok') loadChromaSearch();
            else alert('Delete failed: ' + (d.message || 'unknown'));
        } catch (e) { alert('Error: ' + e.message); }
    };
    openModal('delete-confirm-modal');
}

function deleteChromaChunk(id) { deleteChunk(id); }
function reindexChunk(source)  { reindexFile(source); }

async function reindexFile(filePath) {
    try {
        // Backend expects "source" field (not "file")
        const d = await fetch('/api/chroma/reindex', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ source: filePath })
        }).then(r => r.json());
        if (d.status === 'ok') { loadVaultDrift(); loadChunkStats(); }
        else alert('Reindex failed: ' + (d.message || 'unknown'));
    } catch (e) { alert('Error: ' + e.message); }
}

// ─── BACKFILL QUEUE ───────────────────────────────────────────────────
function renderBackfillQueue() {
    const el = document.getElementById('backfill-queue-list');
    if (!el) return;
    const stale = (_driftData.stale        || []).map(f => ({ file: f.file || f, type: 'stale'  }));
    const never = (_driftData.never_indexed || []).map(f => ({ file: f.file || f, type: 'never' }));
    const all   = [...stale, ...never];
    if (!all.length) {
        el.innerHTML = '<div class="text-slate-700 italic text-[8px]">No files queued. Refresh Drift Monitor first.</div>';
        return;
    }
    el.innerHTML = all.map(f => `
        <div class="flex items-center gap-1.5 py-0.5">
            <input type="checkbox" class="backfill-item-check accent-accent" value="${f.file}" ${f.type === 'stale' ? 'checked' : ''}>
            <span class="text-slate-500 truncate flex-1 text-[8px] font-mono">${(f.file || '').split('/').pop()}</span>
            <span class="text-[7px] ${f.type === 'stale' ? 'text-orange-400' : 'text-yellow-400'}">${f.type}</span>
        </div>`
    ).join('');
}

function selectAllStale() {
    document.querySelectorAll('.backfill-item-check').forEach(cb => {
        const row   = cb.closest('div');
        const label = row ? row.querySelector('span.text-orange-400') : null;
        if (label) cb.checked = true;
    });
}

async function startBackfill() {
    const checks = Array.from(document.querySelectorAll('.backfill-item-check:checked')).map(c => c.value);
    if (!checks.length) { alert('Select at least one file to backfill'); return; }
    try {
        const d = await fetch('/api/backfill/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ files: checks })
        }).then(r => r.json());
        if (d.status === 'started' || d.status === 'ok') {
            document.getElementById('backfill-stop-btn').classList.remove('hidden');
            document.getElementById('backfill-progress-section').classList.remove('hidden');
            if (!_backfillInterval) _backfillInterval = setInterval(pollBackfill, 3000);
        } else {
            alert('Backfill error: ' + (d.message || 'Unknown'));
        }
    } catch (e) { alert('Backfill start error: ' + e.message); }
}

async function stopBackfill() {
    try {
        await fetch('/api/backfill/stop', { method: 'POST' });
        clearInterval(_backfillInterval); _backfillInterval = null;
        document.getElementById('backfill-stop-btn').classList.add('hidden');
    } catch (e) {}
}

async function pollBackfill() {
    try {
        const d   = await fetch('/api/backfill/status').then(r => r.json());
        const pct = d.total > 0 ? Math.round((d.done / d.total) * 100) : 0;
        const setEl = (id, val) => { const e = document.getElementById(id); if (e) e.textContent = val; };
        setEl('backfill-current-file', (d.current_file || '—').split('/').pop());
        setEl('backfill-count',        `${d.done || 0} / ${d.total || 0}`);
        setEl('backfill-eta',          _fmtEta(d.eta_sec || 0));
        const bar = document.getElementById('backfill-progress-bar');
        if (bar) bar.style.width = pct + '%';
        const log = document.getElementById('backfill-log');
        if (log && d.log) {
            log.innerHTML = d.log.map(l => `
                <div class="flex items-center gap-2 py-0.5 border-b border-slate-800/30">
                    <i class="fa-solid ${l.status === 'done' ? 'fa-check text-emerald-400' : l.status === 'error' ? 'fa-xmark text-red-400' : 'fa-clock text-slate-600'} text-[7px] flex-shrink-0"></i>
                    <span class="truncate flex-1 text-[8px] font-mono ${l.status === 'error' ? 'text-red-400' : 'text-slate-400'}">${(l.file || '').split('/').pop()}</span>
                    <span class="text-[7px] ${l.status === 'done' ? 'text-emerald-400' : 'text-red-400'} flex-shrink-0">${l.status || '—'}</span>
                </div>`
            ).join('');
        }
        if (!d.running) {
            clearInterval(_backfillInterval); _backfillInterval = null;
            document.getElementById('backfill-stop-btn').classList.add('hidden');
        }
    } catch (e) {}
}
