"""Text of the monthly report, generated from the processed data for every edition.

Everything here applies to any month: levels, changes, records, rankings and the position on the [0, 1] scale,
written with fixed rules.  Nothing here interprets the movements or judges economic policy; a comment of that
kind is written by the authors for a given edition and added by hand (see ``PIPELINE.md``).

Style of the report: decimal comma; no bold in running text, except the labels of the component items; the
values of the IDC in the results table are bold.  The months appear in full in the summary and in the results
(``agosto de 2026``) and abbreviated in the trajectory and in the captions (``ago-2026``).

``src.fill_report`` writes these blocks into the monthly ``.tex``.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from src import low_income as LI
from src.income_idc import JANELA_INICIO, primeira_exibicao
from src.plot import KEY_EVENTS, RECENT_START
from src.pt_format import mes, num, pct, pp

# First edition of the IDC Baixa Renda; the summary of that edition says that it introduces the index.
LANCAMENTO_BAIXA_RENDA = "202610"
# An index at or above this normalised value is described as close to its historical maximum.
PROXIMO_DO_MAXIMO = 0.900
SERIES_INICIO = pd.Timestamp("2011-03-01")  # first month of the raw C, I and Q
MESES_RECENTES = 12  # months of the figure of the latest months (``index_12m.png``)
MESES_TABELA = 7  # months of the table of the trajectory section

NOTA_ARREDONDAMENTO = "com base nos valores não arredondados"

_MES_EXTENSO = {1: "janeiro", 2: "fevereiro", 3: "março", 4: "abril", 5: "maio", 6: "junho", 7: "julho",
                8: "agosto", 9: "setembro", 10: "outubro", 11: "novembro", 12: "dezembro"}
_ROTULO = {"C": "Comprometimento de renda (C)", "I": "Inadimplência (I)", "Q": "Participação do crédito oneroso (Q)"}
_VERBOS = {"C": ("avançou", "recuou"), "I": ("avançou", "recuou"), "Q": ("subiu", "caiu")}
ROTULOS_DOS_ITENS = tuple(f"{r}:" for r in _ROTULO.values())  # the only bold text allowed outside the tables


def mes_extenso(t: pd.Timestamp, ano: bool = True) -> str:
    """``agosto de 2026`` (or ``agosto``)."""
    return f"{_MES_EXTENSO[t.month]} de {t.year}" if ano else _MES_EXTENSO[t.month]


def mes_anterior_extenso(t: pd.Timestamp, ref: pd.Timestamp) -> str:
    """Month ``t`` in full, with the year only when it differs from the year of ``ref``."""
    return mes_extenso(t, ano=t.year != ref.year)


def _lista(itens: list[str]) -> str:
    return itens[0] if len(itens) == 1 else ", ".join(itens[:-1]) + " e " + itens[-1]


def _inconsistente(t0: float, t1: float, nd: int) -> bool:
    """True when the difference of the printed levels is not the printed change (both rounded to ``nd`` places)."""
    return abs((round(t1, nd) - round(t0, nd)) - round(t1 - t0, nd)) >= 0.5 * 10 ** -nd


# --------------------------------------------------------------------------- facts
@dataclass
class Componente:
    nome: str            # C, I or Q
    t1: float            # raw value (percent) in the reference month
    tprev: float
    norm_t1: float
    norm_tprev: float
    casas: int           # decimals of the raw value in the text
    maximo: bool = False  # raw value above every earlier month of its series
    minimo: bool = False

    @property
    def rotulo(self) -> str:
        return _ROTULO[self.nome]


@dataclass
class FatosIndice:
    nome: str                 # "IDC Geral" or "IDC Baixa Renda"
    t1: pd.Timestamp
    tprev: pd.Timestamp
    serie: pd.Series          # the displayed index (from jan-2014 or mai-2015)
    componentes: dict = field(default_factory=dict)
    escopo_serie: str = ""    # how the records of the raw series are described, e.g. "da série desde mar-2011"

    @property
    def valor(self) -> float:
        return float(self.serie.loc[self.t1])

    @property
    def anterior(self) -> float:
        return float(self.serie.loc[self.tprev])

    @property
    def inicio(self) -> pd.Timestamp:
        return self.serie.index[0]

    @property
    def n_obs(self) -> int:
        return int(self.serie.notna().sum())

    @property
    def rank(self) -> int:
        return int((self.serie > self.valor + 1e-12).sum() + 1)

    @property
    def empatado(self) -> bool:
        return bool(((self.serie - self.valor).abs() < 1e-12).sum() > 1)

    def recentes(self, meses: int = MESES_RECENTES) -> pd.Series:
        return self.serie.loc[:self.t1].iloc[-meses:]


def _componente(nome: str, raw: pd.Series, norm: pd.Series, t1: pd.Timestamp, tprev: pd.Timestamp, casas: int) -> Componente:
    anteriores = raw.loc[:tprev].dropna()
    return Componente(nome, float(raw.loc[t1]), float(raw.loc[tprev]), float(norm.loc[t1]), float(norm.loc[tprev]), casas,
                      maximo=bool(raw.loc[t1] > anteriores.max()), minimo=bool(raw.loc[t1] < anteriores.min()))


def fatos_geral(comp: pd.DataFrame, idx: pd.DataFrame) -> FatosIndice:
    """Facts of the IDC Geral from ``components_raw.csv`` and ``index.csv``."""
    serie = idx["index"].dropna()
    t1 = serie.index[-1]
    tprev = t1 - pd.DateOffset(months=1)
    raw = {"C": comp["C"], "I": comp["I"], "Q": 100 * comp["Q"]}
    f = FatosIndice("IDC Geral", t1, tprev, serie, escopo_serie=f"da série desde {mes(SERIES_INICIO)}")
    f.componentes = {c: _componente(c, raw[c].loc[SERIES_INICIO:], idx[f"{c}_norm"], t1, tprev, 1) for c in "CIQ"}
    return f


def fatos_baixa_renda(low: pd.DataFrame, geral: FatosIndice) -> FatosIndice:
    """Facts of the IDC Baixa Renda from ``low_income_idc.csv``; C is the national one of the IDC Geral."""
    t1, tprev = geral.t1, geral.tprev
    f = FatosIndice("IDC Baixa Renda", t1, tprev, low["IDC"].loc[primeira_exibicao():t1].dropna(), escopo_serie=f"da série do grupo desde {mes(JANELA_INICIO)}")
    c = geral.componentes["C"]
    f.componentes = {"C": Componente("C", c.t1, c.tprev, float(low["C_norm"].loc[t1]), float(low["C_norm"].loc[tprev]), 1,
                                     c.maximo, c.minimo)}
    for nome in "IQ":
        f.componentes[nome] = _componente(nome, low[nome].loc[JANELA_INICIO:], low[f"{nome}_norm"], t1, tprev, 2)
    return f


# --------------------------------------------------------------------------- summary
def apresentacao(period: str, baixa_renda_disponivel: bool) -> str:
    """Sentence that closes the opening paragraph: it presents the IDC Baixa Renda (empty when unavailable)."""
    if not baixa_renda_disponivel:
        return ""
    if period == LANCAMENTO_BAIXA_RENDA:
        return ("Esta edição também introduz o IDC Baixa Renda, referente a tomadores pessoa física com renda de até "
                "2 salários mínimos. A partir de agora, o IDC Geral e o IDC Baixa Renda serão calculados e divulgados periodicamente.")
    return "Esta nota apresenta também o IDC Baixa Renda, referente a tomadores pessoa física com renda de até 2 salários mínimos."


def _movimento_indice(f: FatosIndice, verbo_alta: str) -> str:
    anterior = mes_anterior_extenso(f.tprev, f.t1)
    if round(f.valor, 3) == round(f.anterior, 3):
        return f"manteve-se em {num(f.valor, 3)}, mesmo valor de {anterior}"
    verbo = f"{verbo_alta}" if f.valor > f.anterior else "recuou para"
    return f"{verbo} {num(f.valor, 3)}, ante {num(f.anterior, 3)} em {anterior}"


def _posicao(f: FatosIndice) -> str:
    if f.rank == 1:
        lugar = "empatado com o maior resultado" if f.empatado else "o maior resultado"
    else:
        lugar = f"o {LI.ordinal(f.rank)} maior resultado"
    return f"{lugar} entre as {f.n_obs} observações válidas desde {mes_extenso(f.inicio)}"


def _proximos_do_maximo(indices: list[FatosIndice]) -> str:
    perto = [f for f in indices if f.valor >= PROXIMO_DO_MAXIMO]
    if not perto:
        return ""
    antes = all(f.anterior >= PROXIMO_DO_MAXIMO for f in perto)
    if len(perto) == 2:
        return f"Os dois índices {'permanecem' if antes else 'estão'} próximos de seus máximos históricos"
    return f"O {perto[0].nome} {'permanece' if antes else 'está'} próximo de seu máximo histórico"


def resumo(geral: FatosIndice, baixa: FatosIndice | None) -> str:
    """The paragraphs of the summary after the opening one."""
    p1 = f"Em {mes_extenso(geral.t1)}, o {geral.nome} {_movimento_indice(geral, 'atingiu')}, {_posicao(geral)}."
    if baixa is not None:
        p1 += f" O {baixa.nome} {_movimento_indice(baixa, 'alcançou')}, {_posicao(baixa)}."
    indices = [geral] + ([baixa] if baixa is not None else [])
    perto = _proximos_do_maximo(indices)
    p2 = f"{perto}." if perto else ""
    if baixa is not None:
        acima = {c: baixa.componentes[c].t1 > geral.componentes[c].t1 for c in "IQ"}
        if acima["I"] == acima["Q"]:
            termos = f"inadimplência e participação do crédito oneroso {'superiores' if acima['I'] else 'inferiores'}"
        else:
            termos = (f"inadimplência {'superior' if acima['I'] else 'inferior'} e participação do crédito oneroso "
                      f"{'superior' if acima['Q'] else 'inferior'}")
        p2 += f" Em valores brutos, o grupo de baixa renda apresenta {termos} às observadas no conjunto geral dos tomadores."
    return p1 + ("\n\n" + p2.strip() if p2.strip() else "")


# --------------------------------------------------------------------------- results
def tabela(geral: FatosIndice, baixa: FatosIndice | None, competencia: str) -> str:
    """Results table (raw and normalised components, side by side when the IDC Baixa Renda is available) and its source."""
    g = geral.componentes
    nomes = {"C": "C --- Comprometimento de renda das famílias com a dívida",
             "I": "I --- Inadimplência da carteira de crédito livre PF (90+ dias)",
             "Q": "Q --- Participação do crédito oneroso no crédito livre PF"}
    linhas = [["IDC (média dos componentes normalizados)", "---", r"\textbf{" + num(geral.valor, 3) + "}"]]
    linhas += [[nomes[c], pct(g[c].t1, 1), num(g[c].norm_t1, 3)] for c in "CIQ"]
    if baixa is not None:
        b = baixa.componentes
        linhas[0] += ["---", r"\textbf{" + num(baixa.valor, 3) + "}"]
        for linha, c in zip(linhas[1:], "CIQ"):
            linha += [pct(b[c].t1, 1), num(b[c].norm_t1, 3)]
        titulo = f"Componentes brutos e valores normalizados do IDC Geral e do IDC Baixa Renda --- {mes(geral.t1)}."
        colunas = r">{\raggedright\arraybackslash}p{6.0cm}rrrr"
        cabecalho = (r"    & \multicolumn{2}{c}{IDC Geral} & \multicolumn{2}{c}{IDC Baixa Renda} \\" "\n"
                     r"    \cmidrule(lr){2-3}\cmidrule(lr){4-5}" "\n"
                     r"    Indicador & Bruto & Normalizado & Bruto & Normalizado \\")
        fonte = (f"Banco Central do Brasil (Estatísticas Monetárias e de Crédito, divulgação {competencia}; "
                 "SCR.data para o IDC Baixa Renda), elaboração própria.")
    else:
        titulo = f"Componentes brutos e valores normalizados do IDC Geral --- {mes(geral.t1)}."
        colunas = r">{\raggedright\arraybackslash}p{8.0cm}rr"
        cabecalho = r"    Indicador & Valor bruto & Valor normalizado \\"
        fonte = f"Banco Central do Brasil (Estatísticas Monetárias e de Crédito, divulgação {competencia}), elaboração própria."
    corpo = "\n".join("    " + " & ".join(l) + r" \\" for l in linhas)
    return "\n".join([
        r"\begin{table}[htbp]",
        r"  \centering",
        f"  \\caption{{{titulo}}}",
        r"  \label{tab:componentes}",
        f"  \\begin{{tabular}}{{{colunas}}}",
        r"    \toprule",
        cabecalho,
        r"    \midrule",
        corpo,
        r"    \bottomrule",
        r"  \end{tabular}",
        r"\end{table}",
        "",
        f"\\fonte{{{fonte}}}",
    ])


def _variacao(c: Componente, delta: bool = True) -> str:
    """``avançou de 7,8\\% para 8,0\\% (+0,2~p.p.)``, with the rounding qualifier when the printed numbers disagree."""
    nd = c.casas
    if round(c.t1, nd) == round(c.tprev, nd):
        return f"ficou estável em {pct(c.t1, nd)}"
    alta, queda = _VERBOS[c.nome]
    movimento = f"{alta if c.t1 > c.tprev else queda} de {pct(c.tprev, nd)} para {pct(c.t1, nd)}"
    if not delta:
        return movimento
    nota = f", {NOTA_ARREDONDAMENTO}" if _inconsistente(c.tprev, c.t1, nd) else ""
    return f"{movimento} ({pp(c.t1 - c.tprev, nd)}{nota})"


def _normalizado(c: Componente, sujeito: str = "O valor normalizado") -> str:
    if round(c.norm_t1, 3) == round(c.norm_tprev, 3):
        return f"{sujeito} permaneceu em {num(c.norm_t1, 3)}."
    return f"{sujeito} passou de {num(c.norm_tprev, 3)} para {num(c.norm_t1, 3)}."


def _recorde(c: Componente, escopo: str) -> str:
    """Record of the raw series up to the reference month, e.g. ``, novo máximo histórico``."""
    if c.maximo:
        return f", {escopo.format(extremo='máximo', maior='maior')}"
    if c.minimo:
        return f", {escopo.format(extremo='mínimo', maior='menor')}"
    return ""


def _de_para(c: Componente, f: "FatosIndice") -> str:
    """``de julho para agosto``, with the years when they differ."""
    return f"de {mes_anterior_extenso(f.tprev, f.t1)} para {mes_extenso(f.t1, ano=f.t1.year != f.tprev.year)}"


def _atribuicao(f: FatosIndice) -> dict[str, str]:
    """When a single component moved on the normalised scale, the sentence that credits it with the monthly change."""
    if round(f.valor, 3) == round(f.anterior, 3):
        return {}
    mudou = [c for c in f.componentes.values() if round(c.norm_t1, 3) != round(c.norm_tprev, 3)]
    if len(mudou) != 1:
        return {}
    unico = mudou[0]
    outros = [c for c in f.componentes.values() if c is not unico]
    valores = {round(c.norm_t1, 3) for c in outros}
    estado = f"permaneceram em {num(valores.pop(), 3)}" if len(valores) == 1 else "não variaram na escala normalizada"
    subiu = unico.norm_t1 > unico.norm_tprev
    if subiu != (f.valor > f.anterior):
        return {}
    efeito = f"o aumento de {unico.nome} explicou a alta" if subiu else f"a queda de {unico.nome} explicou o recuo"
    return {unico.nome: f" Como {_lista([c.nome for c in outros])} {estado}, {efeito} mensal do índice."}


def _item(rotulo: str, texto: str) -> str:
    return f"  \\item \\textbf{{{rotulo}:}} {texto}"


def resultados_geral(geral: FatosIndice) -> str:
    """Heading and component items of the IDC Geral (the wording of the coauthors' model, for any month)."""
    extra = _atribuicao(geral)
    c, i, q = (geral.componentes[k] for k in "CIQ")
    escopo = "novo {extremo} histórico"
    if round(c.norm_t1, 3) == round(c.norm_tprev, 3) == 1.0:  # a raw value at its maximum in both months
        texto_c = (f"{_variacao(c)}. Como o valor bruto permaneceu no maior nível da série histórica, o componente "
                   "normalizado manteve-se em 1,000.")
    else:
        texto_c = f"{_variacao(c)}{_recorde(c, escopo)}. {_normalizado(c, 'O componente normalizado')}"
    texto_i = f"{_variacao(i)}{_recorde(i, escopo)}. {_normalizado(i)}"
    norm_q = ("o valor normalizado permaneceu em " + num(q.norm_t1, 3) if round(q.norm_t1, 3) == round(q.norm_tprev, 3)
              else f"o valor normalizado passou de {num(q.norm_tprev, 3)} para {num(q.norm_t1, 3)}")
    texto_q = f"{_variacao(q, delta=False)}{_recorde(q, escopo)}, e {norm_q}."
    itens = [_item(x.rotulo, texto + extra.get(x.nome, "")) for x, texto in ((c, texto_c), (i, texto_i), (q, texto_q))]
    return "\n".join([r"\subsection*{IDC Geral --- Componentes}", "", r"\begin{itemize}", "\n\n".join(itens), r"\end{itemize}"])


def resultados_baixa_renda(geral: FatosIndice, baixa: FatosIndice) -> str:
    """Heading and component items of the IDC Baixa Renda, and the comparison with the IDC Geral."""
    extra = _atribuicao(baixa)
    c, i, q = (baixa.componentes[k] for k in "CIQ")
    periodo = _de_para(c, baixa)
    norm_c = ("o valor normalizado permaneceu em " + num(c.norm_t1, 3) if round(c.norm_t1, 3) == round(c.norm_tprev, 3)
              else f"o valor normalizado passou de {num(c.norm_tprev, 3)} para {num(c.norm_t1, 3)}")
    norm_q = ("o valor normalizado permaneceu em " + num(q.norm_t1, 3) if round(q.norm_t1, 3) == round(q.norm_tprev, 3)
              else f"o valor normalizado atingiu {num(q.norm_t1, 3)}")
    itens = [
        _item(c.rotulo, f"por limitação de dados, utiliza a mesma série do IDC Geral. {periodo[0].upper() + periodo[1:]}, "
                        f"C {_variacao(c)}, e {norm_c}.{extra.get('C', '')}"),
        _item(i.rotulo, f"{periodo}, I {_variacao(i)}{_recorde(i, 'o {maior} valor da série do grupo')}. "
                        f"{_normalizado(i)}{extra.get('I', '')}"),
        _item(q.rotulo, f"{periodo}, Q {_variacao(q)}{_recorde(q, 'o {maior} valor da série do grupo')}, e {norm_q}."
                        f"{extra.get('Q', '')}"),
    ]
    gi, gq = geral.componentes["I"], geral.componentes["Q"]
    if round(i.norm_t1, 3) == round(gi.norm_t1, 3):
        conclusao = (f"Assim, o fato de I atingir {num(i.norm_t1, 3)} nos dois índices não significa que os níveis "
                     "absolutos de inadimplência sejam iguais.")
    else:
        conclusao = ("Assim, a comparação entre os valores normalizados dos dois índices não indica a diferença entre os "
                     "níveis absolutos de inadimplência e de crédito oneroso dos dois grupos.")
    comparacao = (
        "Como C é comum aos dois índices, a diferença entre o IDC Geral e o IDC Baixa Renda decorre de I e Q. "
        f"Em {mes_extenso(baixa.t1, ano=False)}, o grupo de baixa renda apresentou inadimplência de {pct(i.t1, 2)}, "
        f"ante {pct(gi.t1, 1)} no conjunto dos tomadores, e participação do crédito oneroso de {pct(q.t1, 2)}, ante {pct(gq.t1, 1)}. "
        "Os valores normalizados, porém, indicam a posição de cada componente dentro da série histórica do próprio grupo. "
        + conclusao
    )
    return "\n".join([r"\subsection*{IDC Baixa Renda --- Componentes}", "", r"\begin{itemize}", "\n\n".join(itens),
                      r"\end{itemize}", "", comparacao])


def baixa_renda_indisponivel(resultado: LI.Resultado) -> str:
    """Sentence that replaces the IDC Baixa Renda blocks when the index could not be updated in the edition."""
    razao = {
        "bloqueio": "porque os dados do SCR.data do Banco Central divergem das séries oficiais além do limite de tolerância adotado na construção do índice",
        "sem_cobertura": ("porque os dados do SCR.data do Banco Central ainda não cobrem " + (mes(resultado.t1) if resultado.t1 is not None else "o mês de referência")),
        "sem_dados": "porque os dados do SCR.data do Banco Central não estavam disponíveis",
    }.get(resultado.status, "porque os dados necessários não estavam disponíveis")
    return f"O IDC Baixa Renda não foi atualizado nesta edição, {razao}. O IDC Geral não depende dessa fonte."


# --------------------------------------------------------------------------- trajectory, notes and annex
def _extremo(s: pd.Series, maior: bool) -> str:
    alvo = round(s.max() if maior else s.min(), 3)
    meses = [mes(t) for t, v in s.items() if round(v, 3) == alvo]
    return f"{num(alvo, 3)} ({_lista(meses)})"


def _eventos_desde(inicio: pd.Timestamp, fim: pd.Timestamp) -> str:
    """The events marked in the figures between ``inicio`` and ``fim``, e.g. ``o Programa Desenrola (jun-2023)``."""
    eventos = [f"o {nome.replace(chr(10), ' ')} ({mes(data)})" for nome, data in KEY_EVENTS.items() if inicio <= data <= fim]
    return _lista(eventos) if eventos else ""


def _valores_mensais(serie: pd.Series) -> str:
    """``0,960 em mar-2026, 0,990 em abr-2026 e 0,966 em ago-2026``."""
    return _lista([f"{num(v, 3)} em {mes(t)}" for t, v in serie.items()])


def trajetoria(geral: FatosIndice, baixa: FatosIndice | None) -> str:
    """Paragraphs that present the four annex figures and the table of the latest months (the coauthors' wording)."""
    rg = geral.serie.loc[:geral.t1].iloc[-MESES_TABELA:]
    indices = [rg] + ([baixa.serie.loc[:baixa.t1].iloc[-MESES_TABELA:]] if baixa is not None else [])
    periodo = (f"ao longo de {rg.index[-1].year}" if rg.index[0].year == rg.index[-1].year
               else f"entre {mes(rg.index[0])} e {mes(rg.index[-1])}")
    if all((s >= PROXIMO_DO_MAXIMO).all() for s in indices):
        sujeito = "os dois índices permaneceram" if baixa is not None else "o índice permaneceu"
        p1 = f"A Figura~\\ref{{fig:indice}} mostra que {sujeito} em níveis historicamente elevados {periodo}. "
    else:
        p1 = f"A Figura~\\ref{{fig:indice}} mostra a evolução {'dos dois índices' if baixa is not None else 'do índice'}. "
    if round(rg.iloc[0], 3) == 1.0:
        p1 += f"O IDC Geral, após atingir 1,000 em {mes(rg.index[0])}, passou a {_valores_mensais(rg.iloc[1:])}."
    else:
        p1 += f"O IDC Geral registrou {_valores_mensais(rg)}."
    p2 = ""
    if baixa is not None:
        rb = indices[1]
        maximos = [mes(t) for t, v in rb.items() if round(v, 3) == 1.0]
        anterior, ultimo = baixa.anterior, baixa.valor
        if round(anterior, 3) == round(ultimo, 3):
            final = f"manteve-se em {num(ultimo, 3)} em {mes(baixa.tprev)} e {mes(baixa.t1)}"
        else:
            final = f"passou de {num(anterior, 3)} em {mes(baixa.tprev)} para {num(ultimo, 3)} em {mes(baixa.t1)}"
        atingiu = f"atingiu 1,000 em {_lista(maximos)} e " if maximos else ""
        p2 = f"O IDC Baixa Renda, exibido desde {mes(baixa.inicio)}, {atingiu}{final}. "
    eventos = _eventos_desde(RECENT_START, geral.t1)
    p2 += (f"A Figura~\\ref{{fig:periodo}} repete a Figura~\\ref{{fig:indice}} a partir de {mes(RECENT_START)}"
           + (f", período que inclui {eventos}" if eventos else "")
           + f", e a Figura~\\ref{{fig:recente}} detalha os últimos {MESES_RECENTES} meses, com o valor de cada mês. "
           "A Figura~\\ref{fig:componentes} apresenta os componentes brutos")
    p2 += ("; nos painéis de I e Q, as linhas tracejadas correspondem ao grupo de baixa renda." if baixa is not None else ".")
    return p1 + "\n\n" + p2 + "\n\n" + tabela_meses(geral, baixa)


def tabela_meses(geral: FatosIndice, baixa: FatosIndice | None) -> str:
    """Table of the two indices in the latest ``MESES_TABELA`` months, kept in place in the trajectory section."""
    rg = geral.serie.loc[:geral.t1].iloc[-MESES_TABELA:]
    if baixa is not None:
        rb = baixa.serie.reindex(rg.index)
        linhas = [f"    {mes(t)} & {num(rg.loc[t], 3)} & {num(rb.loc[t], 3) if pd.notna(rb.loc[t]) else '---'} \\\\" for t in rg.index]
        cabecalho, colunas, titulo = r"Mês & IDC Geral & IDC Baixa Renda \\", "lrr", "IDC Geral e IDC Baixa Renda"
        fonte = "BCB (SGS e SCR.data), elaboração própria."
    else:
        linhas = [f"    {mes(t)} & {num(rg.loc[t], 3)} \\\\" for t in rg.index]
        cabecalho, colunas, titulo = r"Mês & IDC Geral \\", "lr", "IDC Geral"
        fonte = "BCB, elaboração própria."
    return "\n".join([
        r"\begin{table}[H]",
        r"  \centering",
        f"  \\caption{{{titulo} nos últimos {MESES_TABELA} meses --- {mes(rg.index[0])} a {mes(rg.index[-1])}.}}",
        r"  \label{tab:meses}",
        f"  \\begin{{tabular}}{{{colunas}}}",
        r"    \toprule",
        "    " + cabecalho,
        r"    \midrule",
        *linhas,
        r"    \bottomrule",
        r"  \end{tabular}",
        r"\end{table}",
        "",
        f"\\fonte{{{fonte}}}",
    ])


def nota_baixa_renda() -> str:
    """Note on the method of the IDC Baixa Renda (the report is self-contained: it cites no other document)."""
    return (
        "Sobre o IDC Baixa Renda. O IDC Baixa Renda segue as regras do IDC Geral, com duas diferenças. "
        "O componente C é o mesmo, porque o Banco Central não divulga o comprometimento de renda por faixa de renda. I e Q passam a ser calculados para o "
        "crédito livre de pessoas físicas com renda de até 2 salários mínimos, incluindo as que não têm rendimento, segundo a faixa de renda informada "
        "ao Sistema de Informações de Crédito (SCR), com o SCR.data do Banco Central (operações de crédito livre PF, exceto financiamento rural, "
        "imobiliário e de exportação ou importação). Esses dois componentes são normalizados pelo método min-max com janela expansiva a partir de "
        f"{mes(JANELA_INICIO)}, primeiro mês do SCR.data, e o índice é exibido a partir de {mes(primeira_exibicao())}, 34 meses depois, o mesmo período de "
        "aquecimento do IDC Geral. O Banco Central reprocessa os arquivos do SCR.data continuamente, e as séries do grupo incorporam a versão "
        "disponível na data do cálculo. Os valores de I e Q do grupo aparecem com duas casas decimais no texto."
    )


def _figura(arquivo: str, altura_reserva: str, legenda: str, rotulo: str, fonte: str) -> str:
    return "\n".join([
        r"\begin{figure}[H]",
        r"  \centering",
        f"  \\IfFileExists{{{arquivo}}}{{%",
        f"    \\includegraphics[width=\\linewidth]{{{arquivo}}}%",
        r"  }{%",
        f"    \\fbox{{\\rule{{0pt}}{{{altura_reserva}}}%",
        r"      \rule{\dimexpr\linewidth-2\fboxsep-2\fboxrule\relax}{0pt}}%",
        r"  }",
        f"  \\caption{{{legenda}}}",
        f"  \\label{{{rotulo}}}",
        f"  \\fonte{{{fonte}}}",
        r"\end{figure}",
    ])


def anexo(geral: FatosIndice, baixa: FatosIndice | None) -> str:
    """The four annex figures, one per page."""
    fim = mes(geral.t1)
    rg = geral.recentes()
    if baixa is not None:
        fonte = "BCB (SGS e SCR.data), elaboração própria."
        l1 = f"Evolução do IDC Geral ({mes(geral.inicio)} a {fim}) e do IDC Baixa Renda ({mes(baixa.inicio)} a {fim})."
        l_periodo = f"Evolução do IDC Geral e do IDC Baixa Renda ({mes(RECENT_START)} a {fim})."
        l2 = f"IDC Geral e IDC Baixa Renda nos últimos {MESES_RECENTES} meses ({mes(rg.index[0])} a {fim})."
        l3 = (f"Evolução das componentes brutas C, I e Q ({mes(SERIES_INICIO)} a {fim}); I e Q também para o grupo de "
              f"baixa renda ({mes(JANELA_INICIO)} a {fim}).")
    else:
        fonte = "BCB, elaboração própria."
        l1 = f"Evolução do IDC Geral ({mes(geral.inicio)} a {fim})."
        l_periodo = f"Evolução do IDC Geral ({mes(RECENT_START)} a {fim})."
        l2 = f"IDC Geral nos últimos {MESES_RECENTES} meses ({mes(rg.index[0])} a {fim})."
        l3 = f"Evolução das componentes brutas C, I e Q ({mes(SERIES_INICIO)} a {fim})."
    return "\n\n\\clearpage\n".join([
        _figura("index.png", "14cm", l1, "fig:indice", fonte),
        _figura("index_since_2022.png", "14cm", l_periodo, "fig:periodo", fonte),
        _figura("index_12m.png", "11cm", l2, "fig:recente", fonte),
        _figura("components_raw.png", "17cm", l3, "fig:componentes", fonte),
    ])
