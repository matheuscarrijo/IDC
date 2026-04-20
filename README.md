# Índice de Desconforto Financeiro

Este repositório contém o código e a documentação para a construção de um **índice** que captura o nível de desconforto financeiro das famílias brasileiras associado ao uso de crédito.

## 1. Motivação

O projeto surge no contexto de:

- Crescente debate público sobre **endividamento das famílias**
- Políticas recentes como o **Programa Desenrola**
- Interesse em criar uma métrica análoga ao "índice de desconforto econômico" tradicional (inflação + desemprego), mas focada em **crédito**

## 2. Estrutura do Índice

O índice é composto por **três dimensões**, cada uma com dados disponíveis na planilha [data/estatisticas-monetarias-e-de-credito/tabelas-estatisticas-monetarias-e-de-credito.xlsx](data/estatisticas-monetarias-e-de-credito/tabelas-estatisticas-monetarias-e-de-credito.xlsx). Para mais informações sobre os dados, ver a seção 9 abaixo.

### 2.1. Comprometimento de renda com dívida

- Código SGS: `29034`
- Conceito: Comprometimento de renda - Relação entre o valor correspondente aos pagamentos esperados para o serviço da dívida com o Sistema Financeiro Nacional e a renda mensal das famílias, em média móvel trimestral, ajustado sazonalmente.
- Para mais informações sobre a série: [https://dadosabertos.bcb.gov.br/dataset/29034-comprometimento-de-renda-das-familias-com-o-servico-da-divida-com-o-sistema-financeiro-nacion](https://dadosabertos.bcb.gov.br/dataset/29034-comprometimento-de-renda-das-familias-com-o-servico-da-divida-com-o-sistema-financeiro-nacion)

### 2.2. Inadimplência da carteira de crédito (90+ dias)

- Código SGS: `21112`
- Conceito: Percentual da carteira de crédito livre do Sistema Financeiro Nacional com pelo menos uma parcela com atraso superior a 90 dias. Não inclui operações referenciadas em taxas regulamentadas, operações vinculadas a recursos do BNDES ou quaisquer outras lastreadas em recursos compulsórios ou governamentais.
- Para mais informações sobre a série: [https://dadosabertos.bcb.gov.br/dataset/21112-inadimplencia-da-carteira-de-credito-com-recursos-livres---pessoas-fisicas---total](https://dadosabertos.bcb.gov.br/dataset/21112-inadimplencia-da-carteira-de-credito-com-recursos-livres---pessoas-fisicas---total)

### 2.3. Qualidade do crédito (composição do crédito "caro")

Mede a fração do crédito livre de pessoa física alocada em modalidades consideradas mais onerosas.

Componentes:

- Cheque especial (código SGS: `20573`)
- Crédito pessoal não consignado (código SGS: `20574`)
- Cartão de crédito rotativo (código SGS: `20587`)
- Cartão de crédito parcelado (código SGS: `20588`)
- Total de crédito livre para pessoa física (código SGS: `20570`)

Métrica:

- Participação dessas modalidades no total de crédito livre para pessoa física, expressa como **fração [0, 1]** (e.g., 0,21 = 21% do crédito livre PF alocado em modalidades onerosas)

## 3. Construção do Índice

### 3.1. Normalização

Como as três séries têm escalas distintas, cada componente é normalizado antes da agregação. Todas as normalizações são calculadas sobre a **amostra completa (mar-2011 em diante)**, e o índice é produzido em três versões paralelas — uma por método — para comparação.

#### 3.1.1. Min-Max

$$
x^{norm}_t = \frac{x_t - \min(x)}{\max(x) - \min(x)}
$$

O numerador mede a distância entre o valor atual e o mínimo histórico da série; o denominador é o range total (máximo menos mínimo). O resultado indica **qual fração do range histórico o valor atual representa**: 0 corresponde ao mínimo absoluto da amostra e 1 ao máximo absoluto.

| | |
|---|---|
| **Prós** | Simples; interpretável como proporção do range histórico; linearidade |
| **Contras** | Sensível a outliers; extremos da pandemia (mínimos artificiais por moratórias e transferências emergenciais) podem distorcer a escala, comprimindo o restante da série |

#### 3.1.2. Min-Max Robusto (Q10/Q90)

$$
x^{norm}_t = \text{clip}\!\left(\frac{x_t - Q_{10}}{Q_{90} - Q_{10}},\ 0,\ 1\right)
$$

onde $Q_{10}$ e $Q_{90}$ são os percentis 10 e 90 da série histórica completa, e $\text{clip}(v, 0, 1)$ trunca o valor $v$ ao intervalo $[0, 1]$, isto é, retorna 0 se $v < 0$, 1 se $v > 1$, e $v$ caso contrário.

Funciona como o Min-Max, mas substitui os extremos absolutos (min e max) pelos percentis 10 e 90, que são estatisticamente mais estáveis. O $\text{clip}$ garante que valores abaixo do $Q_{10}$ sejam tratados como 0 ("estresse mínimo normal") e valores acima do $Q_{90}$ como 1 ("estresse elevado"), sem que esses outliers distorçam a escala da faixa central.

| | |
|---|---|
| **Prós** | Robusto a outliers (Q10/Q90 são muito mais estáveis que min/max); preserva linearidade e informação de magnitude na faixa central (80% das obs) |
| **Contras** | 20% das observações (abaixo do Q10 e acima do Q90) são colapsadas em 0 ou 1, perdendo distinção entre si; a escolha de Q10/Q90 é arbitrária (poderia ser Q5/Q95 etc.) |

#### 3.1.3. Rank Percentil

$$
x^{norm}_t = \frac{|\{s \in \{1,\ldots,N\} : x_s \leq x_t\}|}{N}
$$

O numerador conta quantas observações da **amostra completa** são menores ou iguais ao valor atual; $N$ é o total de observações. O resultado é diretamente o **percentil empírico** de $x_t$ na distribuição histórica: um valor de 0,8 significa que 80% de todas as observações da amostra foram iguais ou inferiores ao nível atual. Note que o ranqueamento é feito sobre a amostra inteira (*ex post*), não apenas sobre observações anteriores a $t$.

| | |
|---|---|
| **Prós** | Totalmente robusto a outliers; interpretável diretamente como percentil histórico ("o componente está no percentil 80 desde 2011") |
| **Contras** | Não-linear: perde informação sobre a magnitude das diferenças entre observações |

### 3.2. Agregação

Após normalização, o índice é calculado como média simples dos três componentes:

$$
Índice_t = \frac{1}{3} (C_t + I_t + Q_t)
$$

onde:

- $C_t$: comprometimento de renda (normalizado)
- $I_t$: inadimplência (normalizada)
- $Q_t$: qualidade do crédito (normalizada)

O índice é produzido em **três versões paralelas**, uma para cada método de normalização (4.1.1, 4.1.2, 4.1.3), com pesos iguais (1/3) em todas.

## 4. Horizonte Temporal

O índice cobre todo o período disponível dos dados. Na prática, o horizonte efetivo é **mar-2011 a jan-2026** (179 observações mensais), determinado pela série mais curta disponível na planilha — SGS 29034 (comprometimento de renda), que é publicada com maior defasagem que as demais.

## 5. Como Reproduzir

**Pré-requisitos:** Python 3.9+ com as dependências listadas em `requirements.txt`:

```bash
pip install -r requirements.txt
```

**Execução** a partir do diretório raiz do projeto:

```bash
python main.py
```

O script carrega os dados, constrói os três componentes e as três versões do índice, salva os CSVs em `outputs/data/` e as figuras em `outputs/figures/`.

## 6. Estrutura do Repositório

```
├── data/
│   ├── estatisticas-monetarias-e-de-credito/
│   │   └── tabelas-estatisticas-monetarias-e-de-credito.xlsx   # fonte primária (BCB)
│   └── sgs-estatisticas-de-credito-endividamento-das-familias/
│       ├── tabelas-estatisticas-de-credito-endividamento-das-familias.csv
│       ├── metodologia.md
│       └── alreracoes-metodologicas/                           # boxes metodológicos do BCB
├── src/
│   ├── load_data.py     # carrega as séries do Excel
│   ├── normalize.py     # três funções de normalização
│   ├── build_index.py   # constrói componentes C, I, Q e agrega o índice
│   └── plot.py          # gera as figuras
├── outputs/
│   ├── data/            # series_raw.csv, components_raw.csv, index_full.csv
│   └── figures/         # figuras 01–08 (PNG)
├── main.py              # ponto de entrada
├── requirements.txt
└── README.md
```

## 7. Outputs Gerados

- **`outputs/data/series_raw.csv`** — séries brutas carregadas do Excel
- **`outputs/data/components_raw.csv`** — componentes C, I, Q antes da normalização
- **`outputs/data/index_full.csv`** — componentes normalizados e índice agregado para os três métodos
- **`outputs/figures/01_index_comparison.png`** — três versões do índice sobrepostas para comparação direta
- **`outputs/figures/02_components_raw.png`** — componentes individuais em valores brutos (não normalizados)
- **`outputs/figures/03_components_minmax.png`** — componentes normalizados pelo método Min-Max
- **`outputs/figures/04_components_robust.png`** — componentes normalizados pelo método Min-Max Robusto
- **`outputs/figures/05_components_percentile.png`** — componentes normalizados pelo método Rank Percentil
- **`outputs/figures/06_index_minmax.png`** — índice Min-Max isolado
- **`outputs/figures/07_index_robust.png`** — índice Min-Max Robusto isolado
- **`outputs/figures/08_index_percentile.png`** — índice Rank Percentil isolado

## 8. Observações

- O índice não tem pretensão de precisão estrutural (não é modelo causal)
- O foco é **sinalização agregada e comunicação**
- Simplicidade e transparência são prioritárias sobre sofisticação desnecessária

## 9. Estrutura e Fontes de Dados

### 9.1. Fonte principal (construção do índice)

O arquivo **[`data/estatisticas-monetarias-e-de-credito/tabelas-estatisticas-monetarias-e-de-credito.xlsx`](data/estatisticas-monetarias-e-de-credito/tabelas-estatisticas-monetarias-e-de-credito.xlsx)** é a **fonte primária** para a construção do índice.

- Obtido em: [https://www.bcb.gov.br/estatisticas/estatisticasmonetariascredito](https://www.bcb.gov.br/estatisticas/estatisticasmonetariascredito)
- Trata-se de uma **compilação oficial do Banco Central do Brasil** de um subconjunto selecionado de séries temporais do Sistema Gerenciador de Séries Temporais (SGS).
- Reúne, em uma única planilha, as principais séries necessárias para o índice.
- As observações mais recentes são marcadas com `*` na planilha, indicando **dados preliminares** sujeitos a revisão. Essas observações são incluídas no índice sem tratamento especial.

**Identificação das séries dentro da planilha:** em cada aba, a **linha 7** contém o cabeçalho `SGS` com o número identificador de cada série no sistema SGS/BCB. Exemplo: a série **29034** está na célula **D7** da aba **`Tab 27`**.

### 9.2. Fontes auxiliares (conferência e metodologia)

As demais pastas em `data/` contêm dados obtidos **diretamente do SGS** ([https://www3.bcb.gov.br/sgspub](https://www3.bcb.gov.br/sgspub/localizarseries/localizarSeries.do?method=prepararTelaLocalizarSeries)), série a série, e servem como **referência auxiliar**:

| Pasta | Finalidade |
|---|---|
| [`data/sgs-estatisticas-de-credito-endividamento-das-familias/`](data/sgs-estatisticas-de-credito-endividamento-das-familias/) | Dados brutos e documentação de metodologia da série de endividamento das famílias, obtidos diretamente da fonte (SGS/BCB) |

Estas pastas são úteis para:

1. **Conferência de consistência**: verificar se os dados da planilha principal estão alinhados com os dados brutos da fonte primária.
2. **Sanamento de dúvidas metodológicas**: cada pasta contém documentação sobre a construção das séries (ex.: `metodologia.md`), alterações metodológicas históricas e notas técnicas.
3. **Horizonte temporal estendido**: os dados do SGS podem cobrir períodos mais longos do que os disponíveis na planilha compilada.

---
