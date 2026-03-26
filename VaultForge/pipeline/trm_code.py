#!/usr/bin/env python3
"""
TRM Code Snippet Extractor — Phase 1.3
Extracts code blocks from the page map and saves as structured JSON.
In this TRM, "code" blocks are Trebuchet MS 8pt register/struct definitions.
Output: pipeline_output/trm_structured/code_snippets/code_PAGE_IDX.json
"""
import json
import logging
import sys
import re
from pathlib import Path

PAGE_MAP = "/Users/lab/research/VaultForge/pipeline_output/trm_structured/page_map.json"
OUT_DIR  = "/Users/lab/research/VaultForge/pipeline_output/trm_structured/code_snippets"
LOG_PATH = "/Users/lab/research/VaultForge/pipeline_output/logs/pipeline.log"


def detect_language(text):
    if any(k in text for k in ["void ", "uint8_t", "uint32_t", "#define", "->", "typedef struct", "#include", "int32_t", "uint16_t", "int8_t"]):
        return "c"
    if any(k in text for k in ["func ", "package ", ":= ", "chan ", "goroutine"]):
        return "go"
    if any(k in text for k in ["def ", "class ", "self.", "import ", "    "]) and "=>" not in text:
        return "python"
    if any(k in text for k in ["message ", "service ", "rpc ", "repeated ", "syntax ="]):
        return "protobuf"
    if any(k in text for k in ["function ", "const ", "let ", "var ", "=>", "require("]):
        return "javascript"
    if re.match(r"^\d+\s+\d+\s+\w+", text.strip()):
        return "c_struct"
    return "unknown"


def extract_function_name(text, lang):
    first_line = text.strip().split("\n")[0].strip()
    try:
        if lang == "c":
            m = re.match(r"(?:\w[\w\s*]+\s+)(\w+)\s*\(", first_line)
            if m:
                return m.group(1)
        elif lang == "go":
            m = re.match(r"func\s+(?:\(\w+\s+\*?\w+\)\s+)?(\w+)\s*\(", first_line)
            if m:
                return m.group(1)
        elif lang == "python":
            m = re.match(r"def\s+(\w+)\s*\(", first_line)
            if m:
                return m.group(1)
    except Exception:
        pass
    return None


def extract_struct_names(text):
    """Extract C struct/type names from code blocks."""
    names = []
    for m in re.finditer(r"typedef\s+struct\s+(\w+)", text):
        names.append(m.group(1))
    for m in re.finditer(r"struct\s+(\w+)\s*\{", text):
        names.append(m.group(1))
    # Register field names (all-caps words)
    for m in re.finditer(r"\b([A-Z][A-Z_]{2,})\b", text):
        names.append(m.group(1))
    return list(set(names))[:10]  # cap at 10


def count_tokens(text):
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        return len(text.split())


def run():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(LOG_PATH, mode="a"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    log = logging.getLogger("trm_code")
    log.info("=== TRM CODE EXTRACTOR START ===")

    Path(OUT_DIR).mkdir(parents=True, exist_ok=True)

    with open(PAGE_MAP) as f:
        page_map = json.load(f)

    snippet_count = 0
    snippet_id_counter = {}

    for page_data in page_map:
        page_num = page_data["page"]
        chapter = page_data.get("chapter")
        section = page_data.get("section")
        subsection = page_data.get("subsection")
        blocks = page_data.get("blocks", [])

        # Group consecutive code blocks (they belong to the same table/struct)
        current_group = []
        current_header = None
        current_caption = None

        def flush_group():
            nonlocal snippet_count
            if not current_group:
                return
            content = "\n".join(current_group)
            if len(content.strip()) < 5:
                return

            lang = detect_language(content)
            fn = extract_function_name(content, lang)
            struct_names = extract_struct_names(content)
            tokens = count_tokens(content)

            if tokens < 3:
                return

            chapter_key = (chapter or "none").replace(" ", "_")[:20]
            ch_num = snippet_id_counter.get(page_num, 0)
            snippet_id_counter[page_num] = ch_num + 1
            snippet_id = f"C{page_num}.{ch_num + 1}"

            record = {
                "snippet_id": snippet_id,
                "chapter": chapter,
                "section": section,
                "subsection": subsection,
                "page": page_num,
                "language": lang,
                "function_name": fn,
                "struct_names": struct_names,
                "table_header": current_header,
                "caption": current_caption,
                "content": content,
                "token_count": tokens,
                "repo_links": [],
            }

            out_file = Path(OUT_DIR) / f"code_{page_num}_{ch_num + 1}.json"
            try:
                with open(out_file, "w") as f:
                    json.dump(record, f, indent=2)
                snippet_count += 1
            except Exception as e:
                log.warning(f"Failed to write snippet {snippet_id}: {e}")

        for block in blocks:
            btype = block.get("type")
            text = block.get("text", "").strip()

            if btype == "table_header":
                # Start of new table group
                flush_group()
                current_group = []
                current_header = text
                current_caption = None

            elif btype == "code":
                current_group.append(text)

            elif btype == "caption":
                current_caption = text
                flush_group()
                current_group = []
                current_header = None
                current_caption = None

            elif btype in ("section_heading", "subsection_heading", "chapter_heading"):
                # Section break — flush current group
                flush_group()
                current_group = []
                current_header = None
                current_caption = None

        # Flush any remaining group at end of page
        flush_group()

    log.info(f"Code snippets extracted: {snippet_count}")
    print(f"\n=== TRM CODE COMPLETE ===")
    print(f"Code snippets: {snippet_count}")
    print(f"Files in {OUT_DIR}: {len(list(Path(OUT_DIR).glob('*.json')))}")


if __name__ == "__main__":
    run()
