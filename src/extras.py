"""Single entry point that builds every extra exhibit for one IDC reference month.

``construir`` only needs data up to the reference month: the SCR.data panels and
the SGS snapshot are truncated first, so running it for a past month yields the
numbers that would have been produced then (no look-ahead), which the backtest
relies on.  Layer 2 degrades gracefully: if the SCR.data panels do not cover the
reference month or the same month a year earlier, only Layer 1 is produced.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from src import lenses as L
from src.pt_format import mes
from src.exhibits import (Contexto, memo_sem_rendimento, tabela_anatomia, tabela_c_q, tabela_idc_faixa, tabela_lente,
                      tabela_preco_fluxo, tabela_uf, texto_anatomia, texto_idc_faixa, texto_lentes, texto_preco_fluxo)
from src.income_idc import c_normalizado, indice_por_faixa
from src.workbook_tables import read_table
from src.anatomy import preco_e_fluxo


@dataclass
class Exibicoes:
    t1: pd.Timestamp
    tabelas: dict[str, str] = field(default_factory=dict)
    textos: dict[str, str] = field(default_factory=dict)
    dados: dict[str, object] = field(default_factory=dict)
    camada2: str = "ok"          # "ok" or the reason why it was skipped
    avisos: list[str] = field(default_factory=list)


def _cobre(painel: pd.DataFrame, *meses: pd.Timestamp) -> bool:
    disponiveis = set(painel.index.get_level_values("data_base"))
    return all(m in disponiveis for m in meses)


def construir(t1: pd.Timestamp, sgs: pd.DataFrame, comp: pd.DataFrame, idx: pd.DataFrame,
              paineis: dict[str, pd.DataFrame] | None, workbook: Path, scr_brutos: dict[str, pd.DataFrame] | None = None) -> Exibicoes:
    """Build tables, draft texts and data for the month ``t1``."""
    t0 = t1 - pd.DateOffset(years=1)
    sg = sgs.loc[:t1]
    out = Exibicoes(t1=t1)

    # ---------------------------------------------------------------- Camada 1 (SGS + workbook)
    taxas, _ = read_table(workbook, "Tab 16")
    conc_pf, _ = read_table(workbook, "Tab 11")
    preco = preco_e_fluxo(taxas, conc_pf, t1)
    preco.loc["Total do crédito livre PF", ["fluxo_12m_bi", "fluxo_var_pct"]] = float("nan")  # includes revolving flows
    ctx = Contexto(sgs=sg, paineis={}, idc_faixa=pd.DataFrame(), idc_geral=idx["index"].loc[:t1], preco_fluxo=preco, t1=t1, conc={})
    out.tabelas["anatomia"], a = tabela_anatomia(ctx)
    out.tabelas["c_q"], cq = tabela_c_q(ctx)
    out.tabelas["preco_fluxo"] = tabela_preco_fluxo(ctx)
    out.textos["anatomia"] = texto_anatomia(ctx, a, cq)
    out.textos["preco_fluxo"] = texto_preco_fluxo(ctx)
    out.dados.update({"anatomia": a, "c_q": cq, "preco_fluxo": preco})

    # ---------------------------------------------------------------- Camada 2 (SCR.data)
    if not paineis:
        out.camada2 = "SCR.data indisponível"
        return out
    ps = {n: p[p.index.get_level_values("data_base") <= t1] for n, p in paineis.items()}
    if not all(_cobre(p, t0, t1) for p in ps.values()):
        out.camada2 = f"SCR.data não cobre {t0:%Y-%m} e {t1:%Y-%m}"
        return out
    conc = L.conciliar(ps["faixa"], sg, t0, t1)
    if L.bloqueado(conc):
        out.camada2 = (f"conciliação com o SGS acima do limite (I: nível {conc['gap_I_nivel']:+.2f}, variação {conc['gap_I_delta']:+.2f} p.p.; "
                       f"Q: variação {conc['gap_Q_delta']:+.2f} p.p.)")
        out.dados["conciliacao"] = conc
        return out
    idc = indice_por_faixa(ps["faixa"], c_normalizado(comp.loc[:t1]))
    ctx = Contexto(sgs=sg, paineis=ps, idc_faixa=idc, idc_geral=idx["index"].loc[:t1], preco_fluxo=preco, t1=t1, conc=conc)
    quebras = {n: L.detectar_quebras(ps[n], t0, t1) for n in ps}

    def nota(nome):
        q = quebras[nome]
        if q.empty:
            return ""
        meses = [mes(m) for m in sorted({r.data_base for r in q.itertuples()})]
        lista = meses[0] if len(meses) == 1 else ", ".join(meses[:-1]) + " e " + meses[-1]
        return f"Atenção: houve reclassificação de pesos superior a 1 p.p. em {lista}, o que afeta a comparação de 12 meses."

    memo = memo_sem_rendimento(ctx, scr_brutos["faixa"]) if scr_brutos else None
    out.tabelas["faixa"], comb_faixa, d_faixa = tabela_lente(
        ctx, "faixa", f"Decomposição da variação de I e de Q em 12 meses por faixa de renda --- {mes(t1)}.", "tab:faixa",
        ordem=L.FAIXA_ORDEM, memo_sem_rendimento=memo, nota_quebras=nota("faixa"), primeiro=True)
    out.tabelas["credor"], comb_credor, d_credor = tabela_lente(
        ctx, "credor", f"Decomposição da variação de I e de Q em 12 meses por tipo de credor --- {mes(t1)}.", "tab:credor",
        ordem=L.CREDOR_ORDEM, manter=("Fintechs", "Instituições de pagamento"), nota_quebras=nota("credor"))
    out.tabelas["ocupacao"], comb_ocup, d_ocup = tabela_lente(
        ctx, "ocupacao", f"Decomposição da variação de I e de Q em 12 meses por natureza da ocupação --- {mes(t1)}.", "tab:ocupacao",
        ordenar_por="peso_t1", nota_quebras=nota("ocupacao"))
    out.tabelas["uf"], comb_uf = tabela_uf(ctx)
    out.tabelas["idc_faixa"], resumo = tabela_idc_faixa(ctx)
    tabs = {"faixa": comb_faixa, "credor": comb_credor, "ocupacao": comb_ocup, "uf": comb_uf}
    out.textos["lentes"] = texto_lentes(ctx, tabs, {"faixa": d_faixa}, conc)
    out.textos["idc_faixa"] = texto_idc_faixa(ctx, resumo)
    out.dados.update({"conciliacao": conc, "quebras": quebras, "tabs": tabs, "decs": {"faixa": d_faixa, "credor": d_credor, "ocupacao": d_ocup},
                      "idc_faixa": idc, "resumo_idc": resumo, "ctx": ctx})
    if conc["status"] != "ok" or conc["status_Q"] != "ok":
        out.avisos.append(f"conciliação I: {conc['status']} | Q: {conc['status_Q']}")
    for nome, q in quebras.items():
        if not q.empty:
            out.avisos.append(f"quebra de classificação na lente {nome}: {sorted({f'{r.data_base:%Y-%m}' for r in q.itertuples()})}")
    return out
