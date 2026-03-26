#!/usr/bin/env python3
"""
Code Similarity Detector — Phase 2.5
Uses datasketch MinHash LSH to detect clone/fork relationships between repos.
Output: pipeline_output/clone_pairs/similarity_pairs.json
"""
import json
import logging
import sys
import re
from pathlib import Path

SYMBOL_TABLES_DIR = "/Users/lab/research/VaultForge/pipeline_output/symbol_tables"
OUT_FILE = "/Users/lab/research/VaultForge/pipeline_output/clone_pairs/similarity_pairs.json"
LOG_PATH = "/Users/lab/research/VaultForge/pipeline_output/logs/pipeline.log"

REPO_ORDER = [
    "vector", "chipper", "vector-cloud", "vector-python-sdk",
    "vector-go-sdk", "wire-pod", "escape-pod-extension", "hugh",
    "vector-bluetooth", "dev-docs", "vector-web-setup", "vectorx", "vectorx-voiceserver"
]

LSH_THRESHOLD = 0.60
NUM_PERM = 128
MIN_TOKENS = 20

THRESHOLDS = {
    "exact_copy":             0.95,
    "near_identical_fork":    0.80,
    "fork_with_modifications": 0.60,
}


def tokenize(source):
    """Tokenize source code into a set of tokens for MinHash."""
    # Normalize: lowercase, split on non-alphanumeric
    tokens = set(re.findall(r"[a-z0-9_]{2,}", source.lower()))
    # Remove very common tokens that don't distinguish code
    stop = {"self", "return", "true", "false", "nil", "none", "const", "var", "let", "the", "and", "for"}
    return tokens - stop


def classify_similarity(score):
    if score >= THRESHOLDS["exact_copy"]:
        return "exact_copy"
    elif score >= THRESHOLDS["near_identical_fork"]:
        return "near_identical_fork"
    elif score >= THRESHOLDS["fork_with_modifications"]:
        return "fork_with_modifications"
    return "different"


def run():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(LOG_PATH, mode="a"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    log = logging.getLogger("similarity_detector")
    log.info("=== SIMILARITY DETECTOR START ===")

    from datasketch import MinHash, MinHashLSH

    Path(OUT_FILE).parent.mkdir(parents=True, exist_ok=True)

    # Load symbols with source code
    all_functions = []
    for repo in REPO_ORDER:
        sym_path = Path(SYMBOL_TABLES_DIR) / f"{repo}_symbols.json"
        if not sym_path.exists():
            continue
        try:
            symbols = json.load(open(sym_path))
            for sym in symbols:
                if sym.get("type") not in ("function", "method", "struct", "type", "class"):
                    continue
                source = sym.get("source", "")
                tokens = count_tokens_approx(source)
                if tokens < 3:  # very low threshold to catch small structs
                    continue
                all_functions.append({
                    "repo": sym.get("repo"),
                    "file": sym.get("file"),
                    "name": sym.get("name"),
                    "type": sym.get("type"),
                    "line_start": sym.get("line_start"),
                    "source": source,
                    "language": sym.get("language"),
                })
        except Exception as e:
            log.warning(f"Load {repo}: {e}")

    log.info(f"Loaded {len(all_functions)} functions for similarity analysis")

    # Build MinHash signatures
    lsh = MinHashLSH(threshold=LSH_THRESHOLD, num_perm=NUM_PERM)
    minhashes = []

    for i, fn in enumerate(all_functions):
        try:
            tokens = tokenize(fn["source"])
            if len(tokens) < 5:
                continue
            m = MinHash(num_perm=NUM_PERM)
            for token in tokens:
                m.update(token.encode("utf-8"))
            key = f"fn_{i}"
            lsh.insert(key, m)
            minhashes.append((key, m, fn))
        except Exception as e:
            log.warning(f"MinHash {i}: {e}")
            continue

    log.info(f"Built {len(minhashes)} MinHash signatures")

    # Query for similar pairs (only cross-repo)
    pairs = []
    seen_pairs = set()
    key_to_idx = {key: (m, fn) for key, m, fn in minhashes}

    for key, m, fn in minhashes:
        try:
            candidates = lsh.query(m)
            for cand_key in candidates:
                if cand_key == key:
                    continue
                _, cand_fn = key_to_idx[cand_key]

                # Only care about cross-repo pairs
                if fn["repo"] == cand_fn["repo"]:
                    continue

                # Create a canonical pair key
                pair_key = tuple(sorted([key, cand_key]))
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)

                # Compute exact Jaccard similarity
                tokens_a = tokenize(fn["source"])
                tokens_b = tokenize(cand_fn["source"])
                union = len(tokens_a | tokens_b)
                if union == 0:
                    continue
                exact_sim = len(tokens_a & tokens_b) / union

                if exact_sim < LSH_THRESHOLD:
                    continue

                relationship = classify_similarity(exact_sim)

                pairs.append({
                    "repo_a": fn["repo"],
                    "file_a": fn["file"],
                    "symbol_a": fn["name"],
                    "language_a": fn["language"],
                    "line_start_a": fn["line_start"],
                    "repo_b": cand_fn["repo"],
                    "file_b": cand_fn["file"],
                    "symbol_b": cand_fn["name"],
                    "language_b": cand_fn["language"],
                    "line_start_b": cand_fn["line_start"],
                    "similarity_token": round(exact_sim, 3),
                    "relationship": relationship,
                    "llm_narrative": "",  # Phase 3 will fill this in
                })
        except Exception as e:
            log.warning(f"Query {key}: {e}")
            continue

    # Sort by similarity
    pairs.sort(key=lambda x: -x["similarity_token"])

    with open(OUT_FILE, "w") as f:
        json.dump(pairs, f, indent=2)

    # Count by relationship type and repo pairs
    from collections import Counter
    rel_counts = Counter(p["relationship"] for p in pairs)
    repo_pairs = Counter(f"{p['repo_a']} ↔ {p['repo_b']}" for p in pairs)

    log.info(f"Clone pairs found: {len(pairs)}")
    print(f"\n=== SIMILARITY DETECTOR COMPLETE ===")
    print(f"Clone pairs: {len(pairs)}")
    for rel, c in rel_counts.most_common():
        print(f"  {rel:30s}: {c}")
    print(f"\nTop repo pair relationships:")
    for pair, c in repo_pairs.most_common(10):
        print(f"  {pair}: {c}")


def count_tokens_approx(text):
    return len(text.split())


if __name__ == "__main__":
    run()
