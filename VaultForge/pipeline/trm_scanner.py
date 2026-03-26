#!/usr/bin/env python3
"""
TRM Scanner — Phase 1.1
Builds a structural page map of VectorTRM.pdf using correct font rules
discovered by inspecting the actual PDF font distribution.

Font rules for THIS document:
  Garamond Bold >= 14pt     → chapter_heading
  Tahoma Bold >= 12pt       → section_heading    (numbered, e.g. "17. STORAGE SYSTEM")
  Tahoma >= 11pt            → subsection_heading (e.g. "17.1. EMR")
  Arial Bold >= 11pt        → sub_section_heading
  Trebuchet MS <= 9pt       → code (structured data, register definitions)
  Verdana Bold <= 9pt       → table_header
  Arial BoldItalic <= 9pt   → caption (Table X / Figure X)
  Arial <= 9pt              → figure_label (labels on diagram elements)
  Franklin Gothic Medium    → skip (running page header)
  Times New Roman / Calibri → prose
  developer_note prefix     → developer_note (overrides prose)
"""
import fitz
import json
import logging
import sys
import re
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────
PDF_PATH = "/Users/lab/research/Sources/VectorTRM.pdf"
OUT_PATH = "/Users/lab/research/VaultForge/pipeline_output/trm_structured/page_map.json"
LOG_PATH = "/Users/lab/research/VaultForge/pipeline_output/logs/pipeline.log"

# ── Classification constants ──────────────────────────────────────────────────
NOTE_PREFIXES = ("NOTE:", "WARNING:", "IMPORTANT:", "CAUTION:", "DESIGN DECISION:", "DESIGN NOTE:")
CAPTION_PREFIXES = ("Table", "Figure", "Fig.", "Listing", "Diagram", "Appendix")


def setup_logging():
    Path(LOG_PATH).parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(LOG_PATH, mode="a"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def get_spans(block):
    spans = []
    for line in block.get("lines", []):
        for span in line.get("spans", []):
            spans.append(span)
    return spans


def classify_block(block, spans):
    """
    Returns one of:
        chapter_heading | section_heading | subsection_heading |
        prose | code | table_header | figure_region | developer_note |
        caption | figure_label | skip
    """
    if block.get("type") == 1:
        return "figure_region"

    if not spans:
        return "figure_region"

    primary = spans[0]
    font_size = primary.get("size", 9)
    font_name = primary.get("font", "")
    text = " ".join(s.get("text", "") for s in spans).strip()

    # Skip running headers (Franklin Gothic Medium — appears on every page)
    if "Franklin Gothic" in font_name:
        return "skip"

    # Skip Wingdings (bullet symbols in lists)
    if "Wingdings" in font_name or "Symbol" in font_name:
        return "skip"

    # Chapter headings: Garamond Bold at large size
    if "Garamond" in font_name and font_size >= 14:
        return "chapter_heading"

    # Section headings: Tahoma Bold at 12pt (numbered sections: "17. STORAGE")
    if "Tahoma" in font_name and "Bold" in font_name and font_size >= 12:
        return "section_heading"

    # Subsection headings: Tahoma 11pt (numbered subsections: "17.1. EMR")
    if "Tahoma" in font_name and font_size >= 11:
        return "subsection_heading"

    # Sub-subsection headings: Arial Bold 11pt (e.g., "17.1.1 FAC Mode")
    if "Arial" in font_name and "Bold" in font_name and font_size >= 11 and "Italic" not in font_name:
        return "subsection_heading"

    # Calibri Bold (used occasionally for headings like Table of Contents)
    if "Calibri" in font_name and "Bold" in font_name and font_size >= 12:
        return "section_heading"

    # Table data rows: Trebuchet MS at small size (register definitions, protocol tables)
    if "Trebuchet" in font_name and font_size <= 9:
        return "code"

    # Table header rows: Verdana Bold at small size
    if "Verdana" in font_name and "Bold" in font_name and font_size <= 9:
        return "table_header"

    # Captions (Table X / Figure X): Arial BoldItalic or similar at small size
    if "Arial" in font_name and "BoldItalic" in font_name and font_size <= 9:
        text_clean = text.strip()
        if any(text_clean.startswith(p) for p in CAPTION_PREFIXES):
            return "caption"
        return "caption"

    # Figure element labels: Arial at small size (labels on diagrams)
    if "Arial" in font_name and font_size <= 9:
        return "figure_label"

    # Verdana Italic — often used for emphasis or notes
    if "Verdana" in font_name and "Italic" in font_name:
        return "prose"

    # Developer notes — check text prefix (overrides prose classification)
    text_upper = text.upper()
    if any(text_upper.startswith(p) for p in NOTE_PREFIXES):
        return "developer_note"

    # Default: prose
    return "prose"


def detect_language_hint(text):
    """Quick language detection for code/table blocks."""
    if any(k in text for k in ["void ", "uint8_t", "uint32_t", "#define", "typedef struct", "->", "#include", "int32_t", "uint16_t"]):
        return "c"
    if any(k in text for k in ["func ", "package ", ":= ", "chan ", "goroutine", "go func", "type ", "struct {"]):
        return "go"
    if any(k in text for k in ["def ", "class ", "self.", "import ", "    "]) and "=>" not in text:
        return "python"
    if any(k in text for k in ["message ", "service ", "rpc ", "repeated ", "syntax ="]):
        return "protobuf"
    if any(k in text for k in ["function ", "const ", "let ", "var ", "=>", "require("]):
        return "javascript"
    # Register/struct table data
    if re.match(r"^\d+\s+\d+\s+\w+", text.strip()):
        return "c_struct"
    return "unknown"


def count_tokens(text, enc):
    try:
        return len(enc.encode(text))
    except Exception:
        return max(1, len(text.split()))


def run():
    setup_logging()
    log = logging.getLogger("trm_scanner")
    log.info("=== TRM SCANNER START ===")
    log.info(f"Opening PDF: {PDF_PATH}")

    import tiktoken
    enc = tiktoken.get_encoding("cl100k_base")

    doc = fitz.open(PDF_PATH)
    total_pages = len(doc)
    log.info(f"PDF has {total_pages} pages")

    page_map = []
    current_chapter = None
    current_chapter_num = None
    current_section = None
    current_subsection = None

    # Counters per page
    fig_counter = {}
    code_counter = {}
    table_counter = {}

    for page_num in range(total_pages):
        try:
            page = doc[page_num]
            blocks_raw = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]

            page_data = {
                "page": page_num,
                "chapter": current_chapter,
                "chapter_num": current_chapter_num,
                "section": current_section,
                "subsection": current_subsection,
                "blocks": [],
            }

            # Group consecutive code blocks that belong to the same table
            pending_table_header = None

            for block_idx, block in enumerate(blocks_raw):
                try:
                    spans = get_spans(block)
                    btype = classify_block(block, spans)
                    text = " ".join(s.get("text", "") for s in spans).strip()
                    bbox = list(block.get("bbox", []))

                    if btype == "skip":
                        continue

                    # Update context trackers
                    if btype == "chapter_heading" and text:
                        current_chapter = text
                        m = re.search(r"chapter\s+(\d+)", text.lower())
                        if not m:
                            m = re.search(r"C\s*H\s*A\s*P\s*T\s*E\s*R\s+(\d+)", text)
                        current_chapter_num = int(m.group(1)) if m else None
                        page_data["chapter"] = current_chapter
                        page_data["chapter_num"] = current_chapter_num
                        current_section = None
                        current_subsection = None
                        pending_table_header = None

                    elif btype == "section_heading" and text:
                        current_section = text
                        page_data["section"] = current_section
                        current_subsection = None
                        pending_table_header = None

                    elif btype == "subsection_heading" and text:
                        current_subsection = text
                        page_data["subsection"] = current_subsection
                        pending_table_header = None

                    # Build block record
                    block_record = {
                        "type": btype,
                        "bbox": bbox,
                    }

                    if btype == "figure_region":
                        idx = fig_counter.get(page_num, 0)
                        fig_counter[page_num] = idx + 1
                        block_record["text"] = ""
                        block_record["figure_idx"] = idx
                        block_record["image_saved"] = False
                        block_record["caption"] = ""

                    elif btype == "table_header":
                        block_record["text"] = text
                        block_record["is_table_header"] = True
                        pending_table_header = text
                        idx = table_counter.get(page_num, 0)
                        table_counter[page_num] = idx + 1
                        block_record["table_idx"] = idx

                    elif btype == "code":
                        idx = code_counter.get(page_num, 0)
                        code_counter[page_num] = idx + 1
                        lang = detect_language_hint(text)
                        block_record["text"] = text
                        block_record["language_hint"] = lang
                        block_record["code_idx"] = idx
                        block_record["token_count"] = count_tokens(text, enc)
                        if pending_table_header:
                            block_record["table_header"] = pending_table_header

                    elif btype == "caption":
                        block_record["text"] = text
                        # Update figure_region or table_header with this caption
                        # Find last figure_region or code block to attach caption
                        for prev in reversed(page_data["blocks"]):
                            if prev["type"] in ("figure_region", "table_header", "code"):
                                prev["caption"] = text
                                break
                        pending_table_header = None  # caption ends a table block

                    elif btype == "figure_label":
                        # Attach to most recent figure_region
                        block_record["text"] = text
                        for prev in reversed(page_data["blocks"]):
                            if prev["type"] == "figure_region":
                                prev.setdefault("labels", []).append(text)
                                break

                    elif btype == "developer_note":
                        block_record["text"] = text
                        # Classify note type
                        text_upper = text.upper()
                        note_type = "NOTE"
                        if text_upper.startswith("WARNING:"):
                            note_type = "WARNING"
                        elif text_upper.startswith("IMPORTANT:"):
                            note_type = "IMPORTANT"
                        elif text_upper.startswith("CAUTION:"):
                            note_type = "CAUTION"
                        elif text_upper.startswith("DESIGN DECISION:"):
                            note_type = "DESIGN_DECISION"
                        elif text_upper.startswith("DESIGN NOTE:"):
                            note_type = "DESIGN_NOTE"
                        block_record["note_type"] = note_type
                        block_record["token_count"] = count_tokens(text, enc)

                    else:
                        block_record["text"] = text
                        if text:
                            block_record["token_count"] = count_tokens(text, enc)

                    page_data["blocks"].append(block_record)

                except Exception as e:
                    log.warning(f"Block error page {page_num} idx {block_idx}: {e}")
                    continue

            page_map.append(page_data)

            if page_num % 100 == 0:
                log.info(f"Scanned page {page_num}/{total_pages}")

        except Exception as e:
            log.error(f"Page {page_num} failed: {e}", exc_info=True)
            page_map.append({"page": page_num, "error": str(e), "blocks": []})
            continue

    # Write output
    out_path = Path(OUT_PATH)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(page_map, f, indent=2)

    # Summary
    all_blocks = [b for p in page_map for b in p.get("blocks", [])]
    type_counts = {}
    for b in all_blocks:
        t = b.get("type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1

    log.info(f"Page map written: {len(page_map)} pages → {OUT_PATH}")
    log.info(f"Block type counts: {type_counts}")

    print(f"\n=== TRM SCAN COMPLETE ===")
    print(f"Pages:  {len(page_map)}")
    for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"  {t:30s}: {c}")

    dev_notes = [b for p in page_map for b in p.get("blocks", []) if b.get("type") == "developer_note"]
    code_blocks = [b for p in page_map for b in p.get("blocks", []) if b.get("type") == "code"]
    figures = [b for p in page_map for b in p.get("blocks", []) if b.get("type") == "figure_region"]
    print(f"\nKey stats:")
    print(f"  Developer notes: {len(dev_notes)}")
    print(f"  Code/table data blocks: {len(code_blocks)}")
    print(f"  Figure regions: {len(figures)}")


if __name__ == "__main__":
    run()
