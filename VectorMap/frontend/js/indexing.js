// ─── INDEXING CONTROLS ────────────────────────────────────────────────

async function triggerIndex(limit = null) {
    closeModal('cache-modal');
    try {
        const d = await fetch('/start_index', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ limit })
        }).then(r => r.json());
        if (d.status === 'started') fetchStatus();
        else alert(d.message);
    } catch (e) { alert('Failed to reach server.'); }
}

async function stopIndexing() {
    const r = await fetch('/api/indexing/stop', { method: 'POST' }).then(r => r.json());
    if (r.status === 'stopping') document.getElementById('p1-idx-status').textContent = 'Stopping...';
}

async function openFilesModal() {
    openModal('files-modal');
    try {
        const d     = await fetch('/api/indexing/files').then(r => r.json());
        const stats = document.getElementById('files-modal-stats');
        const list  = document.getElementById('files-modal-list');
        stats.textContent = `${d.processed}/${d.total} files processed`;
        list.innerHTML = d.files.map((f, i) => `
            <div class="flex items-center gap-2 py-0.5 ${i < d.processed ? 'opacity-100' : 'opacity-40'}">
                <i class="fa-solid ${f.done ? 'fa-check text-emerald-400' : 'fa-clock text-slate-600'} text-[8px] flex-shrink-0"></i>
                <span class="truncate text-[8px] ${f.done ? 'text-slate-400' : 'text-slate-600'}">${f.name}</span>
            </div>`
        ).join('') || '<div class="text-slate-700 text-[8px] italic">No indexing data yet.</div>';
    } catch (e) {}
}

function closeFilesModal() {
    closeModal('files-modal');
}
