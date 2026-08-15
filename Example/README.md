# Exemplos

`examples.pgn` traz 24 posições com tags `[FEN]` e solução no corpo da partida;
`chapters.pgn` é o mesmo material dividido por `[Chapter "..."]`.

Os seis PDFs saem dos comandos abaixo. **Eles ficaram sem registro de 2011 até a
0.15.0**, e quando as fontes mudaram foi preciso deduzir os parâmetros de volta a
partir dos próprios arquivos — contagem de páginas, glifo do indicador, número de
linhas de notação. Se regerar um destes com outras opções, atualize a linha aqui.

Todos usam `--title-template "{event}"`, porque o número da posição no livro está
na tag `[Event]` (`1.1 Сочи`), e o mesmo cabeçalho.

```bash
python fen2rtf.py Example/examples.pgn -o Example/ex1_2col_alpha_plain.pdf \
  --title-template "{event}" --header "Шахматные задачи" \
  -l 2 -f chess-alpha --symbol circle

python fen2rtf.py Example/examples.pgn -o Example/ex2_2col_alpha_lines.pdf \
  --title-template "{event}" --header "Шахматные задачи" \
  -l 2 -f chess-alpha --symbol square --lines 2

python fen2rtf.py Example/examples.pgn -o Example/ex3_2col_leipzig_numbered.pdf \
  --title-template "{event}" --header "Шахматные задачи" \
  -l 2 -f LeipzigDG --symbol square --lines 2 --lines-numbered

python fen2rtf.py Example/examples.pgn -o Example/ex4_2col_answers_1col.pdf \
  --title-template "{event}" --header "Шахматные задачи" \
  -l 2 -f chess-alpha --symbol square --answers --answers-cols 1 --figurine-font Zurich

python fen2rtf.py Example/examples.pgn -o Example/ex5_3col_answers_2col.pdf \
  --title-template "{event}" --header "Шахматные задачи" \
  -l 3 -f CondalDG --symbol square --answers --answers-cols 2 --figurine-font Hastings

python fen2rtf.py Example/examples.pgn -o Example/ex6_4col_kingdom.pdf \
  --title-template "{event}" --header "Шахматные задачи" \
  -l 4 -f KingdomDG --symbol triangle
```

## O que mudou na 0.15.0

Os três exemplos com `alpha` no nome tinham sido gerados com a **`AlphaDG`**, que
não está em `Fonts/`. Passaram para a `chess-alpha`, que usa o mesmo mapa de peças
— os diagramas saem com o mesmo desenho, e a borda superior também, porque o
`_board_top_fill` cai para `"` na ausência do `z` e o resultado é visualmente
igual.

A diferença real está no **indicador de lance**: a `chess-alpha` não tem os glifos
`F G I M f i`, então o marcador vem de um caractere Unicode da fonte de texto em
vez do próprio tabuleiro. Ele fica menor que o original. É o que
`FONTS_WITHOUT_EMBEDDED_INDICATOR` prevê.

As cópias da `AlphaDG` que aqueles PDFs carregavam foram extraídas antes de
regravar — veja [`../Fonts-recovered/`](../Fonts-recovered/README.md).

O `ex4` é o primeiro exemplo que realmente usa a **`Zurich`**: antes da 0.15.0 a
fonte não existia em `Fonts/`, e pedir por ela era erro.
