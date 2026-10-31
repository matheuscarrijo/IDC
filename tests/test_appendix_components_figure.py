import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from docx import Document

from src import appendix_document as appendix
from src import plot_overlay
from src.build_appendix_docx import build_docx


class ComponentsFigureTests(unittest.TestCase):
    def test_overlay_keeps_both_lines_when_the_caption_replaces_the_legend(self):
        dates = pd.date_range("2024-01-01", periods=3, freq="MS")
        low = pd.DataFrame({"I": [7, 8, 9], "Q": [20, 21, 22]}, index=dates)
        for legend in (True, False):
            with self.subTest(legend=legend):
                fig, axes = plt.subplots(3)
                self.addCleanup(plt.close, fig)
                for ax in axes:
                    ax.plot(dates, [5, 6, 7])
                plot_overlay.components_raw(fig, low, legend=legend)
                self.assertEqual(len(fig.legends), int(legend))
                for ax, column in zip(axes[1:], ("I", "Q")):
                    self.assertEqual(ax.lines[1].get_linestyle(), "--")
                    self.assertEqual(list(ax.lines[1].get_ydata()), list(low[column]))

    def test_caption_is_shared_by_latex_and_editable_word(self):
        data = SimpleNamespace(t1=pd.Timestamp("2026-08-01"), f=SimpleNamespace(inicio=pd.Timestamp("2015-05-01")))
        figure = appendix.montar_figuras(data)["componentes"]
        self.assertIn(appendix.FIGURAS["componentes"], figure)
        self.assertIn("as linhas tracejadas mostram I e Q para baixa renda", figure)
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            fig, _ = plt.subplots()
            fig.savefig(folder / "logo.png")
            fig.savefig(folder / appendix.FIGURAS["componentes"])
            plt.close(fig)
            tex = (r"\newcommand{\reporttitle}{IDC}" "\n" r"\newcommand{\reportsubtitle}{Apêndice}"
                   "\n" r"\newcommand{\authorone}{A}" "\n" r"\newcommand{\authortwo}{B}"
                   "\n" r"\newcommand{\authorthree}{C}" "\n" r"\newcommand{\reportdate}{2026}"
                   "\n" r"\newcommand{\seriesinicio}{mar-2011}" "\n" r"\newcommand{\mesref}{ago-2026}"
                   "\n" r"\tableofcontents" "\n" r"\section{Índices}" "\n" + figure + r"\end{document}")
            (folder / "appendix.tex").write_text(tex, encoding="utf-8")
            build_docx(folder / "appendix.tex", folder / "appendix.docx")
            text = "\n".join(p.text for p in Document(folder / "appendix.docx").paragraphs)
            self.assertIn("as linhas tracejadas mostram I e Q para baixa renda", text)
            self.assertIn("incluindo sem rendimento", text)


if __name__ == "__main__":
    unittest.main()
