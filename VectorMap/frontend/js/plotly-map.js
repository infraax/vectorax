// ─── VECTOR MAP & MINIMAP ─────────────────────────────────────────────

async function renderVectorMap() {
    if (_mapRendered && !confirm('Re-run PCA projection?')) return;
    document.getElementById('vector-loader').classList.remove('hidden');
    try {
        const d = await fetch('/api/vector_map').then(r => r.json());
        if (d.status !== 'online' || !d.points || !d.points.length) {
            alert(d.status === 'error' ? d.message : 'No embeddings returned.');
            document.getElementById('vector-loader').classList.add('hidden');
            return;
        }
        _pcaPoints  = d.points;
        _repoFilter = new Set(d.points.map(p => p.repo));
        renderPlot3D(d.points);
        renderMinimap2D(d.points);
        buildRepoFilter(d.points);
        buildRepoStats(d.points);
        document.getElementById('p3-pca-stats').classList.remove('hidden');
        document.getElementById('p3-chunk-count').textContent = d.points.length.toLocaleString();
        if (d.explained_var) {
            document.getElementById('p3-variance').textContent =
                (d.explained_var.reduce((a, b) => a + b, 0) * 100).toFixed(1) + '%';
        }
        _mapRendered = true;
        renderP1Minimap([]);
    } catch (e) { console.error(e); alert('Vector map error: ' + e.message); }
    document.getElementById('vector-loader').classList.add('hidden');
}

function renderPlot3D(points, spotlightSet) {
    const groups = {};
    points.forEach(p => {
        if (!_repoFilter.has(p.repo)) return;
        if (!groups[p.repo]) groups[p.repo] = { x: [], y: [], z: [], text: [], full: [], opacity: [] };
        groups[p.repo].x.push(p.x);
        groups[p.repo].y.push(p.y);
        groups[p.repo].z.push(p.z);
        const short = p.name.includes('__') ? p.name.split('__').slice(1).join('__') : p.name;
        groups[p.repo].text.push(short.length > 40 ? short.substring(0, 38) + '…' : short);
        groups[p.repo].full.push(p.name);
        const inSpotlight = !spotlightSet || spotlightSet.has(p.name);
        groups[p.repo].opacity.push(spotlightSet ? (inSpotlight ? 1 : 0.05) : 0.82);
    });
    const traces = Object.keys(groups).map(r => ({
        x: groups[r].x, y: groups[r].y, z: groups[r].z,
        text: groups[r].text, customdata: groups[r].full,
        mode: 'markers', type: 'scatter3d',
        name: r.length > 20 ? r.substring(0, 18) + '…' : r,
        marker: {
            size: groups[r].opacity.map(() => 3.5),
            color: repoColor(r),
            opacity: groups[r].opacity,
            line: { color: 'rgba(255,255,255,0.08)', width: 0.5 }
        },
        hovertemplate: '<b>%{text}</b><br><span style="color:#64748b">%{customdata}</span><extra>' + r + '</extra>'
    }));
    const layout = {
        margin: { l: 0, r: 0, b: 0, t: 0 },
        paper_bgcolor: '#030712',
        scene: {
            xaxis: { showgrid: false, zeroline: false, showline: false, ticks: '', showticklabels: false, showspikes: false, backgroundcolor: '#030712' },
            yaxis: { showgrid: false, zeroline: false, showline: false, ticks: '', showticklabels: false, showspikes: false, backgroundcolor: '#030712' },
            zaxis: { showgrid: false, zeroline: false, showline: false, ticks: '', showticklabels: false, showspikes: false, backgroundcolor: '#030712' },
            bgcolor: '#030712',
            camera: { eye: { x: 1.4, y: 1.4, z: 0.8 } }
        },
        legend: { font: { color: '#94a3b8', size: 10 }, y: 0.02, bgcolor: 'rgba(15,23,42,0.8)', bordercolor: '#1e293b', borderwidth: 1 }
    };
    Plotly.newPlot('vector-plot', traces, layout, { responsive: true, displayModeBar: false });
    const el = document.getElementById('vector-plot');
    el.removeAllListeners && el.removeAllListeners('plotly_click');
    el.on('plotly_click', function (data) {
        if (!data.points || !data.points.length) return;
        const pt = data.points[0];
        document.getElementById('pd-name').textContent  = pt.text;
        document.getElementById('pd-repo').textContent  = 'Repo: ' + pt.data.name;
        document.getElementById('pd-coords').textContent = `PCA (${pt.x.toFixed(3)}, ${pt.y.toFixed(3)}, ${pt.z.toFixed(3)})`;
        document.getElementById('point-detail').classList.remove('hidden');
    });
    el.on('plotly_relayout', function (ev) {
        if (ev['scene.camera']) updateMinimapViewport(ev['scene.camera']);
    });
}

function renderMinimap2D(points) {
    const groups = {};
    points.forEach(p => {
        if (!groups[p.repo]) groups[p.repo] = { x: [], y: [], text: [] };
        groups[p.repo].x.push(p.x);
        groups[p.repo].y.push(p.y);
        groups[p.repo].text.push(p.name.includes('__') ? p.name.split('__').pop() : p.name);
    });
    const traces = Object.keys(groups).map(r => ({
        x: groups[r].x, y: groups[r].y, text: groups[r].text,
        mode: 'markers', type: 'scatter', name: r,
        marker: { size: 2.5, color: repoColor(r), opacity: 0.65 },
        hovertemplate: '%{text}<extra></extra>'
    }));
    Plotly.newPlot('vector-minimap', traces, {
        margin: { l: 0, r: 0, b: 0, t: 0 },
        paper_bgcolor: '#0f172a', plot_bgcolor: '#0f172a',
        showlegend: false,
        xaxis: { showgrid: false, zeroline: false, showticklabels: false, showline: false, fixedrange: true },
        yaxis: { showgrid: false, zeroline: false, showticklabels: false, showline: false, fixedrange: true },
    }, { responsive: true, displayModeBar: false, staticPlot: false });
}

function updateMinimapViewport(camera) {
    if (!camera || !camera.eye) return;
    const { x, y } = camera.eye;
    Plotly.relayout('vector-minimap', { shapes: [{
        type: 'circle', xref: 'paper', yref: 'paper',
        x0: 0.5 - (0.1 / Math.abs(x || 1)), y0: 0.5 - (0.1 / Math.abs(y || 1)),
        x1: 0.5 + (0.1 / Math.abs(x || 1)), y1: 0.5 + (0.1 / Math.abs(y || 1)),
        line: { color: 'rgba(56,189,248,0.5)', width: 1.5 }, fillcolor: 'rgba(56,189,248,0.05)'
    }] });
}

// ─── P1 MINIMAP ───────────────────────────────────────────────────────
function renderP1Minimap(highlighted) {
    if (!_pcaPoints) return;
    const el     = document.getElementById('p1-minimap');
    const groups = {};
    const hlSet  = new Set((highlighted || []).map(s => s.filename));
    _pcaPoints.forEach(p => {
        if (!groups[p.repo]) groups[p.repo] = { x: [], y: [], m: [], hl: [] };
        groups[p.repo].x.push(p.x);
        groups[p.repo].y.push(p.y);
        groups[p.repo].m.push(hlSet.has(p.name) ? 6 : 2);
        groups[p.repo].hl.push(hlSet.has(p.name));
    });
    const traces = Object.keys(groups).map(r => ({
        x: groups[r].x, y: groups[r].y,
        mode: 'markers', type: 'scatter', name: r,
        marker: { size: groups[r].m, color: groups[r].hl.map(h => h ? '#fbbf24' : repoColor(r)), opacity: groups[r].hl.map(h => h ? 1 : 0.5) },
        hoverinfo: 'none'
    }));
    Plotly.newPlot(el, traces, {
        margin: { l: 0, r: 0, b: 0, t: 0 },
        paper_bgcolor: '#030712', plot_bgcolor: '#030712',
        showlegend: false,
        xaxis: { showgrid: false, zeroline: false, showticklabels: false, showline: false },
        yaxis: { showgrid: false, zeroline: false, showticklabels: false, showline: false },
    }, { responsive: true, displayModeBar: false, staticPlot: true });
}

// ─── REPO FILTER ──────────────────────────────────────────────────────
function buildRepoFilter(points) {
    const repos = [...new Set(points.map(p => p.repo))].sort();
    const el    = document.getElementById('repo-filter-chips');
    el.innerHTML = repos.map(r =>
        `<span onclick="toggleRepo('${r}')" id="chip-${CSS.escape(r)}"
          class="chip on" style="border-color:${repoColor(r)}33;color:${repoColor(r)}">${r.substring(0, 18)}</span>`
    ).join('');
}

function toggleRepo(repo) {
    if (_repoFilter.has(repo)) _repoFilter.delete(repo);
    else _repoFilter.add(repo);
    const chip = document.getElementById('chip-' + CSS.escape(repo));
    if (chip) {
        const on = _repoFilter.has(repo);
        chip.className = 'chip' + (on ? ' on' : '');
        if (on)  { chip.style.borderColor = repoColor(repo) + '33'; chip.style.color = repoColor(repo); }
        else     { chip.style.borderColor = ''; chip.style.color = ''; }
    }
    if (_repoFilter.has(repo) && _pcaPoints) {
        const pts = _pcaPoints.filter(p => p.repo === repo);
        if (pts.length) {
            const xs = pts.map(p => p.x), ys = pts.map(p => p.y);
            const pad = 0.3;
            Plotly.relayout('vector-minimap', { shapes: [{
                type: 'rect',
                x0: Math.min(...xs) - pad, x1: Math.max(...xs) + pad,
                y0: Math.min(...ys) - pad, y1: Math.max(...ys) + pad,
                line: { color: repoColor(repo), width: 1.5, dash: 'dot' },
                fillcolor: 'rgba(56,189,248,0.04)'
            }] });
        }
    } else { Plotly.relayout('vector-minimap', { shapes: [] }); }
    if (_pcaPoints) renderPlot3D(_pcaPoints);
}

function buildRepoStats(points) {
    const counts = {};
    points.forEach(p => { counts[p.repo] = (counts[p.repo] || 0) + 1; });
    const sorted = Object.entries(counts).sort((a, b) => b[1] - a[1]);
    const total  = points.length;
    document.getElementById('repo-stats').innerHTML = sorted.map(([r, n]) => `
        <div class="space-y-0.5">
            <div class="flex justify-between items-center">
                <span class="truncate text-slate-500" style="color:${repoColor(r)}">${r.substring(0, 22)}</span>
                <span class="ml-2 flex-shrink-0 font-bold" style="color:${repoColor(r)}">${n}</span>
            </div>
            <div class="w-full bg-slate-800 h-0.5 rounded overflow-hidden">
                <div style="width:${((n / total) * 100).toFixed(1)}%;background:${repoColor(r)}" class="h-full rounded"></div>
            </div>
        </div>`
    ).join('');
}

// ─── SPOTLIGHT SEARCH ─────────────────────────────────────────────────
async function spotlightSearch() {
    const q = document.getElementById('p3-spotlight-input').value.trim();
    if (!q || !_pcaPoints) { alert('Generate PCA map first'); return; }
    try {
        const d = await fetch('/api/vector_search', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: q, k: 20 })
        }).then(r => r.json());
        const matchSet = new Set((d.results || []).map(r => r.filename));
        _spotlightActive = true;
        renderPlot3D(_pcaPoints, matchSet);
    } catch (e) { alert('Search error: ' + e.message); }
}

function clearSpotlight() {
    _spotlightActive = false;
    if (_pcaPoints) renderPlot3D(_pcaPoints);
    document.getElementById('p3-spotlight-input').value = '';
}
