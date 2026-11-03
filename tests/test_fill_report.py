import tempfile
import unittest
from pathlib import Path

import pandas as pd
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.shared import Mm
from PIL import Image

from src import fill_report as F
from src import low_income as LI
from src.build_report_docx import SPAN, _parse_report, build_docx
from synthetic import T1, componentes, indice_geral
from test_report_text import synthetic_facts

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "report_template.tex"
PERIOD = "201702"  # release whose reference month is the synthetic T1 (dez-2016)
QUOTE = "\\begin{quote}\nComentário dos autores sobre a edição.\n\\end{quote}\n"


def template() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def with_quote(tex: str) -> str:
    anchor = "% nunca escreve esse comentário nem o reaproveita de uma edição anterior.\n"
    assert anchor in tex
    return tex.replace(anchor, anchor + "\n" + QUOTE)


def build(tex: str, folder: Path) -> Path:
    for name, size in (("logo.png", (300, 100)), ("index.png", (1000, 1000)), ("index_since_2022.png", (1000, 1000)),
                       ("index_12m.png", (1000, 760)),
                       ("components_raw.png", (1000, 1200))):
        Image.new("RGB", size, "white").save(folder / name)
    source = folder / "report.tex"
    source.write_text(tex, encoding="utf-8")
    out = folder / "report.docx"
    build_docx(source, out, assets_dir=folder, require_filled=True)
    return out


class FillTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.geral, cls.baixa = synthetic_facts()
        cls.ok = LI.Resultado("ok", t1=T1)
        cls.tex = F.fill(template(), PERIOD, cls.geral, cls.baixa, cls.ok)

    def test_every_block_is_generated_and_the_report_is_valid(self):
        names = [m.group("name") for m in F._BLOCK.finditer(self.tex)]
        self.assertEqual(names, list(F.BLOCKS))
        self.assertNotIn(r"\placeholder{", F._body(self.tex))
        self.assertEqual(F.validate(self.tex), [])

    def test_the_date_macros_are_filled_from_the_release_and_the_data(self):
        for macro, value in (("mesref", "dez-2016"), ("mesanterior", "nov-2016"), ("mesreferencia", "dezembro de 2016"),
                             ("competencia", "201702"), ("mespublicacao", "fevereiro de 2017"), ("reportdate", "Fevereiro de 2017")):
            self.assertRegex(self.tex, rf"\\newcommand\{{\\{macro}\}}\{{{value}\}}")

    def test_running_it_again_changes_nothing(self):
        self.assertEqual(F.fill(self.tex, PERIOD, self.geral, self.baixa, self.ok), self.tex)

    def test_what_is_added_by_hand_is_kept(self):
        revisions = "\\section{Revisões dos dados}\n\nTexto da revisão.\n\n"
        edited = with_quote(self.tex).replace("% SEÇÃO OPCIONAL — REVISÕES DOS DADOS\n", revisions + "% SEÇÃO OPCIONAL — REVISÕES DOS DADOS\n")
        again = F.fill(edited, PERIOD, self.geral, self.baixa, self.ok)
        self.assertIn(QUOTE, again)
        self.assertIn(revisions, again)

    def test_the_presentation_sentence_closes_the_first_paragraph_of_the_summary(self):
        report = _parse_report(self.tex)
        self.assertEqual(len(report["summary"]), 3)
        self.assertTrue(report["summary"][0].endswith("renda de até 2 salários mínimos."))
        self.assertIn("(SGS~29034). Esta nota apresenta também o IDC Baixa Renda", report["summary"][0])

    def test_an_unavailable_low_income_index_leaves_the_general_report_only(self):
        sem = LI.Resultado("sem_cobertura", "x", t1=T1)
        tex = F.fill(template(), PERIOD, self.geral, None, sem)
        self.assertEqual(F.validate(tex), [])
        self.assertIn("O IDC Baixa Renda não foi atualizado nesta edição", tex)
        self.assertNotIn("IDC Baixa Renda --- Componentes", tex)
        self.assertNotIn("Sobre o IDC Baixa Renda", tex)
        report = _parse_report(tex)
        self.assertEqual({len(row) for row in report["table_rows"]}, {3})
        self.assertNotIn("Baixa Renda", report["summary"][0])

    def test_data_of_another_month_never_enter_the_report(self):
        older = self.tex.replace(r"\newcommand{\mesref}{dez-2016}", r"\newcommand{\mesref}{jul-2026}")
        with self.assertRaisesRegex(ValueError, "jul-2026.*dez-2016"):
            F.fill(older, PERIOD, self.geral, self.baixa, self.ok)

    def test_a_report_without_the_blocks_is_rejected(self):
        broken = template().replace("% >>> IDC (trajetoria)", "% IDC (trajetoria)")
        with self.assertRaisesRegex(ValueError, "bloco gerado ausente no relatório: trajetoria"):
            F.fill(broken, PERIOD, self.geral, self.baixa, self.ok)
        with self.assertRaisesRegex(ValueError, "mesref"):
            F.fill(template().replace(r"\newcommand{\mesref}", r"\newcommand{\outro}"), PERIOD, self.geral, self.baixa, self.ok)

    def test_validation_flags_the_appendix_bold_text_and_a_misplaced_comment(self):
        self.assertEqual(F.validate(self.tex + "\n% o apêndice fica em outro arquivo\n"), [])
        self.assertEqual(len(F.validate(self.tex.replace("Como C é comum", "Como C (ver o Apêndice) é comum", 1))), 1)
        bold = F.validate(self.tex.replace("Como C é comum", r"Como \textbf{C} é comum", 1))
        self.assertEqual(bold, ["negrito fora da regra: C"])
        misplaced = self.tex.replace(r"\section*{Anexo de figuras}", QUOTE + r"\section*{Anexo de figuras}", 1)
        self.assertIn("o comentário dos autores (quote) só pode ficar no fim de Trajetória dos índices", F.validate(misplaced))

    def test_the_docx_mirrors_the_new_structure(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = build(with_quote(self.tex), Path(tmp))
            document = Document(out)
            table = document.tables[0]
            self.assertEqual(len(table.columns), 5)
            self.assertEqual((table.rows[0].cells[1].text, table.rows[0].cells[3].text), ("IDC Geral", "IDC Baixa Renda"))
            subheadings = [p.text for p in document.paragraphs if p.style.name == "Heading 2"]
            self.assertEqual(subheadings, ["IDC Geral — Componentes", "IDC Baixa Renda — Componentes"])
            headings = [p for p in document.paragraphs if p.style.name in ("Heading 1", "Heading 2") and p.text]
            self.assertTrue(all(run.bold for p in headings for run in p.runs))  # titles are bold, as in the PDF
            quote = next(p for p in document.paragraphs if p.text.startswith("Comentário dos autores"))
            self.assertAlmostEqual(quote.paragraph_format.left_indent.mm, 6, places=1)
            self.assertAlmostEqual(quote.paragraph_format.right_indent.mm, 6, places=1)
            borders = quote._p.pPr.find(qn("w:pBdr"))  # the box of the coauthors' model
            self.assertEqual({b.get(qn("w:color")) for b in borders}, {"FFC42F"})
            self.assertEqual(len(borders), 4)
            months = document.tables[1]
            self.assertEqual([c.text for c in months.rows[0].cells], ["Mês", "IDC Geral", "IDC Baixa Renda"])
            self.assertEqual(len(months.rows), 8)
            self.assertEqual(months.alignment, WD_TABLE_ALIGNMENT.CENTER)  # centred, as in the PDF
            self.assertIn("Tabela 2.", "\n".join(p.text for p in document.paragraphs))
            self.assertEqual(len(document.inline_shapes), 5)  # the logo and the four figures
            self.assertTrue(all(abs(shape.width - Mm(150)) < Mm(0.1) for shape in list(document.inline_shapes)[1:]))
            texts = "\n".join(p.text for p in document.paragraphs)
            self.assertIn("Figura\xa02 repete a Figura\xa01 a partir de dez-2022", texts)
            self.assertIn("Figura\xa03 detalha os últimos 12 meses", texts)
            self.assertIn("Figura 4.", texts)
            labels = [r.text for p in document.paragraphs if p.style.name == "Normal" for r in p.runs if r.bold and r.text.strip()]
            self.assertEqual(sorted(set(labels) - {"Índice de Desconforto de Crédito (IDC)"}),
                             sorted({"Comprometimento de renda (C):", "Inadimplência (I):", "Participação do crédito oneroso (Q):"}))

    def test_the_docx_reads_the_results_table_with_the_merged_header(self):
        rows = _parse_report(self.tex)["table_rows"]
        self.assertEqual(rows[0], ["", "IDC Geral", SPAN, "IDC Baixa Renda", SPAN])
        self.assertEqual(rows[1], ["Indicador", "Bruto", "Normalizado", "Bruto", "Normalizado"])


class PrepareTests(unittest.TestCase):
    def test_the_template_is_copied_once_and_the_figures_every_time(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            templates, figures, folder = root / "template", root / "figures", root / "update"
            templates.mkdir()
            figures.mkdir()
            (templates / "template.tex").write_text("modelo", encoding="utf-8")
            Image.new("RGB", (10, 10)).save(templates / "logo.png")
            for name in F.FIGURES:
                Image.new("RGB", (10, 10)).save(figures / name)
            path = F.prepare(PERIOD, templates, figures, folder)
            self.assertEqual(path.read_text(encoding="utf-8"), "modelo")
            path.write_text("preenchido", encoding="utf-8")
            F.prepare(PERIOD, templates, figures, folder)
            self.assertEqual(path.read_text(encoding="utf-8"), "preenchido")
            self.assertTrue(all((folder / name).exists() for name in (*F.FIGURES, "logo.png")))
            (figures / "index_12m.png").unlink()
            with self.assertRaisesRegex(FileNotFoundError, "index_12m.png"):
                F.prepare(PERIOD, templates, figures, folder)


class FactsFromDataTests(unittest.TestCase):
    def setUp(self):
        self.comp = componentes()
        self.idx = indice_geral(self.comp)
        self.idx["index"] = self.idx.mean(axis=1)

    def write(self, folder: Path, resultado: LI.Resultado) -> None:
        self.comp.to_csv(folder / "components_raw.csv")
        self.idx.to_csv(folder / "index.csv")
        LI.gravar(resultado, folder / "low_income_idc.csv", folder / "low_income_status.json")

    def test_status_without_series_gives_the_general_index_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.write(Path(tmp), LI.Resultado("bloqueio", "diverge", t1=T1))
            geral, baixa, resultado = F.facts_from_data(Path(tmp))
            self.assertEqual((geral.t1, baixa, resultado.status), (T1, None, "bloqueio"))

    def test_a_low_income_series_of_another_month_is_rejected(self):
        _, baixa = synthetic_facts()
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            serie = pd.DataFrame({"IDC": baixa.serie}).reindex(columns=["I", "Q", "I_norm", "Q_norm", "C_norm", "IDC"])
            self.write(folder, LI.Resultado("ok", t1=T1 - pd.DateOffset(months=1), serie=serie.loc[:T1 - pd.DateOffset(months=1)]))
            with self.assertRaisesRegex(ValueError, "rode python3 main.py"):
                F.facts_from_data(folder)



class ReleaseCheckTests(unittest.TestCase):
    """The processed data must come from the workbook of the release of the report (stamped by main.py)."""

    def setUp(self):
        import main

        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.raw, self.processed = root / "raw", root / "processed"
        self.processed.mkdir()
        self.workbooks = {}
        for period in ("202609", "202610"):
            folder = self.raw / period
            folder.mkdir(parents=True)
            self.workbooks[period] = folder / f"{period}_Tabelas_de_estatisticas_monetarias_e_de_credito.xlsx"
            self.workbooks[period].write_bytes(period.encode())
        self.stamp = lambda period: main.write_release_stamp(self.workbooks[period], pd.Timestamp("2026-08-01"),
                                                             self.processed / "release.json")

    def test_data_of_the_release_of_the_report_are_accepted(self):
        self.stamp("202610")
        F.check_release("202610", self.processed, self.raw)

    def test_a_new_workbook_without_rerunning_main_is_refused(self):
        self.stamp("202609")  # the 202610 workbook was downloaded, but main.py has not run on it yet
        with self.assertRaisesRegex(ValueError, "divulgação 202609, não 202610"):
            F.check_release("202610", self.processed, self.raw)

    def test_data_without_a_stamp_are_refused(self):
        with self.assertRaisesRegex(ValueError, "release.json ausente"):
            F.check_release("202610", self.processed, self.raw)

    def test_a_workbook_replaced_after_main_ran_is_refused(self):
        self.stamp("202610")
        self.workbooks["202610"].write_bytes(b"another download")
        with self.assertRaisesRegex(ValueError, "não é a que gerou os dados processados"):
            F.check_release("202610", self.processed, self.raw)


if __name__ == "__main__":
    unittest.main()
