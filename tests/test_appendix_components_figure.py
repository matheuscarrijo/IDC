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
    def test_the_panels_keep_both_lines_and_the_note_is_optional(self):
        import numpy as np

        from src import plot

        plot._apply_excel_style()
        dates = pd.date_range("2011-03-01", "2026-08-01", freq="MS")
        wave = np.sin(np.linspace(0, 12, len(dates)))
        components = pd.DataFrame({"C": 25 + 2 * wave, "I": 6 + wave, "Q": 0.22 + 0.02 * wave}, index=dates)
        low = pd.DataFrame({"I": 9 + wave, "Q": 24 + 2 * wave}, index=dates).loc["2012-07":]
        for legend in (True, False):
            with self.subTest(legend=legend):
                fig, axes = plt.subplots(3)
                self.addCleanup(plt.close, fig)
                for ax, (comp, series) in zip(axes, (("C", components["C"]), ("I", components["I"]), ("Q", 100 * components["Q"]))):
                    plot._plot_raw_component_panel(ax, comp, series, "%", low=low[comp] if comp in low else None)
                if legend:
                    plot_overlay.components_legend(fig)
                self.assertEqual(len(fig.legends), int(legend))
                for ax, column in zip(axes[1:], ("I", "Q")):
                    dashed = [line for line in ax.lines if line.get_linestyle() == "--" and len(line.get_ydata()) > 2]  # not the event lines
                    self.assertEqual([list(line.get_ydata()) for line in dashed], [list(low[column])])

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
