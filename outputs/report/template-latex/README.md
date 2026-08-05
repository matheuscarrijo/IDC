# Template LaTeX — Índice de Desconforto de Crédito (IDC)

Este é o template mestre do relatório mensal. O espelho Word editável em `../template-docx/template.docx` é gerado diretamente deste `template.tex` por `src.build_report_docx`, de modo que os formatos não sejam mantidos manualmente em paralelo.

O objetivo é produzir a saída PDF de referência e, a partir da mesma fonte preenchida, uma saída Word editável com o mesmo conteúdo e a mesma identidade visual, especialmente:

- Página A4 com margens idênticas
- Primeira página (capa) com logo no canto superior direito, título e autores alinhados à direita
- Tipografia profissional (serif para corpo, sans para títulos)
- Legendas de figuras e tabelas no formato exato usado nos relatórios IDC
- Cabeçalho e rodapé discretos nas páginas internas

## Arquivos

- `template.tex` — o template propriamente dito (auto-contido)
- `logo.png` — logotipo institucional usado na capa

Ao compilar, LuaLaTeX gera localmente `template.pdf`, `template.aux`, `template.log` e `template.out`. Esses artefatos reproduzíveis são ignorados pelo Git; o PDF atual deve ter cinco páginas, seguindo a mesma organização exigida para o relatório mensal.

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
   \newcommand{\reportsubtitle}{Nota Técnica de Atualização --- Divulgação maio de 2026; competência março de 2026}
   \newcommand{\reportdate}{28 de maio de 2026}

   \newcommand{\authorone}{Lauro Gonzalez}
   \newcommand{\authortwo}{Rafael Schiozer}
   \newcommand{\authorthree}{Matheus L. Carrijo}
   ```

3. Preencha os `\placeholder{...}` e os comandos da seção "DADOS DO RELATÓRIO", preservando a estrutura de seções reconhecida por `src.build_report_docx`.

4. Mantenha as figuras fora do corpo principal. Atualize os dois blocos existentes no `Anexo de figuras`, usando `[H]`, largura integral e `\clearpage` entre eles:

   ```latex
   \clearpage
   \begin{figure}[H]
     \centering
     \includegraphics[width=\linewidth]{index.png}
     \caption{Evolução do Índice de Desconforto de Crédito (jan-2014 a mar-2026).}
     \label{fig:indice}
     \fonte{Banco Central do Brasil (Estatísticas Monetárias e de Crédito, divulgação 202605), elaboração própria.}
   \end{figure}
   ```

5. Compile duas vezes.

6. Na raiz do repositório, gere o DOCX editável da fonte já preenchida:

   ```bash
   python -m src.build_report_docx \
     outputs/report/update-YYYYMM/idc-update-YYYYMM.tex \
     outputs/report/update-YYYYMM/idc-update-YYYYMM.docx \
     --assets-dir outputs/report/update-YYYYMM \
     --require-filled
   ```

7. Renderize e inspecione todas as páginas do PDF e do DOCX conforme `PIPELINE.md`. Se o LaTeX mudar, recompile o PDF e regenere o DOCX.

## Personalização de fontes (fidelidade máxima)

O template usa **TeX Gyre Pagella** (corpo) e **TeX Gyre Heros** (títulos) — clones de alta qualidade de Palatino e Helvetica, muito próximos de Cambria e Calibri.

Se você tem o Microsoft Office instalado e deseja usar as fontes originais do template DOCX, descomente no preâmbulo:

```latex
%\setsansfont{Calibri}[Scale=0.95]
%\setmainfont{Cambria}
```

e comente as linhas de TeX Gyre.

## Relação com o template DOCX

O LaTeX é a autoridade de conteúdo e design. O conversor Word reproduz em elementos editáveis a página A4, a capa, os cabeçalhos e rodapés internos, a hierarquia de títulos, o espaçamento, a tabela em estilo `booktabs`, as listas, as figuras, as legendas e as notas de fonte.

As figuras não dependem da decisão automática de floats. O corpo principal contém somente a narrativa, a tabela e as notas; depois dele, `Anexo de figuras` reúne exatamente uma figura por página. Ambas usam a largura integral do texto; se um gráfico for alto demais, corrija a proporção do PNG na geração da figura em vez de reduzi-lo até ficar ilegível. O DOCX aplica a mesma política com quebras de página explícitas e controles `keep-with-next`/`keep-together` do Word.

O gráfico `index.png` é gerado em formato aproximadamente quadrado. Isso aproveita a altura da primeira página do anexo sem ampliar fontes artificialmente nem distorcer a série.

LuaLaTeX e Word usam mecanismos de composição diferentes, portanto pequenas diferenças de quebra de linha são aceitáveis. O critério de aprovação é: conteúdo idêntico, organização equivalente de páginas, elementos plenamente editáveis e ausência de defeitos visuais após renderização.

Para regenerar o template Word após alterar este arquivo:

```bash
python -m src.build_report_docx \
  outputs/report/template-latex/template.tex \
  outputs/report/template-docx/template.docx \
  --assets-dir outputs/report/template-latex
```

## Estrutura recomendada para releases mensais

```
outputs/report/update-YYYYMM/
├── idc-update-YYYYMM.tex          (copiado de template.tex + preenchido)
├── idc-update-YYYYMM.docx         (gerado do .tex preenchido; editável)
├── logo.png                       (copiado)
├── components_raw.png
├── index.png
├── ...
└── idc-update-YYYYMM.pdf          (gerado)
```

## Licença

O template LaTeX é software livre. O logotipo pertence à FGV e é usado aqui apenas para reprodução fiel do template institucional.

## Contato / Autoria original do conteúdo

Lauro Gonzalez, Rafael Schiozer e Matheus L. Carrijo — FGVcemif / FGV-EAESP.
