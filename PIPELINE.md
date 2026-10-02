# Monthly Update Pipeline

This document is written for automated agents executing the IDC monthly update. It contains every detail needed to reproduce the full pipeline without human intervention.

## When to run

**Days 27–31 of each month, with retries on days 1–7 of the next month.** The Banco Central do Brasil (BCB) usually publishes the monthly *Estatísticas Monetárias e de Crédito* release during the last week of the nominal release month, but publication can slip into the first days of the following month. Late-month runs use the current nominal month; early-month retries continue using only the previous nominal month.

## What the pipeline does

1. Downloads the new monthly BCB release (XLSX table + PDF report) from the BCB website.
2. Rebuilds all three IDC components (C, I, Q) and the aggregate index from scratch.
3. Saves processed CSVs and a consolidated Excel workbook to `data/processed/`.
4. Regenerates the six PNG figures in `outputs/figures/`.
5. Updates the two auto-managed tables and the latest-release narrative in `README.md`.
6. **Generates the monthly update report** as matching `.tex`, `.pdf`, and editable `.docx` files in `outputs/report/update-YYYYMM/` (see [Report generation](#5-generate-the-monthly-report)).
7. Runs PDF and DOCX content/style/layout reviews and fixes any issues before committing.
8. Creates a git commit with the updated data, figures, documentation, and final monthly PDF. Report sources, build files, DOCX files, copied images, revision audits, and templates stay local and are ignored by Git.

## Release period

The BCB filenames use the **nominal release month**, not necessarily the actual calendar day when the files become available and not the month the IDC data refers to (there is typically a ~2-month data lag). Runs on days 27–31 use the current month in `YYYYMM` format. Retry runs on days 1–7 use only the previous calendar month, keeping every retry in the same release cycle. If that release already exists locally, the cycle has succeeded and the automation stops without attempting another period.

Examples:
- Running on 2026-05-31 → period `202605`
- Running on 2026-06-30 → period `202606`
- Running on 2026-07-02 → period `202606`; stop if that release already exists

To compute the scheduled period programmatically:

```python
from datetime import date

today = date.today()
current = today.strftime("%Y%m")
previous_month_year = today.year if today.month > 1 else today.year - 1
previous_month = today.month - 1 if today.month > 1 else 12
previous = f"{previous_month_year}{previous_month:02d}"

# BCB may publish the nominal month-t release in the first days of month t+1.
period = previous if today.day <= 7 else current
```

After synchronizing local `main` with `origin/main` as described in the preflight below, check whether the release XLSX already exists under `data/raw/PERIOD/`. If it exists, stop and report that the release cycle has already succeeded. If it is missing locally, attempt to download it; an HTTP 404 means the same period should be retried on the next scheduled date.

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

### 0. Synchronize local `main`

Before calculating the release period, checking for local release files, downloading data, or modifying anything, require a clean working tree and fast-forward local `main` from GitHub:

```bash
if [ -n "$(git status --porcelain)" ]; then
    echo "Working tree is not clean; aborting before synchronization."
    git status --short
    exit 1
fi

if ! git switch main; then
    echo "Could not switch to local main; aborting."
    exit 1
fi

if ! git fetch --prune origin main; then
    echo "Could not fetch origin/main; aborting rather than using stale local state."
    exit 1
fi

if ! git merge --ff-only origin/main; then
    echo "Local main cannot be fast-forwarded to origin/main; aborting for manual reconciliation."
    exit 1
fi
```

The order is mandatory: clean-tree check, switch to `main`, fetch, fast-forward, and only then the release-file check. If any preflight command fails, stop and report the failure. Never continue the pipeline from stale local state, and never reset, rebase, or force-update `main` automatically.

### 1. Select the release period

```bash
PERIOD=$(python3 - <<'PY'
from datetime import date

today = date.today()
current = today.strftime("%Y%m")
if today.month == 1:
    previous = f"{today.year - 1}12"
else:
    previous = f"{today.year}{today.month - 1:02d}"

print(previous if today.day <= 7 else current)
PY
)
printf 'Scheduled release period: %s\n' "$PERIOD"
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
TABLE="data/raw/${PERIOD}/${PERIOD}_Tabelas_de_estatisticas_monetarias_e_de_credito.xlsx"
if [ -f "$TABLE" ]; then
    echo "Release cycle already completed: $PERIOD"
    exit 0
fi

DOWNLOAD_LOG=$(mktemp)
if python3 -m src.download_bcb_release "$PERIOD" 2>&1 | tee "$DOWNLOAD_LOG"; then
    rm -f "$DOWNLOAD_LOG"
elif grep -q "HTTP 404" "$DOWNLOAD_LOG"; then
    rm -f "$DOWNLOAD_LOG"
    echo "Release not available yet: $PERIOD"
    exit 0
else
    echo "Direct BCB download failed; trying the GitHub Actions bridge."
    if ! gh auth status >/dev/null 2>&1; then
        rm -f "$DOWNLOAD_LOG"
        echo "Direct download failed and gh is not authenticated; aborting."
        exit 1
    fi

    if python3 -m src.download_bcb_via_github "$PERIOD" 2>&1 | tee -a "$DOWNLOAD_LOG"; then
        rm -f "$DOWNLOAD_LOG"
    elif grep -q "HTTP 404" "$DOWNLOAD_LOG"; then
        rm -f "$DOWNLOAD_LOG"
        echo "Release not available yet: $PERIOD"
        exit 0
    else
        rm -f "$DOWNLOAD_LOG"
        echo "Both direct and GitHub Actions downloads failed for a non-404 reason."
        exit 1
    fi
fi

echo "Selected release period: $PERIOD"
```

This downloads two files into `data/raw/$PERIOD/`:
- `${PERIOD}_Tabelas_de_estatisticas_monetarias_e_de_credito.xlsx`
- `${PERIOD}_Texto_de_estatisticas_monetarias_e_de_credito.pdf`

**If a download fails with HTTP 404:** the BCB has not yet published that nominal release. Do not proceed; report that it is unavailable and retry the same period on the next scheduled run or check manually at `https://www.bcb.gov.br/estatisticas/estatisticasmonetariascredito`.

**If the direct downloader cannot reach the BCB for a non-404 network reason:** use `python3 -m src.download_bcb_via_github PERIOD`. This dispatches `.github/workflows/fetch-bcb-release.yml` on `main`, downloads the untouched official files on a GitHub-hosted runner, validates their XLSX/PDF signatures, and copies the workflow artifact into `data/raw/PERIOD/`. The bridge requires an authenticated `gh` session and the workflow must already exist on the selected GitHub ref. It must not be used to reinterpret an actual HTTP 404 as a network failure.

**If files already exist** (re-run scenario): the release cycle is complete, so stop without modifying files, rebuilding outputs, or creating another branch/PR. Use `--overwrite` only for a deliberate manual recovery outside the scheduled task.

### 3a. Audit revisions between BCB releases

Before rebuilding the index, compare the new workbook with the immediately preceding
release already stored in `data/raw/`. The comparator distinguishes changes inside
the preceding release's historical coverage — revisions and retroactive backfills —
from genuinely new observations:

```bash
python3 -m src.compare_releases "$PERIOD"
```

The output identifies every revised raw observation and lists every overlapping
reference month whose IDC changes when recalculated under the current vintage, with
the prior value, recalculated value, and difference. Preserve this complete output as
the technical audit; public-disclosure materiality is a separate downstream decision.
If there is no preceding workbook, state that the revision audit is unavailable for
that cycle; do not describe the absence of a comparison as evidence that the BCB made
no revisions.

For month-over-month analysis, always compare the last two IDC observations rebuilt
from the **current** workbook, so both months use one internally consistent vintage.
Never raise the audit tolerance to implement editorial materiality.

For public disclosure, apply the strict two-part rule implemented by
`quantify_revision_magnitude` and `assess_revision_materiality`:

1. A routine revision must change at least one IDC value by **0.010 point** or more,
   measured either against the immediately preceding vintage or as a net cumulative
   change since the last vintage whose revisions were publicly disclosed.
2. It must also affect an element actually discussed in the report: the current
   month-over-month comparison, a cited record, a sequence, a component attribution,
   the historical trajectory described in prose, or the conclusion.

Do not use a relative-percentage trigger. A small revision is not public merely because
the current monthly movement is also small. Qualitative overrides may independently
require disclosure when a revision reverses the reported sign, creates or removes a
record, invalidates a published statement, changes the IDC methodology, changes the
source definition or coverage, or corrects a relevant error. A broad source
reprocessing is not automatically public: disclose it
when its effect on the final IDC meets the magnitude rule and materially changes the
trajectory or interpretation.
Treat a record override as a change to a record that is actually cited or relevant to
the interpretation; a normalized component merely touching `1.000` mechanically is not
by itself a public-disclosure trigger.

The following executable pattern keeps the consecutive and cumulative checks explicit.
Set the editorial flags only after reviewing the current draft and prior public claims;
`LAST_DISCLOSED_PERIOD` is the vintage named in the most recent earlier report that
actually contained a public `Revisões dos dados` section:

```python
from src.compare_releases import (
    RevisionEditorialContext,
    assess_revision_materiality,
    compare_release_vintages,
    compare_releases,
    idc_revision_deltas_by_date,
    quantify_revision_magnitude,
)

PERIOD = "YYYYMM"
LAST_DISCLOSED_PERIOD = "YYYYMM"

consecutive = compare_releases(PERIOD)
cumulative = compare_release_vintages(LAST_DISCLOSED_PERIOD, PERIOD)
facts = quantify_revision_magnitude(
    consecutive,
    cumulative_idc_deltas_since_last_disclosure=(
        idc_revision_deltas_by_date(cumulative)
    ),
)
context = RevisionEditorialContext(
    affects_relevant_element=False,  # change only when report evidence supports it
)
decision = assess_revision_materiality(facts, context)

print("consecutive_max=", facts.largest_current_absolute_delta)
print("cumulative_max=", facts.largest_cumulative_absolute_delta)
print("publicly_material=", decision.is_publicly_material)
print("routine_rule_met=", decision.routine_rule_met)
print("qualitative_overrides=", decision.qualitative_overrides)
```

If no revision has ever been publicly disclosed, use the earliest comparable stored
vintage as the cumulative baseline and document that choice in the technical audit.
The cumulative check is unnecessary only when there is no earlier comparable workbook.

If the decision is publicly material, add a short `Revisões dos dados` section. Its
table contains only the material reference months and any additional comparison-base
row strictly needed to explain the current-vintage monthly change. Show public values
with three decimal places; retain all raw and IDC revisions at full precision in the
technical audit. If the decision is not material, omit the section entirely; the fixed
methodological note under `Notas` explains that the published series still incorporates
every revision.

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

Report generation requires the local master template at `outputs/report/template-latex/template.tex` and its `logo.png`. Templates and all report auxiliaries are intentionally absent from GitHub. Supply these files locally when setting up a fresh clone; preserve them on the pipeline host. Only `outputs/report/update-YYYYMM/idc-update-YYYYMM.pdf` is committed after review.

#### 5a. Create the report directory and copy assets

```bash
for REPORT_ASSET in template.tex logo.png; do
    if [ ! -f "outputs/report/template-latex/$REPORT_ASSET" ]; then
        echo "Missing local report asset: outputs/report/template-latex/$REPORT_ASSET"
        exit 1
    fi
done

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
| `\reportdate` | Nominal BCB publication/release month in full Portuguese, initial capital, without the day | `Maio de 2026` |
| `\reportsubtitle` | Must name both publication and reference months | `Nota Técnica de Atualização --- Divulgação maio de 2026; competência março de 2026` |
| IDC table value | Last value of `index` column | `0,954` |
| C raw/norm, I raw/norm, Q raw/norm | Last row of `components_raw.csv` and `index.csv` | `29,3% / 0,968`, … |
| Previous IDC, delta, direction | Compare last two rows of `index.csv` | `1,000`, `0,046`, `recuou` |
| C/I/Q prev→last in bullets | Compare last two rows of `components_raw.csv` | `29,6% → 29,3%` |
| Revision disclosure | Audit with `compare_releases`; assess with `quantify_revision_magnitude` + `assess_revision_materiality` | Strict `0.010` + editorial relevance, with explicit qualitative overrides |

**Analysis text** — the agent must write these in Portuguese based on the data:

- `\placeholder{Parágrafo de destaque: ...}` — 1–2 sentences summarising the IDC level and all three components simultaneously, with historical context.
- Three `\placeholder{Contextualização histórica e interpretação econômica.}` items (one per component C, I, Q) — each ≈ 2 sentences: magnitude of change, historical positioning, economic interpretation.
- `\placeholder{Breve caracterização: variação disseminada ou concentrada nos componentes.}` — 1 sentence: was the movement broad-based or driven by one component?
- `\placeholder{Parágrafo de síntese sobre o significado conjunto dos movimentos.}` — 1–2 sentences: what the joint movement means for household credit stress.
- `Revisões dos dados` is **absent from the template by default**. Add it between `Resultados` and `Trajetória do índice` only when the strict public-materiality decision is positive. Name the compared BCB releases and explain the material effect on the IDC. The table contains only material months and any indispensable comparison-base row, with prior-vintage IDC, current-vintage recalculation, difference, and three decimal places. When the section is present, distinguish the homogeneous current-vintage monthly change from a comparison with the value printed in the preceding report. When the decision is negative, omit the section and any “no revisions” boilerplate.

**Format rules for the analysis text:**
- Write in formal Brazilian Portuguese.
- Do not invent or extrapolate beyond the numerical data available in the repo.
- Normalised values range [0, 1]: 1.000 = worst in history, 0.000 = best. Always include this context.
- Use comma as decimal separator (e.g. `0,954` not `0.954`).
- Remove each `\placeholder{...}` wrapper and replace the whole command with the written text.
- The report subtitle must make clear that the update/publication month and IDC reference month can differ. Use the pattern `Divulgação <mês de publicação>; competência <mês de referência>`.
- The cover date (`\reportdate`) uses the nominal BCB publication/release month in `Mês de AAAA` format, with an initial capital and no day (e.g. `Setembro de 2026` for release `202609`). It must agree with `\mespublicacao`, even if the report is generated during a retry in the following month; do not use today's date or the IDC observation month. Keep the observation months in the body, tables, captions, and charts tied to the actual data.
- A month-over-month figure in the results section must use two observations from the current BCB vintage. Never mix vintages. Explain the difference from the value printed in the prior report only when the revision is publicly material and `Revisões dos dados` is present; otherwise the fixed methodological note is sufficient.
- Use `\textbf{}` only for numbers, percentages, deltas, and abbreviated month-year values such as `mar-2026`. Do not bold indicator names, institution names, prose labels, or explanatory phrases in running text.
- Keep every figure's source note inside the same `figure` environment as its `\caption{...}`. Do not place `\fonte{BCB, elaboração própria.}` after `\end{figure}`.
- Preserve the template's annex structure: the main body contains the narrative, table, trajectory discussion, next-update text, and notes; `\clearpage` then starts `Anexo de figuras`. Keep `[H]` on both figures and `\clearpage` between them so each annex page contains exactly one full-width figure.
- The report has no fixed page count. Let the main body use as many pages as its content requires; never reduce type below the template sizes merely to meet a page target.
- Keep `Notas` at `\footnotesize` in LaTeX (9 pt in the 11 pt document class) and at no less than 9 pt in the generated DOCX. `\tiny`, `\scriptsize`, and explicit font sizes below 9 pt are forbidden in that section.
- Let `Notas` break naturally between body pages. Do not force the whole section onto a new page or keep it as an indivisible block, since either choice can create unnecessary blank space after the preceding section.
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

The local reusable Word template at `outputs/report/template-docx/template.docx` is generated from the local LaTeX template with:

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
- The DOCX uses A4 pages and lets the report body flow across as many pages as necessary without reducing the prescribed font sizes. `Anexo de figuras` always starts on a new page, even if it could fit after `Notas`; explicit page breaks keep one full-width figure on each annex page. Figure paragraphs, captions, and source notes use Word keep-with-next/keep-together controls.
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

# Only the two official BCB inputs are force-added from the ignored raw folder.
git add -f data/raw/"$PERIOD"/"${PERIOD}_Tabelas_de_estatisticas_monetarias_e_de_credito.xlsx" \
           data/raw/"$PERIOD"/"${PERIOD}_Texto_de_estatisticas_monetarias_e_de_credito.pdf"

# The final monthly PDF is explicitly allowed by .gitignore.
git add "outputs/report/update-${PERIOD}/idc-update-${PERIOD}.pdf"
```

Never force-add a report directory or its auxiliaries. Inspect `git diff --cached --name-only -- outputs/report/` before committing: report additions and modifications must be final monthly PDFs only. Keep the `.tex`, `.docx`, LaTeX build files, `logo.png`, `index.png`, `components_raw.png`, revision audits, and all templates local.

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
- [ ] `python3 -m src.compare_releases PERIOD` — revision audit completed against the immediately preceding BCB workbook; newly added observations were not misclassified as revisions.
- [ ] The technical audit retains every revision at full precision, and the public-materiality decision is recorded separately. A routine section exists only when `|revision| >= 0.010` **and** the report's interpretation is affected, unless an explicit qualitative override applies. The table contains only material or indispensable comparison-base rows at three decimal places.
- [ ] The fixed note beginning `Revisões dos dados. Os valores históricos do IDC...` is present under `Notas`, whether or not the optional public section exists.
- [ ] `outputs/report/update-PERIOD/idc-update-PERIOD.tex` — no `\placeholder{...}` commands remain.
- [ ] `outputs/report/update-PERIOD/idc-update-PERIOD.pdf` — PDF compiled successfully (if lualatex available).
- [ ] `outputs/report/update-PERIOD/idc-update-PERIOD.docx` — editable Word report generated from the filled `.tex`, non-empty, and opens successfully.
- [ ] Codex style review of the filled `.tex` passes: bold is restricted to numbers, percentages, deltas, and abbreviated month-year values.
- [ ] Codex layout review of the final PDF passes: figures are referenced coherently from the text, captions and source notes are together, no source note is duplicated, and no visually relevant LaTeX overfull warning remains.
- [ ] Codex content/layout review of the rendered DOCX passes: content matches the `.tex`/PDF, all pages were inspected, charts are uncropped, the table remains editable, and no layout defect or template placeholder remains.
- [ ] Only final monthly PDFs under `outputs/report/` are staged for publication; templates and report auxiliaries remain local and ignored.

Tests that require local report sources or assets explicitly skip when those files are absent, as in a fresh GitHub clone. On the report-generation host, keep those local files available so the complete report checks run.

## Repository layout (relevant paths)

```
IDC/
├── main.py                          # Full pipeline orchestrator (one command)
├── requirements.txt                 # pandas, openpyxl, matplotlib, numpy, python-docx
├── src/
│   ├── build_report_docx.py         # Filled IDC LaTeX report → editable DOCX
│   ├── compare_releases.py           # Consecutive BCB vintages → revision audit
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
    ├── template-latex/              # Local only: LaTeX template and logo
    │   ├── template.tex             # Master template with \placeholder{} variables
    │   └── logo.png                 # FGV logo
    ├── template-docx/               # Local only: Word mirror of template.tex
    │   ├── template.docx            # Editable A4 Word template
    │   └── README.md                # Regeneration and fidelity notes
    └── update-YYYYMM/               # Only the final PDF is committed
        ├── idc-update-YYYYMM.tex    # Local filled LaTeX source
        ├── idc-update-YYYYMM.pdf    # Reviewed final PDF (committed)
        ├── idc-update-YYYYMM.docx   # Local editable Word report
        ├── logo.png                # Local copy of the logo
        ├── index.png               # Local copy of the main IDC chart
        ├── components_raw.png      # Local copy of the components chart
        └── revision-audit-YYYYMM.txt # Local full-precision revision audit
```

## How `load_data.py` picks the right file

`find_latest_bcb_table()` scans `data/raw/` for subdirectories matching `\d{6}`, sorts them lexicographically, and picks the last one. No configuration needed — downloading a new `PERIOD` directory is sufficient for it to be picked up automatically on the next `python3 main.py` run.

## Error scenarios

| Symptom | Likely cause | Action |
|---|---|---|
| Working tree is dirty before the preflight | Another task or the user has uncommitted changes | Stop and report `git status --short`; do not switch branches or modify files |
| Fetch fails or local `main` cannot fast-forward to `origin/main` | Network/authentication failure or divergent local history | Stop and report the exact failure; never continue from stale state or reset/rebase automatically |
| HTTP 404 on download | Scheduled BCB release not yet published | Stop without modifying files and retry the same period on the next scheduled run |
| DNS or socket failure reaching BCB | Local runner has no outbound access | If `gh auth status` succeeds, run `python3 -m src.download_bcb_via_github PERIOD`; otherwise report the infrastructure blocker |
| `ModuleNotFoundError: No module named 'pandas'` | `.venv` missing or not activated | Run `uv venv && uv pip install -r requirements.txt` |
| `ModuleNotFoundError: No module named 'docx'` | Updated requirements were not installed | Run `uv pip install -r requirements.txt` in the active environment |
| DOCX generation rejects `\placeholder{...}` | The monthly `.tex` is still an unfilled template | Fill every monthly placeholder, rerun the LaTeX checks, then regenerate the DOCX |
| DOCX chart is clipped or pagination differs unexpectedly | Word/LibreOffice layout needs review | Render the DOCX to PNG, fix only genuine clipping, overlap, or grouping defects, regenerate, and inspect every page. Accept additional body pages and never compress `Notas` below the 9 pt floor |
| Revision section appears for immaterial noise, is missing for a material change, or mixes bases | Audit and editorial materiality were conflated | Keep the complete `compare_releases` audit, assess the `0.010` threshold and editorial context separately, check cumulative net changes since the last public disclosure, and always use current-vintage values for month-over-month analysis |
| Figure is too tall at full width | The source chart aspect ratio cannot fit its annex page | Adjust the figure dimensions in `src/plot.py` and regenerate the PNG; do not reduce the figure until labels become hard to read |
| `RuntimeError: Bloco automático do IDC não encontrado no README.md` | README markers were accidentally removed | Restore `<!-- IDC_LATEST_START -->` / `<!-- IDC_LATEST_END -->` and `<!-- IDC_STATS_START -->` / `<!-- IDC_STATS_END -->` markers in README.md |
| Index value unchanged from prior month | The new observation may be unchanged, or revisions may offset it | Run `python3 -m src.compare_releases PERIOD`, inspect the current-vintage components, and flag unexplained equality for human review; file size alone is not evidence |
