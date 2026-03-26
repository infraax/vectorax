// ─── PAGE 3: SEMANTIC OBSERVATORY ────────────────────────────────────

// ─── PAGE 3 TABS ─────────────────────────────────────────────────────
function switchP3Tab(tab) {
    ['repos', 'chunks', 'heatmap'].forEach(t => {
        const el  = document.getElementById('p3-tab-' + t);
        const btn = document.getElementById('p3t-' + t);
        if (el) el.classList.toggle('hidden', t !== tab);
        if (btn) {
            if (t === tab) { btn.className = 'flex-1 py-2 text-[8px] font-bold uppercase tracking-widest text-accent border-b-2 border-accent'; }
            else           { btn.className = 'flex-1 py-2 text-[8px] font-bold uppercase tracking-widest text-slate-500'; }
        }
    });
    if (tab === 'chunks')  loadChunkStats();
    if (tab === 'heatmap') loadHeatmap();
}

// ─── CHUNK STATS ──────────────────────────────────────────────────────
async function loadChunkStats() {
    const el = document.getElementById('chunk-stats-content');
    if (el) el.innerHTML = '<div class="text-[8px] text-slate-600 animate-pulse">Loading…</div>';
    try {
        const d = await fetch('/api/chunks/stats').then(r => r.json());
        if (!el) return;

        // Backend field names: avg_size_chars, size_distribution (array), top_files (array of {source, chunk_count})
        const avgSize  = d.avg_size_chars || 0;
        const distArr  = d.size_distribution || [];   // [{bucket, count}]
        const topFiles = d.top_files        || [];    // [{source, chunk_count}]

        let html = `<div class="grid grid-cols-2 gap-2 mb-3">
            <div class="bg-slate-800/60 p-2 rounded border border-slate-700/50 text-center">
                <div class="text-slate-200 font-bold text-lg">${(d.total_chunks || 0).toLocaleString()}</div>
                <div class="text-[7px] text-slate-600 uppercase tracking-widest">Total Chunks</div>
            </div>
            <div class="bg-slate-800/60 p-2 rounded border border-slate-700/50 text-center">
                <div class="text-slate-200 font-bold text-lg">${avgSize ? avgSize.toLocaleString() : '—'}</div>
                <div class="text-[7px] text-slate-600 uppercase tracking-widest">Avg chars</div>
            </div>
        </div>
        <div class="text-[8px] text-slate-500 uppercase tracking-widest font-bold mb-2">Size Distribution</div>
        <div class="space-y-1.5 mb-3">`;

        const bucketMax = Math.max(...distArr.map(b => b.count || 0), 1);
        distArr.forEach(b => {
            const label = `${(b.bucket || 0).toLocaleString()}–${((b.bucket || 0) + 200).toLocaleString()}`;
            html += `<div class="flex items-center gap-2 text-[8px] font-mono">
                <span class="text-slate-600 w-20 flex-shrink-0 truncate">${label}</span>
                <div class="flex-1 bg-slate-800 h-2 rounded overflow-hidden">
                    <div class="bg-accent h-full rounded" style="width:${Math.round(((b.count || 0) / bucketMax) * 100)}%"></div>
                </div>
                <span class="text-slate-400 w-8 text-right">${b.count || 0}</span>
            </div>`;
        });

        html += `</div><div class="text-[8px] text-slate-500 uppercase tracking-widest font-bold mb-2">Top Files by Chunks</div><div class="space-y-1.5">`;
        const fileMax = Math.max(...topFiles.map(f => f.chunk_count || 0), 1);
        topFiles.slice(0, 10).forEach(f => {
            const src   = f.source || '';
            const short = src.split('__').pop() || src.split('/').pop() || src || '—';
            html += `<div class="flex items-center gap-2 text-[8px] font-mono">
                <span class="text-slate-500 truncate flex-1" title="${src}">${short}</span>
                <div class="w-20 bg-slate-800 h-1.5 rounded overflow-hidden flex-shrink-0">
                    <div class="bg-purple-500 h-full rounded" style="width:${Math.round(((f.chunk_count || 0) / fileMax) * 100)}%"></div>
                </div>
                <span class="text-slate-400 w-6 text-right">${f.chunk_count || 0}</span>
            </div>`;
        });
        html += `</div>`;

        if (d.sampled && d.sampled < d.total_chunks) {
            html += `<div class="mt-2 text-[7px] text-slate-700 italic">Sampled ${d.sampled.toLocaleString()} of ${d.total_chunks.toLocaleString()} chunks</div>`;
        }
        el.innerHTML = html;

        // Populate chroma file selector (page 4) with source names
        const sel = document.getElementById('chroma-file-sel');
        if (sel && topFiles.length) {
            sel.innerHTML = '<option value="">— Select file —</option>'
                + topFiles.map(f => {
                    const src   = f.source || '';
                    const short = src.split('__').pop() || src || src;
                    return `<option value="${src}">${short}</option>`;
                }).join('');
        }
    } catch (e) {
        if (el) el.innerHTML = '<div class="text-[8px] text-red-400">Failed to load chunk stats: ' + e.message + '</div>';
    }
}

// ─── RETRIEVAL HEATMAP ────────────────────────────────────────────────
async function loadHeatmap() {
    const el = document.getElementById('heatmap-content');
    if (el) el.innerHTML = '<div class="text-[8px] text-slate-600 animate-pulse">Loading…</div>';
    try {
        const d     = await fetch('/api/vault/heatmap').then(r => r.json());
        // Backend returns {files: [{path, count, last_accessed}]}
        const files = d.files || [];
        if (!el) return;
        if (!files.length) {
            el.innerHTML = '<div class="text-[8px] text-slate-700 italic">No retrieval data yet — ask some questions first.</div>';
            return;
        }
        const maxR = Math.max(...files.map(f => f.count || 0), 1);
        el.innerHTML = files.slice(0, 50).map(f => {
            const pct   = Math.round(((f.count || 0) / maxR) * 100);
            const color = pct > 66 ? '#f87171' : pct > 33 ? '#fbbf24' : '#60a5fa';
            // Backend uses "path" field
            const src   = f.path || f.file || '';
            const short = src.split('__').pop() || src.split('/').pop() || src || '—';
            const lastAccess = f.last_accessed ? f.last_accessed.substring(0, 10) : '';
            return `<div class="flex items-center gap-2 text-[8px] font-mono mb-1.5">
                <span class="text-slate-500 truncate flex-1" title="${src}">${short}</span>
                ${lastAccess ? `<span class="text-slate-700 flex-shrink-0 hidden sm:block">${lastAccess}</span>` : ''}
                <div class="w-16 bg-slate-800 h-1.5 rounded overflow-hidden flex-shrink-0">
                    <div class="h-full rounded" style="width:${pct}%;background:${color}"></div>
                </div>
                <span class="w-6 text-right flex-shrink-0" style="color:${color}">${f.count || 0}</span>
            </div>`;
        }).join('');
    } catch (e) {
        if (el) el.innerHTML = '<div class="text-[8px] text-red-400">Failed to load heatmap: ' + e.message + '</div>';
    }
}
