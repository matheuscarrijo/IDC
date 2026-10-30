# Licença para documentação e outputs

Salvo indicação em contrário, a documentação autoral, a metodologia autoral, as figuras, os componentes calculados e o índice agregado produzidos pelo Índice de Desconforto de Crédito (IDC) neste repositório são disponibilizados sob a licença Creative Commons Attribution 4.0 International (CC BY 4.0).

Texto da licença: <https://creativecommons.org/licenses/by/4.0/>

## Atribuição recomendada

Ao usar, redistribuir ou adaptar materiais cobertos por esta licença, atribua crédito de forma razoável, por exemplo:

> Gonzalez, Lauro; Carrijo, Matheus L.; Schiozer, Rafael. Índice de Desconforto de Crédito (IDC). FGVcemif/FGV-EAESP. Disponível no repositório do projeto.

Indique também se foram feitas alterações.

## Materiais de terceiros

Dados brutos, planilhas, relatórios, PDFs, documentação metodológica e demais materiais obtidos do Banco Central do Brasil ou de terceiros não são relicenciados por este repositório. Esses materiais permanecem sujeitos aos termos, licenças e condições das respectivas fontes originais.

Isso inclui, sem limitação, arquivos em `data/raw/YYYYMM/`, séries brutas obtidas do SGS/BCB, relatórios do Banco Central do Brasil e materiais de apoio metodológico derivados de documentação do Banco Central do Brasil.

## Dados derivados do SCR.data (ODbL)

Os arquivos de `data/processed/scr/` são agregados mensais, por faixa de renda, credor, ocupação e unidade da federação, calculados a partir do **SCR.data** do Banco Central do Brasil (dados agregados do Sistema de Informações de Crédito, <https://dadosabertos.bcb.gov.br/dataset/scr_data>), que é distribuído sob a **Open Database License (ODbL) 1.0**. Esses arquivos são uma base de dados derivada e são redistribuídos aqui sob a **ODbL 1.0** (<https://opendatacommons.org/licenses/odbl/1-0/>): quem os reutiliza deve atribuir a fonte (Banco Central do Brasil, SCR.data, e este projeto), indicar as alterações e compartilhar qualquer base derivada sob a mesma licença.

O índice para baixa renda (`data/processed/low_income_idc.csv`) é calculado por este projeto a partir desses agregados e das séries oficiais do Banco Central; como as figuras e o texto das notas, ele é um resultado autoral (produced work) disponibilizado nos termos da seção anterior, com a atribuição devida ao SCR.data. A série `data/external/cri_faixa_ref202504.csv` reproduz o Gráfico 1.2.2.16 do Relatório de Estabilidade Financeira de abril de 2025 e permanece sujeita aos termos do Banco Central.
