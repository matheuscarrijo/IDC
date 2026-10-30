"""Appendix-style text of the IDC statistical appendix (Portuguese).

Tone: reference document.  Each section says what the exhibit contains, how it is built and
what the numbers of the reference month are, without the narrative of the monthly note.
Numbers in running text are not bold (bold is a convention of the note).  Every figure quoted
comes from the data (``DadosApendice``) so that the text can be regenerated each month.
"""
from __future__ import annotations

import pandas as pd

from src import lenses as L
from src.anatomy import PRODUTOS, Q_MODALIDADES
from src.appendix_data import DadosApendice
from src.exhibits import FAIXA_TEXTO, FRASE_GRUPO, FRASE_NO, FRASE_PELO, _lista
from src.pt_format import mes, num, pct, pp
from src.income_idc import BAIXA_RENDA


def T(rot: str) -> str:
    return f"Tabela~\\ref{{{rot}}}"


def F(rot: str) -> str:
    return f"Figura~\\ref{{{rot}}}"


def S(rot: str) -> str:
    return f"Seção~\\ref{{{rot}}}"


def Fs(a: str, b: str) -> str:
    return f"Figuras~\\ref{{{a}}} e~\\ref{{{b}}}"


def _aspas(texto: str) -> str:
    return "``" + texto + "''"


def _periodo(anos: list[int], prep_lista: str = "em") -> str:
    """``[2017, 2018, 2019, 2020]`` -> ``de 2017 a 2020``; other sets -> ``em 2017 e 2019``."""
    anos = sorted(anos)
    if len(anos) > 2 and anos == list(range(anos[0], anos[-1] + 1)):
        return f"de {anos[0]} a {anos[-1]}"
    return f"{prep_lista} {_lista([str(a) for a in anos])}"


def _meses(meses: list) -> str:
    """List of months; three or more consecutive months are written as a range (``fev-2026 a jun-2026``)."""
    meses = sorted(meses)
    grupos, atual = [], [meses[0]] if meses else []
    for m in meses[1:]:
        if m == atual[-1] + pd.DateOffset(months=1):
            atual.append(m)
        else:
            grupos.append(atual)
            atual = [m]
    if atual:
        grupos.append(atual)
    itens = [f"{mes(g[0])} a {mes(g[-1])}" if len(g) >= 3 else _lista([mes(m) for m in g]) for g in grupos]
    return _lista(itens)


def _ponto(x: float, nd: int = 3, sinal: bool = True) -> str:
    return num(x, nd, sinal) + "~ponto"


# ================================================================================ 1. escopo
def s1_escopo(d: DadosApendice) -> str:
    return rf"""
\section{{Escopo e organização}}\label{{sec:escopo}}

Este apêndice acompanha a Nota Técnica de Atualização do Índice de Desconforto de Crédito (IDC) com divulgação em
\mespublicacao{{}} (competência \competencia), cujo último mês de referência é \mesreferencia{{}}. Ele reúne, em documento
separado, as informações estatísticas que sustentam e ampliam a Nota: os dois índices nela apresentados (o IDC
geral e o IDC para a população de baixa renda), a decomposição das variações de I, Q e C, as decomposições de I e Q por faixa
de renda, credor, ocupação e unidade da federação, o IDC calculado para as quatro faixas de renda e os testes de qualidade e
conciliação dos dados. A Nota é a referência para a leitura dos resultados; este apêndice não os altera nem os substitui.

\paragraph{{Organização.}} A {S('sec:indices')} define os dois índices da Nota e detalha seus componentes. A {S('sec:anatomia')}
decompõe as variações de I, Q e C com as séries do SGS. A {S('sec:segmentos')} decompõe I e Q por segmento com o SCR.data. A
{S('sec:faixas')} apresenta o IDC para as quatro faixas de renda e seus limites. A {S('sec:qualidade')} trata da qualidade e da
conciliação dos dados, e a {S('sec:metodologia')} descreve os métodos e as fontes. As tabelas e as figuras têm o prefixo A, para
distingui-las das da Nota.

\paragraph{{Convenções.}} Salvo indicação em contrário, as taxas são percentuais do saldo do crédito livre de pessoas físicas;
as variações são em pontos percentuais (p.p.); ``12 meses'' compara o mês de referência com o mesmo mês do ano anterior; e os
valores normalizados variam de 0,000 (melhor posição histórica) a 1,000 (pior), como no IDC. As séries do SGS aparecem com duas
casas decimais, o que permite as decomposições, ao passo que a planilha mensal usada na Nota as traz com uma. As decomposições
por segmento cobrem o crédito livre de pessoas físicas, exceto financiamento rural, imobiliário e de exportação ou importação.
SGS refere-se ao Sistema Gerenciador de Séries Temporais e SCR.data, aos dados agregados do Sistema de Informações de Crédito (SCR), ambos do Banco Central do Brasil.
"""


# ================================================================================ 2. dois índices
def s2_indices(d: DadosApendice, tabs: dict) -> str:
    f, sg = d.f, d.sgs
    t1, t0 = d.t1, d.t0
    i_ger = float(sg["inad_total"].loc[t1])
    i_ger0 = float(sg["inad_total"].loc[t0])
    q_ger = float(100 * sum(sg[f"saldo_{m}"].loc[t1] for m in Q_MODALIDADES) / sg["saldo_total"].loc[t1])
    rel = f.relacao
    anos = sorted(rel["por_ano"])
    alto = [a for a in anos if rel["por_ano"][a] >= 0.2]
    recente = [a for a in anos if a >= t1.year - 3]
    g1, g0 = float(d.idx["index"].loc[t1]), float(d.idx["index"].loc[t0])
    l1, l0 = f.idc["t1"], f.idc["t0"]
    igual = round(l1, 3) == round(f.geral["idc_t1"], 3)
    valores = (f"os dois índices valem {num(l1, 3)}" if igual else
               f"o IDC para baixa renda vale {num(l1, 3)} e o IDC geral, {num(f.geral['idc_t1'], 3)}")
    frase_alto = (f"A diferença foi maior {_periodo(alto)}, com médias anuais de {num(min(rel['por_ano'][a] for a in alto), 2)} a "
                  f"{num(max(rel['por_ano'][a] for a in alto), 2)} ponto ({T('tab:anual')}), e desde {recente[0]} varia entre "
                  f"{num(min(rel['por_ano'][a] for a in recente), 2, True)} e {num(max(rel['por_ano'][a] for a in recente), 2, True)}. ") if alto else ""
    return rf"""
\section{{Os dois índices da Nota}}\label{{sec:indices}}

\subsection{{Definições}}

O IDC geral é a média simples de três componentes normalizados: o comprometimento de renda das famílias com o serviço da dívida
(C, SGS~29034), a inadimplência da carteira de crédito livre de pessoas físicas, com atrasos acima de 90 dias (I, SGS~21112), e a
participação do crédito oneroso (cheque especial, crédito pessoal não consignado, cartão rotativo e cartão parcelado) no saldo do
crédito livre PF (Q). Cada componente é normalizado pelo método min-max com janela expansiva desde \seriesinicio, e o índice é
exibido desde \janelainicio.

O IDC para a população de baixa renda mantém o C nacional e substitui I e Q pelos valores do crédito livre tomado por pessoas físicas
com renda de até 2 salários mínimos (SM), incluindo as que não têm rendimento, segundo a faixa de renda informada ao Sistema de
Informações de Crédito (SCR). I e Q desse grupo vêm do SCR.data e são normalizados com janela expansiva desde jul-2012, o primeiro
mês do SCR.data; o índice é exibido desde {mes(f.inicio)}, 34 meses depois, o mesmo período de aquecimento do IDC geral. O Banco Central
não divulga o comprometimento de renda por faixa de renda, e por isso os dois índices compartilham C: as diferenças entre eles vêm
somente de I e Q.

\subsection{{Componentes em {mes(t1)}}}

A {T('tab:componentes')} apresenta, para cada índice, os componentes em valor bruto e na escala normalizada. Em {mes(t1)}, {valores}. A inadimplência do grupo de baixa renda
({pct(f.i['t1'], 2)}) supera a do total ({pct(i_ger, 2)}) em {num(f.i['t1'] - i_ger, 2)}~p.p., e o crédito oneroso responde por {pct(f.q['t1'], 1)} do
crédito livre do grupo e por {pct(q_ger, 1)} do total. Na escala normalizada, porém, as posições são próximas: I em
{num(f.i['norm_t1'], 3)} no grupo e {num(f.geral['I_norm_t1'], 3)} no total, e Q em {num(f.q['norm_t1'], 3)} e {num(f.geral['Q_norm_t1'], 3)}.

{tabs['componentes']}

\subsection{{Trajetória e comparação}}

A {T('tab:evolucao')} mostra a evolução recente dos dois índices e de seus componentes brutos. Em 12 meses, o IDC geral passou de
{num(g0, 3)} para {num(g1, 3)} ({_ponto(g1 - g0)}) e o IDC para baixa renda, de {num(l0, 3)} para {num(l1, 3)} ({_ponto(l1 - l0)}); a inadimplência do grupo de baixa renda
variou {num(f.i['t1'] - f.i['t0'], 2, True)}~p.p., contra {num(i_ger - i_ger0, 2, True)}~p.p. no total.

{tabs['evolucao']}

Entre {mes(f.inicio)} e {mes(t1)}, o IDC para baixa renda ficou acima do geral em {num(100 * rel['share_acima'], 0)}\% dos meses, com diferença média
de {num(rel['media_dif'], 3)} ponto e correlação de {num(rel['corr_nivel'], 2)} nos níveis e de {num(rel['corr_d12'], 2)} nas variações de 12 meses.
{frase_alto}As diferenças anteriores a 2019 devem ser lidas com cautela, porque o SCR registra mudanças bruscas na classificação por faixa
de renda em nov-2018 e mar-2019 ({S('sec:qualidade')}). As {Fs('fig:indice', 'fig:componentes')} mostram as séries.

{tabs['anual']}
"""


# ================================================================================ 3. anatomia
def s3_anatomia(d: DadosApendice, tabs: dict) -> str:
    a, cq = d.ext.dados["anatomia"], d.ext.dados["c_q"]
    t1, tp = d.t1, d.tprev
    m, an, gm = a["mensal"], a["anual"], a["gm"]
    sg = d.sgs["inad_total"]
    top = gm.sort_values("total", ascending=False)
    principais = [f"{FRASE_GRUPO[g]} ({pp(top.loc[g, 'total'], 2)})" for g in top.index[:3]]
    comp = an.tabela.sort_values("composicao", ascending=False).iloc[0]
    cm, ca, qm, q = cq["cm"], cq["ca"], cq["qm"], cq["q"]
    ck, jk, ak, ek = ("C — serviço da dívida (SGS 29034)", "dos quais juros (SGS 29033)", "dos quais amortização (SGS 29036)",
                      cm.index[-1])
    pf = d.ext.dados["preco_fluxo"]
    tot, priv = pf.loc["Total do crédito livre PF"], pf.loc["Crédito pessoal — consignado, setor privado"]
    maior_q = qm["contribuicao"].abs().idxmax()
    return rf"""
\section{{Anatomia das variações de I, Q e C}}\label{{sec:anatomia}}

Esta seção decompõe as variações de I, Q e C com as séries do SGS por modalidade, a mesma fonte e a mesma safra do IDC. Para I, a
variação entre dois meses é dividida em uma parte \emph{{dentro dos produtos}}, que mede quanto mudou a inadimplência de cada
produto, ponderada pelo peso médio do produto na carteira, e uma parte de \emph{{composição}}, que mede o efeito da mudança do peso de
cada produto no crédito livre PF ({S('sec:metodologia')}). A média das taxas por modalidade, ponderada pelos saldos, reproduz o nível de I com
diferença máxima de 0,01~p.p., e a soma das contribuições coincide com a variação oficial a menos do arredondamento das séries publicadas.

A {T('tab:anatomia')} traz as contribuições dos grupos de produtos no mês e em 12 meses. Em {mes(t1)}, I passou de {pct(sg.loc[tp], 2)} para
{pct(sg.loc[t1], 2)} ({pp(m.delta_oficial, 2)}), dos quais {pp(m.dentro, 2)} dentro dos produtos e {pp(m.composicao, 2)} por composição; as maiores contribuições vieram de
{_lista(principais)}. Em 12 meses, I variou {num(an.delta_oficial, 2, True)}~p.p., com {pp(an.dentro, 2)} dentro dos produtos e {pp(an.composicao, 2)} por composição; o efeito
composição concentra-se {FRASE_NO.get(comp.name, 'em ' + comp['produto'].lower())}, cujo peso no crédito livre PF passou de {pct(comp['peso_t0'], 1)} para {pct(comp['peso_t1'], 1)}
e cuja inadimplência é de {pct(comp['I_t1'], 1)}.

{tabs['anatomia']}

A {T('tab:c_q')} apresenta C e Q. Q variou {pp(q.loc[t1] - q.loc[tp], 2)} no mês ({pct(q.loc[tp], 2)} para {pct(q.loc[t1], 2)}), principalmente
{FRASE_PELO.get(maior_q, 'por ' + PRODUTOS[maior_q][0].lower())} ({pp(qm.loc[maior_q, 'contribuicao'], 2)}). C variou {pp(cm.loc[ck, 'delta'], 2)} ({pct(cm.loc[ck, 't0'], 2)} para
{pct(cm.loc[ck, 't1'], 2)}), com {pp(cm.loc[jk, 'delta'], 2)} de juros e {pp(cm.loc[ak, 'delta'], 2)} de amortização; em 12 meses, C variou {num(ca.loc[ck, 'delta'], 2, True)}~p.p.,
sendo {num(ca.loc[jk, 'delta'], 2, True)} de juros e {num(ca.loc[ak, 'delta'], 2, True)} de amortização. O endividamento (dívida sobre a renda de 12 meses) variou
{pp(ca.loc[ek, 'delta'], 2)} em 12 meses.

{tabs['c_q']}

A {T('tab:preco_fluxo')} reúne taxas médias e concessões por modalidade, das Tabelas 11 e 16 da planilha mensal. A taxa média do crédito livre PF foi de
{pct(tot['taxa_t1'], 1)} a.a. em {mes(t1)} ({pp(tot['taxa_delta'], 1)} em 12 meses). As concessões de consignado do setor privado somaram R\$~{num(priv['fluxo_12m_bi'], 1)}~bilhões em 12 meses
({num(priv['fluxo_var_pct'], 1, True)}\%), a {pct(priv['taxa_t1'], 1)} a.a. A {F('fig:atribuicao')} mostra as contribuições mensais dos grupos de produtos à variação de I nos últimos 18 meses.

{tabs['preco_fluxo']}
"""


# ================================================================================ 4. segmentos
def _frase_quebras(d: DadosApendice, lente: str) -> str:
    q = d.quebras[d.quebras["lente"] == lente].sort_values("data_base")
    if q.empty:
        return ""
    meses = sorted(set(q["data_base"]))
    return (f"Há variações de peso superiores a 2~p.p. em um único mês em {_meses(meses)} ({T('tab:quebras')}); comparações que atravessam "
            f"{'esse mês' if len(meses) == 1 else 'esses meses'} devem ser evitadas. ")


def s4_segmentos(d: DadosApendice, tabs: dict) -> str:
    ext = d.ext
    conc = ext.dados["conciliacao"]
    tb, decs = ext.dados["tabs"], ext.dados["decs"]
    t1, t0 = d.t1, d.t0
    dI = decs["faixa"]["dI"]
    memo, sr = d.memo, d.sem_rend
    # ---- faixa de renda
    fx = tb["faixa"].loc[list(L.FAIXAS_INDICE)]
    ord_ = fx["contribuicao"].sort_values(ascending=False)
    rel = (fx["x_t1"] / fx["x_t0"] - 1) * 100
    q_faixa = ext.dados["quebras"]["faixa"]
    if q_faixa.empty:
        aviso_faixa = ""
    else:
        unid = _lista([_aspas(u) for u in sorted(set(q_faixa["unidade"]))])
        aviso_faixa = (f" Houve variação de peso superior a 1~p.p. em {_meses(sorted(set(q_faixa['data_base'])))} nas faixas {unid}, "
                       "o que afeta a leitura da comparação de 12 meses dessas faixas.")
    sr19 = sr.loc["2019-01-01":]
    # ---- credor
    cr = tb["credor"]
    pesos_cr = 100 * L.taxas(d.paineis["credor"])["peso"].unstack() / 100
    ordem_cr = cr["contribuicao"].sort_values(ascending=False)
    c1, c2 = ordem_cr.index[0], ordem_cr.index[1]

    def decomp_cr(u: str) -> str:
        r = cr.loc[u]
        return (f"{pp(r['dentro'], 2)} dentro do segmento e {pp(r['composicao'], 2)} de composição "
                f"(peso de {pct(pesos_cr.loc[t0, u], 1)} para {pct(pesos_cr.loc[t1, u], 1)})")

    # ---- ocupação
    oc = tb["ocupacao"]
    ordem_oc = oc["contribuicao"].sort_values(ascending=False)
    # ---- UF
    uf = tb["uf"]
    ub = uf["contribuicao"].sort_values(ascending=False).head(3)
    ud = uf["dx"].sort_values(ascending=False).head(3)
    alto = uf["x_t1"].sort_values(ascending=False).head(3)
    frase_uf_quebras = _frase_quebras(d, "uf") or "A unidade da federação não registrou variações de peso superiores a 2~p.p. no período. "
    ap, sv = oc.loc["Aposentado/pensionista"], oc.loc["Servidor ou empregado público"]
    return rf"""
\section{{Decomposições por segmento}}\label{{sec:segmentos}}

\subsection{{Universo e leitura das tabelas}}

As tabelas desta seção usam o SCR.data, que o Banco Central divulga cerca de um mês depois do fechamento e reprocessa continuamente ({S('sec:qualidade')}). O universo
é o crédito livre de pessoas físicas, sem financiamento rural, imobiliário e de exportação ou importação, e equivale a {pct(100 + conc['gap_carteira_pct'], 1)} do saldo do
SGS~20570 em {mes(t1)} ({T('tab:conc_t1')}). Cada tabela decompõe a variação de I e a de Q em 12 meses em contribuições de cada segmento, somando o efeito da
variação da taxa do segmento (\emph{{dentro}}) e o da mudança de seu peso na carteira (\emph{{composição}}). A linha ``Total (SCR.data)'' soma as contribuições; a linha
``Variação oficial (SGS)'' traz a variação dos mesmos indicadores no SGS, e a diferença entre as duas é o resíduo de conciliação. Em {mes(t1)}, o resíduo de I é de
{num(abs(conc['gap_I_delta']), 2)}~p.p. (status {conc['status']}) e o de Q, de {num(abs(conc['gap_Q_delta']), 2)}~p.p. (status {conc['status_Q']}); por isso a coluna ``Contrib. Q'' é indicativa. O nível de Q no SCR.data
({pct(conc['Q_scr_t1'], 1)}) fica abaixo do oficial ({pct(conc['Q_sgs_t1'], 1)}) por diferenças de classificação das modalidades entre as fontes.

{tabs['conc_t1']}

\subsection{{Faixa de renda}}

Na {T('tab:faixa')}, a variação de I em 12 meses ({num(dI.delta_scr, 2, True)}~p.p. no SCR.data) tem as maiores contribuições nas faixas {FAIXA_TEXTO[ord_.index[0]]} ({pp(ord_.iloc[0], 2)}) e
{FAIXA_TEXTO[ord_.index[1]]} ({pp(ord_.iloc[1], 2)}), seguidas das faixas {FAIXA_TEXTO[ord_.index[2]]} ({pp(ord_.iloc[2], 2)}) e {FAIXA_TEXTO[ord_.index[3]]} ({pp(ord_.iloc[3], 2)}). A maior variação relativa da inadimplência
foi na faixa {FAIXA_TEXTO[rel.idxmax()]}, de {pct(fx.loc[rel.idxmax(), 'x_t0'], 2)} para {pct(fx.loc[rel.idxmax(), 'x_t1'], 2)} ({num(rel.max(), 1, True)}\%). A faixa ``Até 2 SM'' inclui o subgrupo sem rendimento,
que respondeu por {pct(memo['peso'], 1)} do crédito livre PF em {mes(t1)}, com inadimplência de {pct(memo['I_t1'], 2)} ({pct(memo['I_t0'], 2)} em {mes(t0)}). O subgrupo é pequeno e volátil: desde 2019, seu peso
variou entre {pct(sr19['peso'].min(), 1)} e {pct(sr19['peso'].max(), 1)} e sua inadimplência mensal, entre {pct(sr19['I'].min(), 0)} e {pct(sr19['I'].max(), 0)}.{aviso_faixa}

{tabs['faixa']}

\subsection{{Credor}}

Na {T('tab:credor')}, a maior contribuição à variação de I em 12 meses vem do segmento {c1} ({pp(cr.loc[c1, 'contribuicao'], 2)}) e a segunda, do segmento {c2} ({pp(cr.loc[c2, 'contribuicao'], 2)}). No segmento {c1}, a contribuição
decompõe-se em {decomp_cr(c1)}; no segmento {c2}, em {decomp_cr(c2)}. A inadimplência do segmento {c2} é de {pct(cr.loc[c2, 'x_t1'], 2)} e a do segmento {c1}, de {pct(cr.loc[c1, 'x_t1'], 2)}.
{_frase_quebras(d, 'credor')}

{tabs['credor']}

\subsection{{Ocupação}}

A {T('tab:ocupacao')} segue a natureza da ocupação principal, segundo o cadastro da Receita Federal. A categoria {_aspas(ordem_oc.index[0])} concentra {pct(oc.loc[ordem_oc.index[0], 'peso_t1'], 0)} da carteira e responde pela maior contribuição
({pp(ordem_oc.iloc[0], 2)}); em seguida vêm as categorias {_aspas(ordem_oc.index[1])} ({pp(ordem_oc.iloc[1], 2)}) e {_aspas(ordem_oc.index[2])} ({pp(ordem_oc.iloc[2], 2)}). Os aposentados e pensionistas têm contribuição de
{pp(ap['contribuicao'], 2)}, com inadimplência de {pct(ap['x_t1'], 2)}, e os servidores e empregados públicos, de {pp(sv['contribuicao'], 2)}, com {pct(sv['x_t1'], 2)}.
{_frase_quebras(d, 'ocupacao')}

{tabs['ocupacao']}

\subsection{{Unidade da federação}}

A {T('tab:uf')} traz as unidades da federação, definidas pelo CEP de residência do tomador. As maiores contribuições à variação de I vêm de {_lista([f'{k} ({pp(v, 2)})' for k, v in ub.items()])}, em boa parte por seus pesos na carteira;
as maiores variações da inadimplência foram as de {_lista([f'{k} ({pp(v, 2)})' for k, v in ud.items()])}, e as maiores taxas em {mes(t1)} são as de {_lista([f'{k} ({pct(v, 2)})' for k, v in alto.items()])}.
{frase_uf_quebras}As {Fs('fig:lentes', 'fig:uf')} resumem as contribuições por segmento e a inadimplência por unidade da federação.

{tabs['uf']}
"""


# ================================================================================ 5. faixas
def s5_faixas(d: DadosApendice, tabs: dict) -> str:
    r = d.ext.dados["resumo_idc"]
    ref, s, se = d.ref, d.sens, d.sens_extra
    t1 = d.t1
    var = {fx: r.loc[fx, "IDC_t1"] - r.loc[fx, "IDC_t0"] for fx in L.FAIXAS_INDICE}
    maior = max(var, key=var.get)
    base, janela, rees = s.index[0], s.index[1], s.index[2]
    col_max = "máx |dif. vs base| (2015-)"
    dif_j = {fx: s.loc[janela, fx] - s.loc[base, fx] for fx in L.FAIXAS_INDICE}
    dif_r = {fx: s.loc[rees, fx] - s.loc[base, fx] for fx in L.FAIXAS_INDICE}
    itens = _lista([f"{FAIXA_TEXTO[fx]} ({num(r.loc[fx, 'IDC_t1'], 3)})" for fx in L.FAIXAS_INDICE])
    n_sobe = sum(v > 0 for v in var.values())
    sobe = "nas quatro faixas" if n_sobe == 4 else f"em {n_sobe} das quatro faixas"
    # a bracket can sit at the top of its own history while its raw rate is not the highest
    topo = r["I_norm"].idxmax()
    maiores = [FAIXA_TEXTO[fx] for fx in L.FAIXAS_INDICE if r.loc[fx, "I"] > r.loc[topo, "I"]]
    perto = "no máximo" if r.loc[topo, "I_norm"] >= 0.9995 else "perto do máximo"
    if maiores:
        frase_topo = (f"a faixa {FAIXA_TEXTO[topo]} tem inadimplência de {pct(r.loc[topo, 'I'], 2)}, inferior à das faixas {_lista(maiores)}, mas valor normalizado de I de "
                      f"{num(r.loc[topo, 'I_norm'], 3)}, porque a inadimplência da faixa está {perto} da própria série")
    else:
        frase_topo = (f"a faixa {FAIXA_TEXTO[topo]} tem a maior inadimplência bruta ({pct(r.loc[topo, 'I'], 2)}) e valor normalizado de I de {num(r.loc[topo, 'I_norm'], 3)}")
    # national C against the bracket CRI (REF)
    r_b = ref.loc[BAIXA_RENDA]
    ult = ref["ult_mes"].iloc[0]
    maximo = [FAIXA_TEXTO[fx] for fx in L.FAIXAS_INDICE if ref.loc[fx, "c_faixa_ult"] >= 0.999]
    clausula_max = (f", enquanto o CRI das faixas {_lista(maximo)} estava no máximo da série desde dez-2018" if maximo else "")
    sentido = "abaixo" if r_b["idc_nac_ult"] < r_b["idc_faixa_ult"] else "acima"
    frase_max = (", em 2015 ou 2016" if abs(se["max_2015_16"] - s.loc[janela, col_max]) < 5e-4 else f" (em 2015 e 2016, até {num(se['max_2015_16'], 3)})")
    corr_min, corr_max = ref["corr_c_d12"].min(), ref["corr_c_d12"].max()
    menor_nac = min(L.FAIXAS_INDICE, key=lambda fx: ref.loc[fx, "idc_nac_ult"])
    menor_cri = min(L.FAIXAS_INDICE, key=lambda fx: ref.loc[fx, "idc_faixa_ult"])
    inv = ref.loc["Mais de 10 SM"]
    frase_ordem = (f"; com o C nacional, o menor índice entre as faixas é o da faixa {FAIXA_TEXTO[menor_nac]}, e com o CRI, o da faixa {FAIXA_TEXTO[menor_cri]}"
                   if menor_nac != menor_cri else "")
    comp_inv = "superava o calculado" if inv["idc_nac_ult"] > inv["idc_faixa_ult"] else "ficava abaixo do calculado"
    return rf"""
\section{{IDC por faixa de renda}}\label{{sec:faixas}}

A {T('tab:idc_faixa')} traz o IDC das quatro faixas de renda; a primeira, até 2~SM e incluindo os sem rendimento, é o IDC para baixa renda da Nota. A construção é a mesma para todas:
C nacional e I e Q de cada faixa, normalizados com janela expansiva desde jul-2012. Em {mes(t1)}, o índice vale, por faixa, {itens}. Em 12 meses, o índice subiu {sobe},
e a maior alta foi na faixa {FAIXA_TEXTO[maior]} ({num(var[maior], 3, True)} ponto). A {F('fig:idc_faixa')} mostra as séries desde {mes(d.f.inicio)}.

{tabs['idc_faixa']}

\paragraph{{Como ler.}} Como C é o mesmo em todas as faixas, as diferenças entre elas vêm somente de I e Q. Cada índice mede a posição da faixa em sua própria história, e não o
nível de desconforto: {frase_topo}. Por isso o índice por faixa não deve ser usado para ordenar faixas por desconforto, e cada faixa deve ser comparada com ela mesma ao longo do tempo. A faixa de
``renda indisponível'' fica fora do índice.

\paragraph{{Sensibilidade.}} A {T('tab:sensibilidade')} testa duas escolhas de construção. Iniciar a janela em jan-2014, em vez de jul-2012, altera o valor de {mes(t1)} em
{_lista([f'{num(abs(dif_j[fx]), 3)} ({FAIXA_TEXTO[fx]})' for fx in L.FAIXAS_INDICE])}; no período exibido, a diferença absoluta máxima é de {num(s.loc[janela, col_max], 3)}{frase_max}, e a média absoluta desde 2018 não passa de {num(se['media_abs_2018'], 3)}. Reescalar I e Q ao total oficial do SGS altera o valor de {mes(t1)} em até
{num(max(abs(v) for v in dif_r.values()), 3)} e, no histórico exibido, em até {num(s.loc[rees, col_max], 3)}.

{tabs['sensibilidade']}

\paragraph{{Teste do C nacional.}} A edição de abril de 2025 do Relatório de Estabilidade Financeira (REF) publicou o comprometimento de renda individual (CRI) por faixa de renda, mensal, de dez-2018
a dez-2024, e deixou de publicá-lo nas edições seguintes. Com essa série, a {T('tab:teste_ref')} compara, entre dez-2020 e {mes(ult)}, o IDC com o C nacional e o IDC com o CRI da própria faixa. Para a faixa até 2~SM, as variações de 12 meses do C nacional
têm correlação de {num(r_b['corr_c_d12'], 2)} com as do CRI; o IDC com C nacional supera em média {num(r_b['erro_medio_idc'], 3)} o calculado com o CRI (diferença máxima de {num(r_b['erro_max_idc'], 3)}), e as variações de 12 meses dos dois índices têm correlação de
{num(r_b['corr_idc_d12'], 2)}. Entre as quatro faixas, a correlação das variações de 12 meses de C varia de {num(corr_min, 2)} a {num(corr_max, 2)}.

Em {mes(ult)}, último mês da série do REF, o C nacional estava em {num(r_b['c_nac_ult'], 3)} na escala normalizada{clausula_max}; com isso, o IDC da faixa até 2~SM calculado com o C nacional ({num(r_b['idc_nac_ult'], 3)}) ficava
{sentido} do calculado com o CRI ({num(r_b['idc_faixa_ult'], 3)}). Na faixa acima de 10~SM, o CRI normalizado estava em {num(inv['c_faixa_ult'], 3)} e o índice com C nacional ({num(inv['idc_nac_ult'], 3)}) {comp_inv} com o CRI ({num(inv['idc_faixa_ult'], 3)}){frase_ordem}.
O C nacional é, portanto, uma aproximação: acompanha parte da dinâmica de cada faixa, mas não o nível, em especial nas faixas extremas. O CRI do REF se refere a tomadores com renda, ao passo que a faixa até 2~SM do IDC inclui os sem rendimento.

{tabs['teste_ref']}
"""


# ================================================================================ 6. qualidade
def s6_qualidade(d: DadosApendice, tabs: dict) -> str:
    h, full, v = d.conc_hist, d.conc_full, d.vintage
    t1 = d.t1
    ok_i, al_i = int((h["status"] == "ok").sum()), int((h["status"] != "ok").sum())
    ok_q, al_q = int((h["status_Q"] == "ok").sum()), int((h["status_Q"] != "ok").sum())
    meses_al = list(h.index[h["status"] != "ok"])
    gaps_al = h.loc[meses_al, "gap_I_nivel"]
    frase_gap = (f", com diferença de nível (SCR.data menos SGS) de {num(gaps_al.min(), 2, True)} a {num(gaps_al.max(), 2, True)}~p.p. nos meses em alerta ({_meses(meses_al)})" if meses_al else "")
    n_full = len(full)
    bloq = int(((full["status"] == "bloqueio") | (full["status_Q"] == "bloqueio")).sum())
    ok_i_f, ok_q_f = int((full["status"] == "ok").sum()), int((full["status_Q"] == "ok").sum())
    sem_alerta = full["status"].eq("ok").groupby(full.index.year).all()
    anos_ok = [int(a) for a in sem_alerta.index if sem_alerta.loc[a] and a < t1.year]
    bloq_txt = "nenhuma conciliação chegou ao bloqueio" if bloq == 0 else f"{bloq} conciliações chegaram ao bloqueio"
    fecho = (f", e o status de I foi \\emph{{ok}} em todos os meses {_periodo(anos_ok, 'de')}." if anos_ok else ".")
    jan, js, cen = d.janeiros, d.jan_stats, d.cenarios
    grp = d.quebras[(d.quebras["lente"] == "faixa") & (d.quebras["unidade"] == BAIXA_RENDA)]
    altas_jan = sorted(set(grp[(grp["data_base"].dt.month == 1) & (grp["variacao_pp"] > 0)]["data_base"].dt.year))
    fora = sorted(grp[grp["data_base"].dt.month != 1]["data_base"])
    quedas = grp[grp["variacao_pp"] < 0].sort_values("variacao_pp")
    if len(quedas):
        mp = quedas.iloc[0]["data_base"]
        di_g, di_geral = float(d.low["I"].diff().loc[mp]), float(d.sgs["inad_total"].diff().loc[mp])
        frase_queda = (f" A maior queda do peso do grupo ocorreu em {mes(mp)} ({num(quedas.iloc[0]['variacao_pp'], 1, True)}~p.p.); nesse mês, I do grupo variou {num(di_g, 2, True)}~p.p., contra {num(di_geral, 2, True)}~p.p. na série geral.")
        frase_desloc = f"; como essa margem é da ordem do excesso de {num(di_g - di_geral, 2)}~p.p. da variação de I do grupo sobre a da série geral em {mes(mp)}"
    else:
        frase_queda, frase_desloc = "", ""
    i_prev_max = d.low["I"].loc[: d.t0].max()
    mes_prev_max = d.low["I"].loc[: d.t0].idxmax()
    margem = d.f.i["t1"] - i_prev_max
    fim_mes = pd.Timestamp(t1) + pd.offsets.MonthEnd(0)
    atraso = (v["gerado_t1"].normalize() - fim_mes).days
    lista_altas = f"altas em janeiro de {_lista([str(a) for a in altas_jan])}" if altas_jan else "nenhuma alta em janeiro"
    lista_quedas = f" e quedas em {_meses(fora)}" if fora else ""
    return rf"""
\section{{Qualidade e conciliação dos dados}}\label{{sec:qualidade}}

\subsection{{Conciliação do SCR.data com o SGS}}

O SCR.data e o SGS partem de documentos diferentes do Banco Central e não coincidem exatamente. A conciliação compara, a cada mês, o I e o Q do universo do
SCR.data com os valores oficiais, no nível e na variação de 12 meses. O status é \emph{{ok}} quando a diferença é de até 0,25~p.p., \emph{{alerta}} até 0,75~p.p. e \emph{{bloqueio}} acima disso;
no caso de I, vale a pior das duas diferenças (nível e variação), e no de Q, apenas a da variação, porque o nível de Q no SCR.data fica de 0,1 a 0,5~p.p. abaixo do oficial. A {T('tab:conc_hist')}
mostra os 12 meses de referência mais recentes: o status de I foi \emph{{ok}} em {ok_i} e \emph{{alerta}} em {al_i}{frase_gap}; o de Q foi \emph{{ok}} em {ok_q} e \emph{{alerta}} em {al_q}. Entre jan-2016 e {mes(t1)} ({n_full} meses),
o status de I foi \emph{{ok}} em {ok_i_f} meses e o de Q, em {ok_q_f}; {bloq_txt}{fecho}

{tabs['conc_hist']}

\subsection{{Reclassificações de peso}}

A {T('tab:quebras')} lista as mudanças de peso superiores a 2~p.p. em um único mês, que sugerem reclassificações no SCR e comprometem comparações que as atravessem. Para o IDC para baixa renda, importam as da faixa de
renda até 2~SM: {lista_altas} (tratadas adiante){lista_quedas}.{frase_queda} As tabelas por segmento sinalizam as reclassificações de mais de 1~p.p. que caem na janela de 12 meses.

{tabs['quebras']}

\subsection{{Composição do grupo de baixa renda em cada janeiro}}

O peso do grupo de baixa renda no crédito livre PF sobe, em média, {num(js['peso_jan'], 2)}~p.p. em cada janeiro ({js['peso_pos']} altas em {js['n']} janeiros, de jan-{jan.index[0].year} a jan-{jan.index[-1].year}), contra uma variação média de {num(js['peso_demais'], 2, True)}~p.p.
nos demais meses ({T('tab:janeiros')}). Uma hipótese, não verificada na documentação do SCR, é que os reajustes anuais do salário mínimo desloquem, mecanicamente, tomadores com renda informada em valores nominais para a faixa mais baixa. Nos janeiros,
Q também sobe: em {js['q_pos_grupo']} dos {js['n']} anos no grupo e em {js['q_pos_geral']} na série geral, o que indica um componente sazonal.

{tabs['janeiros']}

Para medir o efeito desses saltos sobre o IDC para baixa renda, a {T('tab:cenarios')} substitui, nos meses de salto, as variações de I e de Q do grupo pelas da série geral e recalcula o índice. Em {mes(t1)}, a variação é de
{num(cen.loc['janeiros', 'var_t1'], 3, True)} ponto sem os saltos de janeiro, {num(cen.loc['fora_jan', 'var_t1'], 3, True)} sem as reclassificações de {_meses(fora)} e {num(cen.loc['ambos', 'var_t1'], 3, True)} sem ambos; no período exibido, a diferença absoluta máxima é de
{num(cen.loc['ambos', 'max_abs'], 3)} ({mes(cen.loc['ambos', 'mes_max'])}), e a média, de {num(cen.loc['ambos', 'media_abs'], 3)}. Os efeitos não são aditivos, porque a normalização usa os extremos históricos. Em {mes(t1)}, I do grupo ({pct(d.f.i['t1'], 2)}) supera em {num(margem, 2)}~p.p. o máximo registrado até {mes(d.t0 - pd.DateOffset(months=1))}
({pct(i_prev_max, 2)}, em {mes(mes_prev_max)}){frase_desloc}, deslocamentos de nível desse tamanho alteram o valor normalizado de I. A tabela é, portanto, um teste de sensibilidade, e não uma série corrigida.

{tabs['cenarios']}

\subsection{{Reprocessamento e disponibilidade}}

Os {v['n']} arquivos mensais do SCR.data usados no cálculo (de jul-2012 a {mes(t1)}) foram gerados pelo Banco Central entre {v['min']:%d/%m/%Y} e {v['max']:%d/%m/%Y}; o de {mes(t1)} foi gerado em {v['gerado_t1']:%d/%m/%Y}, {atraso} dias depois do fim do mês.
Como o Banco Central reprocessa os arquivos continuamente, valores de um mesmo mês podem mudar de uma edição para outra, e as tabelas deste apêndice usam a versão disponível na data do cálculo. O arquivo anual é validado na obtenção (integridade do arquivo compactado e de cada mês).
"""


# ================================================================================ 7. metodologia
def s7_metodologia(d: DadosApendice) -> str:
    return rf"""
\section{{Metodologia e fontes}}\label{{sec:metodologia}}

\subsection{{Decomposição aditiva}}

Seja $X$ a taxa agregada (I ou Q), $w_u$ o peso do segmento $u$ no saldo do crédito livre PF e $x_u$ a taxa do segmento. Como $X=\sum_u w_u x_u$, a variação entre as datas $0$ e $1$ é
\[
\Delta X \;=\; \sum_u \underbrace{{\bar w_u\,\Delta x_u}}_{{\text{{dentro}}}} \;+\; \sum_u \underbrace{{\bar x_u\,\Delta w_u}}_{{\text{{composição}}}},
\qquad \bar w_u=\tfrac{{w_{{u0}}+w_{{u1}}}}{{2}},\quad \bar x_u=\tfrac{{x_{{u0}}+x_{{u1}}}}{{2}},
\]
e a soma das duas partes é exata. Em I por produto, os pesos são os saldos das modalidades do SGS (20570--20592) e as taxas, as inadimplências por modalidade (21112--21131); o cartão à vista, sem série de
inadimplência, entra com taxa zero. Em Q, a contribuição de cada modalidade é a variação de sua participação no saldo total. Em C, o SGS~29034 é a soma dos componentes de juros (SGS~29033) e de amortização (SGS~29036).

\subsection{{Universo e categorias do SCR.data}}

O universo reúne as operações de pessoas físicas com origem de recursos ``sem destinação específica'', exceto as modalidades de financiamento rural, imobiliário e de exportação ou importação. Crédito oneroso é a soma de
cheque especial (com conta garantida), crédito pessoal sem consignação, cartão rotativo (com a submodalidade ``não migrado'', que o SGS inclui no rotativo) e cartão parcelado. A faixa de renda é a
informada ao SCR em múltiplos do salário mínimo, e o grupo ``Até 2 SM'' reúne os sem rendimento, os com renda até 1~SM e os de mais de 1 a 2~SM; o credor é o segmento da instituição credora (bancos, financeiras, cooperativas, fintechs, instituições de pagamento e demais);
a ocupação é a natureza da ocupação principal, segundo o cadastro da Receita Federal; e a unidade da federação é a do CEP de residência do tomador. Nas tabelas por credor e por ocupação, as unidades com menos de 0,5\% da carteira são agrupadas em ``Demais'' (exceto fintechs e instituições de pagamento, que se mantêm separadas).

\subsection{{Normalização e janelas}}

Os índices usam a normalização min-max com janela expansiva,
\[
x^{{norm}}_t \;=\; \frac{{x_t-\min_{{\tau\le t}}x_\tau}}{{\max_{{\tau\le t}}x_\tau-\min_{{\tau\le t}}x_\tau}},
\]
que usa apenas informação até o mês $t$. No IDC geral, a janela começa em mar-2011 e o índice é
exibido desde jan-2014 (34 meses de aquecimento). I e Q das faixas de renda começam em jul-2012, primeiro mês do SCR.data, e são exibidos desde {mes(d.f.inicio)}, com o mesmo aquecimento; C é o do IDC geral. O IDC por faixa é a média
de C, I e Q normalizados.

\subsection{{Conciliação e sinalização}}

O status de conciliação usa os limiares de 0,25~p.p. (alerta) e 0,75~p.p. (bloqueio) sobre a diferença entre o SCR.data e o SGS, no nível de I e na variação de 12 meses de I e de Q. Uma reclassificação é sinalizada quando o peso de um segmento
varia mais de 1~p.p. em um mês (a {T('tab:quebras')} lista as superiores a 2~p.p.). Os limiares são parâmetros do cálculo e podem ser revistos.

\subsection{{Fontes e licença}}

\begin{{itemize}}
  \item Banco Central do Brasil, Sistema Gerenciador de Séries Temporais (SGS): séries 20570--20592, 21112--21131 e 29033--29038.
  \item Banco Central do Brasil, Estatísticas Monetárias e de Crédito (planilha mensal, divulgação \competencia): Tabelas 4, 7, 11, 16 e 27.
  \item Banco Central do Brasil, SCR.data (dados agregados do Sistema de Informações de Créditos), versão 2, disponível em \url{{https://dadosabertos.bcb.gov.br/dataset/scr_data}}, distribuído sob a licença Open Database License (ODbL).
  \item Banco Central do Brasil, Relatório de Estabilidade Financeira de abril de 2025, Anexo Estatístico, Gráfico 1.2.2.16 (CRI por faixa de renda).
\end{{itemize}}
"""
