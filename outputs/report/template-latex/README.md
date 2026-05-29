# Template LaTeX — Índice de Desconforto de Crédito (IDC)

Este é o equivalente em LaTeX do template original `template-docx/template.docx`.

O objetivo é produzir saída visual **o mais próxima possível** do documento Word gerado a partir do template DOCX, especialmente:

- Página A4 com margens idênticas
- Primeira página (capa) com logo no canto superior direito, título e autores alinhados à direita
- Tipografia profissional (serif para corpo, sans para títulos)
- Legendas de figuras e tabelas no formato exato usado nos relatórios IDC
- Cabeçalho e rodapé discretos nas páginas internas

## Arquivos

- `template.tex` — o template propriamente dito (auto-contido)
- `logo.png` — logotipo institucional extraído do DOCX original (usado na capa)
- `template.pdf` — exemplo compilado (3 páginas de demonstração)

## Como compilar

Requer **LuaLaTeX** (recomendado) ou **XeLaTeX**. Distribuições TeX Live 2023+ ou MacTeX funcionam bem.

```bash
cd outputs/report/template-latex

# Compilar (duas passagens para referências cruzadas)
lualatex template.tex
lualatex template.tex
```

Ou com o caminho completo:

```bash
/Library/TeX/texbin/lualatex -interaction=nonstopmode template.tex
```

O PDF de saída é `template.pdf`.

## Como usar para um novo relatório mensal

1. Copie toda a pasta `template-latex/` (ou apenas `template.tex` + `logo.png`) para `outputs/report/update-YYYYMM/`.

2. No topo do arquivo (seção "DADOS DO RELATÓRIO"), edite:

   ```latex
   \newcommand{\reporttitle}{Índice de Desconforto de Crédito}
   \newcommand{\reportsubtitle}{Nota Técnica de Atualização — Competência março de 2026}
   \newcommand{\reportdate}{28 de maio de 2026}

   \newcommand{\authorone}{Lauro Gonzalez}
   \newcommand{\authortwo}{Rafael Schiozer}
   \newcommand{\authorthree}{Matheus L. Carrijo}
   ```

3. Substitua o conteúdo de exemplo (a partir de `\section{Introdução}`) pelo texto real do relatório, ou use `\input{conteudo.tex}`.

4. Insira figuras com o formato padrão:

   ```latex
   \begin{figure}[htbp]
     \centering
     \includegraphics[width=\linewidth]{minha-figura.png}
     \caption{Evolução do Índice de Desconforto de Crédito (jan-2014 a mar-2026).}
     \label{fig:indice}
     \fonte{Banco Central do Brasil (Estatísticas Monetárias e de Crédito, divulgação 202605), elaboração própria.}
   \end{figure}
   ```

5. Compile duas vezes.

## Personalização de fontes (fidelidade máxima)

O template usa **TeX Gyre Pagella** (corpo) e **TeX Gyre Heros** (títulos) — clones de alta qualidade de Palatino e Helvetica, muito próximos de Cambria e Calibri.

Se você tem o Microsoft Office instalado e deseja usar as fontes originais do template DOCX, descomente no preâmbulo:

```latex
%\setsansfont{Calibri}[Scale=0.95]
%\setmainfont{Cambria}
```

e comente as linhas de TeX Gyre.

## Diferenças intencionais em relação ao DOCX

- Cabeçalho e rodapé nas páginas internas (o DOCX original exportado do Google Docs tinha headers/footers praticamente vazios).
- Espaçamento 1,5 (ajustável via `\onehalfspacing` / `\singlespacing`).
- Numeração de páginas e linhas de separação visuais (melhoria de usabilidade sem alterar a identidade visual da primeira página).

Se você precisar de **reprodução pixel-perfect** da primeira página sem nenhum elemento extra, remova o bloco `\usepackage{fancyhdr}` e o `\pagestyle`.

## Estrutura recomendada para releases mensais

```
outputs/report/update-202605/
├── idc-update-202605.tex          (copiado de template.tex + preenchido)
├── logo.png                       (copiado)
├── components_raw.png
├── index.png
├── ...
└── idc-update-202605.pdf          (gerado)
```

## Licença

O template LaTeX é software livre. O logotipo pertence à FGV e é usado aqui apenas para reprodução fiel do template institucional.

## Contato / Autoria original do conteúdo

Lauro Gonzalez, Rafael Schiozer e Matheus L. Carrijo — FGVcemif / FGV-EAESP.
