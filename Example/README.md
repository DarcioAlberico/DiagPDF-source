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
  -l 2 -f AlphaDG --symbol circle

python fen2rtf.py Example/examples.pgn -o Example/ex2_2col_alpha_lines.pdf \
  --title-template "{event}" --header "Шахматные задачи" \
  -l 2 -f AlphaDG --symbol square --lines 2

python fen2rtf.py Example/examples.pgn -o Example/ex3_2col_leipzig_numbered.pdf \
  --title-template "{event}" --header "Шахматные задачи" \
  -l 2 -f LeipzigDG --symbol square --lines 2 --lines-numbered

python fen2rtf.py Example/examples.pgn -o Example/ex4_2col_answers_1col.pdf \
  --title-template "{event}" --header "Шахматные задачи" \
  -l 2 -f AlphaDG --symbol square --answers --answers-cols 1 --figurine-font Zurich

python fen2rtf.py Example/examples.pgn -o Example/ex5_3col_answers_2col.pdf \
  --title-template "{event}" --header "Шахматные задачи" \
  -l 3 -f CondalDG --symbol square --answers --answers-cols 2 --figurine-font Hastings

python fen2rtf.py Example/examples.pgn -o Example/ex6_4col_kingdom.pdf \
  --title-template "{event}" --header "Шахматные задачи" \
  -l 4 -f KingdomDG --symbol triangle
```

## O que mudou na 0.16.0

Os três exemplos com `alpha` no nome **voltaram para a `AlphaDG`**, a fonte com
que foram feitos em 2011. Ela foi remontada nesta versão a partir das cópias que
os próprios PDFs carregavam — veja
[`../Fonts-recovered/`](../Fonts-recovered/README.md) e
[`../build_alphadg.py`](../build_alphadg.py).

O primeiro diagrama de cada um dos três sai **idêntico pixel a pixel** ao do
arquivo de 2011 (670×616, 56.782 pixels de tinta no `ex1`, zero divergentes).
É essa comparação que diz que o mapa de caracteres recuperado está certo — não
a inspeção do arquivo de fonte, que pareceria bem-formada de qualquer jeito.

## O que tinha mudado na 0.15.0

Entre a 0.15.0 e a 0.16.0 estes três rodaram com a `chess-alpha`, que usa o mesmo
mapa de peças mas não tem os glifos `F G I M f i`: o indicador de lance vinha de
um caractere Unicode da fonte de texto, menor que o do tabuleiro, como
`FONTS_WITHOUT_EMBEDDED_INDICATOR` prevê. Com a `AlphaDG` de volta, o indicador
volta a ser desenhado pela própria fonte, dentro da moldura.

O `ex4` é o primeiro exemplo que realmente usa a **`Zurich`**: antes da 0.15.0 a
fonte não existia em `Fonts/`, e pedir por ela era erro.
