# Fontes recuperadas de PDFs

Nada aqui é usado pelo programa. `Fonts-recovered/` não é lido por `_scan_fonts`,
que varre `Fonts/` — isto descreve como a `AlphaDG` foi remontada.

> ⚠️ **Esta pasta chega vazia num clone.** Versionados ficam só este README e o
> `charmap.json`. Os arquivos de fonte e os PDFs de origem **não entram no
> repositório**: um subconjunto extraído de PDF é a tipografia, e o PDF que o
> carrega também. Quem tiver os arquivos os coloca de volta aqui com os nomes da
> tabela abaixo e roda o [`../build_alphadg.py`](../build_alphadg.py); sem eles o
> script diz o que falta e para. O `Fonts/AlphaDG.ttf` também não é versionado, e
> a CI não o constrói.
>
> O mesmo critério vale para as figurinas: `Fonts/ZurichFigurine.TTF` e
> `Fonts/LinaresFigurine.TTF`, recuperadas do `chesswin.pdf` na 0.15.0, saíram do
> repositório junto com a pasta `fonts_6a7de6c2db0e9/` de onde vieram. Um clone
> fica com **17 fontes de tabuleiro e uma figurina**, a `Hastings`, que é
> original e sempre esteve no pacote.

## `Chess Alpha DG` — a matéria-prima da fonte remontada

Os PDFs de exemplo originais, gerados em 2011 quando o autor ainda tinha a fonte,
carregam a **`Chess Alpha DG` de verdade** embutida. Regenerar aqueles arquivos
apagaria as únicas cópias, então elas foram extraídas antes.

Na **0.16.0** estas cópias viraram a entrada do `build_alphadg.py`, que as junta,
devolve o mapa de caracteres e desenha o que falta, produzindo a
`Fonts/AlphaDG.ttf`. Os arquivos continuam intocados — a fonte é gerada, não
editada à mão, e duas construções dão o mesmo arquivo byte a byte.

| Arquivo esperado | Origem |
|---|---|
| `ChessAlphaDG--from-ex1_2col_alpha_plain.ttf` | `Example/ex1_2col_alpha_plain.pdf` |
| `ChessAlphaDG--from-ex2_2col_alpha_lines.ttf` | `Example/ex2_2col_alpha_lines.pdf` |
| `ChessAlphaDG--from-ex4_2col_answers_1col.ttf` | `Example/ex4_2col_answers_1col.pdf` |
| `source-pdfs/` | Os três PDFs de 2011, de onde saem as fontes **e** o mapa de caracteres |

**Cobertura: 52 dos 56 caracteres** que `_ALPHA_REQUIRED_CHARS` exige. Faltam
quatro, e cada um falta por um motivo que se explica:

| Falta | O que é | Por que não está lá | De onde saiu na 0.16.0 |
|---|---|---|---|
| `'` (0x27) | Preenchimento da borda inferior | Com coordenadas ligadas, a base é desenhada pelos caracteres de coluna (0xE8-0xEF) | `z` espelhado — a regra vale exato para os dois pares de canto que a Alpha ainda tem |
| `$` (0x24) | Borda esquerda | Idem: com coordenadas, a lateral vem dentro dos caracteres de linha | `%` espelhado na horizontal, como Leipzig, Condal e Kingdom o desenham |
| `f` (0x66) | Indicador triangular, brancas | Os exemplos usaram o círculo e o quadrado | **Desenhado**: forma comum às três fontes da família, ajustada à caixa e à espessura da própria Alpha |
| `i` (0x69) | Indicador triangular, pretas | idem | idem |

O `$` só apareceu quando a fonte foi montada e testada com `--no-coords`: o
tabuleiro saiu **sem a borda esquerda**. `_ALPHA_REQUIRED_CHARS` não pedia esse
caractere, embora o `fen.py` o usasse — a lista dizia 55 onde o programa precisa
de 56. Corrigido na mesma versão.

**Estas fontes não têm `cmap`.** São subconjuntos CID-keyed com codificação
Identity: a tabela de caracteres foi descartada e o mapeamento vive no CMap
`ToUnicode` do PDF. Ele foi lido de volta e está em `charmap.json`, indexado pelo
codepoint que aparece no texto do PDF (fontes simbólicas são escritas pela área
privada `U+F000`).

⚠️ **O `charmap.json` não basta para remontar a fonte**, e é a armadilha em que
se cai primeiro: o código no texto da página é um **CID**, não um glyph id. Estes
arquivos trazem um `/CIDToGIDMap` de verdade, e tratar CID como glyph id produz
uma fonte bem-formada em que o rei é uma tira de borda. O
[`../build_alphadg.py`](../build_alphadg.py) lê o `CIDToGIDMap` de cada PDF.

## `ZurichFigurine` e `HastingsFigurine` — amostras de conferência

| Arquivo | Origem |
|---|---|
| `ZurichFigurine--from-ex4_2col_answers_1col.ttf` | `Example/ex4_2col_answers_1col.pdf` |
| `HastingsFigurine--from-ex5_3col_answers_2col.ttf` | `Example/ex5_3col_answers_2col.pdf` |

Serviram de prova independente da recuperação feita na 0.15.0. As figurinas
instaladas em `Fonts/` vieram de `fonts_6a7de6c2db0e9/chesswin.pdf`; estas vieram
dos PDFs do autor, anos antes e por outro caminho. Os cinco glifos de peça
(`K Q R B N`) das duas Zurich são **idênticos ao inteiro** — mesma caixa
delimitadora, mesma área. O mesmo vale para a Hastings contra a original de
`Fonts/`. Estes dois arquivos saíram do repositório junto com o resto: a
conferência está registrada, os contornos não.

## Como refazer a extração

```python
import pymupdf as fitz
doc = fitz.open('source-pdfs/ex1_2col_alpha_plain.pdf')
for info in doc[0].get_fonts(full=True):
    name, ext, ftype, content = doc.extract_font(info[0])
```

O mapa de caracteres sai da varredura de `page.get_text('dict')`, comparando o
campo `font` de cada *span* com o nome da fonte.
