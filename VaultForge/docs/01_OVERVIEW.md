# VaultForge — Architecture Overview

## What We Are Building

A multi-stage data pipeline that transforms raw source material into a knowledge base that
makes VectorMap dramatically more accurate and detailed when answering questions about the
Anki Vector robot codebase.

## Source Material

### The VectorTRM.pdf (root source of truth)
- 565 pages. Every hardware component, every firmware decision, every protocol
- Contains code snippets (C, Go, Python, Proto), pin tables, circuit diagrams,
  developer notes explaining WHY decisions were made
- This is the specification all 13 repos were built against
- Gemini flattened it to a 50K line text file, losing ~60% of its value

### 13 Repositories (816MB, all with .git history)

| Repo | Language | Role in Ecosystem |
|------|----------|-------------------|
| `vector` | C++ | Core robot firmware — runs on Snapdragon APQ8009 |
| `chipper` | Go | Voice processing + gRPC server — central hub |
| `vector-cloud` | Go | Cloud authentication + gateway |
| `vector-python-sdk` | Python | Primary public SDK |
| `vector-go-sdk` | Go | Go SDK |
| `wire-pod` | Go | Community local server (chipper fork/reimplementation) |
| `escape-pod-extension` | Go | Local AI processing extension |
| `hugh` | Go | Face recognition service |
| `vector-bluetooth` | Go/JS | BLE onboarding |
| `dev-docs` | Markdown | Official developer documentation |
| `vector-web-setup` | JS/HTML | Web setup UI |
| `vectorx` | Mixed | Community extensions |
| `vectorx-voiceserver` | Go | Voice server extension |

## Pipeline Stages

```
Stage 0: Environment Setup
         ↓
Stage 1: TRM Processing          ← Start here. Builds component registry + code snippets.
         ↓
Stage 2: Repository Deep Parse   ← tree-sitter AST parse all 13 repos
         ↓
Stage 3: Cross-Linking           ← TRM↔Repo links + cross-repo imports + clone detection
         ↓
Stage 4: LLM Annotation          ← Local Ollama: summaries for functions/classes/files/repos
         ↓
Stage 5: Chunk Construction      ← Token-aware, boundary-safe, 25+ metadata fields
         ↓
Stage 6: Vault Generation        ← Obsidian markdown with WikiLinks, frontmatter, Canvas files
         ↓
Stage 7: Database Population     ← ChromaDB (5 collections) + SQLite metadata + BM25 index
         ↓
Stage 8: VectorMap Integration   ← Update VAULT_PATH, re-index, verify
```

## Key Improvement Over Gemini's Approach

| Aspect | Gemini | VaultForge |
|--------|--------|------------|
| TRM extraction | pdftotext (flat text) | PyMuPDF + pdfplumber: tables, code, figures, notes |
| TRM developer notes | Lost | Extracted as highest-priority content |
| Code parsing | `line.startswith("def ")` | tree-sitter full AST |
| Import resolution | Word-overlap guessing | Resolved module paths via go.mod/importlib |
| Clone detection | None | MinHash LSH + AST structural comparison |
| LLM annotations | None | Function/class/file/repo level |
| Chunk token counting | Word count | tiktoken exact count |
| Chunk metadata fields | 4 | 25+ with full provenance |
| Cross-links in vault | Word-match noise | Derived from actual resolved imports |
| TRM→Repo linking | Keyword on filenames | Code symbol matching against symbol table |
| Hardware binding | Filename keyword match | Content-based + confidence scored |
| Vault structure | Flat per-file notes | Repos/Modules/Symbols/TRM hierarchy |
| Canvas views | None | Architecture, hardware map, gRPC map, clones |
| ChromaDB collections | 1 flat | 5 typed (repo_code, trm_prose, trm_code, trm_tables, trm_notes) |
| Line traceability | VSCode links (basic) | Line → commit SHA → author → TRM page |

## Hardware Components (from TRM)

These are the canonical hardware nodes that code symbols bind to:

| ID | Component | Description |
|----|-----------|-------------|
| `TRM__Snapdragon_212` | Qualcomm APQ8009w | Primary quad-core, runs Yocto Linux + CozmoEngine |
| `TRM__STM32_Body_Board` | STM32F427 | Real-time safety CPU, PID loops, cliff sensors, IK |
| `TRM__QCA9377_WiFi_BLE` | Qualcomm QCA9377 | 802.11 b/g/n WiFi + Bluetooth LE |
| `TRM__Camera_OV7740` | OmniVision OV7740 | VGA CMOS, facial recognition, motion tracking |
| `TRM__Mic_Array` | 4-mic beamforming | Wake word, direction-of-arrival, voice streaming |
| `TRM__Laser_ToF_VL53L0X` | STMicro VL53L0X | Time-of-flight ranging, obstacle avoidance |
| `TRM__Motors_Wheels_Head_Lift` | DC brushed + encoders | Locomotion + emotive articulation |
| `TRM__Face_Display_IPS` | 184×96 IPS TFT LCD | Eye rendering, emotive display |

## Output Destinations

| Output | Location | Used By |
|--------|----------|---------|
| New Obsidian Vault | `/Users/lab/research/VectorMap/data/Vector_Obsidian_Vault_V2/` | VectorMap indexer |
| New ChromaDB | `/Users/lab/research/VectorMap/data/chroma_db_v2/` | VectorMap RAG |
| Pipeline SQLite | `/Users/lab/research/VaultForge/pipeline_output/pipeline_metadata.db` | Analytics + debug |
| BM25 Index | `/Users/lab/research/VaultForge/pipeline_output/bm25_index.pkl` | Hybrid search |
| TRM Figures | `/Users/lab/research/VaultForge/pipeline_output/trm_figures/` | Vault figure notes |
| Symbol Tables | `/Users/lab/research/VaultForge/pipeline_output/symbol_tables/` | Cross-linking |
| Chunks JSONL | `/Users/lab/research/VaultForge/pipeline_output/chunks/all_chunks.jsonl` | ChromaDB import |
| Pipeline Log | `/Users/lab/research/VaultForge/pipeline_output/logs/pipeline.log` | Debugging |

## VectorMap Integration

After the pipeline runs, update VectorMap to use the new vault:

1. Edit `/Users/lab/research/VectorMap/src/langgraph_agent.py`:
   - Change `VAULT_PATH` to `Vector_Obsidian_Vault_V2`
   - Change `DB_PATH` to `chroma_db_v2`

2. Restart VectorMap: `cd /Users/lab/research/VectorMap && ./start.sh`

3. Run indexer from dashboard (Page 1 → UPDATE VAULT CACHE)

4. Verify: chunk count should be significantly higher than the old 41,363
