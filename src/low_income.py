"""IDC Baixa Renda (low-income population): series, quality gate, and the facts and table of the appendix.

The low-income group is the set of PF borrowers with income of up to 2 minimum wages, including those with no
income, according to the income class reported to the SCR.  Its IDC keeps the national C of the IDC and uses I
and Q computed for the group with the SCR.data (``src.income_idc``).

``calcular`` builds the series and applies the quality gate (the SCR.data must cover the reference month and
reconcile with the official series); ``gravar`` stores the series and the status in ``data/processed/``;
``fatos`` and ``tabela_componentes`` serve the statistical appendix.  The text of the monthly report is generated
by ``src.report_text``.  The IDC Geral never depends on any of this.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from src import lenses as L
from src.income_idc import JANELA_INICIO, c_normalizado, idc_baixa_renda, indice_por_faixa, primeira_exibicao
from src.pt_format import mes, num, pct

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


# --------------------------------------------------------------------------- table of the statistical appendix
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
  \caption{{Componentes brutos e valores normalizados do IDC Geral e do IDC Baixa Renda --- {mesref}.}}
  \label{{tab:componentes}}
  \begin{{tabular}}{{>{{\raggedright\arraybackslash}}p{{6.0cm}}rrrr}}
    \toprule
    & \multicolumn{{2}}{{c}}{{IDC Geral}} & \multicolumn{{2}}{{c}}{{IDC Baixa Renda}} \\
    \cmidrule(lr){{2-3}}\cmidrule(lr){{4-5}}
    Indicador & Bruto & Normalizado & Bruto & Normalizado \\
    \midrule
{corpo}
    \bottomrule
  \end{{tabular}}
\end{{table}}
{nota}"""
