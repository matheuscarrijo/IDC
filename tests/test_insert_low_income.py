import tempfile
import unittest
from pathlib import Path

import pandas as pd
from PIL import Image

from src import insert_low_income as ins
from src import low_income as LI
from src import lenses as L
from src.build_report_docx import SPAN, _parse_report, build_docx
from src.income_idc import c_normalizado, idc_baixa_renda, indice_por_faixa
from synthetic import T1, componentes, faixa_bruta, indice_geral

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "filled_report.tex"


def report_text(mesref: str = "dez-2016") -> str:
    """The filled report of the fixture, set to the month of the synthetic data (``T1``)."""
    base = FIXTURE.read_text(encoding="utf-8")
    assert r"\newcommand{\mesref}{jul-2026}" in base
    return base.replace(r"\newcommand{\mesref}{jul-2026}", rf"\newcommand{{\mesref}}{{{mesref}}}")


def facts_and_result():
    comp = componentes()
    idx = indice_geral(comp)
    idx["index"] = (idx["C_norm"] + idx["I_norm"] + idx["Q_norm"]) / 3
    low = idc_baixa_renda(indice_por_faixa(L.painel(faixa_bruta(), "faixa"), c_normalizado(comp)))
    resultado = LI.Resultado("ok", t1=T1, serie=low)
    return resultado, LI.fatos(low, idx["index"], comp, idx, T1)


class InsertionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = report_text()
        cls.resultado, cls.facts = facts_and_result()
        cls.tex = ins.insert(cls.base, cls.resultado, cls.facts)

    def test_every_block_is_inserted_where_the_report_structure_puts_it(self):
        names = [m.group("name") for m in ins._BLOCK.finditer(self.tex)]
        self.assertEqual(names, ["resumo", "tabela", "resultados", "trajetória", "nota"])
        positions = {n: self.tex.index(ins.BEGIN.format(name=n)) for n in names}
        i = self.tex.index
        self.assertLess(i(r"\section{Resumo}"), positions["resumo"])
        self.assertLess(positions["resumo"], i(r"\section{Resultados de"))
        self.assertLess(i(r"\section{Resultados de"), positions["tabela"])
        self.assertLess(positions["tabela"], positions["resultados"])
        self.assertLess(positions["resultados"], i("% SEÇÃO OPCIONAL"))
        self.assertLess(i(r"\section{Trajetória do índice}"), positions["trajetória"])
        self.assertLess(positions["trajetória"], i(r"\section{Próxima atualização}"))
        self.assertLess(positions["nota"], i("Revisões dos dados. Os valores históricos"))

    def test_the_results_table_shows_both_indices_side_by_side(self):
        self.assertIn(r"\multicolumn{2}{c}{IDC para baixa renda}", self.tex)
        self.assertEqual(self.tex.count(r"\begin{table}"), 1)  # the table of the template was replaced, not duplicated
        self.assertIn("SCR.data para o IDC para baixa renda), elaboração própria", self.tex)

    def test_figures_mention_the_low_income_series(self):
        self.assertIn("e para baixa renda (mai-2015 a \\mesref)", self.tex)
        self.assertIn("I e Q também para baixa renda (jul-2012 a \\mesref)", self.tex)
        self.assertEqual(self.tex.count(r"\fonte{BCB (SGS e SCR.data), elaboração própria.}"), 2)

    def test_the_report_never_refers_to_the_appendix(self):
        blocks = "\n".join(m.group("body") for m in ins._BLOCK.finditer(self.tex))
        self.assertNotRegex(blocks.lower(), "ap[êe]ndice")
        self.assertEqual(ins.validate(self.tex), [])

    def test_any_mention_of_the_appendix_in_the_report_is_flagged_but_comments_are_not(self):
        self.assertEqual(ins.validate(self.tex + "\n% o apêndice fica em outro arquivo\n"), [])
        problems = ins.validate(self.tex.replace("Em conjunto,", "Em conjunto (ver o Apêndice),", 1))
        self.assertEqual(len(problems), 1)
        self.assertIn("não pode citá-lo", problems[0])

    def test_bold_is_limited_to_numbers_deltas_and_month_years(self):
        blocks = "\n".join(m.group("body") for m in ins._BLOCK.finditer(self.tex))
        self.assertEqual(ins.invalid_bold(blocks), [])
        self.assertEqual(ins.invalid_bold(r"\textbf{texto} e \textbf{0,963} e \textbf{jul-2026} e \textbf{+0,4~p.p.} e \textbf{10,63\%}"), ["texto"])

    def test_running_it_again_regenerates_the_blocks_instead_of_duplicating_them(self):
        again = ins.insert(self.tex, self.resultado, self.facts)
        self.assertEqual(again, self.tex)

    def test_an_unavailable_edition_adds_one_sentence_and_changes_nothing_else(self):
        sem = ins.insert(self.base, LI.Resultado("sem_cobertura", "x", t1=T1), None)
        names = [m.group("name") for m in ins._BLOCK.finditer(sem)]
        self.assertEqual(names, ["indisponível"])
        removed, _ = ins.remove_blocks(sem)
        self.assertEqual(removed, self.base)  # only the commented block was added
        self.assertIn("não foi atualizado nesta edição", sem)
        self.assertEqual(self.base.count(r"\begin{table}"), sem.count(r"\begin{table}"))

    def test_the_month_of_the_report_is_read_from_its_macro(self):
        self.assertEqual(ins.report_month(self.base), "dez-2016")
        self.assertEqual(ins.report_month(report_text(r"\placeholder{mmm-AAAA}")), r"\placeholder{mmm-AAAA}")
        self.assertIsNone(ins.report_month(self.base.replace(r"\newcommand{\mesref}", r"\newcommand{\outro}")))

    def test_data_of_another_month_never_enter_the_report(self):
        older = report_text("jul-2026")  # a report of an older release, with the processed data of a newer one
        with self.assertRaisesRegex(ValueError, "jul-2026.*dez-2016"):
            ins.insert(older, self.resultado, self.facts)
        with self.assertRaisesRegex(ValueError, "jul-2026.*dez-2016"):  # also the one-sentence edition
            ins.insert(older, LI.Resultado("sem_cobertura", "x", t1=T1), None)

    def test_an_unfilled_report_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "preenchido"):
            ins.insert(report_text(r"\placeholder{mmm-AAAA}"), self.resultado, self.facts)
        with self.assertRaisesRegex(ValueError, "preenchido"):
            ins.insert(self.base.replace(r"\newcommand{\mesref}", r"\newcommand{\outro}"), self.resultado, self.facts)

    def test_the_month_is_not_compared_when_the_data_have_none(self):
        sem = ins.insert(self.base, LI.Resultado("sem_dados", "x"), None)
        self.assertIn("não foi atualizado nesta edição", sem)

    def test_a_report_without_the_expected_structure_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "âncora não encontrada"):
            ins.insert(self.base.replace(r"\section{Próxima atualização}", r"\section{Outra}"), self.resultado, self.facts)

    def test_the_docx_converter_reads_the_report_with_the_five_column_table(self):
        report = _parse_report(self.tex)
        rows = report["table_rows"]
        self.assertEqual({len(r) for r in rows}, {5})
        self.assertEqual(rows[0], ["", "IDC geral", SPAN, "IDC para baixa renda", SPAN])
        self.assertEqual(rows[1], ["Indicador", "Bruto", "Normalizado", "Bruto", "Normalizado"])
        self.assertTrue(report["summary"][-1].startswith("O IDC para a população de baixa renda"))
        self.assertTrue(any("Sobre o IDC para baixa renda" in n for n in report["notes"]))

    def test_the_docx_has_the_merged_header_and_the_two_indices(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            for name, size in (("logo.png", (300, 100)), ("index.png", (1000, 1000)), ("components_raw.png", (1000, 1200))):
                Image.new("RGB", size, "white").save(folder / name)
            tex = folder / "report.tex"
            tex.write_text(self.tex, encoding="utf-8")
            out = folder / "report.docx"
            build_docx(tex, out, assets_dir=folder, require_filled=True)
            from docx import Document

            table = Document(out).tables[0]
            self.assertEqual(len(table.columns), 5)
            texts = [c.text for c in table.rows[0].cells]
            self.assertEqual(texts[1], texts[2])  # the merged cell appears once per covered column
            self.assertEqual((texts[1], texts[3]), ("IDC geral", "IDC para baixa renda"))
            self.assertEqual([c.text for c in table.rows[1].cells], ["Indicador", "Bruto", "Normalizado", "Bruto", "Normalizado"])


class FactsFromDataTests(unittest.TestCase):
    def test_status_without_series_gives_no_facts(self):
        with tempfile.TemporaryDirectory() as tmp:
            LI.gravar(LI.Resultado("bloqueio", "diverge", t1=T1), Path(tmp, "low_income_idc.csv"), Path(tmp, "low_income_status.json"))
            resultado, facts = ins.facts_from_data("202609", Path(tmp))
            self.assertEqual((resultado.status, facts), ("bloqueio", None))

    def test_a_series_that_does_not_end_in_the_reference_month_is_rejected(self):
        comp = componentes()
        idx = indice_geral(comp)
        idx["index"] = idx.mean(axis=1)
        low = idc_baixa_renda(indice_por_faixa(L.painel(faixa_bruta(), "faixa"), c_normalizado(comp)))
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            comp.loc[: T1 + pd.DateOffset(months=1)].to_csv(folder / "components_raw.csv")
            idx.to_csv(folder / "index.csv")
            LI.gravar(LI.Resultado("ok", t1=T1, serie=low), folder / "low_income_idc.csv", folder / "low_income_status.json")
            # components_raw.csv ends in T1 as well here; extend it by one month to simulate a stale low-income file
            comp2 = pd.concat([comp, comp.iloc[[-1]].set_axis([T1 + pd.DateOffset(months=1)])])
            comp2.to_csv(folder / "components_raw.csv")
            with self.assertRaisesRegex(ValueError, "rode python3 main.py"):
                ins.facts_from_data("202609", folder)


if __name__ == "__main__":
    unittest.main()
