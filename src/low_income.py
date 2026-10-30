"""IDC for the low-income population: series, quality gate and the blocks of the monthly report.

The low-income group is the set of PF borrowers with income of up to 2 minimum wages, including those with no
income, according to the income class reported to the SCR.  Its IDC keeps the national C of the IDC and uses I
and Q computed for the group with the SCR.data (``src.income_idc``).

``calcular`` builds the series and applies the quality gate (the SCR.data must cover the reference month and
reconcile with the official series); ``gravar`` stores the series and the status in ``data/processed/``; the
remaining functions produce the facts, the paragraphs and the table that ``src.insert_low_income`` writes into
the monthly report.  The general IDC never depends on any of this.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from src import lenses as L
from src.income_idc import JANELA_INICIO, c_normalizado, idc_baixa_renda, indice_por_faixa, primeira_exibicao
from src.pt_format import b, bmes, bn, bpct, bpp, mes, num, pct

SCR_DIR = Path("data/processed/scr")
SERIES_CSV = Path("data/processed/low_income_idc.csv")
STATUS_JSON = Path("data/processed/low_income_status.json")

_ORDINAL = {1: "primeiro", 2: "segundo", 3: "terceiro", 4: "quarto", 5: "quinto", 6: "sexto", 7: "sétimo",
            8: "oitavo", 9: "nono", 10: "décimo"}


def ordinal(n: int) -> str:
    return _ORDINAL.get(n, f"{n}º")


# --------------------------------------------------------------------------- series and quality gate
@dataclass
class Resultado:
    """Outcome of the monthly computation of the low-income IDC.

    ``status`` is ``ok`` when the series was computed, ``bloqueio`` when the SCR.data diverges from the official
    I or Q by more than 0.75 p.p. (``lenses.CONCILIACAO_BLOQUEIO_PP``), ``sem_cobertura`` when the SCR.data does
    not cover every month up to the IDC reference month, and ``sem_dados`` when there is no SCR.data at all.
    """

    status: str
    motivo: str = ""
    t1: pd.Timestamp | None = None
    serie: pd.DataFrame | None = None  # I, Q (percent), I_norm, Q_norm, C_norm and IDC from jul-2012
    conciliacao: dict = field(default_factory=dict)

    @property
    def disponivel(self) -> bool:
        return self.status == "ok" and self.serie is not None


def calcular(components: pd.DataFrame, raw: pd.DataFrame, scr_dir: Path = SCR_DIR) -> Resultado:
    """Compute the low-income IDC up to the latest reference month of ``components``.

    ``components`` is ``components_raw.csv`` (C, I, Q) and ``raw`` is ``series_raw.csv`` (the official national
    series of the workbook, used only to reconcile the SCR.data).  Never raises for data problems: a missing,
    incomplete or inconsistent SCR.data yields a non-``ok`` status with a reason that the report can state.
    """
    faixa_csv = scr_dir / "scr_faixa.csv"
    if not faixa_csv.exists():
        return Resultado("sem_dados", f"agregados do SCR.data ausentes em {scr_dir}")
    t1 = pd.Timestamp(components.dropna().index.max())
    t0 = t1 - pd.DateOffset(years=1)
    painel = L.painel(pd.read_csv(faixa_csv), "faixa")
    meses = painel.index.get_level_values("data_base").unique()
    if not len(meses):
        return Resultado("sem_dados", "agregados do SCR.data vazios", t1=t1)
    faltam = [m for m in pd.date_range(JANELA_INICIO, t1, freq="MS") if m not in meses]
    if faltam:
        ate = meses.max()
        detalhe = f"mês de referência {mes(t1)}" if ate < t1 else f"falta {mes(faltam[0])}"
        return Resultado("sem_cobertura", f"SCR.data até {mes(ate)}; {detalhe}", t1=t1)
    painel = painel[painel.index.get_level_values("data_base") <= t1]  # never look beyond the reference month
    conc = L.conciliar(painel, L.oficial_da_planilha(raw), t0, t1)
    if L.bloqueado(conc):
        return Resultado("bloqueio", f"SCR.data diverge do SGS (I: {conc['gap_I_nivel']:+.2f} p.p. no nível e "
                                     f"{conc['gap_I_delta']:+.2f} na variação de 12 meses; Q: {conc['gap_Q_delta']:+.2f} na variação)",
                         t1=t1, conciliacao=conc)
    serie = idc_baixa_renda(indice_por_faixa(painel, c_normalizado(components.loc[:t1])))
    return Resultado("ok", t1=t1, serie=serie, conciliacao=conc)


def gravar(resultado: Resultado, series_csv: Path = SERIES_CSV, status_json: Path = STATUS_JSON) -> None:
    """Store the series (only when it exists) and the status of this run."""
    status_json.parent.mkdir(parents=True, exist_ok=True)
    if resultado.disponivel:
        resultado.serie.rename_axis("data").to_csv(series_csv)
    conc = {k: (round(v, 4) if isinstance(v, float) else v) for k, v in resultado.conciliacao.items()}
    status_json.write_text(json.dumps({
        "status": resultado.status, "motivo": resultado.motivo,
        "mes_referencia": f"{resultado.t1:%Y-%m}" if resultado.t1 is not None else None, "conciliacao": conc,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def carregar(series_csv: Path = SERIES_CSV, status_json: Path = STATUS_JSON) -> Resultado:
    """Read back what :func:`gravar` stored; the series is returned only if it reaches the reference month."""
    if not status_json.exists():
        return Resultado("sem_dados", f"{status_json} ausente; rode python3 main.py")
    info = json.loads(status_json.read_text(encoding="utf-8"))
    t1 = pd.Timestamp(info["mes_referencia"] + "-01") if info.get("mes_referencia") else None
    resultado = Resultado(info["status"], info.get("motivo", ""), t1=t1, conciliacao=info.get("conciliacao", {}))
    if info["status"] == "ok":
        serie = pd.read_csv(series_csv, index_col=0, parse_dates=True)
        if t1 is None or serie.index.max() != t1:
            return Resultado("sem_dados", f"{series_csv} não termina no mês de referência {mes(t1) if t1 is not None else '?'}")
        resultado.serie = serie
    return resultado


# --------------------------------------------------------------------------- facts
@dataclass
class FatosBaixaRenda:
    t1: pd.Timestamp
    tprev: pd.Timestamp
    t0: pd.Timestamp
    inicio: pd.Timestamp
    idc: dict = field(default_factory=dict)       # t1, tprev, t0 of the low-income IDC
    geral: dict = field(default_factory=dict)     # headline values at t1 and tprev
    i: dict = field(default_factory=dict)
    q: dict = field(default_factory=dict)
    c_norm_t1: float = 0.0
    rank: int = 0
    n_obs: int = 0
    meses_maximo: list = field(default_factory=list)
    rank_i: int = 0
    i_max: float = 0.0
    i_max_mes: pd.Timestamp | None = None
    relacao: dict = field(default_factory=dict)


def fatos(low: pd.DataFrame, idc_geral: pd.Series, comp: pd.DataFrame, idx: pd.DataFrame, t1: pd.Timestamp) -> FatosBaixaRenda:
    tprev, t0 = t1 - pd.DateOffset(months=1), t1 - pd.DateOffset(years=1)
    inicio = primeira_exibicao()
    s = low["IDC"].loc[inicio:t1].dropna()
    f = FatosBaixaRenda(t1=t1, tprev=tprev, t0=t0, inicio=inicio)
    f.idc = {"t1": float(s.loc[t1]), "tprev": float(s.loc[tprev]), "t0": float(s.loc[t0])}
    f.geral = {"idc_t1": float(idc_geral.loc[t1]), "idc_tprev": float(idc_geral.loc[tprev]),
               "I_t1": float(comp.loc[t1, "I"]), "I_tprev": float(comp.loc[tprev, "I"]),
               "Q_t1": float(100 * comp.loc[t1, "Q"]), "Q_tprev": float(100 * comp.loc[tprev, "Q"]),
               "C_t1": float(comp.loc[t1, "C"]), "C_norm_t1": float(idx.loc[t1, "C_norm"]),
               "I_norm_t1": float(idx.loc[t1, "I_norm"]), "Q_norm_t1": float(idx.loc[t1, "Q_norm"])}
    for nome, col in (("i", "I"), ("q", "Q")):
        serie = low[col].dropna()
        getattr(f, nome).update({"t1": float(serie.loc[t1]), "tprev": float(serie.loc[tprev]), "t0": float(serie.loc[t0]),
                                 "norm_t1": float(low[f"{col}_norm"].loc[t1]), "norm_tprev": float(low[f"{col}_norm"].loc[tprev]),
                                 "max": float(serie.max()), "max_mes": serie.idxmax()})
    f.c_norm_t1 = float(low["C_norm"].loc[t1])
    f.n_obs = int(s.notna().sum())
    f.rank = int((s > s.loc[t1] + 1e-12).sum() + 1)
    f.meses_maximo = [d for d in s.index if s.loc[d] >= 0.9995]
    i_serie = low["I"].loc[inicio:t1].dropna()
    f.rank_i = int((i_serie > i_serie.loc[t1] + 1e-12).sum() + 1)
    f.i_max, f.i_max_mes = float(i_serie.max()), i_serie.idxmax()
    g = idc_geral.loc[s.index]
    dif = s - g
    f.relacao = {"corr_nivel": float(s.corr(g)), "corr_d12": float(s.diff(12).corr(g.diff(12))),
                 "share_acima": float((dif > 0).mean()), "media_dif": float(dif.mean()),
                 "por_ano": dif.groupby(dif.index.year).mean().to_dict(),
                 "idc_por_ano": s.groupby(s.index.year).mean().to_dict(), "geral_por_ano": g.groupby(g.index.year).mean().to_dict()}
    return f


def bponto(x: float, nd: int = 3) -> str:
    """Bold magnitude of an index change, e.g. \\textbf{0,013~ponto}."""
    return b(num(abs(x), nd) + "~ponto")


def _verbo(delta: float, subiu="subiu", caiu="recuou", igual="ficou estável") -> str:
    if abs(delta) < 0.0005:
        return igual
    return subiu if delta > 0 else caiu


NOTA_ARREDONDAMENTO = "com base nos valores não arredondados"


def _inconsistente(t0: float, t1: float, nd: int) -> bool:
    """True when the difference of the printed levels is not the printed change (both rounded to ``nd`` places)."""
    return abs((round(t1, nd) - round(t0, nd)) - round(t1 - t0, nd)) >= 0.5 * 10 ** -nd


def _posicao(grupo: float, total: float) -> tuple[str, str]:
    """Conjunction and phrase comparing the normalised position of the group's I with that of the total I."""
    if round(grupo, 3) == round(total, 3):
        return "mas", f"é a mesma ({bn(grupo, 3)} nos dois casos)"
    if abs(grupo - total) <= 0.05:
        return "mas", f"é próxima ({bn(grupo, 3)} e {bn(total, 3)})"
    return "e", f"difere ({bn(grupo, 3)} no grupo e {bn(total, 3)} no total)"


# --------------------------------------------------------------------------- blocks of the monthly report
def par_resumo(f: FatosBaixaRenda) -> str:
    d = f.idc["t1"] - f.idc["tprev"]
    nota_d = f" ({NOTA_ARREDONDAMENTO})" if _inconsistente(f.idc["tprev"], f.idc["t1"], 3) else ""
    return (
        f"O IDC para a população de baixa renda --- tomadores pessoa física com renda de até 2 salários mínimos, incluindo os sem rendimento --- "
        f"foi de {bn(f.idc['t1'], 3)} em {bmes(f.t1)}, com {'alta' if d > 0 else 'queda'} de {bponto(d)}{nota_d} em relação aos "
        f"{bn(f.idc['tprev'], 3)} de {bmes(f.tprev)}. Esse índice mantém o C do IDC geral e usa o I e o Q do crédito livre tomado por esse grupo, que marcaram "
        f"{bn(f.i['norm_t1'], 3)} e {bn(f.q['norm_t1'], 3)} na escala normalizada. O resultado foi o {ordinal(f.rank)} maior entre as "
        f"{b(str(f.n_obs))} observações válidas desde {bmes(f.inicio)}."
    )


def pars_resultados(f: FatosBaixaRenda) -> str:
    d = f.idc["t1"] - f.idc["tprev"]
    di, dq = f.i["t1"] - f.i["tprev"], f.q["t1"] - f.q["tprev"]
    g = f.geral["idc_t1"]
    comparacao = (f"valor igual ao do IDC geral ({bn(g, 3)})" if round(f.idc["t1"], 3) == round(g, 3)
                  else f"{'acima' if f.idc['t1'] > g else 'abaixo'} do IDC geral ({bn(g, 3)})")
    if f.rank_i == 1:
        destaque_i = ", o maior valor da série do grupo"
    elif f.rank_i <= 3:
        destaque_i = f", o {ordinal(f.rank_i)} maior valor da série do grupo (o máximo foi de {bpct(f.i['max'], 2)} em {bmes(f.i_max_mes)})"
    else:
        destaque_i = ""
    mov_i = (f"ficou estável em {bpct(f.i['t1'], 2)}" if round(f.i["tprev"], 2) == round(f.i["t1"], 2)
             else f"{_verbo(di, 'avançou', 'recuou')} de {bpct(f.i['tprev'], 2)} para {bpct(f.i['t1'], 2)}")
    mov_q = (f"ficou estável em {bpct(f.q['t1'], 2)}" if round(f.q["tprev"], 2) == round(f.q["t1"], 2)
             else f"{_verbo(dq, 'subiu', 'caiu')} de {bpct(f.q['tprev'], 2)} para {bpct(f.q['t1'], 2)}")
    nota_d = f" ({NOTA_ARREDONDAMENTO})" if _inconsistente(f.idc["tprev"], f.idc["t1"], 3) else ""
    nota_i = f", {NOTA_ARREDONDAMENTO}" if _inconsistente(f.i["tprev"], f.i["t1"], 2) else ""
    nota_q = f", {NOTA_ARREDONDAMENTO}" if _inconsistente(f.q["tprev"], f.q["t1"], 2) else ""
    p1 = (
        f"No grupo de baixa renda, o IDC {_verbo(d)} {bponto(d)}{nota_d} em {bmes(f.t1)}, de {bn(f.idc['tprev'], 3)} para {bn(f.idc['t1'], 3)}, "
        f"{comparacao}. A inadimplência (I) do grupo {mov_i} "
        f"({bpp(di)}{nota_i}){destaque_i}, e seu valor normalizado passou de {bn(f.i['norm_tprev'], 3)} para {bn(f.i['norm_t1'], 3)}. "
        f"A participação do crédito oneroso (Q) {mov_q} "
        f"({bpp(dq)}{nota_q}), com valor normalizado de {bn(f.q['norm_t1'], 3)}."
    )
    conjuncao, posicao = _posicao(f.i["norm_t1"], f.geral["I_norm_t1"])
    nivel = "maior" if f.i["t1"] > f.geral["I_t1"] else "menor"
    p2 = (
        f"Como C é o mesmo nos dois índices, a diferença entre eles decorre apenas de I e Q: a inadimplência do grupo ({bpct(f.i['t1'], 2)}) é {nivel} "
        f"que a do total ({bpct(f.geral['I_t1'], 1)}), {conjuncao} a posição de cada série em sua própria história {posicao}. "
        f"Assim como o IDC geral, o índice para baixa renda mede posição relativa no histórico do próprio grupo, "
        f"e não o nível absoluto de desconforto."
    )
    return p1 + "\n\n" + p2


def par_trajetoria(f: FatosBaixaRenda) -> str:
    maximos = f.meses_maximo
    txt_max = ""
    if maximos:
        lista = [bmes(m) for m in maximos]
        txt_max = f"atingiu {bn(1.0, 3)} em {' e '.join(lista) if len(lista) <= 2 else ', '.join(lista[:-1]) + ' e ' + lista[-1]}"
    return (
        f"A Figura~\\ref{{fig:indice}} traz também o IDC para baixa renda, exibido desde {bmes(f.inicio)}, que {txt_max + ' e ' if txt_max else ''}"
        f"passou de {bn(f.idc['tprev'], 3)} em {bmes(f.tprev)} para {bn(f.idc['t1'], 3)} em {bmes(f.t1)}. Nos painéis de I e de Q da "
        f"Figura~\\ref{{fig:componentes}}, as linhas tracejadas mostram as séries do grupo de baixa renda desde {bmes(JANELA_INICIO)}."
    )


def par_indisponivel(resultado: Resultado) -> str:
    """Sentence that replaces the low-income blocks when the index could not be updated in the edition."""
    razao = {
        "bloqueio": "porque os dados do SCR.data do Banco Central divergem das séries oficiais além do limite de tolerância adotado na construção do índice",
        "sem_cobertura": ("porque os dados do SCR.data do Banco Central ainda não cobrem " + (bmes(resultado.t1) if resultado.t1 is not None else "o mês de referência")),
        "sem_dados": "porque os dados do SCR.data do Banco Central não estavam disponíveis",
    }.get(resultado.status, "porque os dados necessários não estavam disponíveis")
    return f"O IDC para a população de baixa renda não foi atualizado nesta edição, {razao}. O IDC geral não depende dessa fonte."


def nota_baixa_renda() -> str:
    """Note on the method of the low-income IDC (the report is self-contained: it cites no other document)."""
    return (
        "Sobre o IDC para baixa renda. O IDC para a população de baixa renda segue as regras do IDC geral, com duas diferenças. "
        "O componente C é o mesmo, porque o Banco Central não divulga o comprometimento de renda por faixa de renda. I e Q passam a ser calculados para o "
        "crédito livre de pessoas físicas com renda de até 2 salários mínimos, incluindo as que não têm rendimento, segundo a faixa de renda informada "
        "ao Sistema de Informações de Crédito (SCR), com o SCR.data do Banco Central (operações de crédito livre PF, exceto financiamento rural, "
        "imobiliário e de exportação ou importação). Esses dois componentes são normalizados pelo método min-max com janela expansiva a partir de "
        f"{mes(JANELA_INICIO)}, primeiro mês do SCR.data, e o índice é exibido a partir de {mes(primeira_exibicao())}, 34 meses depois, o mesmo período de "
        "aquecimento do IDC geral. O Banco Central reprocessa os arquivos do SCR.data continuamente, e as séries do grupo incorporam a versão "
        "disponível na data do cálculo. Os valores de I e Q do grupo aparecem com duas casas decimais no texto."
    )


def tabela_componentes(f: FatosBaixaRenda, mesref: str = r"\mesref", fonte: str | None = None) -> str:
    """Components of both IDCs side by side (raw and normalised), with a two-level header."""
    g = f.geral
    linhas = [
        (r"IDC (média dos componentes normalizados)", "---", r"\textbf{" + num(g["idc_t1"], 3) + "}", "---", r"\textbf{" + num(f.idc["t1"], 3) + "}"),
        (r"C --- Comprometimento de renda das famílias com a dívida", pct(g["C_t1"], 1), num(g["C_norm_t1"], 3), pct(g["C_t1"], 1), num(f.c_norm_t1, 3)),
        (r"I --- Inadimplência da carteira de crédito livre PF (90+ dias)", pct(g["I_t1"], 1), num(g["I_norm_t1"], 3), pct(f.i["t1"], 1), num(f.i["norm_t1"], 3)),
        (r"Q --- Participação do crédito oneroso no crédito livre PF", pct(g["Q_t1"], 1), num(g["Q_norm_t1"], 3), pct(f.q["t1"], 1), num(f.q["norm_t1"], 3)),
    ]
    corpo = "\n".join("    " + " & ".join(l) + r" \\" for l in linhas)
    nota = f"\n\\fonte{{{fonte}}}\n" if fonte else ""
    return rf"""\begin{{table}}[htbp]
  \centering
  \caption{{Componentes brutos e valores normalizados do IDC geral e do IDC para baixa renda --- {mesref}.}}
  \label{{tab:componentes}}
  \begin{{tabular}}{{>{{\raggedright\arraybackslash}}p{{6.0cm}}rrrr}}
    \toprule
    & \multicolumn{{2}}{{c}}{{IDC geral}} & \multicolumn{{2}}{{c}}{{IDC para baixa renda}} \\
    \cmidrule(lr){{2-3}}\cmidrule(lr){{4-5}}
    Indicador & Bruto & Normalizado & Bruto & Normalizado \\
    \midrule
{corpo}
    \bottomrule
  \end{{tabular}}
\end{{table}}
{nota}"""
