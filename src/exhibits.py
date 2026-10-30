"""Tables and draft sentences of the statistical appendix.

Everything here is derived from the numbers computed by ``anatomy``, ``lenses``
and ``income_idc``; the sentences are *drafts* with fixed rules for what is worth
saying, so that the agent that writes the monthly report only has to review them.
Numbers follow the report's conventions (see ``fmt``).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src import lenses as L
from src.anatomy import (Q_MODALIDADES, PRODUTOS, agrupar, atribuir_variacao_I, atribuir_variacao_Q, decompor_C)
from src.pt_format import bmes, bn, bpct, bpct_s, bpp, mes, num, tabela_latex

FONTE_SGS = "Banco Central do Brasil (SGS), elaboração própria."
FONTE_SCR = "Banco Central do Brasil (SCR.data, operações de crédito livre PF), elaboração própria."
COL_ROTULO = r">{\raggedright\arraybackslash}p{3.5cm}"
COL_LARGA = r">{\raggedright\arraybackslash}p{7.2cm}"
FRASE_GRUPO = {"Cartão rotativo e parcelado": "cartão rotativo e parcelado", "Cartão à vista e lojista": "cartão à vista e lojista", "Pessoal não consignado": "crédito pessoal não consignado",
               "Consignado": "consignado", "Veículos": "financiamento de veículos", "Cheque especial": "cheque especial",
               "Demais": "demais modalidades"}
FRASE_NO = {"consig_privado": "no consignado do setor privado", "consig_inss": "no consignado do INSS",
            "consig_servidores": "no consignado de servidores públicos", "nao_consignado": "no crédito pessoal não consignado",
            "cartao_rotativo": "no cartão rotativo", "cartao_parcelado": "no cartão parcelado", "cartao_vista": "no cartão à vista",
            "veiculos": "no financiamento de veículos", "cheque_especial": "no cheque especial"}
FRASE_PELO = {"cartao_parcelado": "pelo cartão parcelado", "cartao_rotativo": "pelo cartão rotativo",
              "nao_consignado": "pelo crédito pessoal não consignado", "cheque_especial": "pelo cheque especial"}


@dataclass
class Contexto:
    sgs: pd.DataFrame
    paineis: dict[str, pd.DataFrame]
    idc_faixa: pd.DataFrame          # displayed IDC by income bracket
    idc_geral: pd.Series             # headline IDC
    preco_fluxo: pd.DataFrame
    t1: pd.Timestamp
    conc: dict

    @property
    def tprev(self) -> pd.Timestamp:
        return self.t1 - pd.DateOffset(months=1)

    @property
    def t0(self) -> pd.Timestamp:
        return self.t1 - pd.DateOffset(years=1)


# --------------------------------------------------------------------------- Camada 1
def tabela_anatomia(ctx: Contexto) -> tuple[str, dict]:
    mensal = atribuir_variacao_I(ctx.sgs, ctx.tprev, ctx.t1)
    anual = atribuir_variacao_I(ctx.sgs, ctx.t0, ctx.t1)
    gm, ga = agrupar(mensal), agrupar(anual)
    linhas = []
    for grupo in gm.index:
        linhas.append([
            grupo, num(gm.loc[grupo, "peso_t1"], 1), num(ga.loc[grupo, "I_t0"], 2), num(gm.loc[grupo, "I_t0"], 2),
            num(gm.loc[grupo, "I_t1"], 2), num(gm.loc[grupo, "total"], 2, True), num(ga.loc[grupo, "total"], 2, True),
        ])
    sg = ctx.sgs["inad_total"]
    linhas.append([r"\textit{Soma das contribuições}", "100,0", "", "", "", num(mensal.soma, 2, True), num(anual.soma, 2, True)])
    linhas.append([r"\textit{Variação oficial de I (SGS 21112)}", "", num(sg.loc[ctx.t0], 2), num(sg.loc[ctx.tprev], 2),
                   num(sg.loc[ctx.t1], 2), num(mensal.delta_oficial, 2, True), num(anual.delta_oficial, 2, True)])
    tex = tabela_latex(
        f"Contribuição de cada grupo de produtos à variação da inadimplência (I) --- mês e 12 meses até {mes(ctx.t1)} (p.p.).",
        "tab:anatomia",
        ["Grupo de produtos", r"Peso (\%)", f"I {mes(ctx.t0)}", f"I {mes(ctx.tprev)}", f"I {mes(ctx.t1)}", "Contrib. mês", "Contrib. 12 m"],
        linhas, COL_ROTULO + "rrrrrr", FONTE_SGS + " Decomposição aditiva em variação dentro de cada produto e mudança de composição (ver Notas).",
        tamanho=r"\small", separadores=(len(gm) - 1,))
    return tex, {"mensal": mensal, "anual": anual, "gm": gm, "ga": ga}


def tabela_c_q(ctx: Contexto) -> tuple[str, dict]:
    cm, ca = decompor_C(ctx.sgs, ctx.tprev, ctx.t1), decompor_C(ctx.sgs, ctx.t0, ctx.t1)
    qm, qa = atribuir_variacao_Q(ctx.sgs, ctx.tprev, ctx.t1), atribuir_variacao_Q(ctx.sgs, ctx.t0, ctx.t1)
    linhas = [[r"\textit{Comprometimento de renda (C), \% da renda}", "", "", ""]]
    nomes_c = {"C — serviço da dívida (SGS 29034)": "C --- serviço da dívida (SGS~29034)",
               "dos quais juros (SGS 29033)": r"\quad dos quais juros (SGS~29033)",
               "dos quais amortização (SGS 29036)": r"\quad dos quais amortização (SGS~29036)",
               "C sem financiamento imobiliário (SGS 29035)": "C sem financiamento imobiliário (SGS~29035)",
               "Endividamento (dívida/renda de 12 meses, SGS 29037)": "Endividamento: dívida/renda de 12 meses (SGS~29037)"}
    for chave, rotulo in nomes_c.items():
        linhas.append([rotulo, num(cm.loc[chave, "t1"], 2), num(cm.loc[chave, "delta"], 2, True), num(ca.loc[chave, "delta"], 2, True)])
    q1 = 100 * sum(ctx.sgs[f"saldo_{m}"] for m in Q_MODALIDADES) / ctx.sgs["saldo_total"]
    linhas.append([r"\textit{Crédito oneroso (Q), \% do crédito livre PF}", "", "", ""])
    linhas.append(["Q --- participação das quatro modalidades", num(q1.loc[ctx.t1], 2), num(q1.loc[ctx.t1] - q1.loc[ctx.tprev], 2, True),
                   num(q1.loc[ctx.t1] - q1.loc[ctx.t0], 2, True)])
    for m in Q_MODALIDADES:
        linhas.append([r"\quad " + PRODUTOS[m][0], num(qm.loc[m, "peso_t1"], 2), num(qm.loc[m, "contribuicao"], 2, True),
                       num(qa.loc[m, "contribuicao"], 2, True)])
    tex = tabela_latex(
        f"Comprometimento de renda (C) e crédito oneroso (Q) --- nível em {mes(ctx.t1)} e variações (p.p.).", "tab:c_q",
        ["Indicador", f"{mes(ctx.t1)}", "Δ mês", "Δ 12 meses"], linhas, COL_LARGA + "rrr", FONTE_SGS + " Variações de Q por modalidade são "
        "variações de sua participação no saldo do crédito livre PF.", separadores=())
    return tex, {"cm": cm, "ca": ca, "qm": qm, "qa": qa, "q": q1}


def tabela_preco_fluxo(ctx: Contexto) -> str:
    pf = ctx.preco_fluxo
    linhas = []
    for nome, r in pf.iterrows():
        fluxo = "---" if np.isnan(r["fluxo_12m_bi"]) else num(r["fluxo_12m_bi"], 1)
        var = "---" if np.isnan(r["fluxo_var_pct"]) else num(r["fluxo_var_pct"], 1, True)
        linhas.append([nome, num(r["taxa_t1"], 1), num(r["taxa_delta"], 1, True), fluxo, var])
    return tabela_latex(
        f"Taxas médias de juros e concessões por modalidade --- {mes(ctx.t1)}.", "tab:preco_fluxo",
        ["Modalidade (crédito livre PF)", "Taxa (\\% a.a.)", "Δ 12 m (p.p.)", "Conc. 12 m (R\\$ bi)", "Var. 12 m (\\%)"],
        linhas, r">{\raggedright\arraybackslash}p{4.4cm}rrrr",
        "Banco Central do Brasil (Estatísticas Monetárias e de Crédito, Tabelas 11 e 16), elaboração própria. Concessões são a soma dos "
        "12 meses até o mês de referência; o cartão rotativo e o cheque especial não têm concessões comparáveis (são saldos rotativos).",
        tamanho=r"\small", posicao="H")


# --------------------------------------------------------------------------- Camada 2
def _combinar(ctx: Contexto, lente: str, ordem: list[str] | None = None, compactar_pesos: bool = True,
              manter: tuple[str, ...] = ()):
    p = ctx.paineis[lente]
    nac = L.totais(p)
    q_of = lambda t: 100 * sum(ctx.sgs[f"saldo_{m}"].loc[t] for m in Q_MODALIDADES) / ctx.sgs["saldo_total"].loc[t]  # noqa: E731
    dI = L.decompor(p, ctx.t0, ctx.t1, "I", float(ctx.sgs["inad_total"].loc[ctx.t1] - ctx.sgs["inad_total"].loc[ctx.t0]))
    dQ = L.decompor(p, ctx.t0, ctx.t1, "Q", float(q_of(ctx.t1) - q_of(ctx.t0)))
    ti = dI.tabela.copy()
    tq = dQ.tabela[["x_t0", "x_t1", "contribuicao"]].add_prefix("Q_")
    comb = ti.join(tq)
    if compactar_pesos:
        # compact I and Q tables consistently: merge units below 0.5% weight
        pequenos = comb.index[(comb["peso_t1"] < 0.5) & (comb.index != "Demais") & (~comb.index.isin(manter))]
        if len(pequenos):
            resto = comb.loc[pequenos]
            w = resto["peso_t1"].sum()
            linha = {"peso_t1": w}
            for col in ("dentro", "composicao", "contribuicao", "Q_contribuicao"):
                linha[col] = resto[col].sum()
            for col in ("x_t0", "x_t1", "Q_x_t0", "Q_x_t1"):
                linha[col] = (resto[col] * resto["peso_t1"]).sum() / w
            linha["dx"] = linha["x_t1"] - linha["x_t0"]
            comb = pd.concat([comb.drop(index=pequenos), pd.DataFrame(linha, index=["Demais"])])
    if ordem:
        comb = comb.reindex([u for u in ordem if u in comb.index])
    return comb, dI, dQ, nac


def tabela_lente(ctx: Contexto, lente: str, titulo: str, rotulo: str, ordem: list[str] | None = None,
                 ordenar_por: str | None = None, memo_sem_rendimento: dict | None = None,
                 nota_quebras: str = "", manter: tuple[str, ...] = (), primeiro: bool = False) -> tuple[str, pd.DataFrame, dict]:
    comb, dI, dQ, nac = _combinar(ctx, lente, ordem, manter=manter)
    if ordenar_por:
        comb = comb.sort_values(ordenar_por, ascending=False)
        if "Demais" in comb.index:  # keep the residual row last
            comb = pd.concat([comb.drop(index="Demais"), comb.loc[["Demais"]]])
    linhas = []
    for unidade, r in comb.iterrows():
        linhas.append([unidade, num(r["peso_t1"], 1), num(r["x_t0"], 2), num(r["x_t1"], 2), num(r["contribuicao"], 2, True),
                       num(r["Q_x_t1"], 1), num(r["Q_contribuicao"], 2, True)])
        if memo_sem_rendimento is not None and unidade == "Até 2 SM":
            m = memo_sem_rendimento
            linhas.append([r"\quad\textit{dos quais sem rendimento}", num(m["peso"], 1), num(m["I_t0"], 2), num(m["I_t1"], 2), "---",
                           num(m["Q_t1"], 1), "---"])
    aviso_q = ""
    if ctx.conc.get("status_Q", "ok") != "ok" and primeiro:
        aviso_q = (f" Atenção: a variação de Q no SCR.data ({num(dQ.delta_scr, 2, True)} p.p.) difere da oficial ({num(dQ.delta_oficial, 2, True)} p.p.) em "
                   f"{num(abs(dQ.residuo), 2)} p.p.; a coluna Contrib. Q é indicativa.")
    nac0, nac1 = nac.loc[ctx.t0], nac.loc[ctx.t1]
    if primeiro:
        q_ofic = 100 * sum(ctx.sgs[f"saldo_{m}"].loc[ctx.t1] for m in Q_MODALIDADES) / ctx.sgs["saldo_total"].loc[ctx.t1]
        aviso_q += (f" O nível de Q no SCR.data ({num(nac1['Q'], 1)}\\%) difere do oficial ({num(q_ofic, 1)}\\%) por diferenças de "
                    "classificação das modalidades entre as fontes.")
    linhas.append([r"\textit{Total (SCR.data)}", "100,0", num(nac0["I"], 2), num(nac1["I"], 2), num(dI.delta_scr, 2, True),
                   num(nac1["Q"], 1), num(dQ.delta_scr, 2, True)])
    linhas.append([r"\textit{Variação oficial (SGS)}", "", num(ctx.sgs["inad_total"].loc[ctx.t0], 2), num(ctx.sgs["inad_total"].loc[ctx.t1], 2),
                   num(dI.delta_oficial, 2, True), "", num(dQ.delta_oficial, 2, True)])
    tex = tabela_latex(
        titulo, rotulo,
        ["Segmento", r"Peso (\%)", f"I {mes(ctx.t0)}", f"I {mes(ctx.t1)}", "Contrib. I", f"Q {mes(ctx.t1)}", "Contrib. Q"],
        linhas, COL_ROTULO + "rrrrrr",
        FONTE_SCR + " Contribuições à variação de I e de Q em 12 meses (p.p.); a diferença entre o total do SCR.data e a variação oficial do SGS é o resíduo (ver Notas)."
        + (" " + nota_quebras if nota_quebras else "") + aviso_q,
        tamanho=r"\small", separadores=(len(linhas) - 3,))
    return tex, comb, {"dI": dI, "dQ": dQ}


def memo_sem_rendimento(ctx: Contexto, bruto: pd.DataFrame) -> dict:
    """Weight, I and Q of the 'sem rendimento' sub-group (inside 'Até 2 SM')."""
    b_ = bruto.copy()
    b_["data_base"] = pd.to_datetime(b_["data_base"], format="mixed").dt.to_period("M").dt.to_timestamp()
    sr = b_[b_["unidade"] == "Sem rendimento"].groupby("data_base")[["carteira", "inad"]].sum()
    sr["onerosa"] = b_[(b_["unidade"] == "Sem rendimento") & b_["oneroso"]].groupby("data_base")["carteira"].sum()
    total = b_.groupby("data_base")["carteira"].sum()
    return {"peso": float(100 * sr["carteira"].loc[ctx.t1] / total.loc[ctx.t1]),
            "I_t0": float(100 * sr["inad"].loc[ctx.t0] / sr["carteira"].loc[ctx.t0]),
            "I_t1": float(100 * sr["inad"].loc[ctx.t1] / sr["carteira"].loc[ctx.t1]),
            "Q_t1": float(100 * sr["onerosa"].fillna(0).loc[ctx.t1] / sr["carteira"].loc[ctx.t1])}


def tabela_idc_faixa(ctx: Contexto) -> tuple[str, pd.DataFrame]:
    r = L.taxas(ctx.paineis["faixa"])
    linhas, resumo = [], {}
    for faixa in L.FAIXAS_INDICE:
        peso = float(r["peso"].xs(faixa, level="grupo").loc[ctx.t1])
        i, q = float(r["I"].xs(faixa, level="grupo").loc[ctx.t1]), float(r["Q"].xs(faixa, level="grupo").loc[ctx.t1])
        idc = ctx.idc_faixa[(faixa, "IDC")]
        linhas.append([faixa, num(peso, 1), num(i, 2), num(q, 1), num(ctx.idc_faixa[(faixa, "I_norm")].loc[ctx.t1], 3),
                       num(ctx.idc_faixa[(faixa, "Q_norm")].loc[ctx.t1], 3), num(idc.loc[ctx.t0], 3), num(idc.loc[ctx.tprev], 3), num(idc.loc[ctx.t1], 3)])
        resumo[faixa] = {"peso": peso, "I": i, "Q": q, "IDC_t0": float(idc.loc[ctx.t0]), "IDC_tprev": float(idc.loc[ctx.tprev]),
                         "IDC_t1": float(idc.loc[ctx.t1]), "I_norm": float(ctx.idc_faixa[(faixa, "I_norm")].loc[ctx.t1]),
                         "Q_norm": float(ctx.idc_faixa[(faixa, "Q_norm")].loc[ctx.t1])}
    geral = ctx.idc_geral
    linhas.append([r"\textit{IDC (todas as faixas)}", "100,0", num(ctx.sgs["inad_total"].loc[ctx.t1], 2), "", "", "", num(geral.loc[ctx.t0], 3),
                   num(geral.loc[ctx.tprev], 3), num(geral.loc[ctx.t1], 3)])
    tex = tabela_latex(
        f"IDC por faixa de renda --- {mes(ctx.t1)} (C nacional; I e Q de cada faixa).", "tab:idc_faixa",
        ["Faixa de renda", r"Peso (\%)", r"I (\%)", r"Q (\%)", "I norm.", "Q norm.", f"IDC {mes(ctx.t0)}", f"IDC {mes(ctx.tprev)}", f"IDC {mes(ctx.t1)}"],
        linhas, r">{\raggedright\arraybackslash}p{2.8cm}rrrrrrrr",
        FONTE_SCR + " IDC por faixa = média de C normalizado (nacional, igual para todas as faixas) e de I e Q normalizados de cada faixa (min-max com "
        "janela expansiva desde jul-2012). A faixa mais baixa inclui famílias sem rendimento. As diferenças entre faixas decorrem apenas de I e Q.",
        tamanho=r"\footnotesize", separadores=(len(linhas) - 2,), tabcolsep="2.5pt")
    return tex, pd.DataFrame(resumo).T


def tabela_uf(ctx: Contexto) -> tuple[str, pd.DataFrame]:
    comb, dI, dQ, nac = _combinar(ctx, "uf", compactar_pesos=False)
    comb = comb.sort_values("x_t1", ascending=False)
    linhas = []
    for uf, r in comb.iterrows():
        linhas.append([uf, num(r["peso_t1"], 1), num(r["x_t0"], 2), num(r["x_t1"], 2), num(r["dx"], 2, True), num(r["contribuicao"], 2, True), num(r["Q_x_t1"], 1)])
    nac0, nac1 = nac.loc[ctx.t0], nac.loc[ctx.t1]
    linhas.append([r"\textit{Brasil (SCR.data)}", "100,0", num(nac0["I"], 2), num(nac1["I"], 2), num(nac1["I"] - nac0["I"], 2, True), num(dI.delta_scr, 2, True), num(nac1["Q"], 1)])
    tex = tabela_latex(
        f"Inadimplência e crédito oneroso por unidade da federação --- {mes(ctx.t1)}.", "tab:uf",
        ["UF", r"Peso (\%)", f"I {mes(ctx.t0)}", f"I {mes(ctx.t1)}", "Δ I (p.p.)", "Contrib. I", f"Q {mes(ctx.t1)}"],
        linhas, r"lrrrrrr", FONTE_SCR + " Estados ordenados pela inadimplência no mês de referência; contribuição à variação de I em 12 meses (p.p.). "
        "Unidade da federação pelo CEP de residência do tomador.", tamanho=r"\footnotesize", separadores=(len(linhas) - 2,), posicao="H")
    return tex, comb


# --------------------------------------------------------------------------- texto
def _lista(itens: list[str]) -> str:
    if len(itens) <= 1:
        return "".join(itens)
    return ", ".join(itens[:-1]) + " e " + itens[-1]


def texto_anatomia(ctx: Contexto, a: dict, cq: dict) -> str:
    m, an = a["mensal"], a["anual"]
    gm = a["gm"]
    sg = ctx.sgs["inad_total"]
    top_m = gm.sort_values("total", ascending=False)
    principais = [f"{FRASE_GRUPO[g]} ({bpp(top_m.loc[g, 'total'])})" for g in top_m.index[:3]]
    # composition effect in 12 months: product with the largest weight change
    comp = an.tabela.sort_values("composicao", ascending=False).iloc[0]
    texto = [
        f"A inadimplência (I) {'subiu' if m.delta_oficial > 0 else 'recuou'} {bpp(abs(m.delta_oficial), 2, False)} em {bmes(ctx.t1)}, de "
        f"{bpct(sg.loc[ctx.tprev], 2)} para {bpct(sg.loc[ctx.t1], 2)} (série do SGS com duas casas decimais, necessárias à decomposição). "
        f"{'A piora' if m.delta_oficial > 0 else 'A queda'} ocorreu dentro dos produtos ({bpp(m.dentro)}), e não por mudança na composição "
        f"da carteira ({bpp(m.composicao)}). Os grupos de maior contribuição foram {_lista(principais)} (Tabela~\\ref{{tab:anatomia}}).",
        f"Em 12 meses, I avançou {bpp(an.delta_oficial, 2, False)}: {bpp(an.dentro)} dentro dos produtos e {bpp(an.composicao)} por composição. "
        f"O efeito composição concentra-se {FRASE_NO.get(comp.name, 'em ' + comp['produto'].lower())}, cujo peso no crédito livre PF passou de {bpct(comp['peso_t0'], 1)} para "
        f"{bpct(comp['peso_t1'], 1)} e cuja inadimplência é de {bpct(comp['I_t1'], 1)}.",
    ]
    cm, ca, qm = cq["cm"], cq["ca"], cq["qm"]
    c_chave, j_chave, a_chave = "C — serviço da dívida (SGS 29034)", "dos quais juros (SGS 29033)", "dos quais amortização (SGS 29036)"
    maior_q = qm["contribuicao"].abs().idxmax()
    q = cq["q"]
    texto.append(
        f"A participação do crédito oneroso (Q) {'subiu' if q.loc[ctx.t1] > q.loc[ctx.tprev] else 'caiu'} "
        f"{bpp(abs(q.loc[ctx.t1] - q.loc[ctx.tprev]), 2, False)} no mês (de {bpct(q.loc[ctx.tprev], 2)} para {bpct(q.loc[ctx.t1], 2)}), "
        f"principalmente {FRASE_PELO.get(maior_q, 'por ' + PRODUTOS[maior_q][0].lower())} ({bpp(qm.loc[maior_q, 'contribuicao'])}). "
        f"O comprometimento de renda (C) {'subiu' if cm.loc[c_chave, 'delta'] > 0 else 'recuou'} {bpp(abs(cm.loc[c_chave, 'delta']), 2, False)} "
        f"(de {bpct(cm.loc[c_chave, 't0'], 2)} para {bpct(cm.loc[c_chave, 't1'], 2)}), sendo {bpp(cm.loc[j_chave, 'delta'])} de juros e "
        f"{bpp(cm.loc[a_chave, 'delta'])} de amortização; em 12 meses, a alta de C foi de {bpp(ca.loc[c_chave, 'delta'], 2, False)}, "
        f"{bpp(ca.loc[j_chave, 'delta'], 2, False)} de juros e {bpp(ca.loc[a_chave, 'delta'], 2, False)} de amortização."
    )
    return "\n\n".join(texto)


def texto_preco_fluxo(ctx: Contexto) -> str:
    pf = ctx.preco_fluxo
    tot = pf.loc["Total do crédito livre PF"]
    priv = pf.loc["Crédito pessoal — consignado, setor privado"]
    return (f"A taxa média das operações de crédito livre PF foi de {bpct(tot['taxa_t1'], 1)} a.a. em {bmes(ctx.t1)} "
            f"({bpp(tot['taxa_delta'], 1)} em 12 meses). As concessões de consignado do setor privado somaram R\\$~{bn(priv['fluxo_12m_bi'], 1)}~bilhões "
            f"em 12 meses ({bpct_s(priv['fluxo_var_pct'], 1)}), a uma taxa de {bpct(priv['taxa_t1'], 1)} a.a. (Tabela~\\ref{{tab:preco_fluxo}}).")


FAIXA_TEXTO = {"Até 2 SM": "até 2~SM", "2 a 5 SM": "de 2 a 5~SM", "5 a 10 SM": "de 5 a 10~SM", "Mais de 10 SM": "acima de 10~SM"}


def texto_lentes(ctx: Contexto, tabs: dict[str, pd.DataFrame], decs: dict[str, dict], conc: dict) -> str:
    dI = decs["faixa"]["dI"]
    partes = [
        f"As tabelas desta seção decompõem a variação de I e de Q em 12 meses por faixa de renda, credor, ocupação e unidade da federação, "
        f"com o SCR.data do Banco Central (operações de crédito livre PF, exceto rural, imobiliário e exportação/importação; esse universo "
        f"corresponde a {bpct(100 + conc['gap_carteira_pct'], 1)} do saldo do SGS~20570). Em {bmes(ctx.t1)}, I medido pelo SCR.data é "
        f"{bpct(conc['I_scr_t1'], 2)}, {bpp(conc['gap_I_nivel'], 2)} em relação ao SGS, e a variação em 12 meses difere em {bpp(conc['gap_I_delta'], 2)}; "
        f"essas diferenças aparecem como resíduo nas tabelas."
    ]
    fx = tabs["faixa"].loc[list(L.FAIXAS_INDICE)]
    rel = (fx["x_t1"] / fx["x_t0"] - 1) * 100
    ordenadas = fx["contribuicao"].sort_values(ascending=False)
    primeira, segunda = ordenadas.index[0], ordenadas.index[1]
    partes.append(
        f"Por faixa de renda, a alta de I em 12 meses ({bpp(dI.delta_scr, 2, False)} no SCR.data) concentrou-se nas faixas {FAIXA_TEXTO[primeira]} "
        f"({bpp(fx.loc[primeira, 'contribuicao'])}) e {FAIXA_TEXTO[segunda]} ({bpp(fx.loc[segunda, 'contribuicao'])}). A maior variação relativa de I foi na faixa "
        f"{FAIXA_TEXTO[rel.idxmax()]}, de {bpct(fx.loc[rel.idxmax(), 'x_t0'], 2)} para {bpct(fx.loc[rel.idxmax(), 'x_t1'], 2)} ({bpct_s(rel.max(), 1)}).")
    cb = tabs["credor"].sort_values("contribuicao", ascending=False)
    segundo = cb.index[1]
    partes.append(
        f"Por credor, {cb.index[0].lower()} contribuíram com {bpp(cb.iloc[0]['contribuicao'])} e {segundo.lower()} com {bpp(cb.iloc[1]['contribuicao'])}; "
        f"estas últimas têm {bpct(cb.loc[segundo, 'peso_t1'], 0)} da carteira e inadimplência de {bpct(cb.loc[segundo, 'x_t1'], 2)}, "
        f"contra {bpct(tabs['credor'].loc['Bancos', 'x_t1'], 2)} nos bancos.")
    o = tabs["ocupacao"]
    ap = o.loc["Aposentado/pensionista"]
    partes.append(
        f"Por ocupação, o grupo ``Outros'' ({bpct(o.loc['Outros', 'peso_t1'], 0)} da carteira) contribuiu com {bpp(o.loc['Outros', 'contribuicao'])}, "
        f"os empregados de empresas privadas com {bpp(o.loc['Empregado de empresa privada', 'contribuicao'])} e os aposentados e pensionistas com "
        f"{bpp(ap['contribuicao'])} (I de {bpct(ap['x_t1'], 2)})."
    )
    u = tabs["uf"]
    ub = u["contribuicao"].sort_values(ascending=False).head(3)
    ud = u["dx"].sort_values(ascending=False).head(3)
    partes.append(
        f"Por unidade da federação, as maiores contribuições vieram de {_lista([f'{k} ({bpp(v)})' for k, v in ub.items()])}, "
        f"refletindo em boa parte seus pesos na carteira; em variação de I, destacam-se {_lista([f'{k} ({bpp(v)})' for k, v in ud.items()])} "
        f"(Tabelas~\\ref{{tab:faixa}} a~\\ref{{tab:ocupacao}} e Tabela~\\ref{{tab:uf}})."
    )
    return "\n\n".join(partes)


def texto_idc_faixa(ctx: Contexto, resumo: pd.DataFrame) -> str:
    geral = ctx.idc_geral
    itens = [f"{FAIXA_TEXTO[f]} {bn(resumo.loc[f, 'IDC_t1'], 3)}" for f in L.FAIXAS_INDICE]
    variacao = {f: resumo.loc[f, "IDC_t1"] - resumo.loc[f, "IDC_t0"] for f in L.FAIXAS_INDICE}
    maior = max(variacao, key=variacao.get)
    n_sobe = sum(v > 0 for v in variacao.values())
    return (f"Com C mantido no valor nacional e I e Q medidos em cada faixa, o IDC por faixa de renda foi, em {bmes(ctx.t1)}, de {_lista(itens)} "
            f"(IDC de todas as faixas: {bn(geral.loc[ctx.t1], 3)}). Em 12 meses, o índice subiu {'nas quatro faixas' if n_sobe == 4 else 'em ' + bn(n_sobe, 0) + ' das 4 faixas'}, e a maior alta foi na faixa "
            f"{FAIXA_TEXTO[maior]} ({bn(variacao[maior], 3, True)}). Como C é o mesmo em todas as faixas, as diferenças entre elas "
            f"vêm somente de I e Q, e cada faixa deve ser lida contra a sua própria história (Figura~\\ref{{fig:idc_faixa}}).")
