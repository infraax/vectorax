// ─── OLLAMA MODEL MANAGER ─────────────────────────────────────────────

async function fetchOllamaModels() {
    try {
        const d = await fetch('/api/ollama/models').then(r => r.json());
        _ollamaLoaded = d.loaded || [];
        const avail = (d.available || []).slice().sort((a, b) => b.size_gb - a.size_gb);
        const activeCfgModel = document.getElementById('p1-active-model')?.textContent || '';

        // Loaded models panel
        const loadedEl = document.getElementById('ollama-loaded');
        if (_ollamaLoaded.length === 0) {
            loadedEl.innerHTML = '<div class="text-[8px] text-slate-700 italic px-1 pb-1">No models currently in GPU memory</div>';
        } else {
            loadedEl.innerHTML = _ollamaLoaded.map(m => {
                const r = modelRole(m.name);
                return `<div class="model-card ${m.name === activeCfgModel ? 'active-model' : ''}">
                    <div class="flex items-start gap-2">
                        <div class="flex-1 min-w-0">
                            <div class="flex items-center gap-1.5 mb-0.5">
                                <span class="text-[9px] font-mono font-bold text-white truncate">${m.name}</span>
                                ${m.name === activeCfgModel ? '<span class="text-[7px] bg-accent/20 text-accent px-1 py-0.5 rounded font-bold flex-shrink-0">ACTIVE</span>' : ''}
                            </div>
                            <div class="text-[8px] text-slate-500"><i class="fa-solid ${r.icon} mr-1 ${r.color}"></i>${r.role}</div>
                        </div>
                        <div class="text-right flex-shrink-0">
                            <div class="text-[10px] font-bold text-purple-300">${m.size_gb}G</div>
                            <button onclick="evictModel('${m.name}')" class="text-[7px] mt-0.5 bg-red-900/30 hover:bg-red-800/50 text-red-400 px-1.5 py-0.5 rounded border border-red-800/40 transition"><i class="fa-solid fa-eject mr-0.5"></i>evict</button>
                        </div>
                    </div>
                </div>`;
            }).join('');
        }

        const wiredTotal = _ollamaLoaded.reduce((s, m) => s + m.size_gb, 0);
        const wiredEl = document.getElementById('ollama-wired-total');
        if (wiredEl) wiredEl.textContent = wiredTotal.toFixed(1) + 'GB wired';

        // Available models panel
        const availEl = document.getElementById('ollama-available');
        availEl.innerHTML = avail.map(m => {
            const r       = modelRole(m.name);
            const isActive = m.name === activeCfgModel;
            return `<div class="model-card ${isActive ? 'active-model' : ''} ${m.loaded ? 'border-purple-800/40' : ''}">
                <div class="flex items-center gap-2">
                    <div class="flex-1 min-w-0">
                        <div class="flex items-center gap-1 mb-0.5">
                            <span class="text-[9px] font-mono text-slate-300 truncate">${m.name}</span>
                            ${m.loaded  ? '<span class="text-[6px] bg-purple-900/60 text-purple-400 px-1 py-0.5 rounded flex-shrink-0">GPU</span>'    : ''}
                            ${isActive  ? '<span class="text-[6px] bg-accent/20 text-accent px-1 py-0.5 rounded flex-shrink-0">ACTIVE</span>'           : ''}
                        </div>
                        <div class="text-[7px] text-slate-600"><i class="fa-solid ${r.icon} mr-1 ${r.color}"></i>${r.role}</div>
                    </div>
                    <div class="text-[10px] font-mono text-slate-400 flex-shrink-0">${m.size_gb}G</div>
                </div>
            </div>`;
        }).join('');

        // Page 2 ollama loaded display
        const p2Loaded = document.getElementById('p2-ollama-loaded');
        if (p2Loaded) p2Loaded.textContent = wiredTotal.toFixed(1) + 'GB';

        // Benchmark model dropdowns
        ['bench-model-a', 'bench-model-b'].forEach(id => {
            const sel = document.getElementById(id);
            if (sel) sel.innerHTML = (d.available || []).map(m =>
                `<option value="${m.name}">${m.name} (${m.size_gb}G)</option>`
            ).join('');
        });
    } catch (e) {}
}

function renderModelCards(loaded, available, activeCfgModel) {
    // Thin wrapper kept for external callers if needed
    _ollamaLoaded = loaded || [];
    fetchOllamaModels();
}

async function evictModel(name) {
    const r = await fetch('/api/ollama/evict', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: name })
    });
    const d = await r.json();
    if (d.status === 'evicted') fetchOllamaModels();
    else alert('Evict failed: ' + d.message);
}

async function evictAllModels() {
    for (const m of _ollamaLoaded) await evictModel(m.name);
}
