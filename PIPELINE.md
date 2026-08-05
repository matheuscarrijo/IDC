# Monthly Update Pipeline

This document is written for automated agents executing the IDC monthly update. It contains every detail needed to reproduce the full pipeline without human intervention.

## When to run

**Last calendar day of every month, with retries in the first days of the next month.** The Banco Central do Brasil (BCB) usually publishes the monthly *Estatísticas Monetárias e de Crédito* release during the last week of the nominal release month, but publication can slip into the first days of the following month. The automation must therefore handle both the current nominal release and the previous nominal release when it runs early in a month.

## What the pipeline does

1. Downloads the new monthly BCB release (XLSX table + PDF report) from the BCB website.
2. Rebuilds all three IDC components (C, I, Q) and the aggregate index from scratch.
3. Saves processed CSVs and a consolidated Excel workbook to `data/processed/`.
4. Regenerates the six PNG figures in `outputs/figures/`.
5. Updates the two auto-managed tables and the latest-release narrative in `README.md`.
6. **Generates the monthly update report** as matching `.tex`, `.pdf`, and editable `.docx` files in `outputs/report/update-YYYYMM/` (see [Report generation](#report-generation)).
7. Runs PDF and DOCX content/style/layout reviews and fixes any issues before committing.
8. Creates a git commit with all changed files.

## Release period

The BCB filenames use the **nominal release month**, not necessarily the actual calendar day when the files become available and not the month the IDC data refers to (there is typically a ~2-month data lag). Runs on days 27–31 use the current month in `YYYYMM` format. Retry runs on days 1–7 use only the previous calendar month, keeping every retry in the same release cycle. If that release already exists locally, the cycle has succeeded and the automation stops without attempting another period.

Examples:
- Running on 2026-05-31 → period `202605`
- Running on 2026-06-30 → period `202606`
- Running on 2026-07-02 → period `202606`; stop if that release already exists

To compute candidate periods programmatically:

```python
from datetime import date

today = date.today()
current = today.strftime("%Y%m")
previous_month_year = today.year if today.month > 1 else today.year - 1
previous_month = today.month - 1 if today.month > 1 else 12
previous = f"{previous_month_year}{previous_month:02d}"

# BCB may publish the nominal month-t release in the first days of month t+1.
candidates = [previous] if today.day <= 7 else [current]
```

First check whether the release XLSX already exists under `data/raw/PERIOD/`. If it exists, stop and report that the release cycle has already succeeded. If it is missing locally, attempt to download it; an HTTP 404 means the same period should be retried on the next scheduled date.

## Python environment

The project requires **Python ≥ 3.11** with `pandas`, `openpyxl`, `matplotlib`, `numpy`, and `python-docx`. There is no system-level Python with these packages pre-installed; use `uv` (available at `/opt/homebrew/bin/uv`) to manage the local virtual environment.

```bash
# Create the environment once, then synchronize dependencies on every run:
[ -d .venv ] || uv venv
uv pip install -r requirements.txt
source .venv/bin/activate
```

The `.venv` directory is in `.gitignore` and will not be committed.

## Step-by-step commands

All commands must be run from the repository root (`/Users/matheuslopescarrijo/Documents/Git/IDC`).

### 1. Select the release period

```bash
PERIOD_CANDIDATES_FILE=$(mktemp)
trap 'rm -f "$PERIOD_CANDIDATES_FILE"' EXIT
python3 - <<'PY' > "$PERIOD_CANDIDATES_FILE"
from datetime import date

today = date.today()
current = today.strftime("%Y%m")
if today.month == 1:
    previous = f"{today.year - 1}12"
else:
    previous = f"{today.year}{today.month - 1:02d}"

candidates = [previous] if today.day <= 7 else [current]
for period in candidates:
    print(period)
PY
printf 'Release period candidates:\n'
cat "$PERIOD_CANDIDATES_FILE"
```

### 2. Ensure the Python environment exists

```bash
if [ ! -d ".venv" ]; then
    uv venv
fi
uv pip install -r requirements.txt
source .venv/bin/activate
```

### 3. Download the BCB release

```bash
PERIOD=""
while IFS= read -r CANDIDATE; do
    TABLE="data/raw/${CANDIDATE}/${CANDIDATE}_Tabelas_de_estatisticas_monetarias_e_de_credito.xlsx"
    if [ -f "$TABLE" ]; then
        echo "Release cycle already completed: $CANDIDATE"
        exit 0
    fi

    DOWNLOAD_LOG=$(mktemp)
    if python3 -m src.download_bcb_release "$CANDIDATE" 2>&1 | tee "$DOWNLOAD_LOG"; then
        rm -f "$DOWNLOAD_LOG"
        PERIOD="$CANDIDATE"
        break
    fi

    if ! grep -q "HTTP 404" "$DOWNLOAD_LOG"; then
        echo "Direct BCB download failed; trying the GitHub Actions bridge."
        if ! gh auth status >/dev/null 2>&1; then
            rm -f "$DOWNLOAD_LOG"
            echo "Direct download failed and gh is not authenticated; aborting."
            exit 1
        fi

        if python3 -m src.download_bcb_via_github "$CANDIDATE" 2>&1 | tee -a "$DOWNLOAD_LOG"; then
            rm -f "$DOWNLOAD_LOG"
            PERIOD="$CANDIDATE"
            break
        fi

        if ! grep -q "HTTP 404" "$DOWNLOAD_LOG"; then
            rm -f "$DOWNLOAD_LOG"
            echo "Both direct and GitHub Actions downloads failed for a non-404 reason."
            exit 1
        fi
    fi

    rm -f "$DOWNLOAD_LOG"
    echo "Release not available yet: $CANDIDATE"
done < "$PERIOD_CANDIDATES_FILE"

if [ -z "$PERIOD" ]; then
    echo "The scheduled release was not downloaded."
    exit 0
fi

echo "Selected release period: $PERIOD"
```

This downloads two files into `data/raw/$PERIOD/`:
- `${PERIOD}_Tabelas_de_estatisticas_monetarias_e_de_credito.xlsx`
- `${PERIOD}_Texto_de_estatisticas_monetarias_e_de_credito.pdf`

**If a download fails with HTTP 404:** the BCB has not yet published that nominal release. Do not proceed; report that it is unavailable and retry the same period on the next scheduled run or check manually at `https://www.bcb.gov.br/estatisticas/estatisticasmonetariascredito`.

**If the direct downloader cannot reach the BCB for a non-404 network reason:** use `python3 -m src.download_bcb_via_github PERIOD`. This dispatches `.github/workflows/fetch-bcb-release.yml` on `main`, downloads the untouched official files on a GitHub-hosted runner, validates their XLSX/PDF signatures, and copies the workflow artifact into `data/raw/PERIOD/`. The bridge requires an authenticated `gh` session and the workflow must already exist on the selected GitHub ref. It must not be used to reinterpret an actual HTTP 404 as a network failure.

**If files already exist** (re-run scenario): the release cycle is complete, so stop without modifying files, rebuilding outputs, or creating another branch/PR. Use `--overwrite` only for a deliberate manual recovery outside the scheduled task.

### 4. Rebuild the index and all outputs

```bash
python3 main.py
```

Expected console output ends with a summary like:

```
Índice de Desconforto de Crédito — último dado: <Mmm-YYYY>
     Atual    Média  Desvpad      Mín      Máx
  --------------------------------------------
     X.XXX    X.XXX   X.XXX   X.XXX   X.XXX
```

Verify that "último dado" matches the expected reference month (typically two months before the release month).

#### 4a. Review the README narrative

`python3 main.py` updates the two managed README tables, but the agent must also review and update the surrounding narrative by hand. Before generating the report, inspect `README.md` and ensure that:

- The latest-release heading is succinct and names both the BCB publication month and the IDC reference month, e.g. `## Atualização maio/2026 — competência mar/2026`.
- The paragraph immediately below it names the current BCB release month and the latest calculable IDC month.
- The explanatory paragraph below `<!-- IDC_LATEST_END -->` describes the current IDC value and comparison with the previous month; it must not keep stale text from the prior release.
- Reproduction examples and repository tree examples use the current `PERIOD` when they are intended to illustrate the latest release.
- No stale prior-period strings remain in top-level README prose, except where they are explicitly used as historical comparison or generic examples.

### 5. Generate the monthly report

The analysis and monthly LaTeX filling are performed **by the agent**. After the filled `.tex` is final, the PDF is compiled with LuaLaTeX and the editable DOCX is generated deterministically from that same `.tex`. The filled LaTeX file is the monthly content source of truth; do not maintain an independent Word copy by hand.

#### 5a. Create the report directory and copy assets

```bash
REPORT_DIR="outputs/report/update-${PERIOD}"
mkdir -p "$REPORT_DIR"
cp outputs/report/template-latex/template.tex  "$REPORT_DIR/idc-update-${PERIOD}.tex"
cp outputs/report/template-latex/logo.png      "$REPORT_DIR/logo.png"
cp outputs/figures/index.png                   "$REPORT_DIR/index.png"
cp outputs/figures/components_raw.png          "$REPORT_DIR/components_raw.png"
```

#### 5b. Fill in the report

The agent reads `$REPORT_DIR/idc-update-${PERIOD}.tex` and substitutes every `\placeholder{...}` and `\newcommand` variable in the preamble and body. Two kinds of substitution are required:

**Mechanical (dates and numbers)** — derive from `data/processed/index.csv` and `data/processed/components_raw.csv`:

| LaTeX variable | Value to write | Example |
|---|---|---|
| `\mesreferencia` | Full Portuguese month and year of last data point | `março de 2026` |
| `\mesref` | Abbreviated month-year of last data point | `mar-2026` |
| `\mesanterior` | Abbreviated month-year of the previous data point | `fev-2026` |
| `\competencia` | BCB release period | `202605` |
| `\mespublicacao` | Full Portuguese month and year of the release | `maio de 2026` |
| `\proxdivulgacao` | Next publication month (release month + 1) | `junho de 2026` |
| `\mesproximo` | Next reference month (reference month + 1) | `abr-2026` |
| `\reportdate` | Today's date in full Portuguese | `28 de maio de 2026` |
| `\reportsubtitle` | Must name both publication and reference months | `Nota Técnica de Atualização --- Divulgação maio de 2026; competência março de 2026` |
| IDC table value | Last value of `index` column | `0,954` |
| C raw/norm, I raw/norm, Q raw/norm | Last row of `components_raw.csv` and `index.csv` | `29,3% / 0,968`, … |
| Previous IDC, delta, direction | Compare last two rows of `index.csv` | `1,000`, `0,046`, `recuou` |
| C/I/Q prev→last in bullets | Compare last two rows of `components_raw.csv` | `29,6% → 29,3%` |

**Analysis text** — the agent must write these in Portuguese based on the data:

- `\placeholder{Parágrafo de destaque: ...}` — 1–2 sentences summarising the IDC level and all three components simultaneously, with historical context.
- Three `\placeholder{Contextualização histórica e interpretação econômica.}` items (one per component C, I, Q) — each ≈ 2 sentences: magnitude of change, historical positioning, economic interpretation.
- `\placeholder{Breve caracterização: variação disseminada ou concentrada nos componentes.}` — 1 sentence: was the movement broad-based or driven by one component?
- `\placeholder{Parágrafo de síntese sobre o significado conjunto dos movimentos.}` — 1–2 sentences: what the joint movement means for household credit stress.

**Format rules for the analysis text:**
- Write in formal Brazilian Portuguese.
- Do not invent or extrapolate beyond the numerical data available in the repo.
- Normalised values range [0, 1]: 1.000 = worst in history, 0.000 = best. Always include this context.
- Use comma as decimal separator (e.g. `0,954` not `0.954`).
- Remove each `\placeholder{...}` wrapper and replace the whole command with the written text.
- The report subtitle must make clear that the update/publication month and IDC reference month can differ. Use the pattern `Divulgação <mês de publicação>; competência <mês de referência>`.
- Use `\textbf{}` only for numbers, percentages, deltas, and abbreviated month-year values such as `mar-2026`. Do not bold indicator names, institution names, prose labels, or explanatory phrases in running text.
- Keep every figure's source note inside the same `figure` environment as its `\caption{...}`. Do not place `\fonte{BCB, elaboração própria.}` after `\end{figure}`.
- Preserve the template's annex structure: the main body contains the narrative, table, trajectory discussion, next-update text, and notes; `\clearpage` then starts `Anexo de figuras`. Keep `[H]` on both figures and `\clearpage` between them so each annex page contains exactly one full-width figure.
- Keep report figures at `width=\linewidth`. Do not shrink a chart merely to make it fit. If a full-width chart cannot fit on its annex page with its caption and source, correct the chart's aspect ratio in the plotting code and regenerate it.
- Keep `index.png` approximately square so Figure 1 uses the annex page vertically instead of recreating a large blank gap below a wide chart. The report regression test requires at least 130 mm of rendered height at the fixed 150 mm width.
- The main text must explicitly refer to every figure by number or `\ref{...}` and describe what it shows.

#### 5c. Compile the PDF (if lualatex is available)

```bash
cd "$REPORT_DIR"
if command -v lualatex &> /dev/null; then
    lualatex -interaction=nonstopmode "idc-update-${PERIOD}.tex"
    lualatex -interaction=nonstopmode "idc-update-${PERIOD}.tex"   # second pass for references
    echo "PDF compiled: idc-update-${PERIOD}.pdf"
else
    echo "lualatex not found — .tex file created but PDF not compiled."
fi
cd -
```

If compilation fails, save the `.tex` and report the error. Do not abort the whole pipeline.

#### 5d. Generate the editable DOCX

Generate the Word report only after the filled LaTeX source has no placeholders. The converter supports the commands and report structure in `outputs/report/template-latex/template.tex`; it preserves the same cover, headings, table, prose emphasis, bullets, figures, captions, source notes, notes, and citation as editable Word content.

```bash
python3 -m src.build_report_docx \
    "$REPORT_DIR/idc-update-${PERIOD}.tex" \
    "$REPORT_DIR/idc-update-${PERIOD}.docx" \
    --assets-dir "$REPORT_DIR" \
    --require-filled
```

The reusable Word template at `outputs/report/template-docx/template.docx` is generated from the versioned LaTeX template with:

```bash
python3 -m src.build_report_docx \
    outputs/report/template-latex/template.tex \
    outputs/report/template-docx/template.docx \
    --assets-dir outputs/report/template-latex
```

Regenerate the Word template whenever `template.tex`, the logo, or `src/build_report_docx.py` changes. Do not edit the generated template independently; otherwise it can drift from the LaTeX design.

#### 5e. Report style and layout review

After the PDF and DOCX are created, Codex must perform a dedicated style and layout review before any commit. This pass is separate from the data-writing pass: the agent should treat the final `.tex`, LaTeX log, rendered PDF, editable DOCX, and a DOCX-to-PDF render as publication artifacts, inspect them directly, and make any layout or style corrections itself.

The reviewing agent must read the `.tex`, inspect the LaTeX log, render every PDF page, render every DOCX page to PNG (prefer the bundled Documents skill `render_docx.py` with `--emit_pdf`), and inspect all pages at 100% zoom. Fix the `.tex` first when the content is wrong; regenerate the DOCX after every `.tex` change. Fix `src/build_report_docx.py` only when the editable Word rendering is wrong. Repeat until all of the following are true:

- `\textbf{}` appears only around numbers, percentages, deltas, or abbreviated month-year values.
- Figures do not float through the report body: the explicit annex, `[H]`, and inter-figure `\clearpage` keep exactly one full-width figure on each annex page.
- Every figure is referenced coherently in the main text.
- Each figure keeps its chart, caption, and source note together.
- No source note is duplicated, stranded after a float, or separated from its figure.
- Captions and source notes do not collide with text.
- No figure has been reduced below full text width to conceal a pagination problem; an over-tall figure is corrected at its source instead.
- The LaTeX log contains no `! LaTeX Error`.
- Any `Overfull \hbox` warning in the report body or tables has been inspected by Codex and fixed when it affects the rendered layout.
- The DOCX contains the same title, subtitle, authors, dates, section text, numerical values, table rows, bullets, captions, sources, notes, and citation as the filled `.tex` and PDF.
- The DOCX is genuinely editable: body text remains Word paragraphs, the results remain a Word table, and charts remain embedded images rather than full-page screenshots.
- The DOCX uses A4 pages and retains the intended five-page organization for both template and filled report: cover; results; remaining narrative/notes; annex Figure 1; annex Figure 2. Figure paragraphs, captions, and source notes use Word keep-with-next/keep-together controls, and explicit page breaks enforce one figure per annex page.
- The DOCX render has no clipped or overlapping text, broken table rows, missing glyphs, cropped charts, incorrect page numbers, or misplaced headers/footers.
- The final `.docx` is non-empty, opens successfully, and contains no red template placeholders.

If the review changes the `.tex`, compile twice again, regenerate the DOCX, and repeat both reviews. Do not commit, push, or open a PR until the PDF and DOCX review passes are clean.

---

### 6. Commit

Stage exactly these files — do **not** use `git add .` as it may pick up unintended artefacts:

```bash
git add README.md \
        data/processed/series_raw.csv \
        data/processed/components_raw.csv \
        data/processed/index.csv \
        data/processed/idc_data.xlsx \
        outputs/figures/components_raw.png \
        outputs/figures/components_raw_c.png \
        outputs/figures/components_raw_i.png \
        outputs/figures/components_raw_q.png \
        outputs/figures/components_normalized.png \
        outputs/figures/index.png

# These paths are intentionally ignored by default, but monthly updates must
# explicitly version the release inputs and the generated report for the period.
git add -f data/raw/"$PERIOD"/ \
           outputs/report/update-"$PERIOD"/
```

Also stage `main.py` only if `git diff main.py` shows changes.

Commit message format:

```
data: update IDC to <PERIOD> BCB release (<Mmm-YYYY>)

<one sentence describing the new index value and any notable change>
```

Example:

```
data: update IDC to 202605 BCB release (Mar-2026)

IDC reaches 0.954 (vs 1.000 in Feb-2026); all three components retreated.
```

---

## Verification checklist

After `python3 main.py` completes, verify:

- [ ] "último dado" in the console summary is the expected reference month.
- [ ] `data/processed/index.csv` — last row date matches the reference month.
- [ ] `outputs/figures/index.png` — file modification timestamp is today.
- [ ] `README.md` — the two auto-managed tables (between `<!-- IDC_LATEST_START/END -->` and `<!-- IDC_STATS_START/END -->`) show the new date and values.
- [ ] `README.md` — the latest-release narrative around the managed tables has been manually reviewed and updated for the new release/reference month.
- [ ] `outputs/report/update-PERIOD/idc-update-PERIOD.tex` — no `\placeholder{...}` commands remain.
- [ ] `outputs/report/update-PERIOD/idc-update-PERIOD.pdf` — PDF compiled successfully (if lualatex available).
- [ ] `outputs/report/update-PERIOD/idc-update-PERIOD.docx` — editable Word report generated from the filled `.tex`, non-empty, and opens successfully.
- [ ] Codex style review of the filled `.tex` passes: bold is restricted to numbers, percentages, deltas, and abbreviated month-year values.
- [ ] Codex layout review of the final PDF passes: figures are referenced coherently from the text, captions and source notes are together, no source note is duplicated, and no visually relevant LaTeX overfull warning remains.
- [ ] Codex content/layout review of the rendered DOCX passes: content matches the `.tex`/PDF, all pages were inspected, charts are uncropped, the table remains editable, and no layout defect or template placeholder remains.

## Repository layout (relevant paths)

```
IDC/
├── main.py                          # Full pipeline orchestrator (one command)
├── requirements.txt                 # pandas, openpyxl, matplotlib, numpy, python-docx
├── src/
│   ├── build_report_docx.py         # Filled IDC LaTeX report → editable DOCX
│   ├── download_bcb_release.py      # BCB HTTP downloader
│   ├── load_data.py                 # find_latest_bcb_table() auto-detects newest raw dir
│   ├── build_index.py               # C, I, Q components + expanding min-max normalisation
│   ├── normalize.py                 # Expanding min-max (no lookahead)
│   └── plot.py                      # Generates 6 PNGs
├── data/
│   ├── raw/YYYYMM/                  # One dir per BCB release, auto-detected by load_data.py
│   └── processed/                   # Generated: *.csv, idc_data.xlsx
├── outputs/figures/                 # Generated: 6 PNGs
└── outputs/report/
    ├── template-latex/              # Versioned LaTeX template and logo
    │   ├── template.tex             # Master template with \placeholder{} variables
    │   └── logo.png                 # FGV logo
    ├── template-docx/               # Word mirror generated from template.tex
    │   ├── template.docx            # Editable A4 Word template
    │   └── README.md                # Regeneration and fidelity notes
    └── update-YYYYMM/              # Monthly report (committed)
        ├── idc-update-YYYYMM.tex   # Filled LaTeX source
        ├── idc-update-YYYYMM.pdf   # Compiled PDF
        ├── idc-update-YYYYMM.docx  # Editable Word report generated from the .tex
        ├── index.png               # Copy of main IDC chart
        └── components_raw.png      # Copy of components chart
```

## How `load_data.py` picks the right file

`find_latest_bcb_table()` scans `data/raw/` for subdirectories matching `\d{6}`, sorts them lexicographically, and picks the last one. No configuration needed — downloading a new `PERIOD` directory is sufficient for it to be picked up automatically on the next `python3 main.py` run.

## Error scenarios

| Symptom | Likely cause | Action |
|---|---|---|
| HTTP 404 on download | BCB release candidate not yet published | Try the next candidate; if all candidates fail with 404, abort and retry next scheduled run |
| DNS or socket failure reaching BCB | Local runner has no outbound access | If `gh auth status` succeeds, run `python3 -m src.download_bcb_via_github PERIOD`; otherwise report the infrastructure blocker |
| `ModuleNotFoundError: No module named 'pandas'` | `.venv` missing or not activated | Run `uv venv && uv pip install -r requirements.txt` |
| `ModuleNotFoundError: No module named 'docx'` | Updated requirements were not installed | Run `uv pip install -r requirements.txt` in the active environment |
| DOCX generation rejects `\placeholder{...}` | The monthly `.tex` is still an unfilled template | Fill every monthly placeholder, rerun the LaTeX checks, then regenerate the DOCX |
| DOCX chart is clipped or pagination differs unexpectedly | Word/LibreOffice layout needs review | Render the DOCX to PNG, fix `src/build_report_docx.py` or tighten prose/spacing without dropping content, regenerate, and inspect every page |
| Figure is too tall at full width | The source chart aspect ratio cannot fit its annex page | Adjust the figure dimensions in `src/plot.py` and regenerate the PNG; do not reduce the figure until labels become hard to read |
| `RuntimeError: Bloco automático do IDC não encontrado no README.md` | README markers were accidentally removed | Restore `<!-- IDC_LATEST_START -->` / `<!-- IDC_LATEST_END -->` and `<!-- IDC_STATS_START -->` / `<!-- IDC_STATS_END -->` markers in README.md |
| Index value unchanged from prior month | New XLSX may contain same data (BCB sometimes re-publishes) | Compare `data/raw/PERIOD/` file size against prior period; flag for human review |
