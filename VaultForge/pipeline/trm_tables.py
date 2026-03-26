#!/usr/bin/env python3
"""
TRM Table Extractor — Phase 1.2
Uses pdfplumber to extract structured tables from VectorTRM.pdf.
Output: pipeline_output/trm_structured/tables/table_PAGE_IDX.json
"""
import json
import logging
import sys
import re
from pathlib import Path

PDF_PATH = "/Users/lab/research/Sources/VectorTRM.pdf"
PAGE_MAP = "/Users/lab/research/VaultForge/pipeline_output/trm_structured/page_map.json"
OUT_DIR  = "/Users/lab/research/VaultForge/pipeline_output/trm_structured/tables"
LOG_PATH = "/Users/lab/research/VaultForge/pipeline_output/logs/pipeline.log"

# Hardware component keyword mapping
HW_KEYWORDS = {
    "TRM__Snapdragon_212":      ["snapdragon", "apq8009", "qualcomm", "linux", "yocto", "cozmongine"],
    "TRM__STM32_Body_Board":    ["stm32", "f427", "body board", "body-board", "spi", "pid", "encoder", "motor", "cliff", "ik", "inverse kinematics", "gpio", "pa0", "pa1", "pwm"],
    "TRM__QCA9377_WiFi_BLE":    ["qca9377", "wifi", "bluetooth", "ble", "wlan", "network", "gateway", "onboarding"],
    "TRM__Camera_OV7740":       ["ov7740", "camera", "vision", "image", "capture", "face", "opencv", "vga", "cmos"],
    "TRM__Mic_Array":           ["microphone", "mic", "beamforming", "wake word", "sensory", "vtt", "audio", "speech"],
    "TRM__Laser_ToF_VL53L0X":  ["vl53l0x", "tof", "laser", "lidar", "ranging", "distance", "obstacle", "cliff", "time of flight", "prox"],
    "TRM__Motors_Wheels_Head_Lift": ["motor", "wheel", "drive", "locomotion", "head", "lift", "encoder", "pwm", "pid", "dc motor", "tracks", "h-bridge"],
    "TRM__Face_Display_IPS":    ["display", "lcd", "ips", "tft", "eye", "face", "render", "animation", "screen"],
}


def detect_hardware(text):
    """Return list of hardware component IDs mentioned in text."""
    tl = text.lower()
    found = []
    for hw_id, keywords in HW_KEYWORDS.items():
        if any(kw in tl for kw in keywords):
            found.append(hw_id)
    return found


def linearize_table(headers, rows):
    """Convert table to human-readable text for embedding."""
    parts = []
    for row in rows:
        if isinstance(row, dict):
            row_parts = [f"{k}: {v}" for k, v in row.items() if v and str(v).strip()]
            parts.append(". ".join(row_parts))
        elif isinstance(row, (list, tuple)):
            parts.append("  ".join(str(c) for c in row if c and str(c).strip()))
    return " | ".join(parts)


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
    log = logging.getLogger("trm_tables")
    log.info("=== TRM TABLE EXTRACTOR START ===")

    Path(OUT_DIR).mkdir(parents=True, exist_ok=True)

    # Load page map for chapter/section context
    with open(PAGE_MAP) as f:
        page_map = json.load(f)

    page_context = {}
    for page in page_map:
        page_context[page["page"]] = {
            "chapter": page.get("chapter"),
            "chapter_num": page.get("chapter_num"),
            "section": page.get("section"),
            "subsection": page.get("subsection"),
        }

    import pdfplumber
    table_count = 0
    failed_pages = []

    # Also extract Trebuchet MS blocks as structured table data from page map
    # (these are the register definition tables that pdfplumber may also find)
    trebuchet_tables = {}  # page_num -> list of block groups

    for page in page_map:
        pn = page["page"]
        blocks = page.get("blocks", [])
        current_group = {"header": None, "rows": [], "caption": None}

        for block in blocks:
            btype = block.get("type")
            text = block.get("text", "").strip()
            if not text:
                continue

            if btype == "table_header":
                # Save previous group if it has rows
                if current_group["rows"]:
                    trebuchet_tables.setdefault(pn, []).append(dict(current_group))
                current_group = {"header": text, "rows": [], "caption": None}

            elif btype == "code" and current_group is not None:
                current_group["rows"].append(text)

            elif btype == "caption" and current_group is not None:
                current_group["caption"] = text
                trebuchet_tables.setdefault(pn, []).append(dict(current_group))
                current_group = {"header": None, "rows": [], "caption": None}

        # Save any remaining group
        if current_group["rows"]:
            trebuchet_tables.setdefault(pn, []).append(dict(current_group))

    log.info(f"Extracted {sum(len(v) for v in trebuchet_tables.values())} table groups from page map")

    # Save trebuchet-sourced tables
    for page_num, groups in trebuchet_tables.items():
        ctx = page_context.get(page_num, {})
        for group_idx, group in enumerate(groups):
            try:
                header_row = group.get("header", "")
                data_rows = group.get("rows", [])
                caption = group.get("caption", "")

                if not data_rows:
                    continue

                # Parse header columns
                headers = []
                if header_row:
                    headers = [h.strip() for h in re.split(r"\s{2,}", header_row) if h.strip()]

                # Parse data rows into dicts if we have headers
                parsed_rows = []
                for row_text in data_rows:
                    if headers and len(headers) > 1:
                        # Split on 2+ spaces (column separator in this PDF)
                        cols = [c.strip() for c in re.split(r"\s{2,}", row_text)]
                        if len(cols) >= len(headers) - 1:
                            row_dict = {}
                            for i, h in enumerate(headers):
                                row_dict[h] = cols[i] if i < len(cols) else ""
                            parsed_rows.append(row_dict)
                        else:
                            parsed_rows.append({"data": row_text})
                    else:
                        parsed_rows.append({"data": row_text})

                # Build structured text
                all_text = (header_row + " " + " ".join(data_rows) + " " + (caption or "")).strip()
                hw = detect_hardware(all_text)
                struct_text = linearize_table(headers, parsed_rows)

                table_id = f"T{page_num}.{group_idx+1}"
                table_record = {
                    "table_id": table_id,
                    "caption": caption,
                    "chapter": ctx.get("chapter"),
                    "section": ctx.get("section"),
                    "subsection": ctx.get("subsection"),
                    "page": page_num,
                    "headers": headers,
                    "rows": parsed_rows,
                    "structured_text": struct_text,
                    "token_count": count_tokens(all_text),
                    "hardware_component": hw[0] if hw else None,
                    "hardware_components": hw,
                    "source": "trebuchet_extraction",
                }

                out_file = Path(OUT_DIR) / f"table_{page_num}_{group_idx+1}.json"
                with open(out_file, "w") as f:
                    json.dump(table_record, f, indent=2)
                table_count += 1

            except Exception as e:
                log.warning(f"Table group failed page {page_num} idx {group_idx}: {e}")
                continue

    # Also run pdfplumber for additional table detection (line-based tables)
    try:
        with pdfplumber.open(PDF_PATH) as pdf:
            for page_num, page in enumerate(pdf.pages):
                try:
                    ctx = page_context.get(page_num, {})
                    tables = page.extract_tables({
                        "vertical_strategy": "lines_strict",
                        "horizontal_strategy": "lines_strict",
                        "snap_tolerance": 3,
                    })
                    if not tables:
                        # Try less strict
                        tables = page.extract_tables({
                            "vertical_strategy": "lines",
                            "horizontal_strategy": "lines",
                        })

                    for tbl_idx, table_data in enumerate(tables):
                        try:
                            if not table_data or len(table_data) < 2:
                                continue

                            headers = [str(h).strip() if h else "" for h in table_data[0]]
                            rows = []
                            for row in table_data[1:]:
                                row_dict = {}
                                for i, h in enumerate(headers):
                                    val = str(row[i]).strip() if i < len(row) and row[i] else ""
                                    row_dict[h if h else f"col_{i}"] = val
                                rows.append(row_dict)

                            all_text = " ".join(" ".join(str(v) for v in r.values()) for r in rows)
                            hw = detect_hardware(all_text + " " + " ".join(headers))
                            struct_text = linearize_table(headers, rows)

                            table_id = f"TP{page_num}.{tbl_idx+1}"
                            table_record = {
                                "table_id": table_id,
                                "caption": "",
                                "chapter": ctx.get("chapter"),
                                "section": ctx.get("section"),
                                "subsection": ctx.get("subsection"),
                                "page": page_num,
                                "headers": headers,
                                "rows": rows,
                                "structured_text": struct_text,
                                "token_count": count_tokens(struct_text),
                                "hardware_component": hw[0] if hw else None,
                                "hardware_components": hw,
                                "source": "pdfplumber",
                            }

                            out_file = Path(OUT_DIR) / f"table_p{page_num}_{tbl_idx+1}.json"
                            with open(out_file, "w") as f:
                                json.dump(table_record, f, indent=2)
                            table_count += 1

                        except Exception as e:
                            log.warning(f"pdfplumber table p{page_num}[{tbl_idx}]: {e}")
                            continue

                    if page_num % 100 == 0:
                        log.info(f"pdfplumber: page {page_num}/{len(pdf.pages)}")

                except Exception as e:
                    log.warning(f"pdfplumber page {page_num}: {e}")
                    failed_pages.append(page_num)
                    continue

    except Exception as e:
        log.error(f"pdfplumber failed: {e}")

    log.info(f"Tables extracted: {table_count} (failed pages: {len(failed_pages)})")
    print(f"\n=== TRM TABLES COMPLETE ===")
    print(f"Tables written: {table_count}")
    print(f"Files in {OUT_DIR}: {len(list(Path(OUT_DIR).glob('*.json')))}")


if __name__ == "__main__":
    run()
