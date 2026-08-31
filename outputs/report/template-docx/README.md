# Template Word — Índice de Desconforto de Crédito (IDC)

`template.docx` é o espelho Word editável de `../template-latex/template.tex`. Ele reproduz a estrutura padrão da nota mensal em páginas A4: capa institucional, títulos numerados, tabela de resultados, lista de componentes, figuras com legendas e fontes, cabeçalhos, rodapés, notas e citação. A seção `Revisões dos dados` não aparece no template: ela é inserida no LaTeX mensal e propagada ao Word somente quando o comparador de safras detectar revisões. Quando presente, sua tabela editável deve listar todas as competências cujo IDC mudou, com o valor anterior, o recalculado e a diferença.

O corpo principal contém somente narrativa, tabela e notas. Depois dele, o anexo usa uma página por figura em largura integral. Imagem, legenda e fonte são mantidas juntas por controles nativos do Word e por quebras de página explícitas. O gerador rejeita imagens altas demais para essa composição, para que o processo corrija a proporção do gráfico-fonte em vez de encolher a figura até perder legibilidade.

Para evitar espaço vazio excessivo no primeiro anexo, `index.png` é aproximadamente quadrado e ocupa pelo menos 130 mm de altura quando inserido na largura fixa de 150 mm.

O LaTeX continua sendo a fonte mestre. Não mantenha alterações independentes neste DOCX, pois isso faria os formatos divergirem. Depois de alterar `template.tex`, o logo ou o conversor, regenere o arquivo a partir da raiz do repositório:

```bash
python -m src.build_report_docx \
  outputs/report/template-latex/template.tex \
  outputs/report/template-docx/template.docx \
  --assets-dir outputs/report/template-latex
```

Para uma atualização mensal, preencha primeiro o `.tex` da competência e gere o DOCX final com `--require-filled`. O comando e as verificações obrigatórias estão em `PIPELINE.md`.

O Word e o LuaLaTeX podem quebrar linhas em posições ligeiramente diferentes. A aprovação exige conteúdo idêntico, organização equivalente, elementos Word editáveis e inspeção visual de todas as páginas renderizadas.
