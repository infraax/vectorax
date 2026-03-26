#!/usr/bin/env python3
"""
TRM Developer Notes Extractor — Phase 1.5
Extracts all developer_note blocks from the page map.
These are the highest-priority content in the TRM.
Output: pipeline_output/trm_structured/developer_notes.json
"""
import json
import logging
import sys
import re
from pathlib import Path

PAGE_MAP  = "/Users/lab/research/VaultForge/pipeline_output/trm_structured/page_map.json"
OUT_FILE  = "/Users/lab/research/VaultForge/pipeline_output/trm_structured/developer_notes.json"
LOG_PATH  = "/Users/lab/research/VaultForge/pipeline_output/logs/pipeline.log"

# Hardware keywords for binding
HW_KEYWORDS = {
    "TRM__Snapdragon_212":          ["snapdragon", "apq8009", "qualcomm", "linux", "yocto"],
    "TRM__STM32_Body_Board":        ["stm32", "body board", "body-board", "spi", "pid", "encoder", "motor", "cliff", "gpio"],
    "TRM__QCA9377_WiFi_BLE":        ["qca9377", "wifi", "bluetooth", "ble", "wlan", "network"],
    "TRM__Camera_OV7740":           ["ov7740", "camera", "vision", "image", "capture", "face"],
    "TRM__Mic_Array":               ["microphone", "mic", "beamforming", "wake word", "audio", "speech"],
    "TRM__Laser_ToF_VL53L0X":      ["vl53l0x", "tof", "laser", "lidar", "ranging", "distance", "obstacle", "cliff"],
    "TRM__Motors_Wheels_Head_Lift": ["motor", "wheel", "drive", "locomotion", "head", "lift", "encoder", "pwm", "pid", "h-bridge", "integrat"],
    "TRM__Face_Display_IPS":        ["display", "lcd", "ips", "tft", "eye", "face", "render", "animation"],
}

CODE_KEYWORDS = [
    r"\b\w+_\w+\s*\(", r"uint\d+_t", r"int\d+_t", r"\bPID\b", r"\bSPI\b",
    r"\bUART\b", r"\bI2C\b", r"\bGPIO\b", r"\bPWM\b", r"0x[0-9a-fA-F]+",
    r"\b[A-Z][A-Z_]{3,}\b",
]


def detect_hardware_mentions(text):
    tl = text.lower()
    return [hw_id for hw_id, kws in HW_KEYWORDS.items() if any(k in tl for k in kws)]


def detect_code_mentions(text):
    mentions = []
    for pattern in CODE_KEYWORDS:
        for m in re.finditer(pattern, text):
            mentions.append(m.group(0).strip())
    return list(set(mentions))[:10]


def slugify(text, maxlen=50):
    text = re.sub(r"[^a-zA-Z0-9\s]", "", text)
    text = "_".join(text.split()[:6])
    return text[:maxlen]


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
    log = logging.getLogger("trm_notes")
    log.info("=== TRM NOTES EXTRACTOR START ===")

    with open(PAGE_MAP) as f:
        page_map = json.load(f)

    notes = []
    note_counter = 0

    for page_data in page_map:
        page_num = page_data["page"]
        chapter  = page_data.get("chapter")
        section  = page_data.get("section")
        subsect  = page_data.get("subsection")
        blocks   = page_data.get("blocks", [])

        for block in blocks:
            if block.get("type") != "developer_note":
                continue
            try:
                text = block.get("text", "").strip()
                if not text or len(text) < 10:
                    continue

                # Determine note type from prefix
                text_upper = text.upper()
                note_type = "NOTE"
                clean_text = text
                for prefix in ["WARNING:", "IMPORTANT:", "CAUTION:", "DESIGN DECISION:", "DESIGN NOTE:", "NOTE:"]:
                    if text_upper.startswith(prefix):
                        note_type = prefix.rstrip(":").replace(" ", "_")
                        clean_text = text[len(prefix):].strip()
                        break

                note_counter += 1
                note_id = f"N{page_num}.{note_counter}"
                slug = slugify(clean_text)
                vault_note = f"TRM_Note__{note_id}_{slug}.md"

                hw = detect_hardware_mentions(text)
                code_mentions = detect_code_mentions(text)

                note_record = {
                    "note_id": note_id,
                    "note_type": note_type,
                    "chapter": chapter,
                    "section": section,
                    "subsection": subsect,
                    "page": page_num,
                    "content": clean_text,
                    "full_text": text,  # includes prefix
                    "token_count": count_tokens(text),
                    "hardware_mentions": hw,
                    "code_mentions": code_mentions,
                    "vault_note": vault_note,
                    "priority": "HIGH",
                }
                notes.append(note_record)
                log.info(f"Note {note_id} [{note_type}] p{page_num}: {clean_text[:80]!r}")

            except Exception as e:
                log.warning(f"Note extraction error page {page_num}: {e}")
                continue

    # Write output
    Path(OUT_FILE).parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_FILE, "w") as f:
        json.dump(notes, f, indent=2)

    # Print summary by type
    from collections import Counter
    type_counts = Counter(n["note_type"] for n in notes)
    log.info(f"Developer notes extracted: {len(notes)}")

    print(f"\n=== TRM NOTES COMPLETE ===")
    print(f"Total developer notes: {len(notes)}")
    for note_type, count in sorted(type_counts.items()):
        print(f"  {note_type:20s}: {count}")

    # Print first few notes as preview
    print("\nFirst 5 notes:")
    for n in notes[:5]:
        print(f"  [{n['note_type']}] p{n['page']}: {n['content'][:100]!r}")


if __name__ == "__main__":
    run()
