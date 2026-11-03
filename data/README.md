# Dados

**Para as séries do relatório, abra `processed/idc_data.xlsx`, aba "Séries do relatório".**

| Arquivo | Conteúdo |
|---|---|
| `processed/idc_data.xlsx` | Planilha consolidada. Abas: **Séries do relatório** (IDC Geral, IDC Baixa Renda e componentes brutos C, I e Q, mês a mês); **Notas** (fontes e unidades); IDC e Normalizados; Componentes Brutos; IDC Baixa Renda |
| `processed/index.csv` | IDC Geral (`index`) e componentes normalizados `C_norm`, `I_norm`, `Q_norm` (0 = melhor, 1 = pior), desde jan-2014 |
| `processed/components_raw.csv` | Componentes brutos: C e I em %, Q como fração do crédito livre PF |
| `processed/low_income_idc.csv` | IDC Baixa Renda (renda até 2 salários mínimos): I e Q em %, normalizados, C nacional normalizado e `IDC`; desde jul-2012, exibido desde mai-2015 |
| `processed/low_income_status.json` | Situação do IDC Baixa Renda na última rodada (`ok`, `bloqueio`, `sem_cobertura`, `sem_dados`) e conciliação com as séries oficiais |
| `processed/series_raw.csv` | Séries do BCB usadas no cálculo (comprometimento de renda, inadimplência e saldos do crédito livre PF por modalidade) |
| `processed/sgs_snapshot.csv` | Séries do SGS usadas no apêndice estatístico |
| `processed/scr/` | Agregados do SCR.data por faixa de renda (`scr_faixa.csv`), credor, ocupação e UF, e a data de geração de cada arquivo do BCB (`scr_vintage.csv`) |
| `raw/AAAAMM/` | Planilha e PDF originais de cada divulgação das Estatísticas Monetárias e de Crédito do BCB |
| `external/cri_faixa_ref202504.csv` | Comprometimento de renda por faixa (REF abr-2025), usado no apêndice; ver `external/LEIAME.txt` |

Os arquivos de `processed/` são gerados por `python main.py` a cada divulgação; não edite à mão.
