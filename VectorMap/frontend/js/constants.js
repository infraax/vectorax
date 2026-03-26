// ─── CONSTANTS & SHARED GLOBALS ──────────────────────────────────────

const REPO_COLORS = [
    '#38bdf8','#a78bfa','#34d399','#fb923c','#f472b6',
    '#60a5fa','#4ade80','#fbbf24','#f87171','#818cf8',
    '#2dd4bf','#fb7185','#c084fc','#86efac','#67e8f9',
    '#fca5a5','#a3e635','#93c5fd','#fcd34d','#7dd3fc'
];

const _repoColorMap = {};
let _repoColorIdx = 0;

function repoColor(repo) {
    if (!_repoColorMap[repo]) {
        _repoColorMap[repo] = REPO_COLORS[_repoColorIdx % REPO_COLORS.length];
        _repoColorIdx++;
    }
    return _repoColorMap[repo];
}

const MODEL_ROLES = {
    'qwen2.5-coder': { role: 'Code Analysis · RAG Gen', icon: 'fa-code',     color: 'text-blue-400'   },
    'qwen2.5':       { role: 'General Reasoning',        icon: 'fa-brain',    color: 'text-purple-400' },
    'phi4':          { role: 'Advanced · Long Context',  icon: 'fa-atom',     color: 'text-yellow-400' },
    'smollm2':       { role: 'Fast · Low Memory',        icon: 'fa-bolt',     color: 'text-green-400'  },
    'llama3':        { role: 'General Purpose',          icon: 'fa-robot',    color: 'text-orange-400' },
    'llama3.2':      { role: 'General Purpose',          icon: 'fa-robot',    color: 'text-orange-400' },
    'mistral':       { role: 'Code + General',           icon: 'fa-wind',     color: 'text-cyan-400'   },
};

function modelRole(name) {
    for (const [k, v] of Object.entries(MODEL_ROLES)) {
        if (name.toLowerCase().startsWith(k)) return v;
    }
    return { role: 'LLM', icon: 'fa-microchip', color: 'text-slate-400' };
}

// ─── UTILITY HELPERS ─────────────────────────────────────────────────
function _col(p) { return p < 60 ? 'text-safe' : p < 85 ? 'text-warning' : 'text-danger'; }
function _bg(p)  { return p < 60 ? 'bg-safe'   : p < 85 ? 'bg-warning'   : 'bg-danger';  }
function _ms(ms) { return ms > 999 ? `${(ms / 1000).toFixed(2)}s` : `${Math.round(ms)}ms`; }
function _fmtEta(sec) {
    if (!sec || sec <= 0) return '—';
    if (sec < 60) return sec + 's';
    const m = Math.floor(sec / 60), s = sec % 60;
    return `${m}m${s > 0 ? s + 's' : ''}`;
}

// ─── SHARED STATE GLOBALS ─────────────────────────────────────────────
let _pcaPoints       = null;
let _repoFilter      = new Set();
let _mapRendered     = false;

let _ollamaLoaded    = [];
let _ollamaAvail     = [];

let _procTab         = 'my';
let _lastProc        = { my_ram: [], my_cpu: [], other_ram: [], other_cpu: [] };

let _queryActive     = false;
let _queryStartTs    = 0;
let _lastLogTs       = 0;
let _injectedDocs    = [];
let _useInjected     = false;

let _currentSessionId = null;
let _benchResults    = {};
let _lastTokenUsage  = {};

let _logInterval         = null;
let _backfillInterval    = null;
let _robotLogInterval    = null;
let _backfillQueue       = [];
let _archNetwork         = null;
let _spotlightActive     = false;
let _driftData           = {};
let _refactorData        = {};
let _nodeStartTs         = {};
let _templates           = [];
