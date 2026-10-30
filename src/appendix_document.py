"""Assembly of the appendix body: tables, figures and the seven sections.

``montar_corpo`` returns the LaTeX between the table of contents and ``\\end{document}``; ``gerar_figuras``
draws the four figures that only the appendix uses.  The preamble, the cover and the compilation live in
``src.build_appendix``.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src import appendix_data as AP
from src import low_income as LI
from src import appendix_text as TA
from src import lenses as L
from src.appendix_data import DadosApendice
from src.income_idc import primeira_exibicao
from src.pt_format import mes

FIGURAS = {"atribuicao": "apendice_atribuicao_I.png", "idc_faixa": "apendice_idc_faixa.png",
           "lentes": "apendice_lentes.png", "uf": "apendice_uf.png"}  # figures drawn for the appendix (index.png and
# components_raw.png are the figures of the monthly report, with the low-income lines)
FONTE_COMPONENTES = ("Banco Central do Brasil (SGS e SCR.data), elaboração própria. IDC para baixa renda: C nacional; "
                     "I e Q do crédito livre PF com renda de até 2 SM, incluindo sem rendimento.")
LARGURA_ROTULO_LENTES = ("p{3.5cm}", "p{4.3cm}")  # segment names wrap less with a wider first column


def montar_tabelas(d: DadosApendice) -> dict[str, str]:
    """Every table of the appendix, as floating LaTeX with its source note inside the float."""
    tabs = {k: AP.preparar_tabela(v) for k, v in d.ext.tabelas.items()}
    for k in ("faixa", "credor", "ocupacao"):
        tabs[k] = tabs[k].replace(r">{\raggedright\arraybackslash}" + LARGURA_ROTULO_LENTES[0], r">{\raggedright\arraybackslash}" + LARGURA_ROTULO_LENTES[1])
    novas = {
        "componentes": LI.tabela_componentes(d.f, fonte=FONTE_COMPONENTES),
        "evolucao": AP.tab_evolucao(d), "anual": AP.tab_anual(d), "conc_t1": AP.tab_conciliacao_t1(d), "conc_hist": AP.tab_conciliacao_hist(d),
        "quebras": AP.tab_quebras(d), "janeiros": AP.tab_janeiros(d), "cenarios": AP.tab_cenarios(d),
        "sensibilidade": AP.tab_sensibilidade(d), "teste_ref": AP.tab_teste_ref(d),
    }
    tabs.update({k: AP.preparar_tabela(v) for k, v in novas.items()})
    assert all(r"\fonte" in v.split(r"\end{table}")[0] for v in tabs.values()), "every table needs its source note inside the float"
    return tabs


def figura(arquivo: str, legenda: str, rotulo: str, fonte: str, altura: str = "0.62") -> str:
    return rf"""
\begin{{figure}}[htbp]
  \centering
  \includegraphics[width=0.92\linewidth,height={altura}\textheight,keepaspectratio]{{{arquivo}}}
  \caption{{{legenda}}}
  \label{{{rotulo}}}
  \fonte{{{fonte}}}
\end{{figure}}
"""


def montar_figuras(d: DadosApendice) -> dict[str, str]:
    ini_atrib = d.t1 - pd.DateOffset(months=17)
    return {
        "indice": figura("index.png", rf"Evolução do IDC geral (\janelainicio{{}} a \mesref) e do IDC para baixa renda ({mes(d.f.inicio)} a \mesref).",
                         "fig:indice", "BCB (SGS e SCR.data), elaboração própria."),
        "componentes": figura("components_raw.png", r"Evolução das componentes brutas C, I e Q (\seriesinicio{} a \mesref); I e Q também para baixa renda (jul-2012 a \mesref).",
                              "fig:componentes", "BCB (SGS e SCR.data), elaboração própria.", "0.7"),
        "atribuicao": figura(FIGURAS["atribuicao"], rf"Contribuição de cada grupo de produtos à variação mensal da inadimplência (I), {mes(ini_atrib)} a \mesref.",
                             "fig:atribuicao", "BCB (SGS), elaboração própria."),
        "lentes": figura(FIGURAS["lentes"], "Contribuição à variação de I em 12 meses, por faixa de renda, credor e ocupação.", "fig:lentes",
                         "BCB (SCR.data), elaboração própria.", "0.66"),
        "uf": figura(FIGURAS["uf"], "Inadimplência no crédito livre PF por unidade da federação.", "fig:uf", "BCB (SCR.data), elaboração própria.", "0.7"),
        "idc_faixa": figura(FIGURAS["idc_faixa"], rf"IDC por faixa de renda, com C nacional ({mes(d.f.inicio)} a \mesref).", "fig:idc_faixa",
                            "BCB (SGS e SCR.data), elaboração própria."),
    }


def montar_corpo(d: DadosApendice) -> str:
    tabs, fig = montar_tabelas(d), montar_figuras(d)
    return "\n".join([
        TA.s1_escopo(d),
        TA.s2_indices(d, tabs), fig["indice"], fig["componentes"],
        TA.s3_anatomia(d, tabs), fig["atribuicao"],
        TA.s4_segmentos(d, tabs), fig["lentes"], fig["uf"],
        TA.s5_faixas(d, tabs), fig["idc_faixa"],
        TA.s6_qualidade(d, tabs),
        TA.s7_metodologia(d),
    ])


def gerar_figuras(d: DadosApendice, destino: Path) -> None:
    """Draw the figures of the appendix that are not figures of the monthly report."""
    from src import plot_extras as PX
    from src.anatomy import agrupar, atribuir_variacao_I

    destino.mkdir(parents=True, exist_ok=True)
    meses = pd.date_range(d.t1 - pd.DateOffset(months=17), d.t1, freq="MS")
    contribuicoes = pd.DataFrame({m: agrupar(atribuir_variacao_I(d.sgs, m - pd.DateOffset(months=1), m))["total"] for m in meses}).T
    PX.fig_atribuicao_mensal_I(contribuicoes, d.sgs["inad_total"].diff().loc[meses], destino / FIGURAS["atribuicao"])
    dados = d.ext.dados
    PX.fig_idc_por_faixa(dados["idc_faixa"].loc[primeira_exibicao():d.t1], d.idx["index"], destino / FIGURAS["idc_faixa"])
    PX.fig_lentes({"Faixa de renda": dados["tabs"]["faixa"].loc[list(L.FAIXAS_INDICE)],
                   "Credor": dados["tabs"]["credor"].drop(index=["Instituições de pagamento"], errors="ignore"),
                   "Ocupação": dados["tabs"]["ocupacao"]}, {}, destino / FIGURAS["lentes"])
    PX.fig_uf(dados["tabs"]["uf"], destino / FIGURAS["uf"])
