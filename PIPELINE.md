# Monthly Update Pipeline

This document is written for automated agents executing the IDC monthly update. It contains every detail needed to reproduce the full pipeline without human intervention.

## When to run

**Last calendar day of every month.** The Banco Central do Brasil (BCB) publishes the monthly *Estatísticas Monetárias e de Crédito* release sometime during the last week of the month. Running on the last day maximises the probability that the release is already available.

## What the pipeline does

1. Downloads the new monthly BCB release (XLSX table + PDF report) from the BCB website.
2. Rebuilds all three IDC components (C, I, Q) and the aggregate index from scratch.
3. Saves processed CSVs and a consolidated Excel workbook to `data/processed/`.
4. Regenerates the six PNG figures in `outputs/figures/`.
5. Updates the two auto-managed tables and the latest-release narrative in `README.md`.
6. **Generates the monthly update report** in `outputs/report/update-YYYYMM/` (see [Report generation](#report-generation)).
7. Runs a report style/layout review and fixes any issues before committing.
8. Creates a git commit with all changed files.

## Release period

The BCB names each release by the **calendar month it is published**, not the month the data refers to (there is typically a ~2-month data lag). The period argument is always **the current month** in `YYYYMM` format.

Examples:
- Running on 2026-05-31 → period `202605`
- Running on 2026-06-30 → period `202606`

To compute it programmatically:

```python
from datetime import date
period = date.today().strftime("%Y%m")   # e.g. "202605"
```

## Python environment

The project requires **Python ≥ 3.11** with `pandas`, `openpyxl`, `matplotlib`, and `numpy`. There is no system-level Python with these packages pre-installed; use `uv` (available at `/opt/homebrew/bin/uv`) to manage the local virtual environment.

```bash
# First run (or if .venv is missing):
uv venv
uv pip install -r requirements.txt

# Every run:
source .venv/bin/activate
```

The `.venv` directory is in `.gitignore` and will not be committed.

## Step-by-step commands

All commands must be run from the repository root (`/Users/matheuslopescarrijo/Documents/Git/IDC`).

### 1. Set the release period

```bash
PERIOD=$(python3 -c "from datetime import date; print(date.today().strftime('%Y%m'))")
echo "Release period: $PERIOD"
```

### 2. Ensure the Python environment exists

```bash
if [ ! -d ".venv" ]; then
    uv venv
    uv pip install -r requirements.txt
fi
source .venv/bin/activate
```

### 3. Download the BCB release

```bash
python3 -m src.download_bcb_release "$PERIOD"
```

This downloads two files into `data/raw/$PERIOD/`:
- `${PERIOD}_Tabelas_de_estatisticas_monetarias_e_de_credito.xlsx`
- `${PERIOD}_Texto_de_estatisticas_monetarias_e_de_credito.pdf`

**If the download fails with HTTP 404:** the BCB has not yet published this month's release. Do not proceed. Retry in 24 hours or check manually at `https://www.bcb.gov.br/estatisticas/estatisticasmonetariascredito`.

**If files already exist** (re-run scenario): the script skips them by default. Add `--overwrite` to force re-download.

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

- `## Última Divulgação` names the latest calculable reference month.
- The paragraph immediately below it names the current BCB release month and the latest calculable IDC month.
- The explanatory paragraph below `<!-- IDC_LATEST_END -->` describes the current IDC value and comparison with the previous month; it must not keep stale text from the prior release.
- Reproduction examples and repository tree examples use the current `PERIOD` when they are intended to illustrate the latest release.
- No stale prior-period strings remain in top-level README prose, except where they are explicitly used as historical comparison or generic examples.

### 5. Generate the monthly report

This step is performed **by the agent** (not by a script). After running the pipeline, the agent reads the processed data, writes the report, and compiles the PDF.

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
- Use `\textbf{}` only for numbers, percentages, deltas, and abbreviated month-year values such as `mar-2026`. Do not bold indicator names, institution names, prose labels, or explanatory phrases in running text.
- Keep every figure's source note inside the same `figure` environment as its `\caption{...}`. Do not place `\fonte{BCB, elaboração própria.}` after `\end{figure}`, because the figure may float away from its source note and create duplicate-looking layout.
- The main text must explicitly refer to every figure by number or `\ref{...}` and describe what it shows. Do not write prose that depends on the figure appearing immediately after the paragraph; LaTeX floats may move figures to later pages.

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

#### 5d. Report style and layout review

After the PDF is compiled, Codex must perform a dedicated style and layout review before any commit. This pass is separate from the data-writing pass: the agent should treat the final `.tex`, LaTeX log, and rendered PDF as a publication artifact, inspect them directly, and make any layout or style corrections itself.

The reviewing agent must read the `.tex`, inspect the LaTeX log, and render page previews of the PDF when possible. Fix the `.tex` and re-run `lualatex` twice until all of the following are true:

- `\textbf{}` appears only around numbers, percentages, deltas, or abbreviated month-year values.
- Figures may float across pages, but the prose must not depend on immediate physical placement.
- Every figure is referenced in the main text in a way that remains coherent even if LaTeX moves the float to a later page.
- Each figure keeps its chart, caption, and source note together.
- No source note is duplicated, stranded after a float, or separated from its figure.
- Captions and source notes do not collide with text.
- The LaTeX log contains no `! LaTeX Error`.
- Any `Overfull \hbox` warning in the report body or tables has been inspected by Codex and fixed when it affects the rendered layout.

If the review changes the `.tex`, compile twice again and repeat this review. Do not commit, push, or open a PR until the layout-review pass is clean.

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
- [ ] Codex style review of the filled `.tex` passes: bold is restricted to numbers, percentages, deltas, and abbreviated month-year values.
- [ ] Codex layout review of the final PDF passes: figures are referenced coherently from the text, captions and source notes are together, no source note is duplicated, and no visually relevant LaTeX overfull warning remains.

## Repository layout (relevant paths)

```
IDC/
├── main.py                          # Full pipeline orchestrator (one command)
├── requirements.txt                 # pandas, openpyxl, matplotlib, numpy
├── src/
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
    └── update-YYYYMM/              # Monthly report (committed)
        ├── idc-update-YYYYMM.tex   # Filled LaTeX source
        ├── idc-update-YYYYMM.pdf   # Compiled PDF
        ├── index.png               # Copy of main IDC chart
        └── components_raw.png      # Copy of components chart
```

## How `load_data.py` picks the right file

`find_latest_bcb_table()` scans `data/raw/` for subdirectories matching `\d{6}`, sorts them lexicographically, and picks the last one. No configuration needed — downloading a new `PERIOD` directory is sufficient for it to be picked up automatically on the next `python3 main.py` run.

## Error scenarios

| Symptom | Likely cause | Action |
|---|---|---|
| HTTP 404 on download | BCB release not yet published | Abort; retry next day |
| `ModuleNotFoundError: No module named 'pandas'` | `.venv` missing or not activated | Run `uv venv && uv pip install -r requirements.txt` |
| `RuntimeError: Bloco automático do IDC não encontrado no README.md` | README markers were accidentally removed | Restore `<!-- IDC_LATEST_START -->` / `<!-- IDC_LATEST_END -->` and `<!-- IDC_STATS_START -->` / `<!-- IDC_STATS_END -->` markers in README.md |
| Index value unchanged from prior month | New XLSX may contain same data (BCB sometimes re-publishes) | Compare `data/raw/PERIOD/` file size against prior period; flag for human review |
