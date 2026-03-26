#!/usr/bin/env python3
"""
Repository AST Parser — Phase 2.2
Uses tree-sitter (new API) to extract symbols from all supported languages.
Falls back to regex for proto3.
Output: pipeline_output/symbol_tables/{repo}_symbols.json per repo.
"""
import json
import logging
import sys
import os
import re
from pathlib import Path
from tree_sitter import Language, Parser

# Lazy-load language parsers
_parsers = {}
_parser_error = {}

def _get_parser(lang):
    if lang in _parsers:
        return _parsers[lang]
    if lang in _parser_error:
        return None
    try:
        if lang == "python":
            import tree_sitter_python as m
        elif lang == "go":
            import tree_sitter_go as m
        elif lang == "c":
            import tree_sitter_c as m
        elif lang == "cpp":
            import tree_sitter_cpp as m
        elif lang == "javascript":
            import tree_sitter_javascript as m
        elif lang == "typescript":
            import tree_sitter_typescript
            _parsers[lang] = Parser(Language(tree_sitter_typescript.language_typescript()))
            return _parsers[lang]
        else:
            _parser_error[lang] = True
            return None
        _parsers[lang] = Parser(Language(m.language()))
        return _parsers[lang]
    except Exception as e:
        _parser_error[lang] = str(e)
        return None

# ── Config ────────────────────────────────────────────────────────────────────
REPOS_PATH = "/Users/lab/research/VectorMap/data/Repositories"
OUT_DIR    = "/Users/lab/research/VaultForge/pipeline_output/symbol_tables"
LOG_PATH   = "/Users/lab/research/VaultForge/pipeline_output/logs/pipeline.log"

EXTENSION_MAP = {
    ".py":   "python",
    ".go":   "go",
    ".c":    "c",
    ".h":    "c",
    ".cpp":  "cpp",
    ".hpp":  "cpp",
    ".js":   "javascript",
    ".mjs":  "javascript",
    ".ts":   "typescript",
    ".tsx":  "typescript",
    ".proto":"proto",
}

SKIP_DIRS = {".git", "vendor", "node_modules", "build", "dist", "__pycache__",
             ".cache", ".idea", ".vscode", "testdata", "generated", "gen"}

SKIP_PATTERNS = [
    r".*_test\.go$", r"test_.*\.py$", r".*_pb2\.py$",
    r".*_pb2_grpc\.py$", r".*\.pb\.go$",
]

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

REPO_ORDER = [
    "vector", "chipper", "vector-cloud", "vector-python-sdk",
    "vector-go-sdk", "wire-pod", "escape-pod-extension", "hugh",
    "vector-bluetooth", "dev-docs", "vector-web-setup", "vectorx", "vectorx-voiceserver"
]

HW_KEYWORDS = {
    "TRM__Snapdragon_212":          ["snapdragon", "apq8009", "qualcomm", "yocto", "cozmongine"],
    "TRM__STM32_Body_Board":        ["stm32", "body_board", "bodyboard", "spi", "pid", "encoder", "cliff", "gpio", "pwm", "backpack"],
    "TRM__QCA9377_WiFi_BLE":        ["qca9377", "wifi", "bluetooth", "ble", "wlan", "onboard"],
    "TRM__Camera_OV7740":           ["ov7740", "camera", "vision", "capture", "face_image", "vga", "cmos"],
    "TRM__Mic_Array":               ["microphone", "mic_array", "beamform", "wake_word", "audio_stream"],
    "TRM__Laser_ToF_VL53L0X":      ["vl53l0x", "tof", "laser_range", "lidar", "obstacle_detect", "cliff_sensor"],
    "TRM__Motors_Wheels_Head_Lift": ["motor_ctrl", "wheel_speed", "drive_straight", "head_motor", "lift_motor", "encoder_count", "pwm_duty", "pid_loop"],
    "TRM__Face_Display_IPS":        ["set_eye_color", "eye_color", "face_display", "lcd_draw", "ips_", "eye_render", "animate_face"],
}

# ── Helpers ───────────────────────────────────────────────────────────────────
def detect_hardware(text):
    tl = text.lower()
    return [hw_id for hw_id, kws in HW_KEYWORDS.items() if any(k in tl for k in kws)]


def should_skip(fname):
    for p in SKIP_PATTERNS:
        if re.match(p, fname):
            return True
    return False


_enc = None
def count_tokens(text):
    global _enc
    try:
        if _enc is None:
            import tiktoken
            _enc = tiktoken.get_encoding("cl100k_base")
        return len(_enc.encode(text))
    except Exception:
        return max(1, len(text.split()))


def get_source(code_bytes, start_line, end_line):
    try:
        lines = code_bytes.decode("utf-8", errors="replace").split("\n")
        return "\n".join(lines[start_line:end_line + 1])
    except Exception:
        return ""


def get_node_text(node):
    try:
        return node.text.decode("utf-8", errors="replace") if node and node.text else ""
    except Exception:
        return ""


# ── Python parser ─────────────────────────────────────────────────────────────
def parse_python(code_bytes, filepath, repo, git_info):
    parser = _get_parser("python")
    if not parser:
        return []
    try:
        tree = parser.parse(code_bytes)
        root = tree.root_node
        symbols = []

        def get_docstring(body_node):
            if not body_node or not body_node.children:
                return ""
            try:
                first = body_node.children[0]
                if first.type == "expression_statement" and first.children:
                    s = first.children[0]
                    if s.type == "string":
                        return get_node_text(s).strip("\"'` \n\r")
            except Exception:
                pass
            return ""

        def walk(node, class_ctx=None):
            if node.type == "class_definition":
                name_node = node.child_by_field_name("name")
                cls_name = get_node_text(name_node) or "?"
                body = node.child_by_field_name("body")
                doc = get_docstring(body)
                source = get_source(code_bytes, node.start_point[0], node.end_point[0])
                hw = detect_hardware(cls_name + " " + doc + " " + source[:300])
                symbols.append({
                    "type": "class", "name": cls_name, "class_context": "",
                    "qualified_name": f"{repo}/{filepath}/{cls_name}",
                    "repo": repo, "file": filepath, "language": "python",
                    "line_start": node.start_point[0] + 1,
                    "line_end": node.end_point[0] + 1,
                    "signature": f"class {cls_name}",
                    "docstring": doc, "source": source,
                    "token_count": count_tokens(source),
                    "hardware_binds": hw, **git_info,
                })
                for child in node.children:
                    walk(child, class_ctx=cls_name)

            elif node.type in ("function_definition", "decorated_definition"):
                fn = node if node.type == "function_definition" else node.child_by_field_name("definition")
                if not fn:
                    for c in node.children:
                        walk(c, class_ctx=class_ctx)
                    return
                name_node = fn.child_by_field_name("name")
                fn_name = get_node_text(name_node) or "?"
                body = fn.child_by_field_name("body")
                doc = get_docstring(body)
                source = get_source(code_bytes, fn.start_point[0], fn.end_point[0])
                # Build signature from first 3 lines
                lines = source.split("\n")
                sig_lines = []
                for ln in lines[:5]:
                    sig_lines.append(ln)
                    if ":" in ln and not ln.strip().startswith("#"):
                        break
                sig = " ".join(sig_lines).strip()
                hw = detect_hardware(fn_name + " " + doc + " " + source[:500])
                symbols.append({
                    "type": "method" if class_ctx else "function",
                    "name": fn_name, "class_context": class_ctx or "",
                    "qualified_name": f"{repo}/{filepath}/{class_ctx + '.' if class_ctx else ''}{fn_name}",
                    "repo": repo, "file": filepath, "language": "python",
                    "line_start": fn.start_point[0] + 1,
                    "line_end": fn.end_point[0] + 1,
                    "signature": sig, "docstring": doc, "source": source,
                    "token_count": count_tokens(source),
                    "hardware_binds": hw, **git_info,
                })
            else:
                for c in node.children:
                    walk(c, class_ctx=class_ctx)

        walk(root)
        return symbols
    except Exception:
        return []


# ── Go parser ─────────────────────────────────────────────────────────────────
def parse_go(code_bytes, filepath, repo, git_info):
    parser = _get_parser("go")
    if not parser:
        return []
    try:
        tree = parser.parse(code_bytes)
        root = tree.root_node
        symbols = []
        lines = code_bytes.decode("utf-8", errors="replace").split("\n")

        def get_comment_above(node):
            start = node.start_point[0]
            clines = []
            for i in range(start - 1, max(-1, start - 15), -1):
                ln = lines[i].strip()
                if ln.startswith("//"):
                    clines.insert(0, ln[2:].strip())
                elif ln == "":
                    continue
                else:
                    break
            return " ".join(clines)

        def walk(node):
            if node.type == "function_declaration":
                name_node = node.child_by_field_name("name")
                fn_name = get_node_text(name_node) or "?"
                source = get_source(code_bytes, node.start_point[0], node.end_point[0])
                doc = get_comment_above(node)
                hw = detect_hardware(fn_name + " " + doc + " " + source[:300])
                symbols.append({
                    "type": "function", "name": fn_name, "class_context": "",
                    "qualified_name": f"{repo}/{filepath}/{fn_name}",
                    "repo": repo, "file": filepath, "language": "go",
                    "line_start": node.start_point[0] + 1,
                    "line_end": node.end_point[0] + 1,
                    "docstring": doc, "source": source,
                    "token_count": count_tokens(source),
                    "hardware_binds": hw, **git_info,
                })

            elif node.type == "method_declaration":
                name_node = node.child_by_field_name("name")
                receiver = node.child_by_field_name("receiver")
                fn_name = get_node_text(name_node) or "?"
                recv = get_node_text(receiver) or ""
                source = get_source(code_bytes, node.start_point[0], node.end_point[0])
                doc = get_comment_above(node)
                hw = detect_hardware(fn_name + " " + recv + " " + doc)
                symbols.append({
                    "type": "method", "name": fn_name, "class_context": recv,
                    "qualified_name": f"{repo}/{filepath}/{recv}/{fn_name}",
                    "repo": repo, "file": filepath, "language": "go",
                    "line_start": node.start_point[0] + 1,
                    "line_end": node.end_point[0] + 1,
                    "docstring": doc, "source": source,
                    "token_count": count_tokens(source),
                    "hardware_binds": hw, **git_info,
                })

            elif node.type == "type_declaration":
                for child in node.children:
                    if child.type == "type_spec":
                        name_node = child.child_by_field_name("name")
                        sym_name = get_node_text(name_node) or "?"
                        type_val = child.child_by_field_name("type")
                        sym_type = "struct" if (type_val and "struct" in type_val.type) else "type"
                        source = get_source(code_bytes, node.start_point[0], node.end_point[0])
                        doc = get_comment_above(node)
                        hw = detect_hardware(sym_name + " " + doc)
                        symbols.append({
                            "type": sym_type, "name": sym_name, "class_context": "",
                            "qualified_name": f"{repo}/{filepath}/{sym_name}",
                            "repo": repo, "file": filepath, "language": "go",
                            "line_start": node.start_point[0] + 1,
                            "line_end": node.end_point[0] + 1,
                            "docstring": doc, "source": source,
                            "token_count": count_tokens(source),
                            "hardware_binds": hw, **git_info,
                        })

            for c in node.children:
                walk(c)

        walk(root)
        return symbols
    except Exception:
        return []


# ── C/C++ parser ──────────────────────────────────────────────────────────────
def parse_c(code_bytes, filepath, repo, git_info, lang="c"):
    parser = _get_parser(lang)
    if not parser:
        return []
    try:
        tree = parser.parse(code_bytes)
        root = tree.root_node
        symbols = []

        def walk(node):
            if node.type == "function_definition":
                # Find declarator → function_declarator → identifier
                declarator = node.child_by_field_name("declarator")
                fn_name = None
                if declarator:
                    # Walk into nested declarators
                    def find_name(n):
                        if n.type == "identifier":
                            return get_node_text(n)
                        for c in n.children:
                            r = find_name(c)
                            if r:
                                return r
                        return None
                    fn_name = find_name(declarator)

                if fn_name:
                    source = get_source(code_bytes, node.start_point[0], node.end_point[0])
                    hw = detect_hardware(fn_name + " " + source[:300])
                    symbols.append({
                        "type": "function", "name": fn_name, "class_context": "",
                        "qualified_name": f"{repo}/{filepath}/{fn_name}",
                        "repo": repo, "file": filepath, "language": lang,
                        "line_start": node.start_point[0] + 1,
                        "line_end": node.end_point[0] + 1,
                        "source": source, "token_count": count_tokens(source),
                        "hardware_binds": hw, **git_info,
                    })

            elif node.type == "struct_specifier":
                name_node = node.child_by_field_name("name")
                if name_node:
                    sym_name = get_node_text(name_node)
                    source = get_source(code_bytes, node.start_point[0], node.end_point[0])
                    hw = detect_hardware(sym_name + " " + source[:200])
                    symbols.append({
                        "type": "struct", "name": sym_name, "class_context": "",
                        "qualified_name": f"{repo}/{filepath}/{sym_name}",
                        "repo": repo, "file": filepath, "language": lang,
                        "line_start": node.start_point[0] + 1,
                        "line_end": node.end_point[0] + 1,
                        "source": source, "token_count": count_tokens(source),
                        "hardware_binds": hw, **git_info,
                    })

            for c in node.children:
                walk(c)

        walk(root)
        return symbols
    except Exception:
        return []


# ── JavaScript parser ─────────────────────────────────────────────────────────
def parse_js(code_bytes, filepath, repo, git_info, lang="javascript"):
    parser = _get_parser(lang)
    if not parser:
        return []
    try:
        tree = parser.parse(code_bytes)
        root = tree.root_node
        symbols = []

        def walk(node, class_ctx=None):
            if node.type in ("function_declaration", "generator_function_declaration"):
                name_node = node.child_by_field_name("name")
                fn_name = get_node_text(name_node) or "?"
                source = get_source(code_bytes, node.start_point[0], node.end_point[0])
                symbols.append({
                    "type": "method" if class_ctx else "function",
                    "name": fn_name, "class_context": class_ctx or "",
                    "repo": repo, "file": filepath, "language": lang,
                    "line_start": node.start_point[0] + 1,
                    "line_end": node.end_point[0] + 1,
                    "source": source, "token_count": count_tokens(source),
                    "hardware_binds": [], **git_info,
                })
            elif node.type == "class_declaration":
                name_node = node.child_by_field_name("name")
                cls_name = get_node_text(name_node) or "?"
                source = get_source(code_bytes, node.start_point[0], node.end_point[0])
                symbols.append({
                    "type": "class", "name": cls_name, "class_context": "",
                    "repo": repo, "file": filepath, "language": lang,
                    "line_start": node.start_point[0] + 1,
                    "line_end": node.end_point[0] + 1,
                    "source": source, "token_count": count_tokens(source),
                    "hardware_binds": [], **git_info,
                })
                for c in node.children:
                    walk(c, class_ctx=cls_name)
                return
            for c in node.children:
                walk(c, class_ctx=class_ctx)

        walk(root)
        return symbols
    except Exception:
        return []


# ── Proto regex parser ────────────────────────────────────────────────────────
def parse_proto(code_bytes, filepath, repo, git_info):
    """Regex-based proto3 parser (no tree-sitter available for proto3 in new API)."""
    try:
        code = code_bytes.decode("utf-8", errors="replace")
        lines = code.split("\n")
        symbols = []

        patterns = [
            (r"^message\s+(\w+)\s*\{", "struct"),
            (r"^service\s+(\w+)\s*\{", "interface"),
            (r"^\s+rpc\s+(\w+)\s*\(", "function"),
            (r"^enum\s+(\w+)\s*\{", "enum"),
        ]

        for i, line in enumerate(lines):
            for pattern, sym_type in patterns:
                m = re.match(pattern, line)
                if m:
                    name = m.group(1)
                    # Estimate end: find matching closing brace
                    end_line = i
                    if "{" in line and sym_type != "function":
                        depth = line.count("{") - line.count("}")
                        for j in range(i + 1, min(i + 200, len(lines))):
                            depth += lines[j].count("{") - lines[j].count("}")
                            if depth <= 0:
                                end_line = j
                                break
                    source = "\n".join(lines[i:end_line + 1])
                    symbols.append({
                        "type": sym_type, "name": name, "class_context": "",
                        "qualified_name": f"{repo}/{filepath}/{name}",
                        "repo": repo, "file": filepath, "language": "protobuf",
                        "line_start": i + 1, "line_end": end_line + 1,
                        "source": source, "token_count": count_tokens(source),
                        "hardware_binds": [], **git_info,
                    })
        return symbols
    except Exception:
        return []


# ── File dispatcher ───────────────────────────────────────────────────────────
def process_file(fpath, rel_path, repo_name, git_meta_files):
    ext = Path(fpath).suffix.lower()
    lang = EXTENSION_MAP.get(ext)
    if not lang:
        return []
    if should_skip(os.path.basename(fpath)):
        return []

    try:
        size = os.path.getsize(fpath)
        if size > MAX_FILE_SIZE or size == 0:
            return []
        code = open(fpath, "rb").read()
    except Exception:
        return []

    fmeta = git_meta_files.get(rel_path, {})
    git_info = {
        "commit_sha": fmeta.get("commit_sha", "unknown"),
        "last_author": fmeta.get("last_author", ""),
        "commit_date": fmeta.get("commit_date", ""),
    }

    if lang == "python":
        return parse_python(code, rel_path, repo_name, git_info)
    elif lang == "go":
        return parse_go(code, rel_path, repo_name, git_info)
    elif lang in ("c", "cpp"):
        return parse_c(code, rel_path, repo_name, git_info, lang)
    elif lang in ("javascript", "typescript"):
        return parse_js(code, rel_path, repo_name, git_info, lang)
    elif lang == "proto":
        return parse_proto(code, rel_path, repo_name, git_info)
    return []


def process_repo(repo_name, log):
    repo_path = os.path.join(REPOS_PATH, repo_name)
    all_symbols = []
    file_count = 0
    failed = []

    gm_path = Path(OUT_DIR) / f"{repo_name}_git_meta.json"
    git_meta_files = {}
    if gm_path.exists():
        with open(gm_path) as f:
            gm = json.load(f)
            git_meta_files = gm.get("files", {})

    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fname in files:
            fpath = os.path.join(root, fname)
            rel = os.path.relpath(fpath, repo_path)
            ext = Path(fname).suffix.lower()
            if ext not in EXTENSION_MAP:
                continue
            try:
                syms = process_file(fpath, rel, repo_name, git_meta_files)
                all_symbols.extend(syms)
                file_count += 1
            except Exception as e:
                log.warning(f"File failed {fpath}: {e}")
                failed.append({"file": fpath, "error": str(e)})

    out_path = Path(OUT_DIR) / f"{repo_name}_symbols.json"
    with open(out_path, "w") as f:
        json.dump(all_symbols, f, indent=2)

    log.info(f"{repo_name}: {len(all_symbols)} symbols from {file_count} files (failed: {len(failed)})")
    return all_symbols, failed


def run():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(LOG_PATH, mode="a"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    log = logging.getLogger("repo_parser")
    log.info("=== REPO PARSER START (new tree-sitter API) ===")

    Path(OUT_DIR).mkdir(parents=True, exist_ok=True)

    total_symbols = 0
    all_failed = []

    for repo_name in REPO_ORDER:
        repo_path = os.path.join(REPOS_PATH, repo_name)
        if not os.path.isdir(repo_path):
            log.warning(f"Repo not found: {repo_name}")
            continue
        try:
            syms, failed = process_repo(repo_name, log)
            total_symbols += len(syms)
            all_failed.extend(failed)
        except Exception as e:
            log.error(f"Repo {repo_name} failed: {e}", exc_info=True)

    failed_log = Path("/Users/lab/research/VaultForge/pipeline_output/logs/failed_files_parser.json")
    with open(failed_log, "w") as f:
        json.dump(all_failed, f, indent=2)

    log.info(f"Total symbols: {total_symbols}, failures: {len(all_failed)}")
    print(f"\n=== REPO PARSE COMPLETE ===")
    print(f"Total symbols: {total_symbols}")


if __name__ == "__main__":
    run()
