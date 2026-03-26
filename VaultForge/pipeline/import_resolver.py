#!/usr/bin/env python3
"""
Import Resolver — Phase 2.3
After all repos are parsed, resolves import statements to other indexed repos.
Output: pipeline_output/symbol_tables/cross_repo_imports.json
"""
import json
import logging
import sys
import os
import re
from pathlib import Path

OUT_DIR   = "/Users/lab/research/VaultForge/pipeline_output/symbol_tables"
REPOS_PATH = "/Users/lab/research/VectorMap/data/Repositories"
LOG_PATH  = "/Users/lab/research/VaultForge/pipeline_output/logs/pipeline.log"
OUT_FILE  = f"{OUT_DIR}/cross_repo_imports.json"

REPO_ORDER = [
    "vector", "chipper", "vector-cloud", "vector-python-sdk",
    "vector-go-sdk", "wire-pod", "escape-pod-extension", "hugh",
    "vector-bluetooth", "dev-docs", "vector-web-setup", "vectorx", "vectorx-voiceserver"
]


def read_go_modules():
    """Read go.mod files to get module paths for each Go repo."""
    go_modules = {}  # module_path -> repo_name
    for repo in REPO_ORDER:
        mod_path = os.path.join(REPOS_PATH, repo, "go.mod")
        if os.path.exists(mod_path):
            try:
                content = open(mod_path).read()
                m = re.search(r"^module\s+(\S+)", content, re.MULTILINE)
                if m:
                    go_modules[m.group(1)] = repo
            except Exception:
                pass
    return go_modules


def read_python_packages():
    """Read setup.py/setup.cfg/pyproject.toml to get Python package names."""
    py_packages = {}  # package_name -> repo_name
    for repo in REPO_ORDER:
        repo_path = os.path.join(REPOS_PATH, repo)
        # Check common package names
        for fname in ["setup.py", "setup.cfg", "pyproject.toml"]:
            fpath = os.path.join(repo_path, fname)
            if os.path.exists(fpath):
                try:
                    content = open(fpath).read()
                    m = re.search(r"name\s*=\s*['\"]([^'\"]+)['\"]", content)
                    if m:
                        pkg_name = m.group(1).replace("-", "_").lower()
                        py_packages[pkg_name] = repo
                except Exception:
                    pass
        # Also add common directory-level package names
        for item in os.listdir(repo_path):
            if os.path.isdir(os.path.join(repo_path, item)) and \
               os.path.exists(os.path.join(repo_path, item, "__init__.py")):
                py_packages[item.lower()] = repo
    return py_packages


def scan_python_imports(code, filepath, repo_name, py_packages):
    """Extract import statements from Python code and resolve them."""
    imports = []
    lines = code.split("\n")
    for i, line in enumerate(lines):
        line = line.strip()
        # Handle "import X" and "from X import Y"
        m = re.match(r"^import\s+([\w.]+)", line)
        if m:
            module = m.group(1)
            top_pkg = module.split(".")[0].lower()
            target_repo = py_packages.get(top_pkg)
            imports.append({
                "source_repo": repo_name,
                "source_file": filepath,
                "line": i + 1,
                "import_statement": line,
                "import_module": module,
                "resolves_to_repo": target_repo,
                "resolves_to_file": None,
                "is_cross_repo": target_repo is not None and target_repo != repo_name,
                "confidence": 0.8 if target_repo else 0.0,
            })
        m2 = re.match(r"^from\s+([\w.]+)\s+import", line)
        if m2:
            module = m2.group(1)
            top_pkg = module.split(".")[0].lower()
            target_repo = py_packages.get(top_pkg)
            if not target_repo and module.startswith("."):
                target_repo = repo_name  # relative import within same repo
            imports.append({
                "source_repo": repo_name,
                "source_file": filepath,
                "line": i + 1,
                "import_statement": line,
                "import_module": module,
                "resolves_to_repo": target_repo,
                "resolves_to_file": None,
                "is_cross_repo": target_repo is not None and target_repo != repo_name,
                "confidence": 0.9 if target_repo else 0.0,
            })
    return imports


def scan_go_imports(code, filepath, repo_name, go_modules):
    """Extract import statements from Go code and resolve them."""
    imports = []
    # Find import blocks and single imports
    import_lines = []
    in_block = False
    for i, line in enumerate(code.split("\n")):
        stripped = line.strip()
        if stripped == "import (":
            in_block = True
        elif in_block and stripped == ")":
            in_block = False
        elif in_block:
            m = re.match(r'^\s*(?:\w+\s+)?"([^"]+)"', line)
            if m:
                import_lines.append((i + 1, m.group(1)))
        else:
            m = re.match(r'^import\s+"([^"]+)"', stripped)
            if m:
                import_lines.append((i + 1, m.group(1)))

    for lineno, import_path in import_lines:
        # Check if this import resolves to one of our repos
        target_repo = None
        confidence = 0.0
        for module_path, repo in go_modules.items():
            if import_path.startswith(module_path):
                target_repo = repo
                confidence = 0.95
                break
        # Also check for chipper specifically (commonly imported as digital-dream-labs)
        if not target_repo:
            for keyword, repo in [("chipper", "chipper"), ("wire-pod", "wire-pod"), ("vector-cloud", "vector-cloud")]:
                if keyword in import_path:
                    target_repo = repo
                    confidence = 0.7
                    break

        imports.append({
            "source_repo": repo_name,
            "source_file": filepath,
            "line": lineno,
            "import_statement": f'import "{import_path}"',
            "import_module": import_path,
            "resolves_to_repo": target_repo,
            "resolves_to_file": None,
            "is_cross_repo": target_repo is not None and target_repo != repo_name,
            "confidence": confidence,
        })
    return imports


def run():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(LOG_PATH, mode="a"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    log = logging.getLogger("import_resolver")
    log.info("=== IMPORT RESOLVER START ===")

    go_modules = read_go_modules()
    py_packages = read_python_packages()
    log.info(f"Go modules: {go_modules}")
    log.info(f"Python packages: {list(py_packages.keys())}")

    all_imports = []
    cross_repo_imports = []

    for repo_name in REPO_ORDER:
        repo_path = os.path.join(REPOS_PATH, repo_name)
        if not os.path.isdir(repo_path):
            continue

        try:
            for root, dirs, files in os.walk(repo_path):
                dirs[:] = [d for d in dirs if d not in {".git", "vendor", "node_modules", "__pycache__"}]
                for fname in files:
                    ext = Path(fname).suffix.lower()
                    if ext not in (".py", ".go"):
                        continue

                    fpath = os.path.join(root, fname)
                    rel = os.path.relpath(fpath, repo_path)
                    try:
                        code = open(fpath, encoding="utf-8", errors="replace").read()
                        if ext == ".py":
                            imports = scan_python_imports(code, rel, repo_name, py_packages)
                        else:
                            imports = scan_go_imports(code, rel, repo_name, go_modules)
                        all_imports.extend(imports)
                        cross_repo_imports.extend(i for i in imports if i.get("is_cross_repo"))
                    except Exception as e:
                        log.warning(f"{fpath}: {e}")
        except Exception as e:
            log.error(f"Repo {repo_name}: {e}")

    # Write all cross-repo imports
    with open(OUT_FILE, "w") as f:
        json.dump(cross_repo_imports, f, indent=2)

    # Summary
    log.info(f"Total imports scanned: {len(all_imports)}")
    log.info(f"Cross-repo imports: {len(cross_repo_imports)}")

    # Print cross-repo import pairs
    pairs = {}
    for imp in cross_repo_imports:
        key = f"{imp['source_repo']} → {imp['resolves_to_repo']}"
        pairs[key] = pairs.get(key, 0) + 1

    print(f"\n=== IMPORT RESOLVER COMPLETE ===")
    print(f"Cross-repo imports: {len(cross_repo_imports)}")
    for pair, count in sorted(pairs.items(), key=lambda x: -x[1])[:20]:
        print(f"  {pair}: {count}")


if __name__ == "__main__":
    run()
