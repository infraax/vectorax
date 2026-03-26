#!/usr/bin/env python3
"""
TRM Cross-Reference Extractor — Phase 1.6
Scans all prose blocks for internal references (Section X.X, Figure X.X, Table X.X).
Output: pipeline_output/trm_structured/cross_reference_map.json
"""
import json
import logging
import sys
import re
from pathlib import Path

PAGE_MAP = "/Users/lab/research/VaultForge/pipeline_output/trm_structured/page_map.json"
OUT_FILE = "/Users/lab/research/VaultForge/pipeline_output/trm_structured/cross_reference_map.json"
LOG_PATH = "/Users/lab/research/VaultForge/pipeline_output/logs/pipeline.log"

# Patterns for cross-references
PATTERNS = [
    (r"[Ss]ection\s+(\d+\.[\d.]+)",           "section"),
    (r"[Ss]ec\.\s*(\d+\.[\d.]+)",              "section"),
    (r"[Cc]hapter\s+(\d+)",                    "chapter"),
    (r"[Cc]h\.\s*(\d+)",                       "chapter"),
    (r"[Ff]igure\s+(\d+)",                     "figure"),
    (r"[Ff]ig\.\s*(\d+)",                      "figure"),
    (r"[Tt]able\s+(\d+)",                      "table"),
    (r"[Aa]ppendix\s+([A-Z\d]+)",              "appendix"),
    (r"[Ll]isting\s+(\d+)",                    "listing"),
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
    log = logging.getLogger("trm_crossrefs")
    log.info("=== TRM CROSS-REFERENCE EXTRACTOR START ===")

    with open(PAGE_MAP) as f:
        page_map = json.load(f)

    # Build a map of section/chapter/figure/table identifiers to their pages
    section_to_page = {}
    figure_to_page = {}
    table_to_page = {}

    for page in page_map:
        pn = page["page"]
        section = page.get("section", "")
        if section:
            # Extract section number
            m = re.match(r"(\d+\.[\d.]*)", section.strip())
            if m:
                section_to_page[m.group(1)] = pn

        for block in page.get("blocks", []):
            if block.get("type") == "caption":
                text = block.get("text", "")
                m = re.match(r"[Ff]igure\s+(\d+)", text)
                if m:
                    figure_to_page[m.group(1)] = pn
                m = re.match(r"[Tt]able\s+(\d+)", text)
                if m:
                    table_to_page[m.group(1)] = pn

    # Now scan all prose for references
    cross_refs = {}  # ref_key -> {ref_type, identifier, source_pages, target_page, vault_note}

    for page in page_map:
        pn = page["page"]
        chapter = page.get("chapter", "")
        section = page.get("section", "")

        for block in page.get("blocks", []):
            text = block.get("text", "")
            if not text or block.get("type") not in ("prose", "developer_note", "subsection_heading", "section_heading"):
                continue

            for pattern, ref_type in PATTERNS:
                for m in re.finditer(pattern, text):
                    identifier = m.group(1)
                    ref_key = f"{ref_type}:{identifier}"

                    if ref_key not in cross_refs:
                        target_page = None
                        if ref_type == "section":
                            target_page = section_to_page.get(identifier)
                        elif ref_type == "figure":
                            target_page = figure_to_page.get(identifier)
                        elif ref_type == "table":
                            target_page = table_to_page.get(identifier)

                        # Build vault note name
                        if ref_type == "section":
                            vault_note = f"TRM_Ch_Sec{identifier.replace('.', '_')}"
                        elif ref_type == "figure":
                            vault_note = f"TRM_Figure__Fig_{identifier}"
                        elif ref_type == "table":
                            vault_note = f"TRM_Table__T{identifier}"
                        elif ref_type == "chapter":
                            vault_note = f"TRM_Ch{identifier.zfill(2)}"
                        else:
                            vault_note = f"TRM_{ref_type}_{identifier}"

                        cross_refs[ref_key] = {
                            "ref_type": ref_type,
                            "identifier": identifier,
                            "source_pages": [pn],
                            "target_page": target_page,
                            "vault_note": vault_note,
                            "mention_count": 1,
                        }
                    else:
                        if pn not in cross_refs[ref_key]["source_pages"]:
                            cross_refs[ref_key]["source_pages"].append(pn)
                        cross_refs[ref_key]["mention_count"] += 1

    result = list(cross_refs.values())
    result.sort(key=lambda x: -x["mention_count"])

    with open(OUT_FILE, "w") as f:
        json.dump(result, f, indent=2)

    log.info(f"Cross-references extracted: {len(result)}")
    print(f"\n=== TRM CROSS-REFS COMPLETE ===")
    print(f"Total cross-references: {len(result)}")
    from collections import Counter
    type_counts = Counter(r["ref_type"] for r in result)
    for t, c in sorted(type_counts.items()):
        print(f"  {t:12s}: {c}")


if __name__ == "__main__":
    run()
