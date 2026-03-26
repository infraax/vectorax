#!/usr/bin/env python3
"""
TRM Figure Extractor — Phase 1.4
Extracts figure images from VectorTRM.pdf.
No vision model available (llava not installed), so saves PNGs + placeholders.
Output: pipeline_output/trm_figures/fig_PAGE_IDX.png + trm_structured/figures.json
"""
import fitz
import json
import logging
import sys
import re
from pathlib import Path

PDF_PATH  = "/Users/lab/research/Sources/VectorTRM.pdf"
PAGE_MAP  = "/Users/lab/research/VaultForge/pipeline_output/trm_structured/page_map.json"
OUT_IMGS  = "/Users/lab/research/VaultForge/pipeline_output/trm_figures"
OUT_JSON  = "/Users/lab/research/VaultForge/pipeline_output/trm_structured/figures.json"
LOG_PATH  = "/Users/lab/research/VaultForge/pipeline_output/logs/pipeline.log"

DPI = 200
MIN_IMG_SIZE = 50  # skip tiny images (icons, bullets) smaller than 50px in either dimension


def run():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(LOG_PATH, mode="a"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    log = logging.getLogger("trm_figures")
    log.info("=== TRM FIGURES EXTRACTOR START ===")

    Path(OUT_IMGS).mkdir(parents=True, exist_ok=True)

    # Load page map for chapter/section context and captions
    with open(PAGE_MAP) as f:
        page_map = json.load(f)

    # Build caption lookup from page map
    page_context = {}
    figure_captions = {}  # page_num -> list of captions
    for page in page_map:
        pn = page["page"]
        page_context[pn] = {
            "chapter": page.get("chapter"),
            "section": page.get("section"),
            "subsection": page.get("subsection"),
        }
        # Collect caption blocks
        for block in page.get("blocks", []):
            if block.get("type") == "caption":
                text = block.get("text", "")
                if any(text.startswith(p) for p in ("Figure", "Fig.")):
                    figure_captions.setdefault(pn, []).append(text)

    doc = fitz.open(PDF_PATH)
    figures = []
    figure_counter = 0

    mat = fitz.Matrix(DPI / 72, DPI / 72)

    for page_num in range(len(doc)):
        try:
            page = doc[page_num]
            ctx = page_context.get(page_num, {})
            captions = figure_captions.get(page_num, [])
            caption_iter = iter(captions)

            # Get all images on this page
            img_list = page.get_images(full=True)
            if not img_list:
                continue

            for img_idx, img_info in enumerate(img_list):
                try:
                    xref = img_info[0]
                    width = img_info[2]
                    height = img_info[3]

                    # Skip tiny images (icons, decorative elements)
                    if width < MIN_IMG_SIZE or height < MIN_IMG_SIZE:
                        continue

                    # Get image placement on page
                    rects = page.get_image_rects(xref)
                    if not rects:
                        continue
                    img_rect = rects[0]

                    # Render this region to PNG
                    clip = page.get_pixmap(matrix=mat, clip=img_rect)

                    # Skip very small rendered images
                    if clip.width < 50 or clip.height < 50:
                        continue

                    img_filename = f"fig_{page_num}_{img_idx}.png"
                    img_path = Path(OUT_IMGS) / img_filename
                    clip.save(str(img_path))

                    figure_counter += 1
                    figure_id = f"Fig_{page_num}_{img_idx}"
                    caption = next(caption_iter, "")

                    record = {
                        "figure_id": figure_id,
                        "caption": caption,
                        "chapter": ctx.get("chapter"),
                        "section": ctx.get("section"),
                        "subsection": ctx.get("subsection"),
                        "page": page_num,
                        "image_path": str(img_path),
                        "image_filename": img_filename,
                        "width_px": clip.width,
                        "height_px": clip.height,
                        "llm_description": None,  # No vision model available
                        "llm_model_used": None,
                        "token_count": 0,
                    }
                    figures.append(record)

                except Exception as e:
                    log.warning(f"Figure p{page_num}[{img_idx}]: {e}")
                    continue

            if page_num % 100 == 0:
                log.info(f"Figures: processed page {page_num}/{len(doc)}, total so far: {figure_counter}")

        except Exception as e:
            log.error(f"Figure page {page_num} failed: {e}")
            continue

    # Write JSON
    with open(OUT_JSON, "w") as f:
        json.dump(figures, f, indent=2)

    log.info(f"Figures extracted: {figure_counter}")
    print(f"\n=== TRM FIGURES COMPLETE ===")
    print(f"Total figures: {figure_counter}")
    print(f"Saved to: {OUT_IMGS}")
    print(f"Note: No vision model available — llm_description is null (PNGs saved for manual review)")


if __name__ == "__main__":
    run()
