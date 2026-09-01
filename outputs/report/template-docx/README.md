# Template Word — Índice de Desconforto de Crédito (IDC)

`template.docx` é o espelho Word editável de `../template-latex/template.tex`. Ele reproduz a estrutura padrão da nota mensal em páginas A4: capa institucional, títulos numerados, tabela de resultados, lista de componentes, figuras com legendas e fontes, cabeçalhos, rodapés, notas e citação. A seção `Revisões dos dados` não aparece no template: ela é inserida no LaTeX mensal e propagada ao Word somente quando a revisão satisfaz a dupla materialidade pública. Para revisões rotineiras, isso exige alteração de pelo menos `0,010` ponto no IDC **e** efeito sobre um elemento discutido na nota; exceções qualitativas cobrem mudança de sinal, recorde, afirmação publicada, metodologia do IDC, fonte ou cobertura, ou correção relevante. Quando presente, a tabela editável mostra apenas as competências materiais ou necessárias para explicar a base de comparação, com três casas decimais. A nota metodológica fixa informa que a série sempre incorpora todas as revisões identificadas.

O corpo principal contém somente narrativa, tabela e notas e pode ocupar quantas páginas forem necessárias, sem redução de fonte para cumprir uma contagem fixa. A seção `Notas` pode fluir naturalmente entre páginas; quando houver a seção pública de revisões, o gerador inicia `Notas` em página nova para evitar que apenas a nota fixa ou a citação fique órfã em uma página quase vazia. Depois dela, o anexo sempre começa em nova página e usa uma página por figura em largura integral. Imagem, legenda e fonte são mantidas juntas por controles nativos do Word e por quebras de página explícitas. O gerador rejeita imagens altas demais para essa composição, para que o processo corrija a proporção do gráfico-fonte em vez de encolher a figura até perder legibilidade. A seção `Notas` usa 9,5 pt e nunca pode ficar abaixo de 9 pt.

Para evitar espaço vazio excessivo no primeiro anexo, `index.png` é aproximadamente quadrado e ocupa pelo menos 130 mm de altura quando inserido na largura fixa de 150 mm.

O LaTeX continua sendo a fonte mestre. Não mantenha alterações independentes neste DOCX, pois isso faria os formatos divergirem. Depois de alterar `template.tex`, o logo ou o conversor, regenere o arquivo a partir da raiz do repositório:

```bash
python -m src.build_report_docx \
  outputs/report/template-latex/template.tex \
  outputs/report/template-docx/template.docx \
  --assets-dir outputs/report/template-latex
```

Para uma atualização mensal, preencha primeiro o `.tex` da competência e gere o DOCX final com `--require-filled`. O comando e as verificações obrigatórias estão em `PIPELINE.md`.

O Word e o LuaLaTeX podem quebrar linhas em posições ligeiramente diferentes e, por isso, podem ter totais de páginas distintos. A aprovação exige conteúdo idêntico, `Anexo de figuras` iniciado em nova página, uma figura por página no anexo, tipografia legível, elementos Word editáveis e inspeção visual de todas as páginas renderizadas.
