# VaultForge — VectorTRM.pdf Parsing Specification

## Source File

- **Path:** `/Users/lab/research/Sources/VectorTRM.pdf`
- **Symlink:** `sources/VectorTRM.pdf`
- **Size:** 565 pages
- **Content:** Vector robot full technical reference — hardware specs to pin level, firmware architecture, gRPC protocol definitions, developer notes, code snippets, diagrams, engineering decision rationale

## Why The TRM Is Processed First

The TRM is the root source of truth. Every repository was built with this document as the specification. Processing it first gives us:
1. A hardware component registry that tags code chunks with hardware bindings
2. TRM code snippets to cross-link against repo symbols
3. Pin/register/constant tables to match against `#define` names in C code
4. Engineering decisions that explain WHY code is structured as it is

---

## Why pdftotext Failed

Gemini ran `pdftotext VectorTRM.pdf output.txt` which produced a 50,000-line flat file that lost:
- All tables (columns collapsed to space-separated strings — unreadable)
- Code blocks (indistinguishable from prose)
- Figures and diagrams (skipped entirely)
- Font metadata (can't distinguish headings from body text)
- Developer notes buried in the text stream
- Page numbers and section hierarchy

The 50K line file is effectively a shredded document.

---

## Tool Selection

### Primary: PyMuPDF (`fitz`)

```python
import fitz  # pip install pymupdf

doc = fitz.open("/Users/lab/research/Sources/VectorTRM.pdf")
for page_num in range(len(doc)):
    page = doc[page_num]

    # Get text blocks with full layout metadata
    blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]

    for block in blocks:
        if block["type"] == 0:  # text block
            for line in block["lines"]:
                for span in line["spans"]:
                    font_name = span["font"]       # e.g. "CourierNew", "TimesNewRomanPS-BoldMT"
                    font_size = span["size"]       # float, e.g. 18.0
                    is_bold   = "Bold" in font_name or span["flags"] & 2**4
                    is_mono   = any(m in font_name for m in ["Courier", "Mono", "Code", "Consolas"])
                    text      = span["text"]
        elif block["type"] == 1:  # image block
            bbox = block["bbox"]  # (x0, y0, x1, y1) — coordinates for rendering
```

### Tables: pdfplumber

```python
import pdfplumber

with pdfplumber.open("/Users/lab/research/Sources/VectorTRM.pdf") as pdf:
    page = pdf.pages[page_num]
    tables = page.extract_tables({
        "vertical_strategy": "lines",
        "horizontal_strategy": "lines"
    })
    # Returns: list of lists of strings
    # tables[0][0] = header row, tables[0][1:] = data rows
```

`pdfplumber` uses line detection to find table boundaries — far more reliable than text-stream parsing.

### Figures: PyMuPDF render + Ollama

```python
# Render a specific region of a page to PNG
rect = fitz.Rect(x0, y0, x1, y1)  # from image block bbox
mat  = fitz.Matrix(200/72, 200/72)  # 200 DPI rendering
clip = page.get_pixmap(matrix=mat, clip=rect)
clip.save(f"pipeline_output/trm_figures/fig_{page_num}_{idx}.png")
```

---

## Block Classification Rules

```python
def classify_block(block, spans):
    """
    Returns one of: chapter_heading | section_heading | subsection_heading |
                    prose | code | table_region | figure_region | developer_note | caption
    """
    if not spans:
        return "figure_region"  # image-only block

    primary_span  = spans[0]
    font_size     = primary_span["size"]
    is_bold       = "Bold" in primary_span["font"] or primary_span["flags"] & 16
    is_mono       = any(m in primary_span["font"] for m in ["Courier", "Mono", "Code", "Consolas", "Letter"])
    text          = " ".join(s["text"] for s in spans).strip()

    if is_mono and len(spans) > 2:
        return "code"

    if font_size >= 18 and is_bold:
        return "chapter_heading"

    if font_size >= 13 and is_bold:
        return "section_heading"

    if font_size >= 11 and is_bold:
        return "subsection_heading"

    note_prefixes = ("NOTE:", "WARNING:", "IMPORTANT:", "CAUTION:", "DESIGN DECISION:", "DESIGN NOTE:")
    if any(text.upper().startswith(p) for p in note_prefixes):
        return "developer_note"

    caption_prefixes = ("Figure", "Table", "Fig.", "Listing")
    if any(text.startswith(p) for p in caption_prefixes) and len(text) < 200:
        return "caption"

    return "prose"
```

---

## Page Map Structure

Output file: `pipeline_output/trm_structured/page_map.json`

```json
[
  {
    "page": 0,
    "chapter": null,
    "section": null,
    "subsection": null,
    "blocks": []
  },
  {
    "page": 46,
    "chapter": "Chapter 4: Motor Control Subsystem",
    "chapter_num": 4,
    "section": "4.2 PID Loop Implementation",
    "subsection": null,
    "blocks": [
      {
        "type": "prose",
        "text": "The STM32 body board runs a PID loop at 1kHz...",
        "bbox": [72.0, 120.5, 540.0, 185.3],
        "token_count": 47
      },
      {
        "type": "table_region",
        "caption": "Table 4.1: GPIO Pin Assignments — STM32 Motor Controller",
        "bbox": [72.0, 200.0, 540.0, 350.0],
        "extracted": false
      },
      {
        "type": "code",
        "text": "void PID_Update(MotorState* m) {\n  m->error = m->target - m->actual;\n  m->integral += m->error * dt;\n}",
        "language_hint": "c",
        "function_name": "PID_Update",
        "bbox": [72.0, 360.0, 540.0, 440.0],
        "token_count": 42
      },
      {
        "type": "figure_region",
        "caption": "Figure 4.3: PID Loop Block Diagram",
        "figure_id": "Fig_4_3",
        "bbox": [72.0, 450.0, 540.0, 620.0],
        "image_saved": false
      },
      {
        "type": "developer_note",
        "note_type": "NOTE",
        "text": "NOTE: The integral term is capped at ±500 to prevent integrator windup during rapid direction changes. Values above this caused the motor driver to saturate, resulting in audible clicking and potential thermal damage to the H-bridge.",
        "bbox": [72.0, 630.0, 540.0, 700.0],
        "token_count": 52
      }
    ]
  }
]
```

---

## Table Output Format

Directory: `pipeline_output/trm_structured/tables/`
One file per table: `table_PAGE_IDX.json`

```json
{
  "table_id": "T4.1",
  "caption": "GPIO Pin Assignments — STM32 Motor Controller",
  "chapter": "Chapter 4: Motor Control Subsystem",
  "section": "4.2 PID Loop Implementation",
  "page": 46,
  "headers": ["GPIO", "Alternate Function", "Direction", "Voltage", "Connected To"],
  "rows": [
    {
      "GPIO": "PA0",
      "Alternate Function": "TIM2_CH1 / ENC_A_L",
      "Direction": "Input",
      "Voltage": "3.3V",
      "Connected To": "Left Motor Encoder Channel A"
    },
    {
      "GPIO": "PA1",
      "Alternate Function": "TIM2_CH2 / ENC_B_L",
      "Direction": "Input",
      "Voltage": "3.3V",
      "Connected To": "Left Motor Encoder Channel B"
    }
  ],
  "structured_text": "GPIO PA0 = TIM2_CH1/ENC_A_L, Input 3.3V, Left Motor Encoder Channel A. GPIO PA1 = TIM2_CH2/ENC_B_L, Input 3.3V, Left Motor Encoder Channel B.",
  "token_count": 87,
  "hardware_component": "TRM__STM32_Body_Board"
}
```

The `structured_text` field is the linearized, human-readable version used for embedding.

---

## Code Snippet Output Format

Directory: `pipeline_output/trm_structured/code_snippets/`
One file per snippet: `code_PAGE_IDX.json`

```json
{
  "snippet_id": "C4.1",
  "chapter": "Chapter 4: Motor Control Subsystem",
  "section": "4.2 PID Loop Implementation",
  "page": 46,
  "language": "c",
  "function_name": "PID_Update",
  "struct_names": ["MotorState"],
  "content": "void PID_Update(MotorState* m) {\n  m->error = m->target - m->actual;\n  m->integral += m->error * dt;\n  m->output = Kp * m->error + Ki * m->integral + Kd * m->derivative;\n}",
  "token_count": 67,
  "repo_links": []
}
```

Language detection heuristics:
```python
def detect_language(text):
    if any(k in text for k in ["void ", "uint8_t", "uint32_t", "#define", "->", "typedef struct"]):
        return "c"
    if any(k in text for k in ["func ", "package ", ":= ", "chan ", "goroutine"]):
        return "go"
    if any(k in text for k in ["def ", "import ", "class ", "self.", "    "]) and "=>" not in text:
        return "python"
    if any(k in text for k in ["message ", "service ", "rpc ", "repeated "]):
        return "protobuf"
    if any(k in text for k in ["function ", "const ", "let ", "var ", "=>"]):
        return "javascript"
    return "unknown"
```

---

## Figure Output Format

Directory: `pipeline_output/trm_figures/`
Images saved as: `fig_{page}_{idx}.png` at 200 DPI

JSON record appended to `pipeline_output/trm_structured/figures.json`:
```json
{
  "figure_id": "Fig_4_3",
  "caption": "PID Loop Block Diagram",
  "chapter": "Chapter 4: Motor Control Subsystem",
  "section": "4.2 PID Loop Implementation",
  "page": 46,
  "image_path": "pipeline_output/trm_figures/fig_46_0.png",
  "llm_description": "Block diagram showing a discrete-time PID controller with three parallel signal paths: proportional gain Kp multiplied by error signal, integrator block accumulating error×dt with ±500 saturation limiter, and derivative block computing rate of change. Three paths sum at output node to produce PWM duty cycle 0-100%. Encoder feedback closes the loop. Input reference signal labeled 'target_velocity', output labeled 'PWM_duty_cycle'.",
  "llm_model_used": "llava:13b",
  "token_count": 98
}
```

If no vision model is available, set `llm_description` to `null` and store a placeholder. The PNG is still saved.

Vision prompt template:
```
This is a diagram from the Anki Vector Robot Technical Reference Manual (page {page}).
Caption: "{caption}"
This is a {chapter} diagram.

Describe ALL of the following that you can see:
1. Components/blocks shown (with their exact labels)
2. Signal flows and data paths (with direction of flow)
3. Mathematical operations or logic blocks
4. Input signals and output signals (with their labels)
5. Any numerical values, thresholds, or constants shown
6. Hardware interfaces mentioned

Be precise and technical. This description will be used by an AI agent to understand hardware-software interactions.
```

---

## Developer Notes Output Format

File: `pipeline_output/trm_structured/developer_notes.json`

```json
[
  {
    "note_id": "N4.1",
    "note_type": "NOTE",
    "chapter": "Chapter 4: Motor Control Subsystem",
    "section": "4.2 PID Loop Implementation",
    "page": 46,
    "content": "The integral term is capped at ±500 to prevent integrator windup during rapid direction changes. Values above this caused the motor driver to saturate, resulting in audible clicking and potential thermal damage to the H-bridge.",
    "token_count": 52,
    "hardware_mentions": ["motor driver", "H-bridge"],
    "code_mentions": ["integral", "PID_Update"],
    "vault_note": "TRM_DeveloperNote__N4.1_Integrator_Windup.md",
    "priority": "HIGH"
  }
]
```

All developer notes get `priority: HIGH` — they are boosted in ChromaDB metadata for retrieval.

---

## ChromaDB Collections for TRM

Write to `/Users/lab/research/VectorMap/data/chroma_db_v2/` using these collection names:

| Collection | Source | Metadata filter key |
|---|---|---|
| `trm_prose` | Prose blocks from chapters | `{"content_type": "trm_prose"}` |
| `trm_code` | Extracted code snippets | `{"content_type": "trm_code"}` |
| `trm_tables` | Table structured_text fields | `{"content_type": "trm_table"}` |
| `trm_notes` | Developer notes | `{"content_type": "trm_note", "priority": "HIGH"}` |

Each document in ChromaDB gets metadata:
```python
{
  "content_type": "trm_note",
  "chapter": "Chapter 4: Motor Control Subsystem",
  "section": "4.2 PID Loop Implementation",
  "page": 46,
  "priority": "HIGH",
  "hardware_component": "TRM__STM32_Body_Board",
  "token_count": 52
}
```

---

## Vault Notes for TRM

Generated in `/Users/lab/research/VectorMap/data/Vector_Obsidian_Vault_V2/TRM/`

### Developer Note template

```markdown
---
id: trm-note-n4-1
type: trm_developer_note
note_type: NOTE
chapter: "Chapter 4: Motor Control Subsystem"
section: "4.2 PID Loop Implementation"
page: 46
priority: HIGH
hardware_mentions: [TRM__STM32_Body_Board, TRM__Motors_Wheels_Head_Lift]
tags: [trm_note, motor, pid, stm32, hardware]
---

# [NOTE] Integrator Windup — PID Motor Control

> Source: VectorTRM.pdf · Page 46 · Section 4.2

The integral term is capped at ±500 to prevent integrator windup during rapid direction changes.
Values above this caused the motor driver to saturate, resulting in audible clicking and
potential thermal damage to the H-bridge.

## Context
- Appears in: [[TRM_Ch04_Sec4.2_PID_Loop]]
- Related code: [[TRM_Code__PID_Update]] (snippet C4.1, page 46)
- Hardware affected: [[TRM__STM32_Body_Board]] · [[TRM__Motors_Wheels_Head_Lift]]

## Found in Repositories
(populated by Phase 2.4 — TRM↔Repo cross-linking)
- [[vector__hal_motor_stm32_pid_c]] — PID_Update implementation
```

### Code Snippet template

```markdown
---
id: trm-code-c4-1
type: trm_code_snippet
chapter: "Chapter 4: Motor Control Subsystem"
section: "4.2 PID Loop Implementation"
page: 46
language: c
function_name: PID_Update
tags: [trm_code, c, motor, pid, stm32]
---

# `PID_Update` — TRM Code Snippet C4.1

> Source: VectorTRM.pdf · Page 46 · Section 4.2

```c
void PID_Update(MotorState* m) {
  m->error    = m->target - m->actual;
  m->integral += m->error * dt;
  m->output   = Kp * m->error + Ki * m->integral + Kd * m->derivative;
}
```

## Found in Repositories
- [[vector__hal_motor_stm32_pid_c]] — exact match (95% confidence)

## Related TRM Content
- [[TRM_Table__GPIO_STM32_Motor]] — pin assignments for encoder inputs
- [[TRM_DeveloperNote__N4.1_Integrator_Windup]]
- [[TRM__STM32_Body_Board]] — the hardware this runs on
```
