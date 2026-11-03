import base64
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

from docx import Document

from src.build_appendix_docx import _prepare_math, build_docx

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)
TEX = r"""
\newcommand{\reporttitle}{Índice de Desconforto de Crédito}
\newcommand{\reportsubtitle}{Apêndice Estatístico}
\newcommand{\authorone}{Autora Um}
\newcommand{\authortwo}{Autor Dois}
\newcommand{\authorthree}{Autora Três}
\newcommand{\reportdate}{Outubro de 2026}
\tableofcontents
\section{Escopo}\label{sec:escopo}
Veja a Tabela~\ref{tab:valores}, a Figura~\ref{fig:serie} e a Seção~\ref{sec:metodo}.
\begin{table}[htbp]
\caption{Valores da série.}\label{tab:valores}
\begin{tabular}{lrr}
\toprule
 & \multicolumn{2}{c}{Grupo} \\
Indicador & Valor & Diferença \\
\midrule
IDC & 0,900 & +0,010 \\
\bottomrule
\end{tabular}
\fonte{Banco Central.}
\end{table}
\begin{figure}[htbp]
\includegraphics[width=0.9\linewidth]{chart.png}
\caption{Trajetória.}\label{fig:serie}
\fonte{Banco Central.}
\end{figure}
\section{Método}\label{sec:metodo}
Seja $x_t$ e a normalização:
\[
x_t^{norm}=\frac{x_t-\min x}{\max x-\min x}.
\]
A \emph{fórmula} é editável.
\begin{itemize}
\item Fonte primária.
\item Outra fonte.
\end{itemize}
\end{document}
"""


class AppendixWordTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        (self.folder / "logo.png").write_bytes(PNG)
        (self.folder / "chart.png").write_bytes(PNG)
        self.tex = self.folder / "appendix.tex"
        self.tex.write_text(TEX, encoding="utf-8")
        self.output = self.folder / "appendix.docx"

    @unittest.skipUnless(shutil.which("pandoc"), "requires pandoc for editable equations")
    def test_content_references_tables_figures_and_editable_math(self):
        build_docx(self.tex, self.output)
        doc = Document(self.output)
        paragraphs = "\n".join(p.text for p in doc.paragraphs)
        self.assertIn("1 Escopo", paragraphs)
        self.assertIn("2 Método", paragraphs)
        self.assertIn("Tabela\u00a0A1", paragraphs)
        self.assertIn("Figura\u00a0A1", paragraphs)
        self.assertIn("Seção\u00a02", paragraphs)
        self.assertIn("Fonte primária.", paragraphs)
        self.assertEqual(len(doc.tables), 1)
        self.assertEqual(doc.tables[0].cell(0, 1).text, "Grupo")
        self.assertEqual(doc.tables[0].cell(2, 1).text, "0,900")
        self.assertEqual(len(doc.inline_shapes), 2)
        with ZipFile(self.output) as z:
            xml = z.read("word/document.xml")
        self.assertEqual(xml.count(b"<m:oMath>"), 2)
        self.assertIn(b"<m:f>", xml)  # native editable fraction
        self.assertNotIn(b"IDC_MATH_", xml)

    def test_decomposition_uses_clear_editable_averages(self):
        expression = (r"\sum_u \underbrace{\bar w_u\,\Delta x_u}_{\text{dentro}}"
                      r"+\sum_u \underbrace{\bar x_u\,\Delta w_u}_{\text{composição}}"
                      r",\bar w_u=\tfrac{w_{u0}+w_{u1}}{2}")
        converted, labels = _prepare_math(expression)
        self.assertEqual(labels, ["dentro", "composição"])
        self.assertIn(r"w^{m}_u", converted)
        self.assertIn(r"x^{m}_u", converted)
        self.assertIn(r"\frac{w_{u0}+w_{u1}}{2}", converted)
        self.assertNotIn(r"\underbrace", converted)
        self.assertNotIn(r"\bar", converted)

    def test_unresolved_reference_is_rejected(self):
        self.tex.write_text(TEX.replace("fig:serie}", "fig:ausente}", 1), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Referências não resolvidas"):
            build_docx(self.tex, self.output)
        self.assertFalse(self.output.exists())

    @unittest.skipUnless(shutil.which("pandoc"), "requires pandoc")
    def test_latex_float_barrier_does_not_appear_in_word(self):
        self.tex.write_text(TEX.replace(r"\section{Método}", "\\FloatBarrier\n" + r"\section{Método}"), encoding="utf-8")
        build_docx(self.tex, self.output)
        paragraphs = "\n".join(p.text for p in Document(self.output).paragraphs)
        self.assertNotIn("FloatBarrier", paragraphs)
        self.assertIn("2 Método", paragraphs)

    def test_missing_pandoc_is_an_explicit_error(self):
        with patch("src.build_appendix_docx.shutil.which", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "pandoc"):
                build_docx(self.tex, self.output)
        self.assertFalse(self.output.exists())

    @unittest.skipUnless(shutil.which("pandoc"), "requires pandoc")
    def test_missing_figure_is_an_error(self):
        (self.folder / "chart.png").unlink()
        with self.assertRaisesRegex(FileNotFoundError, "chart.png"):
            build_docx(self.tex, self.output)
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
