import re
import unittest

import pandas as pd

from src import lenses as L
from src import low_income as LI
from src import report_text as RT
from src.income_idc import c_normalizado, idc_baixa_renda, indice_por_faixa
from synthetic import T1, componentes, faixa_bruta, indice_geral


def synthetic_facts():
    """Facts of the two indices from the synthetic data (reference month ``T1``, dez-2016)."""
    comp = componentes()
    idx = indice_geral(comp)
    idx["index"] = (idx["C_norm"] + idx["I_norm"] + idx["Q_norm"]) / 3
    low = idc_baixa_renda(indice_por_faixa(L.painel(faixa_bruta(), "faixa"), c_normalizado(comp)))
    geral = RT.fatos_geral(comp, idx)
    return geral, RT.fatos_baixa_renda(low, geral)


def componente(nome="I", tprev=7.8, t1=8.0, norm_tprev=1.0, norm_t1=1.0, casas=1, **kw):
    return RT.Componente(nome, t1, tprev, norm_t1, norm_tprev, casas, **kw)


def indice(valores: list[float], nome="IDC Geral", **componentes) -> RT.FatosIndice:
    serie = pd.Series(valores, pd.date_range(end="2026-08-01", periods=len(valores), freq="MS"))
    f = RT.FatosIndice(nome, serie.index[-1], serie.index[-2], serie, escopo_serie="da série desde mar-2011")
    f.componentes = componentes or {c: componente(c) for c in "CIQ"}
    return f


class MonthTests(unittest.TestCase):
    def test_months_in_full(self):
        self.assertEqual(RT.mes_extenso(pd.Timestamp("2026-08-01")), "agosto de 2026")
        self.assertEqual(RT.mes_extenso(pd.Timestamp("2026-03-01"), ano=False), "março")

    def test_the_previous_month_carries_the_year_only_when_it_changes(self):
        jan = pd.Timestamp("2027-01-01")
        self.assertEqual(RT.mes_anterior_extenso(pd.Timestamp("2026-12-01"), jan), "dezembro de 2026")
        self.assertEqual(RT.mes_anterior_extenso(pd.Timestamp("2026-07-01"), pd.Timestamp("2026-08-01")), "julho")


class SummaryTests(unittest.TestCase):
    def test_launch_edition_introduces_the_low_income_index(self):
        self.assertIn("Esta edição também introduz o IDC Baixa Renda", RT.apresentacao(RT.LANCAMENTO_BAIXA_RENDA, True))
        self.assertIn("serão calculados e divulgados periodicamente", RT.apresentacao(RT.LANCAMENTO_BAIXA_RENDA, True))
        self.assertEqual(RT.apresentacao("202611", True),
                         "Esta nota apresenta também o IDC Baixa Renda, referente a tomadores pessoa física com renda de até 2 salários mínimos.")
        self.assertEqual(RT.apresentacao("202611", False), "")

    def test_level_wording_follows_the_direction_of_the_change(self):
        self.assertEqual(RT._movimento_indice(indice([0.963, 0.966]), "atingiu"), "atingiu 0,966, ante 0,963 em julho")
        self.assertEqual(RT._movimento_indice(indice([0.983, 0.950]), "atingiu"), "recuou para 0,950, ante 0,983 em julho")
        self.assertEqual(RT._movimento_indice(indice([0.9631, 0.9629]), "atingiu"), "manteve-se em 0,963, mesmo valor de julho")

    def test_rank_among_the_valid_observations(self):
        self.assertEqual(RT._posicao(indice([0.2, 0.9, 0.5, 0.7])), "o segundo maior resultado entre as 4 observações válidas desde maio de 2026")
        self.assertTrue(RT._posicao(indice([0.2, 0.9])).startswith("o maior resultado"))
        self.assertTrue(RT._posicao(indice([1.0, 0.5, 1.0])).startswith("empatado com o maior resultado"))

    def test_closeness_to_the_maximum(self):
        alto, alto_antes, baixo = indice([0.95, 0.96]), indice([0.5, 0.96]), indice([0.5, 0.6], nome="IDC Baixa Renda")
        self.assertEqual(RT._proximos_do_maximo([alto, indice([0.92, 0.97], nome="IDC Baixa Renda")]),
                         "Os dois índices permanecem próximos de seus máximos históricos")
        self.assertEqual(RT._proximos_do_maximo([alto_antes, indice([0.92, 0.97])]), "Os dois índices estão próximos de seus máximos históricos")
        self.assertEqual(RT._proximos_do_maximo([alto, baixo]), "O IDC Geral permanece próximo de seu máximo histórico")
        self.assertEqual(RT._proximos_do_maximo([baixo]), "")

    def test_summary_compares_the_raw_values_in_the_coauthors_wording(self):
        geral, baixa = synthetic_facts()
        texto = RT.resumo(geral, baixa)
        self.assertIn("Os dois índices permanecem próximos de seus máximos históricos.", texto)
        self.assertIn("às observadas no conjunto geral dos tomadores.", texto)
        self.assertNotIn("nominais", texto)  # the raw values are not nominal values
        self.assertIn("Em dezembro de 2016, o IDC Geral", texto)
        self.assertIn("O IDC Baixa Renda", texto)
        self.assertIn("Em valores brutos, o grupo de baixa renda apresenta", texto)
        self.assertNotIn(r"\textbf", texto)
        sozinho = RT.resumo(geral, None)
        self.assertNotIn("Baixa Renda", sozinho)
        self.assertNotIn("Os dois índices", sozinho)


class ResultsTests(unittest.TestCase):
    def test_change_with_the_rounding_qualifier_only_when_the_printed_numbers_disagree(self):
        self.assertEqual(RT._variacao(componente(tprev=10.633, t1=10.8155, casas=2)),
                         r"avançou de 10,63\% para 10,82\% (+0,18~p.p., com base nos valores não arredondados)")
        self.assertEqual(RT._variacao(componente("Q", tprev=26.50, t1=26.92, casas=2)), r"subiu de 26,50\% para 26,92\% (+0,42~p.p.)")
        self.assertEqual(RT._variacao(componente("C", tprev=28.8, t1=28.6)), r"recuou de 28,8\% para 28,6\% (-0,2~p.p.)")
        self.assertEqual(RT._variacao(componente(tprev=7.81, t1=7.79)), r"ficou estável em 7,8\%")

    def test_records_and_normalised_values(self):
        self.assertEqual(RT._recorde(componente(maximo=True), "novo {extremo} histórico"), ", novo máximo histórico")
        self.assertEqual(RT._recorde(componente(minimo=True), "o {maior} valor da série do grupo"), ", o menor valor da série do grupo")
        self.assertEqual(RT._recorde(componente(), "x"), "")
        self.assertEqual(RT._normalizado(componente()), "O valor normalizado permaneceu em 1,000.")
        self.assertEqual(RT._normalizado(componente(norm_tprev=0.888, norm_t1=0.898)), "O valor normalizado passou de 0,888 para 0,898.")

    def test_a_single_moving_component_is_credited_with_the_monthly_change(self):
        comps = {"C": componente("C"), "I": componente("I"), "Q": componente("Q", norm_tprev=0.888, norm_t1=0.898)}
        self.assertEqual(RT._atribuicao(indice([0.963, 0.966], **comps)),
                         {"Q": " Como C e I permaneceram em 1,000, o aumento de Q explicou a alta mensal do índice."})
        comps["I"] = componente("I", norm_tprev=0.9, norm_t1=0.95)
        self.assertEqual(RT._atribuicao(indice([0.963, 0.98], **comps)), {})  # two components moved

    def test_component_items_have_bold_labels_only(self):
        geral, baixa = synthetic_facts()
        for bloco in (RT.resultados_geral(geral), RT.resultados_baixa_renda(geral, baixa)):
            negritos = re.findall(r"\\textbf\{([^{}]*)\}", bloco)
            self.assertEqual(sorted(negritos), sorted(RT.ROTULOS_DOS_ITENS))
        self.assertIn(r"\subsection*{IDC Geral --- Componentes}", RT.resultados_geral(geral))
        self.assertIn("por limitação de dados, utiliza a mesma série do IDC Geral", RT.resultados_baixa_renda(geral, baixa))

    def test_comparison_of_the_two_indices_follows_the_normalised_delinquency(self):
        geral, baixa = synthetic_facts()
        geral.componentes["I"].norm_t1 = baixa.componentes["I"].norm_t1 = 1.0
        self.assertIn("o fato de I atingir 1,000 nos dois índices não significa que os níveis absolutos de inadimplência",
                      RT.resultados_baixa_renda(geral, baixa))
        geral.componentes["I"].norm_t1 = 0.6
        self.assertIn("não indica a diferença entre os níveis absolutos", RT.resultados_baixa_renda(geral, baixa))

    def test_results_table_with_and_without_the_low_income_index(self):
        geral, baixa = synthetic_facts()
        dois = RT.tabela(geral, baixa, "201702")
        self.assertIn(r"\multicolumn{2}{c}{IDC Geral} & \multicolumn{2}{c}{IDC Baixa Renda}", dois)
        self.assertIn("SCR.data para o IDC Baixa Renda", dois)
        um = RT.tabela(geral, None, "201702")
        self.assertIn(r"Indicador & Valor bruto & Valor normalizado \\", um)
        self.assertNotIn("SCR.data", um)

    def test_unavailable_edition_is_stated_without_pointing_to_other_documents(self):
        for res in (LI.Resultado("bloqueio", "x", t1=T1), LI.Resultado("sem_cobertura", "x", t1=T1), LI.Resultado("sem_dados", "x")):
            texto = RT.baixa_renda_indisponivel(res)
            self.assertIn("O IDC Baixa Renda não foi atualizado nesta edição", texto)
            self.assertNotRegex(texto.lower(), "ap[êe]ndice")


class TrajectoryAndAnnexTests(unittest.TestCase):
    def test_range_of_the_last_months_lists_every_month_of_an_extreme(self):
        s = pd.Series([0.95, 1.0, 0.97, 1.0], pd.date_range("2026-05-01", periods=4, freq="MS"))
        self.assertEqual(RT._extremo(s, True), "1,000 (jun-2026 e ago-2026)")
        self.assertEqual(RT._extremo(s, False), "0,950 (mai-2026)")

    def test_trajectory_refers_to_the_three_figures(self):
        geral, baixa = synthetic_facts()
        texto = RT.trajetoria(geral, baixa)
        for ref in ("fig:indice", "fig:periodo", "fig:recente", "fig:componentes"):
            self.assertIn(rf"\ref{{{ref}}}", texto)
        self.assertIn("níveis historicamente elevados ao longo de 2016", texto)
        self.assertIn(r"\label{tab:meses}", texto)
        self.assertNotIn("Baixa Renda", RT.trajetoria(geral, None))

    def test_the_table_of_the_latest_months_has_seven_rows(self):
        geral, baixa = synthetic_facts()
        tabela = RT.tabela_meses(geral, baixa)
        self.assertIn("IDC Geral e IDC Baixa Renda nos últimos 7 meses --- jun-2016 a dez-2016.", tabela)
        self.assertEqual(tabela.count("-2016 & "), 7)
        self.assertIn(r"Mês & IDC Geral \\", RT.tabela_meses(geral, None))

    def test_results_follow_the_coauthors_wording(self):
        geral, baixa = synthetic_facts()
        bloco = RT.resultados_baixa_renda(geral, baixa)
        self.assertIn("por limitação de dados, utiliza a mesma série do IDC Geral. De novembro para dezembro, C ", bloco)
        self.assertIn("de novembro para dezembro, I ", bloco)
        comps = {"C": componente("C", 28.8, 29.0), "I": componente("I", maximo=True), "Q": componente("Q", 24.4377, 24.4507, 0.888, 0.898)}
        texto = RT.resultados_geral(indice([0.963, 0.966], **comps))
        self.assertIn("Como o valor bruto permaneceu no maior nível da série histórica, o componente normalizado manteve-se em 1,000.", texto)
        self.assertIn("(+0,2~p.p.), novo máximo histórico. O valor normalizado permaneceu em 1,000.", texto)
        self.assertIn(r"subiu de 24,4\% para 24,5\%, e o valor normalizado passou de 0,888 para 0,898.", texto)

    def test_the_events_of_the_period_figure_are_named_with_their_month(self):
        fim = pd.Timestamp("2026-08-01")
        self.assertEqual(RT._eventos_desde(RT.RECENT_START, fim), "o Programa Desenrola (jun-2023) e o Novo Desenrola (mai-2026)")
        self.assertEqual(RT._eventos_desde(RT.RECENT_START, pd.Timestamp("2024-01-01")), "o Programa Desenrola (jun-2023)")
        geral, baixa = synthetic_facts()  # dez-2016: no event yet in the window
        self.assertIn("a partir de dez-2022, e a Figura", RT.trajetoria(geral, baixa))

    def test_annex_has_four_full_width_figures_on_their_own_pages(self):
        geral, baixa = synthetic_facts()
        anexo = RT.anexo(geral, baixa)
        self.assertEqual(anexo.count(r"\begin{figure}[H]"), 4)
        self.assertEqual(anexo.count(r"\clearpage"), 3)
        self.assertEqual(anexo.count(r"\includegraphics[width=\linewidth]"), 4)
        self.assertIn(r"\includegraphics[width=\linewidth]{index_since_2022.png}", anexo)
        self.assertIn("IDC Geral e IDC Baixa Renda nos últimos 12 meses (jan-2016 a dez-2016).", anexo)
        self.assertEqual(RT.anexo(geral, None).count("SCR.data"), 0)


if __name__ == "__main__":
    unittest.main()
