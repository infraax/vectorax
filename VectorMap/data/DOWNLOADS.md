# ChromaDB Data — Not Included in Repository

The ChromaDB vector store is **not included in this repository** due to file size constraints:

- `chroma_db_v2/chroma.sqlite3` — 304 MB (exceeds GitHub's 100 MB file limit)
- `chroma_db_v2/data_level0.bin` — 112 MB (HNSW embedding index)
- **Total:** ~420 MB across 5 collections, 34,507 chunks

## What's in the database

| Collection | Chunks | Content |
| --- | --- | --- |
| `repo_code` | 33,773 | All 13 Vector robot source repos |
| `trm_notes` | 74 | VectorTRM PDF — text notes |
| `trm_code` | 250 | VectorTRM PDF — code blocks |
| `trm_tables` | 180 | VectorTRM PDF — tables |
| `trm_prose` | 230 | VectorTRM PDF — prose sections |
| **Total** | **34,507** | nomic-embed-text 768D embeddings |

## Rebuild from scratch

```bash
# 1. Clone source repositories (816 MB — takes a few minutes)
bash VaultForge/sources/clone_repos.sh

# 2. Ensure Ollama is running with the embedding model
ollama serve &
ollama pull nomic-embed-text

# 3. Also pull the chat model used by VectorMap
ollama pull qwen2.5-coder:7b

# 4. Run the VaultForge pipeline (builds all 5 ChromaDB collections)
#    Runtime: ~30-60 min depending on hardware
cd VaultForge
python pipeline/db_writer.py

# 5. Launch VectorMap
cd ../VectorMap
bash start.sh
```

> The pipeline is idempotent — safe to re-run to add new repositories.
> Add new repo URLs to `VaultForge/sources/REPOS.yaml` and `clone_repos.sh`, then re-run.
