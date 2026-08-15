# Fontes recuperadas de PDFs

Nada aqui é usado pelo programa. `Fonts-recovered/` não é lido por `_scan_fonts`,
que varre `Fonts/` — isto é material de referência, guardado porque não existe em
mais nenhum lugar do repositório.

## `Chess Alpha DG` — a que falta comprar

Os PDFs de exemplo originais, gerados em 2011 quando o autor ainda tinha a fonte,
carregam a **`Chess Alpha DG` de verdade** embutida. Regenerar aqueles arquivos
apagaria as únicas cópias, então elas foram extraídas antes.

| Arquivo | Origem |
|---|---|
| `ChessAlphaDG--from-ex1_2col_alpha_plain.ttf` | `Example/ex1_2col_alpha_plain.pdf` |
| `ChessAlphaDG--from-ex2_2col_alpha_lines.ttf` | `Example/ex2_2col_alpha_lines.pdf` |
| `ChessAlphaDG--from-ex4_2col_answers_1col.ttf` | `Example/ex4_2col_answers_1col.pdf` |
| `source-pdfs/` | Os três PDFs originais, para a extração poder ser refeita e conferida |

**Cobertura: 52 dos 55 caracteres** que `_ALPHA_REQUIRED_CHARS` exige. Faltam três:

| Falta | O que é | Por que não está lá |
|---|---|---|
| `'` (0x27) | Preenchimento da borda inferior | Com coordenadas ligadas, a base é desenhada pelos caracteres de coluna (0xE8-0xEF), não por esse |
| `f` (0x66) | Indicador triangular, lance das brancas | Os exemplos usaram o círculo e o quadrado |
| `i` (0x69) | Indicador triangular, lance das pretas | idem |

**Estas fontes não têm `cmap`.** O fpdf2 embute subconjuntos CID-keyed com
codificação Identity e descarta a tabela de caracteres; o mapeamento vive no
CMap `ToUnicode` do PDF. Ele foi lido de volta e está em `charmap.json`, indexado
pelo codepoint que aparece no texto do PDF (o fpdf2 escreve fontes simbólicas
pela área privada `U+F000`).

Para montar uma `AlphaDG.ttf` utilizável seria preciso reconstruir o `cmap` a
partir desse arquivo e desenhar os três glifos que faltam. **Isso não foi feito de
propósito:** uma fonte 52/55 instalada em `Fonts/` renderiza errado com
`--no-coords` e com `--symbol triangle`, em silêncio — exatamente a corrupção que
a resolução estrita do defeito C8 existe para impedir. Melhor um erro claro
dizendo que a fonte não existe.

## `ZurichFigurine` e `HastingsFigurine` — amostras de conferência

| Arquivo | Origem |
|---|---|
| `ZurichFigurine--from-ex4_2col_answers_1col.ttf` | `Example/ex4_2col_answers_1col.pdf` |
| `HastingsFigurine--from-ex5_3col_answers_2col.ttf` | `Example/ex5_3col_answers_2col.pdf` |

Servem de prova independente da recuperação feita na 0.15.0. As figurinas
instaladas em `Fonts/` vieram de `fonts_6a7de6c2db0e9/chesswin.pdf`; estas vieram
dos PDFs do autor, anos antes e por outro caminho. Os cinco glifos de peça
(`K Q R B N`) das duas Zurich são **idênticos ao inteiro** — mesma caixa
delimitadora, mesma área. O mesmo vale para a Hastings contra a original de
`Fonts/`.

## Como refazer a extração

```python
import pymupdf as fitz
doc = fitz.open('source-pdfs/ex1_2col_alpha_plain.pdf')
for info in doc[0].get_fonts(full=True):
    name, ext, ftype, content = doc.extract_font(info[0])
```

O mapa de caracteres sai da varredura de `page.get_text('dict')`, comparando o
campo `font` de cada *span* com o nome da fonte.
