// ─── PAGE 2: AGENTIC FORGE ────────────────────────────────────────────

// ─── PAGE 2 TABS ─────────────────────────────────────────────────────
const P2_TABS = ['config', 'benchmark', 'inject', 'resources', 'history', 'hallucinations', 'trace'];

function switchP2Tab(tab) {
    P2_TABS.forEach(t => {
        const el  = document.getElementById('p2-tab-' + t);
        const btn = document.getElementById('p2t-' + t);
        if (el)  el.classList.toggle('hidden', t !== tab);
        if (btn) { btn.classList.toggle('active', t === tab); }
    });
    if (tab === 'history')        loadQueryHistory();
    if (tab === 'hallucinations') loadHallucinations();
}

// ─── TEMPLATE LIBRARY ────────────────────────────────────────────────
async function loadTemplates() {
    try {
        const d = await fetch('/api/templates').then(r => r.json());
        _templates = d.templates || [];
        renderTemplates();
    } catch (e) {
        document.getElementById('template-list').innerHTML = '<div class="text-[8px] text-slate-700 italic">Templates unavailable</div>';
    }
}

function renderTemplates() {
    const el = document.getElementById('template-list');
    if (!_templates.length) {
        el.innerHTML = '<div class="text-[8px] text-slate-700 italic">No templates yet. Add one above.</div>';
        return;
    }
    el.innerHTML = _templates.map(t => `
        <div class="bg-slate-800/60 p-2 rounded border border-slate-700/50 hover:border-slate-600 transition">
            <div class="flex items-start gap-1.5">
                <div class="flex-1 min-w-0">
                    <div class="text-[9px] font-bold text-slate-300 truncate">${t.name || 'Unnamed'}</div>
                    <div class="text-[8px] text-slate-600 font-mono truncate mt-0.5">${(t.template || '').replace(/\{(\w+)\}/g, '<span class="text-orange-400">{$1}</span>')}</div>
                </div>
                <div class="flex gap-1 flex-shrink-0">
                    <button onclick="useTemplate(${JSON.stringify(t.template || '')})" class="text-[7px] bg-accent/10 hover:bg-accent/20 text-accent px-1.5 py-0.5 rounded border border-accent/20 transition">Use</button>
                    <button onclick="deleteTemplate(${t.id})" class="text-[7px] bg-red-900/20 hover:bg-red-800/40 text-red-400 px-1.5 py-0.5 rounded border border-red-900/30 transition">Del</button>
                </div>
            </div>
        </div>`
    ).join('');
}

function showAddTemplate()  { document.getElementById('template-add-form').classList.remove('hidden'); }
function hideAddTemplate()  { document.getElementById('template-add-form').classList.add('hidden'); }

async function saveTemplate() {
    const name = document.getElementById('tpl-name').value.trim();
    const text = document.getElementById('tpl-text').value.trim();
    if (!name || !text) return;
    try {
        // Backend expects "template" field, not "text"
        await fetch('/api/templates', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, template: text })
        });
        document.getElementById('tpl-name').value = '';
        document.getElementById('tpl-text').value = '';
        hideAddTemplate();
        loadTemplates();
    } catch (e) { alert('Save failed'); }
}

async function deleteTemplate(id) {
    try {
        await fetch(`/api/templates/${id}`, { method: 'DELETE' });
        loadTemplates();
    } catch (e) {}
}

function useTemplate(text) {
    document.getElementById('user-input').value = text;
    switchPage(1);
}

// ─── BENCHMARK ────────────────────────────────────────────────────────
async function runBenchmark() {
    const mA     = document.getElementById('bench-model-a').value;
    const mB     = document.getElementById('bench-model-b').value;
    const prompt = document.getElementById('bench-prompt').value.trim();
    if (!prompt || !mA || !mB) { alert('Fill in both models and a prompt'); return; }
    const res = document.getElementById('bench-results');
    res.classList.add('hidden');

    // Show spinner
    const btn = document.getElementById('bench-run-btn');
    if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin mr-1"></i> Running…'; }

    try {
        // Backend expects "message" field (not "prompt")
        const d = await fetch('/api/benchmark', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ model_a: mA, model_b: mB, message: prompt })
        }).then(r => r.json());
        _benchResults = d;

        // Backend returns results keyed by model name under d.results
        const ra = (d.results || {})[mA] || d.model_a || {};
        const rb = (d.results || {})[mB] || d.model_b || {};
        const maxMs = Math.max(ra.ms || 1, rb.ms || 1);

        document.getElementById('bench-a-name').textContent    = mA;
        document.getElementById('bench-a-preview').textContent = ra.error ? '⚠️ ' + ra.error : (ra.response || '').substring(0, 120);
        document.getElementById('bench-a-ms').textContent      = _ms(ra.ms || 0);
        document.getElementById('bench-a-tps').textContent     = (ra.tokens_per_sec || 0).toFixed(1);
        document.getElementById('bench-a-bar').style.width     = Math.round(((ra.ms || 0) / maxMs) * 100) + '%';

        document.getElementById('bench-b-name').textContent    = mB;
        document.getElementById('bench-b-preview').textContent = rb.error ? '⚠️ ' + rb.error : (rb.response || '').substring(0, 120);
        document.getElementById('bench-b-ms').textContent      = _ms(rb.ms || 0);
        document.getElementById('bench-b-tps').textContent     = (rb.tokens_per_sec || 0).toFixed(1);
        document.getElementById('bench-b-bar').style.width     = Math.round(((rb.ms || 0) / maxMs) * 100) + '%';

        res.classList.remove('hidden');
    } catch (e) { alert('Benchmark error: ' + e.message); }

    if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fa-solid fa-play mr-1"></i> Run Benchmark'; }
}

// ─── INJECTION ────────────────────────────────────────────────────────
function toggleInjection(on) {
    _useInjected = on;
    if (on) {
        const txt = document.getElementById('inject-content').value.trim();
        if (txt) _injectedDocs = [txt];
    }
    const status = document.getElementById('inject-status');
    if (status) {
        status.textContent = on ? 'ON' : 'OFF';
        status.className   = on ? 'text-[8px] font-mono text-warning font-bold' : 'text-[8px] font-mono text-slate-600';
    }
}

function clearInjection() {
    document.getElementById('inject-content').value = '';
    _injectedDocs = [];
    _useInjected  = false;
    const tog = document.getElementById('inject-toggle');
    if (tog) tog.checked = false;
    const status = document.getElementById('inject-status');
    if (status) { status.textContent = 'OFF'; status.className = 'text-[8px] font-mono text-slate-600'; }
}

// ─── HALLUCINATIONS ───────────────────────────────────────────────────
async function loadHallucinations() {
    try {
        const d = await fetch('/api/hallucinations').then(r => r.json());
        const tbody = document.getElementById('hallucinations-tbody');
        const items = d.hallucinations || d.items || [];
        if (!items.length) {
            tbody.innerHTML = '<tr><td colspan="5" class="text-slate-600 italic py-4 text-center text-[8px]">No hallucinations recorded — the validation pipeline is working correctly.</td></tr>';
            return;
        }
        tbody.innerHTML = items.map((h, i) => `
            <tr class="border-b border-slate-800/30 text-[9px]">
                <td class="py-1.5 pr-2 text-slate-600">${i + 1}</td>
                <td class="py-1.5 pr-2 text-slate-500">${(h.timestamp || '—').substring(11, 19)}</td>
                <td class="py-1.5 pr-2 text-danger font-bold">${h.violation || h.violation_type || '—'}</td>
                <td class="py-1.5 pr-4 text-slate-400 max-w-[200px] truncate">${(h.query || '').substring(0, 40)}</td>
                <td class="py-1.5"><button onclick="openHallucinationDetail(${i})" class="text-[7px] bg-slate-800 hover:bg-slate-700 text-slate-400 px-2 py-0.5 rounded border border-slate-700 transition">View</button></td>
            </tr>`
        ).join('');
        window._hallucs = items;
    } catch (e) {
        document.getElementById('hallucinations-tbody').innerHTML =
            '<tr><td colspan="5" class="text-slate-600 italic py-4 text-center text-[8px]">Failed to load.</td></tr>';
    }
}

function openHallucinationDetail(idx) {
    const h = (window._hallucs || [])[idx];
    if (!h) return;
    // Backend stores "violation" (not "violation_type") and "raw_generation"
    document.getElementById('hd-raw').textContent       = h.raw_generation || '—';
    document.getElementById('hd-violation').textContent = h.violation || h.violation_type || '—';
    openModal('halluc-modal');
}

// alias
function openHallucDetail(idx) { openHallucinationDetail(idx); }
