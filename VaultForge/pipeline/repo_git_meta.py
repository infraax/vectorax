#!/usr/bin/env python3
"""
Repository Git Metadata Collector — Phase 2.1
Collects per-repo and per-file git metadata: commits, authors, hotness.
Output: pipeline_output/symbol_tables/{repo}_git_meta.json
"""
import json
import logging
import sys
import os
from pathlib import Path
from datetime import datetime

REPOS_PATH = "/Users/lab/research/VectorMap/data/Repositories"
OUT_DIR    = "/Users/lab/research/VaultForge/pipeline_output/symbol_tables"
LOG_PATH   = "/Users/lab/research/VaultForge/pipeline_output/logs/pipeline.log"

REPO_ORDER = [
    "vector", "chipper", "vector-cloud", "vector-python-sdk",
    "vector-go-sdk", "wire-pod", "escape-pod-extension", "hugh",
    "vector-bluetooth", "dev-docs", "vector-web-setup", "vectorx", "vectorx-voiceserver"
]


def run():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(LOG_PATH, mode="a"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    log = logging.getLogger("repo_git_meta")
    log.info("=== GIT META COLLECTOR START ===")

    Path(OUT_DIR).mkdir(parents=True, exist_ok=True)

    try:
        import git
    except ImportError:
        log.error("gitpython not installed")
        sys.exit(1)

    for repo_name in REPO_ORDER:
        repo_path = os.path.join(REPOS_PATH, repo_name)
        if not os.path.isdir(repo_path):
            log.warning(f"Repo not found: {repo_name}")
            continue

        try:
            repo = git.Repo(repo_path)
            head = repo.head
            head_commit = head.commit

            meta = {
                "repo": repo_name,
                "commit_sha": head_commit.hexsha[:8],
                "commit_sha_full": head_commit.hexsha,
                "commit_date": head_commit.committed_datetime.isoformat(),
                "author": str(head_commit.author),
                "total_commits": None,  # expensive to count, skip
                "contributors": [],
                "files": {},
            }

            # Collect contributor list from last 100 commits
            contributors = set()
            try:
                for commit in list(repo.iter_commits(max_count=200)):
                    contributors.add(str(commit.author.name))
            except Exception:
                pass
            meta["contributors"] = list(contributors)

            # Per-file metadata
            file_meta = {}
            try:
                # Get all tracked files
                for item in repo.tree().traverse():
                    if item.type != "blob":
                        continue
                    rel_path = item.path

                    fmeta = {
                        "commit_sha": head_commit.hexsha[:8],
                        "last_author": "",
                        "hotness": 0,
                        "commit_date": "",
                    }

                    # Get last commit for this file (fast: just the last one)
                    try:
                        commits = list(repo.iter_commits(paths=rel_path, max_count=1))
                        if commits:
                            c = commits[0]
                            fmeta["last_author"] = str(c.author.name)
                            fmeta["commit_sha"] = c.hexsha[:8]
                            fmeta["commit_date"] = c.committed_datetime.isoformat()
                    except Exception:
                        pass

                    file_meta[rel_path] = fmeta

            except Exception as e:
                log.warning(f"{repo_name}: file meta collection failed: {e}")

            meta["files"] = file_meta
            log.info(f"{repo_name}: {len(file_meta)} files, {len(contributors)} contributors, head={meta['commit_sha']}")

            out_path = Path(OUT_DIR) / f"{repo_name}_git_meta.json"
            with open(out_path, "w") as f:
                json.dump(meta, f, indent=2)

        except Exception as e:
            log.error(f"{repo_name} git meta failed: {e}")
            # Write minimal record
            out_path = Path(OUT_DIR) / f"{repo_name}_git_meta.json"
            with open(out_path, "w") as f:
                json.dump({"repo": repo_name, "commit_sha": "unknown", "files": {}}, f)

    log.info("Git metadata collection complete")
    print(f"\n=== GIT META COMPLETE ===")
    files = list(Path(OUT_DIR).glob("*_git_meta.json"))
    print(f"Repos processed: {len(files)}")


if __name__ == "__main__":
    run()
