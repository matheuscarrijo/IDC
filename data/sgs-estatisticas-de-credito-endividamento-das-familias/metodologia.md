# Metodologia 

Este arquivo é o sumário metodológico dos dados [data/sgs-estatisticas-de-credito-endividamento-das-familias/tabelas-estatisticas-de-credito-endividamento-das-familias.csv
](data/sgs-estatisticas-de-credito-endividamento-das-familias/tabelas-estatisticas-de-credito-endividamento-das-familias.csv)

As alterações metodológicas foram divulgadas nos boxes:

- [Endividamento e Comprometimento de Renda das Famílias com Dívidas Bancárias: revisão metodológica, de setembro de 2011](data/sgs-estatisticas-de-credito-endividamento-das-familias/alreracoes-metodologicas/RELESTAB201109-refP.pdf)
- [Evolução Recente do Crédito, da Inadimplência e do Endividamento, de setembro de 2008](data/sgs-estatisticas-de-credito-endividamento-das-familias/alreracoes-metodologicas/ri200809b2p.pdf)
- [Evolução da Inadimplência, do Endividamento e do Comprometimento de Renda das Famílias, de junho de 2009](data/sgs-estatisticas-de-credito-endividamento-das-familias/alreracoes-metodologicas/ri200906b3p.pdf)
- [Evolução dos Indicadores de Endividamento e Comprometimento de Renda após a Crise, de março de 2010](data/sgs-estatisticas-de-credito-endividamento-das-familias/alreracoes-metodologicas/ri201003b2p.pdf)
- [Endividamento e Comprometimento da Renda das Famílias: Incorporação do Conceito de Massa Salarial Ampliada Disponível, de setembro de 2010](data/sgs-estatisticas-de-credito-endividamento-das-familias/alreracoes-metodologicas/ri201009b3p.pdf)
- [Estimativa mensal da Renda Nacional Disponível Bruta das Famílias, de dezembro de 2021](data/sgs-estatisticas-de-credito-endividamento-das-familias/alreracoes-metodologicas/ri202112b2p.pdf)

---

O **comprometimento de renda** é apurado com base na proporção entre os valores médios trimestrais a serem pagos mensalmente no serviço das dívidas (juros e amortização) das famílias com o Sistema Financeiro Nacional (SFN) e a renda média trimestral das famílias líquidas de impostos, expressa na Renda Disponível Bruta das Famílias restrita (RNDBF) publicada pelo IBGE. Adicionalmente, o Banco Central publica o comprometimento de renda ajustado sazonalmente.

$$
CR_t = \left( \frac{PMT_{MM3M}}{RNDBF_{MM3M}} \right) \; \; \text{ou} \; \; CR_t = \left( \frac{PMT_{MM3M}}{RNDBF_{MM3M}} \right)_{\text{dessaz}}

$$

em que $CR_t = \text{Comprometimento a renda em } t$; $PMT_{MM3M} = \text{média móvel e 3 meses o pagamento mensal (serviço da dívida)}$; e $RNDBF_{MM3M} = \text{média móvel e 3 meses da renda disponível publicada pelo IBGE}$.

A média móvel de 3 meses do pagamento mensal no período t considera a média aritmética simples entre os períodos t, t-1 e t-2:

$$
PMT_{MM3M} = \frac{PMT_t + PMT_{t-1} + PMT_{t-2}}{3}
$$

O pagamento mensal – prestação mensal ou ainda serviço da dívida – corresponde à soma dos pagamentos mensais em cada modalidade “m” no período t.

$$
PMT_t = \sum_{m} PMT_{m,t}

$$

Por sua vez, o pagamento mensal em cada modalidade “m” é função da taxa média de juros da carteira da modalidade, do saldo da carteira da modalidade e do prazo médio de amortização da dívida “p”:

$$
PMT_{m,t} =
\frac{
\text{taxa média de juros}_{m,t} \times \text{Saldo da carteira}_{m,t}
}{
\left[ 1 - \left(1 + \text{taxa média de juros}_{m,t}\right)^{-p} \right]
}
$$

Sendo $p = (2n - 1)$, com n igual ao prazo médio de carteira da modalidade.

Cabe esclarecer que o pagamento do principal (amortização) na modalidade “m” corresponde ao saldo da carteira da modalidade dividido pelo prazo médio de amortização das operações “p”. Por resíduo, os juros do serviço da dívida equivalem ao valor do pagamento mensal menos o pagamento do principal.

$$
AMORT_{m,t} = \frac{\text{Saldo da carteira}_{m,t}}{p}

$$

$$
JUROS_{m,t} = PMT_{m,t} - AMORT_{m,t}

$$

Excepcionalmente, para o cálculo do pagamento mensal nas modalidades de cheque especial, cartão rotativo e financiamento imobiliário, a amortização considera valores específicos de prazo “p”, os juros equivalem à taxa média de juros da carteira vezes o saldo da carteira e as prestações são obtidas pela soma da amortização e dos juros:

$$
AMORT_{m,t} = \frac{\text{Saldo da carteira}_{m,t}}{p}

$$

Sendo:

- p no cheque especial = média da base específica de dados internos;
- p no cartão rotativo = 6,7 meses (hipótese de pagamentos mensais equivalentes a 15% da dívida);
- p no financiamento imobiliário = (2n - 1);

$$
JUROS_{m,t} = \text{taxa média de juros}_{m,t} \times \text{Saldo da carteira}_{m,t}
$$

$$
PMT_{m,t} = AMORT_{m,t} + JUROS_{m,t}

$$

Conceitualmente, a Renda Nacional Disponível Bruta das Famílias corresponde à renda total das famílias, que inclui os rendimentos obtidos pelo uso de fatores de produção (trabalho e capital) e as transferências recebidas descontados das transferências pagas, como impostos e contribuições sociais. Essa medida expressa a renda agregada das famílias disponível para consumo final e poupança. Mais especificamente, a RNDBF soma as seguintes parcelas de rendas das famílias, obtidas nas Contas Econômicas Integradas (CEI) do SCN,  remuneração do trabalho, que inclui os salários dos empregados e o rendimento misto bruto; excedente operacional bruto, que para o setor institucional famílias corresponde principalmente às rendas de aluguéis efetivo e imputado; rendas de propriedade, que incluem juros líquidos recebidos, rendas distribuídas das empresas para as famílias e rendas de investimentos, menos as rendas pagas pelo uso de recursos naturais; e benefícios sociais, que englobam benefícios de seguridade social, outros benefícios de seguro social e benefícios de assistência social. Desse total, são deduzidas as transferências das famílias para os demais setores institucionais e para o exterior, impostos sobre renda e patrimônio; contribuições sociais efetivas das famílias; outras transferências correntes líquidas realizadas pelas famílias.
