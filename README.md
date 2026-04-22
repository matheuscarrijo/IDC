# Índice de Desconforto de Crédito

Este repositório contém o código e a documentação para a construção de um **índice** que captura o nível de desconforto de crédito das famílias brasileiras.

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

Métrica:

- Participação dessas modalidades no total de crédito livre para pessoa física (código SGS: `20570`), expressa como **fração [0, 1]** (e.g., 0,21 = 21% do crédito livre PF alocado em modalidades onerosas)

## 3. Construção do Índice

### 3.1. Normalização Min-Max

Como as três séries têm escalas distintas, cada componente é normalizado antes da agregação utilizando o método **Min-Max** com **janela expansiva**:

$$
x^{norm}_t = \frac{x_t - \min_\tau(x)}{\max_\tau(x) - \min_\tau(x)}
$$

onde $\min_\tau$ e $\max_\tau$ denotam o mínimo e o máximo calculados sobre a janela de referência $\tau = \{1, \ldots, t\}$. O resultado indica **qual fração do range histórico o valor atual representa**: 0 corresponde ao mínimo histórico e 1 ao máximo.

A janela é **expansiva** — cresce a partir do início da amostra (mar-2011), sem viés de lookahead: em cada período $t$, utilizam-se apenas observações disponíveis até $t$. Os primeiros anos do histórico servem como período de aquecimento; o índice é exibido a partir de **jan-2014** (~34 meses de aquecimento).

### 3.2. Agregação

Após normalização, o índice é calculado como média simples dos três componentes:

$$
\text{Índice}_t = \frac{1}{3} (C_t + I_t + Q_t)
$$

onde:

- $C_t$: comprometimento de renda (normalizado)
- $I_t$: inadimplência (normalizada)
- $Q_t$: qualidade do crédito (normalizada)

### 3.3. Representação Base 100

Além da versão normalizada [0–1], os componentes brutos e o índice composto são também expressos em **base 100**, facilitando a comparação da dinâmica relativa entre séries com magnitudes distintas.

$$
x^{base100}_t = \frac{x_t}{x_{t_0}} \times 100
$$

onde $t_0$ é a primeira observação válida de cada série. Um valor de 120 indica que a série cresceu 20% em relação à base.

A transformação é aplicada a:

- **Componentes brutos** (C, I, Q): $t_0$ = jan-2014 (alinhado com o início do índice), permitindo visualizar qual componente variou mais em termos relativos.
- **Índice composto**: $t_0$ = jan-2014 (primeiro valor não-NaN após o período de aquecimento).

Diferente da versão normalizada, a escala base 100 **não tem limites fixos** — o eixo Y é livre, refletindo a magnitude real das variações relativas.

## 4. Horizonte Temporal

Os dados brutos cobrem **mar-2011 a jan-2026** (179 observações mensais), determinado pela série mais curta disponível na planilha — SGS 29034 (comprometimento de renda), que é publicada com maior defasagem que as demais. O índice é exibido a partir de **jan-2014**, após ~34 meses de aquecimento da janela expansiva.

## 5. Como Reproduzir

**Pré-requisitos:** Python 3.9+ com as dependências listadas em `requirements.txt`:

```bash
pip install -r requirements.txt
```

**Execução** a partir do diretório raiz do projeto:

```bash
python main.py
```

O script carrega os dados, constrói os três componentes e o índice (normalização min-max com janela expansiva), salva os CSVs em `outputs/data/` e as figuras em `outputs/figures/`.

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
│   ├── normalize.py     # normalização min-max com janela expansiva
│   ├── build_index.py   # constrói componentes C, I, Q e agrega o índice
│   └── plot.py          # gera as figuras
├── outputs/
│   ├── data/            # series_raw.csv, components_raw.csv, index.csv
│   └── figures/         # 6 figuras (PNG)
├── main.py              # ponto de entrada
├── requirements.txt
└── README.md
```

## 7. Outputs Gerados

**Dados (`outputs/data/`):**

- **`series_raw.csv`** — séries brutas carregadas do Excel
- **`components_raw.csv`** — componentes C, I, Q antes da normalização
- **`index.csv`** — componentes normalizados (C_norm, I_norm, Q_norm) e índice agregado (a partir de jan-2014)

**Figuras (`outputs/figures/`):**

| Arquivo | Conteúdo |
|---|---|
| `components_raw.png` | Componentes C, I, Q em valores brutos (não normalizados) |
| `components_base100.png` | C, I, Q sobrepostos em base 100 (Jan-2014 = 100) |
| `components_normalized.png` | Componentes normalizados por Min-Max sobrepostos |
| `components_normalized_base100.png` | Componentes normalizados — evolução em base 100 |
| `index.png` | Índice de Desconforto de Crédito |
| `index_base100.png` | Índice em base 100 |

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
