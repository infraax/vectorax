# VaultForge — VectorMap Integration

## When To Do This

Only after ALL of the following pass:
- `pytest tests/ -v` — all green
- Vault directory has > 5,000 .md files
- ChromaDB v2 has > 50,000 chunks
- TRM developer notes verified in `TRM/DeveloperNotes/`

---

## Step 1 — Update Paths in langgraph_agent.py

```python
# File: /Users/lab/research/VectorMap/src/langgraph_agent.py
# Find and update:

VAULT_PATH = os.path.join(os.path.dirname(__file__), "../data/Vector_Obsidian_Vault_V2")
DB_PATH    = os.path.join(os.path.dirname(__file__), "../data/chroma_db_v2")
```

Search the file for any hardcoded collection names and update:
```bash
grep -n "collection" /Users/lab/research/VectorMap/src/langgraph_agent.py
grep -n "chroma_db" /Users/lab/research/VectorMap/src/langgraph_agent.py
```

If the agent uses a single collection for retrieval, update to use the multi-collection
search pattern from `docs/06_DATABASE_SPEC.md`.

---

## Step 2 — Restart VectorMap

```bash
# Kill existing server (find PID first)
lsof -ti:61392 | xargs kill -9  # adjust port as needed
# or use tmux if server is in a tmux session

# Start fresh
cd /Users/lab/research/VectorMap
./start.sh
```

---

## Step 3 — Trigger Re-Index via Dashboard

1. Open VectorMap in browser: `http://127.0.0.1:PORT`
2. Go to Page 1 (Command Center)
3. Click **UPDATE VAULT CACHE**
4. Watch the indexing progress bar — it should process all files in `Vector_Obsidian_Vault_V2/`
5. Wait for completion — chunk count should appear in the status display

Expected: chunk count significantly higher than old 41,363

---

## Step 4 — Verify via API

```bash
PORT=61392  # adjust to actual port

# Check status
curl -s http://127.0.0.1:$PORT/status | python3 -c "
import sys, json
d = json.load(sys.stdin)
s = d['stats']
print('Status:', d['status'])
print('Chunks:', s['indexed_chunks_total'])
print('Model:', s.get('agent_config', {}).get('model', 'unknown'))
"

# Expected:
# Status: online
# Chunks: 55000+  (significantly more than 41363)
```

---

## Step 5 — Smoke Test Queries

Run these queries via the VectorMap chat and verify responses:

**Query 1 — Hardware question (should cite TRM)**
```
"How does the Vector PID motor control loop work and what are the design constraints?"
```
Expected: Response mentions the 1kHz loop rate, STM32, integrator cap (developer note from TRM page 46)

**Query 2 — Code function lookup**
```
"Show me the set_eye_color function and which hardware it controls"
```
Expected: Response includes function signature, line number, and reference to the IPS display

**Query 3 — Cross-repo question**
```
"How does wire-pod differ from chipper in its gRPC setup?"
```
Expected: Response references the clone relationship between the two repos

**Query 4 — TRM table question**
```
"What GPIO pins does the STM32 use for motor encoder feedback?"
```
Expected: Response includes GPIO pin names (PA0, PA1) and voltage specs from the TRM table

**Query 5 — Developer note question**
```
"Are there any warnings about motor control that the Vector engineers documented?"
```
Expected: Response surfaces the integrator windup warning note (highest priority content)

---

## Rollback Plan

If anything breaks, revert to old vault immediately:

```python
# In langgraph_agent.py, revert to:
VAULT_PATH = os.path.join(os.path.dirname(__file__), "../data/Vector_Obsidian_Vault_TEST")
DB_PATH    = os.path.join(os.path.dirname(__file__), "../data/chroma_db_test")
```

The old ChromaDB (`chroma_db_test`) and old vault (`Vector_Obsidian_Vault_TEST`) are NEVER
modified by the pipeline. They remain as fallback.
