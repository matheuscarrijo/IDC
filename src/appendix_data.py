"""Statistical appendix of the IDC: data gathering, extra tables and appendix-style texts.

The appendix is a separate document.  It gathers everything the main note leaves out
(components of both IDCs, anatomy of the changes, decompositions by segment, IDC for
all income brackets, data-quality tests and methodology), with a reference tone: each
section says what the exhibit contains and how to read it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from src import low_income as LI
from src import lenses as L
from src.anatomy import Q_MODALIDADES
from src.exhibits import memo_sem_rendimento
from src.extras import Exibicoes, construir
from src.pt_format import mes, num, tabela_latex
from src.income_idc import (BAIXA_RENDA, JANELA_INICIO, c_normalizado, expanding_minmax, idc_baixa_renda, indice_por_faixa, primeira_exibicao,
                        sensibilidade)
from src.ref_check import carregar_cri, avaliar_c_nacional

FONTE_SGS = "Banco Central do Brasil (SGS), elaboração própria."
FONTE_SCR = "Banco Central do Brasil (SCR.data), elaboração própria."
SECAO_METODOLOGIA = r"Seção~\ref{sec:metodologia}"


@dataclass
class DadosApendice:
    t1: pd.Timestamp
    ext: Exibicoes
    low: pd.DataFrame
    f: LI.FatosBaixaRenda
    sgs: pd.DataFrame
    comp: pd.DataFrame
    idx: pd.DataFrame
    paineis: dict
    conc_hist: pd.DataFrame = field(default_factory=pd.DataFrame)
    quebras: pd.DataFrame = field(default_factory=pd.DataFrame)
    janeiros: pd.DataFrame = field(default_factory=pd.DataFrame)
    sens: pd.DataFrame = field(default_factory=pd.DataFrame)
    ref: pd.DataFrame = field(default_factory=pd.DataFrame)
    vintage: dict = field(default_factory=dict)
    memo: dict = field(default_factory=dict)
    conc_full: pd.DataFrame = field(default_factory=pd.DataFrame)
    sens_extra: dict = field(default_factory=dict)
    cenarios: pd.DataFrame = field(default_factory=pd.DataFrame)
    jan_stats: dict = field(default_factory=dict)
    sem_rend: pd.DataFrame = field(default_factory=pd.DataFrame)

    @property
    def t0(self) -> pd.Timestamp:
        return self.t1 - pd.DateOffset(years=1)

    @property
    def tprev(self) -> pd.Timestamp:
        return self.t1 - pd.DateOffset(months=1)


def reunir(t1: pd.Timestamp, sgs: pd.DataFrame, comp: pd.DataFrame, idx: pd.DataFrame, paineis: dict, brutos: dict,
           workbook: Path, scr_vintage: pd.DataFrame, cri_csv: Path) -> DadosApendice:
    ext = construir(t1, sgs, comp, idx, paineis, workbook, brutos)
    if ext.camada2 != "ok":
        raise RuntimeError(f"o apêndice exige a Camada 2: {ext.camada2}")
    idc = ext.dados["idc_faixa"]
    low = idc_baixa_renda(idc).loc[:t1]
    f = LI.fatos(low, idx["index"], comp, idx, t1)
    d = DadosApendice(t1=t1, ext=ext, low=low, f=f, sgs=sgs.loc[:t1], comp=comp, idx=idx, paineis=paineis)
    # reconciliation over the last 12 reference months
    linhas = []
    for m in pd.date_range(t1 - pd.DateOffset(months=11), t1, freq="MS"):
        c = L.conciliar(paineis["faixa"], sgs.loc[:m], m - pd.DateOffset(years=1), m)
        c["mes"] = m
        linhas.append(c)
    d.conc_hist = pd.DataFrame(linhas).set_index("mes")
    # reclassification of weights (> 2 p.p. in a month) since the display start
    partes = []
    for nome, p in paineis.items():
        q = L.detectar_quebras(p, primeira_exibicao() - pd.DateOffset(months=1), t1, limiar_pp=2.0)
        if not q.empty:
            partes.append(q.assign(lente=nome))
    d.quebras = pd.concat(partes) if partes else pd.DataFrame(columns=["data_base", "unidade", "variacao_pp", "lente"])
    # January steps of the low-income group (every January since the SCR.data series starts, Jan-2013 on)
    r = L.taxas(paineis["faixa"]).xs(BAIXA_RENDA, level="grupo").loc[:t1]
    ger_i = sgs["inad_total"]
    ger_q = 100 * sum(sgs[f"saldo_{m}"] for m in Q_MODALIDADES) / sgs["saldo_total"]
    dif_mes = r.diff().loc["2013-01-01":]
    j = dif_mes[dif_mes.index.month == 1]
    d.janeiros = pd.DataFrame({"peso": j["peso"], "I": j["I"], "Q": j["Q"], "I_geral": ger_i.diff().reindex(j.index),
                               "Q_geral": ger_q.diff().reindex(j.index)})
    d.jan_stats = {"n": len(j), "peso_jan": float(j["peso"].mean()), "peso_demais": float(dif_mes.loc[dif_mes.index.month != 1, "peso"].mean()),
                   "peso_pos": int((j["peso"] > 0).sum()), "q_pos_grupo": int((j["Q"] > 0).sum()), "q_pos_geral": int((d.janeiros["Q_geral"] > 0).sum())}
    fora_jan = d.quebras[(d.quebras["lente"] == "faixa") & (d.quebras["unidade"] == BAIXA_RENDA) & (d.quebras["data_base"].dt.month != 1)]
    d.cenarios = _cenarios(low, ger_i, ger_q, c_normalizado(comp), list(j.index), sorted(fora_jan["data_base"]))
    d.sens = sensibilidade(paineis["faixa"], c_normalizado(comp), sgs.loc[:t1], t1)
    d.memo = memo_sem_rendimento(ext.dados["ctx"], brutos["faixa"])
    bf = brutos["faixa"].copy()
    bf["data_base"] = pd.to_datetime(bf["data_base"], format="mixed").dt.to_period("M").dt.to_timestamp()
    sr = bf[bf["unidade"] == "Sem rendimento"].groupby("data_base")[["carteira", "inad"]].sum()
    d.sem_rend = pd.DataFrame({"peso": 100 * sr["carteira"] / bf.groupby("data_base")["carteira"].sum(), "I": 100 * sr["inad"] / sr["carteira"]}).loc[:t1]
    longo = []
    for m in pd.date_range("2016-01-01", t1, freq="MS"):
        c = L.conciliar(paineis["faixa"], sgs.loc[:m], m - pd.DateOffset(years=1), m)
        c["mes"] = m
        longo.append(c)
    d.conc_full = pd.DataFrame(longo).set_index("mes")
    base = indice_por_faixa(paineis["faixa"], c_normalizado(comp))
    alt = indice_por_faixa(paineis["faixa"], c_normalizado(comp), inicio=pd.Timestamp("2014-01-01"))
    dif = pd.concat({fx: (alt[(fx, "IDC")] - base[(fx, "IDC")]).loc[primeira_exibicao():t1] for fx in L.FAIXAS_INDICE}, axis=1)
    d.sens_extra = {"media_abs_2018": float(dif.loc["2018":].abs().mean().max()), "media_abs_2022": float(dif.loc["2022":].abs().mean().max()),
                    "max_2015_16": float(dif.loc["2015":"2016"].abs().max().max()), "max_2017": float(dif.loc["2017":].abs().max().max())}
    d.ref = avaliar_c_nacional(comp, idc, carregar_cri(cri_csv))
    v = scr_vintage.copy()
    v["generated"] = pd.to_datetime(v["generated"])
    v["mes"] = pd.to_datetime(v["member"].str.extract(r"scrdata_(\d{6})")[0], format="%Y%m")
    uso = v[(v["mes"] >= JANELA_INICIO) & (v["mes"] <= t1)]
    d.vintage = {"n": len(uso), "min": uso["generated"].min(), "max": uso["generated"].max(),
                 "gerado_t1": v.loc[v["mes"] == t1, "generated"].iloc[0], "ultimo_mes_disponivel": v["mes"].max(),
                 "gerado_ultimo": v.loc[v["mes"].idxmax(), "generated"]}
    return d


def _substituir_variacoes(low: pd.DataFrame, ger_i: pd.Series, ger_q: pd.Series, c_norm: pd.Series, meses: list) -> pd.Series:
    """IDC of the group if, in ``meses``, the monthly changes of I and Q were those of the general series."""
    meses = pd.DatetimeIndex(meses)

    def serie(s_low: pd.Series, s_ger: pd.Series) -> pd.Series:
        dm = s_low.diff()
        dg = s_ger.diff().reindex(dm.index)
        sel = dm.index.isin(meses)
        d2 = dm.copy()
        d2[sel] = dg[sel]
        return s_low.iloc[0] + d2.fillna(0).cumsum()

    c = c_norm.reindex(low.index)
    return (c + expanding_minmax(serie(low["I"], ger_i)) + expanding_minmax(serie(low["Q"], ger_q))) / 3


def _cenarios(low: pd.DataFrame, ger_i: pd.Series, ger_q: pd.Series, c_norm: pd.Series, janeiros: list, fora_jan: list) -> pd.DataFrame:
    """Sensitivity of the low-income IDC to composition jumps (stress test, not a corrected series)."""
    ini = primeira_exibicao()
    linhas = {}
    for nome, meses in (("janeiros", janeiros), ("fora_jan", fora_jan), ("ambos", janeiros + fora_jan)):
        alt = _substituir_variacoes(low, ger_i, ger_q, c_norm, meses)
        dif = (alt - low["IDC"]).loc[ini:]
        linhas[nome] = {"idc_t1": float(alt.iloc[-1]), "var_t1": float(dif.iloc[-1]), "media_abs": float(dif.abs().mean()),
                        "max_abs": float(dif.abs().max()), "mes_max": dif.abs().idxmax(), "n_meses": len(meses)}
    return pd.DataFrame(linhas).T


# =============================================================================== tables
def tab_evolucao(d: DadosApendice) -> str:
    sg = d.sgs
    t0, tp, t1 = d.t0, d.tprev, d.t1
    q_ger = 100 * sum(sg[f"saldo_{m}"] for m in Q_MODALIDADES) / sg["saldo_total"]
    def linha(rotulo, serie, nd, sinal_delta=True, delta_unidade=""):
        return [rotulo, num(serie.loc[t0], nd), num(serie.loc[tp], nd), num(serie.loc[t1], nd),
                num(serie.loc[t1] - serie.loc[tp], nd, True), num(serie.loc[t1] - serie.loc[t0], nd, True)]
    linhas = [
        linha(r"\textbf{IDC geral}", d.idx["index"], 3), linha(r"\textbf{IDC para baixa renda}", d.low["IDC"], 3),
        linha(r"C --- comprometimento de renda, \%", sg["C_total"], 2),
        linha(r"I geral (SGS), \%", sg["inad_total"], 2),
        linha(r"I baixa renda (SCR.data), \%", d.low["I"], 2),
        linha(r"Q geral (SGS), \%", q_ger, 2),
        linha(r"Q baixa renda (SCR.data), \%", d.low["Q"], 2),
    ]
    return tabela_latex(
        "Evolução recente dos dois índices e de seus componentes brutos.", "tab:evolucao",
        ["Indicador", mes(t0), mes(tp), mes(t1), "Δ mês", "Δ 12 meses"], linhas,
        r">{\raggedright\arraybackslash}p{5.6cm}rrrrr",
        "Banco Central do Brasil (SGS e SCR.data), elaboração própria. C: SGS 29034; I geral: SGS 21112. Componentes brutos com duas casas decimais (a Nota usa uma). "
        "Variações dos índices em pontos; dos componentes, em p.p.; todas calculadas sobre os valores não arredondados.", tamanho=r"\small", separadores=(1,), posicao="H")


def tab_anual(d: DadosApendice) -> str:
    rel = d.f.relacao
    linhas = []
    for ano in sorted(rel["idc_por_ano"]):
        linhas.append([str(ano), num(rel["geral_por_ano"][ano], 3), num(rel["idc_por_ano"][ano], 3), num(rel["por_ano"][ano], 3, True)])
    return tabela_latex(
        "IDC geral e IDC para baixa renda: média anual dos meses exibidos.", "tab:anual",
        ["Ano", "IDC geral", "IDC baixa renda", "Diferença"], linhas, r"lrrr",
        f"Banco Central do Brasil (SGS e SCR.data), elaboração própria. {d.f.inicio.year} inclui {mes(d.f.inicio)} a dez-{d.f.inicio.year}; {d.t1.year}, jan-{d.t1.year} a {mes(d.t1)}. "
        "Diferença = IDC para baixa renda menos IDC geral.", tamanho=r"\small", posicao="H")


def tab_conciliacao_t1(d: DadosApendice) -> str:
    c = d.ext.dados["conciliacao"]
    sg, t0, t1 = d.sgs, d.t0, d.t1
    nac = L.totais(d.paineis["faixa"])
    q_of = lambda t: 100 * sum(sg[f"saldo_{m}"].loc[t] for m in Q_MODALIDADES) / sg["saldo_total"].loc[t]  # noqa: E731
    linhas = [
        [r"Inadimplência (I), \% --- " + mes(t1), num(c["I_scr_t1"], 2), num(c["I_sgs_t1"], 2), num(c["gap_I_nivel"], 2, True)],
        [r"Variação de I em 12 meses, p.p.", num(nac["I"].loc[t1] - nac["I"].loc[t0], 2, True), num(sg["inad_total"].loc[t1] - sg["inad_total"].loc[t0], 2, True), num(c["gap_I_delta"], 2, True)],
        [r"Crédito oneroso (Q), \% --- " + mes(t1), num(c["Q_scr_t1"], 2), num(c["Q_sgs_t1"], 2), num(c["gap_Q_nivel"], 2, True)],
        [r"Variação de Q em 12 meses, p.p.", num(nac["Q"].loc[t1] - nac["Q"].loc[t0], 2, True), num(q_of(t1) - q_of(t0), 2, True), num(c["gap_Q_delta"], 2, True)],
        [r"Saldo do crédito livre PF, R\$ bilhões --- " + mes(t1), num(nac["carteira"].loc[t1] / 1e9, 1), num(sg["saldo_total"].loc[t1] / 1e3, 1),
         num(c["gap_carteira_pct"], 1, True) + r"\%"],
    ]
    return tabela_latex(
        f"Conciliação do SCR.data com o SGS em {mes(t1)}.", "tab:conc_t1", ["Medida", "SCR.data", "SGS", "Diferença"], linhas,
        r">{\raggedright\arraybackslash}p{7.2cm}rrr",
        "Banco Central do Brasil (SGS e SCR.data), elaboração própria. Diferença = SCR.data menos SGS (no saldo, em \\%). "
        f"Status de I: {c['status']}; de Q: {c['status_Q']} (Seção~\\ref{{sec:qualidade}}).", tamanho=r"\small", posicao="H")


def tab_conciliacao_hist(d: DadosApendice) -> str:
    linhas = []
    for m, r in d.conc_hist.iterrows():
        linhas.append([mes(m), num(r["I_scr_t1"], 2), num(r["I_sgs_t1"], 2), num(r["gap_I_nivel"], 2, True), num(r["gap_I_delta"], 2, True),
                       num(r["gap_Q_delta"], 2, True), r["status"], r["status_Q"]])
    return tabela_latex(
        "Conciliação do SCR.data com o SGS nos últimos 12 meses de referência.", "tab:conc_hist",
        ["Mês", "I SCR.data", "I SGS", "Dif. nível I", "Dif. Δ12m I", "Dif. Δ12m Q", "Status I", "Status Q"], linhas, r"lrrrrrll",
        "Banco Central do Brasil (SGS e SCR.data), elaboração própria. Valores em \\% e p.p.; Dif. = SCR.data menos SGS; "
        "Δ12m = variação em 12 meses. Alerta: diferença acima de 0,25 p.p.; bloqueio: acima de 0,75 p.p.", tamanho=r"\small", posicao="H")


def tab_quebras(d: DadosApendice) -> str:
    nomes = {"faixa": "Faixa de renda", "credor": "Credor", "ocupacao": "Ocupação", "uf": "UF"}
    linhas = []
    q = d.quebras
    for (lente, m), g in q.groupby(["lente", "data_base"]):
        detalhe = "; ".join(f"{r.unidade} {num(r.variacao_pp, 1, True)}" for r in g.sort_values("variacao_pp", ascending=False).itertuples())
        linhas.append((nomes[lente], m, detalhe))
    ordem = {v: i for i, v in enumerate(nomes.values())}
    linhas.sort(key=lambda r: (ordem[r[0]], r[1]))
    linhas = [[lente, mes(m), detalhe] for lente, m, detalhe in linhas]
    sem = [nome for lente, nome in nomes.items() if lente not in set(q["lente"])]
    nota_sem = f" Sem variação de peso acima de 2 p.p. em: {', '.join(sem)}." if sem else ""
    return tabela_latex(
        "Reclassificações de peso superiores a 2 p.p. em um único mês (" + mes(primeira_exibicao()) + " a " + mes(d.t1) + ").", "tab:quebras",
        ["Lente", "Mês", "Unidades e variação do peso (p.p.)"], linhas, r"llp{9.8cm}",
        "Banco Central do Brasil (SCR.data), elaboração própria. Variação do peso da unidade no crédito livre PF em relação ao mês anterior." + nota_sem,
        tamanho=r"\small", posicao="H")


def tab_janeiros(d: DadosApendice) -> str:
    linhas = []
    for ano, r in d.janeiros.iterrows():
        linhas.append([f"jan-{ano.year}", num(r["peso"], 2, True), num(r["I"], 2, True), num(r["Q"], 2, True), num(r["I_geral"], 2, True), num(r["Q_geral"], 2, True)])
    media = d.janeiros.mean()
    linhas.append([r"\textit{Média}", num(media["peso"], 2, True), num(media["I"], 2, True), num(media["Q"], 2, True), num(media["I_geral"], 2, True), num(media["Q_geral"], 2, True)])
    return tabela_latex(
        "Variação do grupo de baixa renda nos meses de janeiro, comparada à da série geral (p.p.).", "tab:janeiros",
        ["Mês", "Peso do grupo", "I do grupo", "Q do grupo", "I geral", "Q geral"], linhas, r"lrrrrr",
        "Banco Central do Brasil (SGS e SCR.data), elaboração própria. Variação em relação a dezembro. Peso = participação do grupo "
        "no crédito livre PF.", tamanho=r"\small", separadores=(len(linhas) - 2,), posicao="H")


def tab_cenarios(d: DadosApendice) -> str:
    c, obs = d.cenarios, float(d.low["IDC"].iloc[-1])
    jan_mes = f"janeiros de {d.janeiros.index[0].year} a {d.janeiros.index[-1].year}"
    fora = sorted(d.quebras[(d.quebras["lente"] == "faixa") & (d.quebras["unidade"] == BAIXA_RENDA) & (d.quebras["data_base"].dt.month != 1)]["data_base"])
    rotulos = {"janeiros": f"Sem os saltos de janeiro ({jan_mes})",
               "fora_jan": "Sem as reclassificações fora de janeiro (" + ", ".join(mes(m) for m in fora) + ")",
               "ambos": "Sem ambos"}
    linhas = [["Série observada", num(obs, 3), "---", "---", "---"]]
    for k, rot in rotulos.items():
        r = c.loc[k]
        linhas.append([rot, num(r["idc_t1"], 3), num(r["var_t1"], 3, True), num(r["media_abs"], 3), num(r["max_abs"], 3) + f" ({mes(r['mes_max'])})"])
    return tabela_latex(
        f"Sensibilidade do IDC para baixa renda a saltos de composição do grupo --- {mes(d.t1)}.", "tab:cenarios",
        ["Cenário", f"IDC {mes(d.t1)}", "Variação", r"Média $|$var.$|$", r"Máx. $|$var.$|$"], linhas, r">{\raggedright\arraybackslash}p{5.9cm}rrrr",
        "Banco Central do Brasil (SGS e SCR.data), elaboração própria. Nos meses indicados, as variações mensais de I e de Q do grupo são substituídas "
        "pelas da série geral e o índice é recalculado. Variação = cenário menos série observada; média e máximo em valor absoluto entre "
        + mes(primeira_exibicao()) + " e " + mes(d.t1) + ". Teste de sensibilidade, não série corrigida.", tamanho=r"\small", posicao="H")


def tab_sensibilidade(d: DadosApendice) -> str:
    s = d.sens
    linhas = []
    for nome, r in s.iterrows():
        linhas.append([nome, *(num(r[f], 3) for f in L.FAIXAS_INDICE), num(r["máx |dif. vs base| (2015-)"], 3)])
    return tabela_latex(
        f"Sensibilidade do IDC por faixa de renda a escolhas de construção --- {mes(d.t1)}.", "tab:sensibilidade",
        ["Variante", *L.FAIXAS_INDICE, "Dif. máx. 2015-"], linhas, r">{\raggedright\arraybackslash}p{4.4cm}rrrrr",
        "Banco Central do Brasil (SGS e SCR.data), elaboração própria. Janela desde jan/2014: I e Q das faixas normalizados com início em jan-2014. "
        "Reescalado: I e Q de cada faixa multiplicados mensalmente pela razão entre o valor oficial (SGS) e o total do SCR.data. "
        "A última coluna é a maior diferença absoluta em relação à base entre mai-2015 e o mês de referência.", tamanho=r"\small", posicao="H")


def tab_teste_ref(d: DadosApendice) -> str:
    r = d.ref
    ult = r["ult_mes"].iloc[0]
    linhas = []
    for faixa, x in r.iterrows():
        linhas.append([faixa, num(x["corr_c_d12"], 2), num(x["vies_c"], 2, True), num(x["erro_medio_idc"], 3, True), num(x["erro_max_idc"], 3),
                       num(x["corr_idc_d12"], 2), num(x["idc_nac_ult"], 3) + " / " + num(x["idc_faixa_ult"], 3)])
    dir_ = lambda larg: r">{\raggedleft\arraybackslash}p{" + larg + "}"  # noqa: E731
    colunas = r">{\raggedright\arraybackslash}p{2.4cm}" + dir_("1.7cm") * 5 + dir_("2.5cm")
    return tabela_latex(
        f"Teste do C nacional contra o comprometimento de renda individual (CRI) de cada faixa, dez-2020 a {mes(ult)}.", "tab:teste_ref",
        ["Faixa", r"Corr. $\Delta$12m de C", "Viés de C", "Erro médio do IDC", "Erro máx. do IDC", r"Corr. $\Delta$12m do IDC", f"IDC {mes(ult)} (C nac. / CRI)"], linhas,
        colunas,
        "Banco Central do Brasil (REF de abril de 2025, Gráfico 1.2.2.16; SGS e SCR.data), elaboração própria. CRI normalizado por min-max com janela "
        r"expansiva desde dez-2018. Erro = IDC com C nacional menos IDC com o CRI da faixa; $\Delta$12m = variação em 12 meses. O CRI refere-se a tomadores com renda; a faixa até 2 SM do "
        "IDC inclui os sem rendimento.", tamanho=r"\footnotesize", tabcolsep="2.5pt", posicao="H")


def corrigir_referencias(tex: str) -> str:
    """Point table sources to the methodology section instead of the main note's \"Notas\"."""
    return tex.replace("(ver Notas)", f"(ver {SECAO_METODOLOGIA})")


def preparar_tabela(tex: str) -> str:
    """Floating table for the appendix whose source note stays inside the float (the note never detaches from its table)."""
    tex = corrigir_referencias(tex).replace(r"\begin{table}[H]", r"\begin{table}[htbp]")
    return re.sub(r"\\end\{table\}\n\n(\\fonte\{[^\n]*\})\n", lambda m: m.group(1) + "\n\\end{table}\n", tex)
