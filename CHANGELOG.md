# Changelog

## 0.16.0 — A `AlphaDG`, remontada

A última fonte que faltava. A 0.15.0 encontrou a **Chess Alpha DG** embutida em
três dos PDFs de exemplo de 2011 e decidiu **não** instalá-la: 52 dos 55
caracteres exigidos renderizariam errado em silêncio com `--no-coords` e
`--symbol triangle`, que é a corrupção que a resolução estrita da C8 existe para
impedir. Esta versão fecha a lacuna em vez de contorná-la.

```bash
diagpdf livro.pgn -o livro.pdf -f AlphaDG --symbol triangle --no-coords
python build_alphadg.py --check      # mostra cada derivação e o teste dela
```

### O erro que quase passou: CID não é glyph id

O `charmap.json` guardado na 0.15.0 mapeia codepoint → caractere, e a primeira
montagem tratou o código que aparece no texto do PDF como se fosse o índice do
glifo no arquivo extraído. O resultado é uma fonte **bem-formada** — abre no
fontTools, tem as tabelas todas — em que o rei é uma tira de borda e a dama é um
glifo vazio.

O que pegou isso não foi inspecionar o arquivo, foi compará-lo com quem já
tinha razão: as caixas delimitadoras de cada caractere na `LeipzigDG`, que ainda
tem seu `cmap`. Peça é célula cheia, borda é tira fina, e as duas colunas
discordavam em tudo. Estes PDFs trazem um `/CIDToGIDMap` de verdade; lido ele, as
duas colunas passaram a concordar caractere a caractere.

### Os quatro caracteres que não estavam lá

| Caractere | O que é | De onde veio |
|---|---|---|
| `'` | preenchimento da borda inferior | `z` espelhado no meio do em. A regra vale **exata** para os dois pares de canto que a própria Alpha tem (`!`→`&`, `#`→`(`), e para o par de preenchimento da Leipzig e da Kingdom, que têm os dois |
| `$` | borda esquerda | `%` espelhado na horizontal — é assim que Leipzig, Condal e Kingdom o desenham, com um erro máximo de 1 unidade entre as três |
| `f` `i` | indicador triangular | **Desenhados.** O triângulo é idêntico ao inteiro nas três fontes da família, então é constante de família e não escolha de desenho. Foi ajustado às proporções da Alpha: ela desenha os símbolos numa caixa de 1200×1200 onde as outras usam 1400×1400, com o mesmo canto em (2000, 200) — daí a altura escalada por 6/7 — e o vazado é recuado 100 unidades, a espessura que a própria Alpha usa no quadrado e no círculo |

Nenhum dos três PDFs precisou de `'` ou `$` porque todos foram gerados **com
coordenadas**, e aí a base e a lateral vêm dentro dos caracteres de coluna e de
linha. Nenhum usou triângulo: um usou círculo, dois usaram quadrado.

### A prova: pixel a pixel contra 2011

Fonte remontada se confere renderizando, não abrindo. Os três exemplos foram
regerados com a `AlphaDG` e o primeiro diagrama de cada um foi comparado com o
mesmo diagrama do arquivo de 2011, na mesma resolução:

| Exemplo | Recorte | Tinta | Pixels divergentes |
|---|---|---|---|
| `ex1_2col_alpha_plain` | 670×616 | 56.782 px | **0** |
| `ex2_2col_alpha_lines` | 670×617 | 57.876 px | **0** |
| `ex4_2col_answers_1col` | 670×616 | 56.850 px | **0** |

Os dois triângulos não têm como ser comparados assim — não existiam em lugar
nenhum. Foram conferidos contra a `LeipzigDG` lado a lado, com e sem
coordenadas.

### Um defeito que a fonte revelou: faltava um caractere na lista

Com a fonte instalada e `--no-coords`, o tabuleiro saiu **sem a borda esquerda**.
O `fen.py` escrevia `'$'` literal para essa lateral, mas `_ALPHA_REQUIRED_CHARS`
não pedia o `$` — a lista dizia 55 onde o programa precisa de **56**. Uma fonte
de layout Alpha sem `$` passava na verificação de completude e desenhava um
tabuleiro aberto do lado esquerdo, sem aviso.

O `$` virou `BDR_W` em `chars.py`, entrou na lista e o `fen.py` passou a usar a
constante. As outras quatro fontes de layout Alpha já tinham o glifo, então
nenhuma mudou de classificação — verificado uma a uma.

### `AlphaDG` era o nome de "fonte que não existe" em 12 testes

Doze testes usavam `'AlphaDG'` como o nome inválido para checar a mensagem de
erro do C8. Com a fonte instalada eles pararam de testar o caminho de erro — o
mesmo que a 0.15.0 tinha achado com `'Zurich'` no teste de figurine. Agora o nome
vem de `MISSING_FONT` no `conftest.py`, **afirmado ausente na carga**: instalar
uma fonte com esse nome falha ali e em lugar nenhum mais.

### A fonte é gerada, não distribuída

`Fonts/AlphaDG.ttf` **não entra no repositório**. Versionados ficam a
matéria-prima (`Fonts-recovered/`) e a receita (`build_alphadg.py`); quem clona
roda o script uma vez:

```bash
python build_alphadg.py
```

A CI o executa antes de testar e antes de montar o `.exe` — que empacota tudo que
estiver em `Fonts/`, então a ordem importa. Assim o script não pode apodrecer sem
alguém notar: ele se recusa a escrever se as regras de que deriva os caracteres
que faltam deixarem de valer.

Duas construções da mesma entrada dão o **mesmo arquivo byte a byte**. Não davam:
o fontTools carimba a hora do `save` em `head.modified` por padrão, e artefato de
build que muda sozinho a cada execução não serve para comparar nada. Rodar sem a
fonte também foi conferido — 17 fontes, suíte verde, é o estado de quem clona.

### Compatibilidade

Os **182 documentos do corpus saem idênticos** aos de antes da fonte existir
(`output_snapshot.py compare`). A fonte padrão continua `ChessMerida`: a
preferência por `AlphaDG` em `_default_board_font_name` só vale quando a Merida
não está instalada.

**Entregue:** 1.414 testes verdes (os 8 novos são as parametrizações por fonte
que a `AlphaDG` acrescenta), ruff limpo.

## 0.15.0 — Zurich e Linares, recuperadas do PDF

Duas das três fontes que o [ROADMAP](ROADMAP.md) dava como "serão compradas"
estavam o tempo todo dentro de um arquivo do próprio repositório:
`fonts_6a7de6c2db0e9/` guarda as 76 fontes extraídas de `chesswin.pdf`, e entre
elas estão a **ZurichFigurine** e a **LinaresFigurine** de verdade.

```bash
diagpdf livro.pgn -o livro.pdf  --answers --figurine-font Zurich
diagpdf livro.pgn -o livro.docx --answers --figurine-font Linares
```

### Por que dá para confiar na extração

Fonte tirada de PDF é subconjunto: vem só com os glifos que aquele PDF usou, e o
`cmap` pode ter sido reescrito no caminho. A pergunta não é *"o nome do arquivo
diz Zurich?"* — é *"o desenho é o da Zurich?"*.

A pasta respondeu sozinha. Ela também traz uma **HastingsFigurine** extraída, e o
`Fonts/` já tinha a HastingsFigurine original — um controle de graça:

| | Resultado |
|---|---|
| Métricas | `AFMIJD-HastingsFigurine` bate com a original em `K` `R` `B` `N` até o último inteiro (área 769758, 573210, 544490, 476321) |
| Contornos | 33 das 36 assinaturas de glifo são idênticas às da original |
| Pixel | Renderizadas lado a lado, as duas linhas são indistinguíveis |

A extração é fiel. `AFMMKA-ZurichFigurine` e `AFFJAG-LinaresFigurine` vieram do
mesmo processo, no mesmo peso (regular), e desenham peças visivelmente distintas
entre si e da Hastings — não são a mesma fonte com nomes diferentes.

Descartadas no caminho: `AFMLIE`/`AFLPNA` (peso **bold**, não regular) e
`AFFKIH-LinaresFigurineAlternate`, cujo `cmap` está remapeado — `Q` dá uma seta,
`N` dá um relógio de xadrez.

### O que essas fontes têm e o que não têm

Só os glifos que o `chesswin.pdf` usou. Isso cobre **tudo que o DiagPDF pede** de
uma fonte de figurinas — `_figurine_segments` troca a fonte apenas em
`K Q R B N`, e o resto do lance segue na fonte de texto — mas não são as
tipografias inteiras. A Linares veio com o ASCII completo; a Zurich, com 35
caracteres. Nenhuma das duas tem peças minúsculas.

A tag de subconjunto (`AFMMKA+ZurichFigurine`) foi removida dos registros de nome
antes de instalar: aquele texto vai literal para o `fontTable.xml` do DOCX, para
a tabela de fontes do RTF e para o `@font-face` do CSS. Os carimbos de data do
`head`, corrompidos na extração, também — eram um aviso do fontTools a cada
reconstrução do cache de fontes.

### Conferido em cada formato

| Formato | Como |
|---|---|
| PDF | Página de soluções renderizada: `MPDFAA+ZurichFigurine` / `+LinaresFigurine` embutidas, figurinas desenhadas |
| DOCX | Convertido pelo LibreOffice: a fonte embutida é usada, família `ZurichFigurine` — sem a tag de subconjunto |
| RTF | Tabela de fontes nomeia `ZurichFigurine`; o RTF não embute fonte, igual à Hastings que já existia |
| HTML | `@font-face` base64 decodifica na fonte certa, `.figurine { font-family: "fig-zurich" }`, 560 lances marcados |
| EPUB | `OEBPS/Fonts/ZurichFigurine.TTF` no pacote, CSS apontando para ela |

### Os exemplos, e a `AlphaDG` que estava escondida neles

Os seis PDFs de `Example/` eram de 2011 e ninguém tinha registrado como foram
gerados. Regerá-los exigiu deduzir os parâmetros dos próprios arquivos — contagem
de páginas, glifo do indicador, número de linhas de notação, coluna das respostas.
Os comandos agora estão em [`Example/README.md`](Example/README.md).

E a dedução revelou uma coisa: **três daqueles PDFs embutiam a `Chess Alpha DG` de
verdade**. Regerá-los teria apagado as únicas cópias no repositório. Foram
extraídas antes, junto do mapa de caracteres — o fpdf2 embute subconjunto
CID-keyed e descarta o `cmap`, que vive no `ToUnicode` do PDF. Está tudo em
[`Fonts-recovered/`](Fonts-recovered/README.md), com os PDFs de origem.

Cobertura do que sobrou: **52 dos 55** caracteres de `_ALPHA_REQUIRED_CHARS`.
Faltam `'` (base da borda, que nunca aparece porque com coordenadas a base é
desenhada pelos caracteres de coluna) e `f`/`i` (indicador triangular, porque
aqueles exemplos usaram círculo e quadrado). **Não foi instalada como
`AlphaDG.ttf`** de propósito: 52/55 em `Fonts/` renderiza errado com `--no-coords`
e com `--symbol triangle`, em silêncio — a corrupção que a resolução estrita da C8
existe para impedir.

Os três exemplos com `alpha` no nome passaram para a `chess-alpha`. Mesmo mapa de
peças, mesmo desenho; a borda superior sai igual porque o `_board_top_fill` cai
para `"`. Só o indicador de lance fica menor, por vir de um caractere Unicode em
vez do tabuleiro.

### Uma segunda prova para a Zurich

O `ex4_2col_answers_1col.pdf` também embutia a **`ZurichFigurine` original do
autor**, de 2011 — outra fonte, outro caminho, anos antes do `chesswin.pdf`. Os
cinco glifos de peça batem com os da fonte recuperada nesta versão **ao inteiro**,
caixa delimitadora e área. O mesmo para a Hastings do `ex5` contra a original.

### A `AlphaDG` continua faltando

E não está naquela pasta. Comparando **todos** os contornos das 76 fontes contra
`chess-alpha.ttf`, `ChessAlpha.ttf`, `LeipzigDG`, `CondalDG`, `KingdomDG` e
`ChessMerida`, o número de glifos em comum é **zero** — as famílias de lá
(Linares, Zurich, Hastings, Tendo, Beijing, Bermuda, Las Vegas, Canton,
Copenhagen, Edinburgh, Tokyo, Monte Carlo) não têm parentesco com a Alpha.

O que a `chess-alpha.ttf` de 0.13.0 não cobre, medido: falta o `z` (preenchimento
do topo da borda) e os seis glifos de indicador de lance — `F` `G` (círculo),
`I` `M` (quadrado), `f` `i` (triângulo).

### Outras mudanças

- O padrão de `--figurine-font` passa de `Hastings` para `Zurich`, que é o que
  `_default_figurine_font_name` sempre preferiu — só não havia arquivo.
- `test_a_stale_font_name_is_replaced` usava `figurine_font='Zurich'` como nome
  inválido. Agora afirma contra o que está realmente instalado: nomear uma fonte
  de verdade ali só testa o *fallback* até alguém adicionar aquela fonte, quando
  o teste passa a não testar nada.
- **`README_RU.md` reescrito** (item Doc6 do [SPEC](SPEC.md), aberto desde a
  fase 0). Estava parado no release original: prometia saída só em PDF, 4 fontes
  de tabuleiro, `AlphaDG` como padrão de `-f` e `fen2rtf.py` como script
  principal. Agora descreve o programa que existe — os 7 formatos, a matriz de
  capacidades, a referência de CLI inteira, os perfis e a tabela de fontes certa.
- `SPEC.md` ganhou uma convenção para envelhecer sem mentir: onde o texto faz uma
  afirmação no presente que o tempo tornou falsa, entra uma nota
  `> **Situação em X.Y.Z:**`. Os achados da auditoria ficam como foram
  registrados — reescrevê-los apagaria o que ela apurou.

## 0.14.0 — As pontas soltas

O plano do [ROADMAP](ROADMAP.md) estava concluído desde a fase 12, mas seis
itens tinham sido anotados ao longo do caminho e nunca feitos. Esta versão fecha
todos os que dependem de código — e compilar o LaTeX pela primeira vez revelou
que o exportador **nunca havia produzido um arquivo compilável** para PGN russo.

```bash
diagpdf livro.pgn -o livro.docx --watermark "RASCUNHO"
diagpdf livro.pgn -o diagramas/ --export-images svgs/ --image-format svg
diagpdf livro.pgn -o livro.pdf --answers --answers-after-chapter --number-restart-per-chapter
diagpdf --list-languages
```

### Marca d'água em DOCX e RTF

Ficaram de fora na fase 11 por um motivo honesto: *"não há Word aqui para
conferir que o arquivo abre"*. **Havia** — o Word está instalado nesta máquina, e
a verificação que faltava passou a ser possível.

Nos dois formatos a marca é a mesma coisa que no Word: um **objeto de desenho**
(WordArt, `shapeType` 136) ancorado no **cabeçalho**, que é a única parte que se
repete em toda página. Cinza a 45°, com a opacidade pedida, por cima do conteúdo
— as mesmas escolhas do PDF.

| | Como foi conferido |
|---|---|
| Abre no Word | Aberto pelo próprio Word via COM: 9 páginas, 1 forma no cabeçalho da seção 1, exportado para PDF sem pedir reparo |
| Fica onde deve | O PDF exportado pelo Word mostra a marca centralizada, de canto a canto, nos dois formatos |
| Não vira texto | `SAMPLE` não aparece em `word/document.xml` — só na forma do cabeçalho |
| Escape | `a " & <b>` vira `string="a &quot; &amp; &lt;b&gt;"`; no RTF, `a\b{c}ção` sai ASCII com as chaves balanceadas |

O LibreOffice desenha a marca do DOCX no lugar certo e a do RTF **deslocada para
cima** — mas ele faz o mesmo com o RTF que ele próprio exporta, então é o
importador dele, não o arquivo. O Word, que é para quem o RTF existe, acerta.

### Exportação SVG

`--export-images` só escrevia PNG. O SVG carrega **os contornos dos glifos**,
copiados da fonte com o fontTools: escala sem perder nitidez e não precisa de
fonte de xadrez do outro lado. Só o título continua texto.

A parte difícil não é desenhar, é **endereçar** o glifo. As fontes discordam
sobre onde ele mora, e a ordem passou a ser: tabela *Symbol* (U+F020–U+F0EF),
onde as fontes antigas guardam o tabuleiro; depois uma tabela Unicode comum;
e a tabela **Macintosh só quando não há nenhuma das duas**.

Essa última condição é a que importa. A `ChessMerida` não tem tabela Unicode
nenhuma, e a Macintosh é a única que mapeia ASCII para as casas dela — sem ela o
tabuleiro sai vazio. A `chess-alpha` tem Unicode **e** uma Macintosh que mapeia o
espaço — casa clara vazia — para o glifo de uma **torre branca**. Lê-la ali
colocaria no tabuleiro peças que a posição não tem.

Conferido nas 17 fontes instaladas: todo caractere que o diagrama produz encontra
glifo, e dois caracteres distintos nunca caem no mesmo — que é exatamente como a
tabela errada se manifestaria. O tabuleiro do SVG é **decodificado de volta** e
comparado com o que o renderizador pediu.

**Um defeito de tabela junto:** cada PNG exportado saía com o título do **primeiro**
diagrama, porque `render_preview_png` calculava o número da posição 0. O nome do
arquivo tinha o número certo, o desenho não.

### Respostas por capítulo e numeração que recomeça

As duas metades do "formato livro de exercícios" que faltavam:
`--answers-after-chapter` e `--number-restart-per-chapter`.

**A âncora deixou de ser o número.** Enquanto a numeração era corrida, `diag_7`
servia de nome de âncora e de número impresso. Com o reinício por capítulo o 1
volta em todo capítulo, e duas âncoras com o mesmo nome mandariam **todos** os
links do livro para a primeira delas. As âncoras passaram a contar posições ao
longo do documento; o número impresso segue as opções de numeração.

**Uma correção de conceito veio junto.** Um `[Chapter]` marca o *primeiro* jogo do
grupo — os seguintes vêm sem tag. O PDF já tratava um jogo sem tag como
continuação (cabeçalho corrente, quebra de página), mas o agrupamento comum
tratava cada corrida sem nome como um grupo à parte. Sem isso, a numeração
reiniciaria no meio do capítulo e as respostas sairiam em três seções onde há
dois capítulos. Agora quem não tem nome continua o capítulo anterior — em todos
os formatos.

| Formato | Onde a seção por capítulo aparece |
|---|---|
| PDF | Sumário intercalado: `Pins, Solutions, Forks, Solutions`; os links de cada capítulo apontam para a página da resposta dele |
| HTML/EPUB | Uma `<section class='answers'>` por capítulo, com `id` próprio |
| LaTeX, DOCX, RTF, Markdown | Um `\section*`/título por capítulo |

**Capítulo em página nova, também no LaTeX.** Compilar mostrou o único formato
paginado que não fazia isso: `\section` corre no fio do texto por design, então
um capítulo começava no meio da página onde o anterior terminou — enquanto PDF,
DOCX, RTF e HTML impresso já quebravam. Agora sai um `\clearpage` antes de cada
capítulo, menos do primeiro, onde só acrescentaria folha em branco. A regra
virou um teste único sobre os quatro formatos, em vez de um por renderizador.

### `--list-languages`

O quarto item da lista de introspecção da CLI, que tinha ficado sem os outros
três. Mostra o código, o nome no próprio idioma e o nome em inglês.

Escrever isso revelou um defeito à espera: `print` de "Русский" num console
cp1252 **derruba a execução** com `UnicodeEncodeError`. Os avisos já tratavam
disso desde a fase 3; a saída pedida, não. Agora as listagens passam pelo mesmo
tratamento — e o nome em inglês sobrevive a qualquer console.

### O `.tex` compila — e a primeira compilação achou um defeito

A fase 9 escreveu o exportador LaTeX sem nunca compilá-lo: não havia TeX aqui, e
a verificação era estrutural (aninhamento, chaves, escape, links). O MiKTeX foi
instalado, e a primeira execução do `pdflatex` parou na primeira letra cirílica:

```
! LaTeX Error: Command \CYRR unavailable in encoding T1.
!  ==> Fatal error occurred, no output PDF file produced!
```

O preâmbulo trazia `\usepackage[T2A,T1]{fontenc}`, com um comentário afirmando
que assim "o T2A dá codificação ao cirílico e o T1 segue padrão para o latim".
É o contrário: a codificação **listada por último** é a que vale, e nada no
documento trocava para T2A. Ou seja, **todo PGN russo — inclusive o exemplo que
acompanha o programa — gerava um `.tex` que não compilava**, e nenhum teste de
estrutura tinha como perceber, porque o arquivo estava perfeitamente bem-formado.

Só uma das duas pode ser a padrão, e as duas são necessárias: o T1 escreve
latim acentuado com um glifo só (e por isso hifeniza), o T2A é o único que tem
cirílico. Então **quem decide é o documento**: o T2A vai por último exatamente
quando há cirílico para compor — nas posições, em qualquer opção de texto, ou
nos rótulos que o próprio programa escreve quando o idioma é russo.

| Verificação | Resultado |
|---|---|
| Corpus inteiro | **26 de 26** documentos LaTeX compilam, em duas passadas |
| Chaves do `chessboard` | `setfen`, `inverse`, `boardfontsize`, `label` fazem o que o renderizador supõe — conferido na página |
| `draftwatermark` | A marca sai na diagonal, em todas as páginas, inclusive capa e sumário |
| Links | Sumário → capítulo, diagrama → resposta **do capítulo dele**, resposta → diagrama: todos resolvem para a página certa |
| Respostas em 2 colunas | `multicol` sai como pedido |
| Latim acentuado sob T2A | `Peão em ação: coroação — não é óbvio` e `Ñandú español, ¿sí?` saem corretos ao lado do cirílico |

Quatro testes novos compilam de verdade (documento comum, cirílico, latim
acentuado, e um com todas as opções ligadas). Sem TeX instalado eles são
pulados, não falham.

### O arnês de comparação cobria cinco formatos de sete

`output_snapshot.py` é de antes do Markdown e do LaTeX existirem. Passou a
render **182 documentos** (era 115): os sete formatos, mais casos novos para
marca d'água e para as opções por capítulo, com um PGN de capítulos em
`Example/chapters.pgn`.

### O que mudou na saída, e por quê

Dos 115 documentos que já existiam, **103 saem idênticos**. Os 12 que mudaram são
os três casos que mexem na numeração (`--number-start`, `--keep-numbers`) nos
quatro formatos cujas âncoras são texto — e a diferença é **só o número dentro do
nome da âncora**: normalizando `diagram-\d+`, o diff fica vazio. O PDF não mudou:
lá os links sempre foram numéricos.

**Entregue:** 1.425 testes, ruff limpo.

### Ainda falta

Só o que não depende de escrever código: **`ZurichFigurine.TTF`,
`LinaresFigurine.TTF` e a `AlphaDG.ttf` verdadeira** — serão compradas.

---

## 0.13.0 — Fonte classificada pelos glifos, não pelo nome do arquivo

Chegou uma fonte nova em `Fonts/` — `chess-alpha.ttf`, família **Chess Alpha** —
e ela saía com **as peças faltando**. O fpdf2 avisava:

```
WARNING: Font MPDFAA+ChessAlpha is missing the following glyphs: 'M','v','V','m'
```

Esses quatro são os cavalos e os bispos.

### A causa não era a fonte

A descoberta decidia o mapa de caracteres pelo **nome do arquivo**:

```python
legacy = font_name.endswith('DG') or font_name == 'AlphaDG'
```

`chess-alpha` não termina em "DG", então era classificada como compatível com
Merida e recebia o mapa **Merida** — que desenha cavalo e bispo com `m/M` e
`v/V`. A fonte é da família Alpha, que usa `j/J` e `n/N`. Comparando os mapas já
existentes glifo a glifo, `ALPHA_DG` **é exatamente** o layout dessa fonte: não
foi preciso mapa novo, só parar de adivinhar pelo nome.

Agora a decisão é por evidência: as duas famílias divergem justamente no cavalo e
no bispo, então basta ler da fonte quais desses glifos ela tem.

### O que mais precisou de ajuste

| Item | Antes | Agora |
|---|---|---|
| Borda superior | `z` fixo | Vem da fonte: AlphaDG usa `z`, Chess Alpha usa `"` |
| Indicador de lance | Sempre embutido na borda direita | Só nas fontes que têm o glifo; as demais usam o símbolo Unicode ao lado |
| `*_patch.ttf` | Aparecia como fonte selecionável | Ignorado na descoberta — é cópia gerada pelo próprio programa |

### Como isso foi verificado

O mapa foi **derivado olhando os glifos**, não adivinhado: uma folha de contato
rotulada de todos os 88 glifos, depois a posição inicial e uma posição italiana
renderizadas e conferidas casa a casa. Uppercase é casa escura, lowercase é casa
clara; contorno é peça branca, preenchida é preta.

### Testes por fonte reforçados

Os testes por fonte só verificavam "gerou arquivo não vazio" — que uma fonte com
o mapa errado passa alegremente, só desenhando as peças erradas ou nenhuma.
Agora cada fonte instalada:

- tem o tabuleiro **decodificado de volta** e comparado casa a casa com o FEN;
- é conferida glifo a glifo contra tudo que o diagrama lhe entrega.

Foi essa segunda checagem que teria pego o problema no dia em que ele entrou.

Um teste antigo afirmava que toda fonte de layout Alpha endereça glifos pela
Private Use Area. Isso valia para os arquivos *DG* distribuídos, não é uma lei:
essa fonte é layout Alpha com `cmap` Unicode comum. O teste passou a afirmar o
que é verdade sobre os arquivos que têm aquela codificação.

### Sem efeito nas fontes que já existiam

As 16 fontes anteriores mantêm classificação, conjunto de compatibilidade,
glifo de borda e tratamento do indicador — conferido comparando a regra antiga
com a nova para cada uma.

**Entregue:** 1.349 testes, ruff limpo.

### Ainda faltam

`ZurichFigurine.TTF` e `LinaresFigurine.TTF` continuam ausentes, e o
`AlphaDG.ttf` de verdade (família **Chess Alpha DG**, distinta da Chess Alpha)
também. O risco correspondente segue aberto na seção 5 do [ROADMAP](ROADMAP.md).

---

## 0.12.0 — Respostas em página separada (fase 12 do [ROADMAP](ROADMAP.md))

A outra metade da linha "respostas invertidas **ou em página separada**" do plano
original.

### O que já existia, sem ninguém poder desligar

Levantando o estado antes de escrever qualquer coisa: **quatro dos cinco
formatos paginados já quebravam a página** antes das respostas — e nenhum
deixava escolher.

| Formato | Antes | Agora |
|---|---|---|
| PDF | `add_page()` fixo | Opcional, padrão ligado |
| LaTeX | `\clearpage` fixo | Opcional, padrão ligado |
| DOCX | `add_page_break()` fixo | Opcional, padrão ligado |
| RTF | `\page` fixo | Opcional, padrão ligado |
| **HTML** | **nada** | Quebra na impressão, padrão ligado |
| EPUB, Markdown | — | Não têm página; ignoram sem avisar |

Então o trabalho não foi "adicionar quebra de página": foi **tornar controlável**
o que já acontecia e trazer o HTML para a linha dos outros.

O padrão é **ligado**, que é o comportamento que os quatro já tinham. Quem quiser
o contrário usa `--answers-same-page`.

### No PDF, continuar é preferência, não promessa

Com `--answers-same-page`, a seção continua de onde os diagramas pararam — **a
menos que não caiba**. Se não sobrar espaço para o título mais uma linha, a
quebra acontece assim mesmo; do contrário a seção começaria abaixo da borda
inferior, que é o defeito C12 da fase 0 de volta por outro caminho.

### A única saída que mudou

`output_snapshot.py` comparou os 115 documentos: **23 arquivos HTML mudaram, e
mais nada**. O diff de cada um são exatamente duas linhas de CSS:

```css
  break-before: page;
  page-break-before: always;
```

PDF, EPUB, DOCX, RTF, LaTeX e Markdown: byte a byte idênticos. A mudança é
intencional e só afeta a impressão — na tela as respostas seguem os diagramas
como antes.

### Não é capacidade da matriz

`answers_new_page` não virou chave de `FORMAT_CAPABILITIES`. EPUB e Markdown não
têm página para quebrar, mas também não perdem nada: não há opção descartada
para avisar, do mesmo jeito que `--flip` ou `--symbol` não são capacidades. A
tabela do README registra quem faz o quê.

**Entregue:** 1.307 testes, ruff limpo.

---

## 0.11.0 — Marca d'água (fase 11 do [ROADMAP](ROADMAP.md))

O último item do plano original.

```bash
diagpdf livro.pgn -o livro.pdf --watermark "RASCUNHO"
diagpdf livro.pgn -o livro.pdf --watermark "AMOSTRA" --watermark-opacity 25
```

### Carimbada no fim, de propósito

No PDF, a marca é aplicada **depois que todas as páginas existem**, percorrendo
uma a uma. Duas razões:

1. Fica **sobre** o conteúdo, e não embaixo — que é o que a torna visível numa
   página cheia de diagramas.
2. Existe **um** lugar que sabe da marca, em vez de um gancho em cada uma das
   quatro rotinas que abrem página (capa, sumário, diagramas, respostas).

O corpo da fonte é calculado para a diagonal da folha, então o texto atravessa a
página seja ele curto ou longo. A opacidade vira um `ExtGState` do próprio PDF
(`/ca 0.1`), não um cinza claro fingido.

### Onde vai e onde não vai

| Formato | Carimba? | Como |
|---|:--:|---|
| PDF | ✅ | Transformação de 45° + `ExtGState`, uma por página |
| LaTeX | ✅ | `draftwatermark`, carregado **só** quando há marca |
| HTML | ✅ | Elemento `position: fixed` girado |
| EPUB | — | Refluível: não tem página para carimbar |
| DOCX, RTF | — | Marca d'água ali é forma de desenho no cabeçalho |
| Markdown | — | Não tem página |

O `\usepackage{draftwatermark}` só aparece quando há marca: um documento comum
não passa a exigir um pacote que nunca usa.

**DOCX e RTF ficaram de fora deliberadamente.** Marca d'água nesses formatos é um
objeto VML/shape no cabeçalho, e não há Word aqui para conferir se o arquivo
gerado abre — um `.docx` que o Word diz estar corrompido é bem pior que um aviso
honesto de "não suportado".

### Corrigido antes de sair

O CSS da marca nasceu com `color: var(--fg)` — variável que **não existe** neste
folha de estilos (as definidas são `--text`, `--card-bg`, `--card-border`,
`--link`). Uma variável indefinida invalida a declaração inteira, e o navegador a
descarta em silêncio: exatamente o defeito **C2** da fase 0. A suíte não pegou
porque nenhum teste de CSS usava marca d'água. Corrigido para `var(--text)`, com
teste que roda `undefined_css_variables` **com** a marca ligada.

### Verificação

- 7 páginas → 7 transformações de 45° e 7 operações de estado gráfico,
  incluindo capa e sumário.
- `/ca 0.35` no PDF quando se pede `--watermark-opacity 35`.
- Escape conferido nos dois formatos que precisam: `100% & co_` vira
  `100\% \& co\_` no LaTeX, e `<script>` não sobrevive no HTML.
- EPUB conferido pelo **negativo**: nem `watermark` nem o texto aparecem no
  conteúdo.
- `output_snapshot.py` sem marca: os 115 documentos **idênticos**.

**Entregue:** 1.294 testes, ruff limpo.

---

## 0.10.0 — Respostas invertidas (fase 10 do [ROADMAP](ROADMAP.md))

A convenção de livro de exercícios: a solução sai impressa de cabeça para baixo,
para não ser lida de esguelha enquanto se olha o diagrama.

```bash
diagpdf exercicios.pgn -o livro.pdf --answers --answers-upside-down
```

### O bloco inteiro gira, não cada linha

A seção de respostas é girada **180° em torno do centro da folha**, como um
bloco só. O leitor vira a página e lê na ordem de sempre. Girar cada linha em
torno de si mesma seria mais simples e estaria errado: com a página virada, as
linhas correriam de baixo para cima.

Cabeçalho e rodapé continuam de pé — a rotação é aberta depois de eles serem
desenhados e fechada antes de a página terminar. Como o fpdf2 só oferece isso
como *context manager* e a região começa e termina dentro dos laços de
paginação, ela é conduzida à mão.

### O detalhe que quase passou

Retângulo de link é **anotação em espaço de página**: a transformação de
conteúdo não o move. Sem tratamento, o número da resposta ia para o outro lado
da folha e a área clicável ficava para trás — um link que erra o alvo é pior que
link nenhum.

A primeira tentativa reconstruiu o retângulo à mão e errou duas vezes: o
`pdf.link()` toma o `y` da borda **inferior**, não da superior, e o retângulo que
o `cell()` cria envolve os *glifos*, não a célula (altura = corpo da fonte,
largura = largura do texto, com 1 mm de recuo). A versão final não reconstrói
nada: deixa o `cell()` criar a anotação e **espelha o retângulo que ele acabou de
escrever**, seja ele qual for.

Conferido nos 24 links de uma saída real: todos os 24 centros espelhados batem,
com erro máximo de 0,09 pt (arredondamento).

### Matriz de capacidades

| Formato | Vira? | Por quê |
|---|:--:|---|
| PDF | ✅ | Transformação de conteúdo, uma por página de respostas |
| HTML, EPUB | ✅ | `transform: rotate(180deg)` no bloco |
| DOCX | — | O Word só gira texto dentro de uma forma de desenho |
| RTF | — | Não tem texto girado |
| LaTeX | — | Caixa girada não quebra entre páginas: uma seção longa transbordaria a primeira em vez de continuar |
| Markdown | — | Não tem página para virar |

Quem não vira **avisa**, como toda opção não honrada.

### Verificação

- Transformação `-1 0 -0 -1 595.28 841.89` no fluxo de conteúdo — 180° exatos em
  torno do centro. Os fluxos são comprimidos, então o teste os **descomprime**;
  procurar no arquivo cru não acharia nada e diria que está tudo certo.
- Uma rotação por página de respostas, incluindo seção de duas páginas.
- Contagem de páginas idêntica à da saída de pé: girar é transformação, não
  rediagramação.
- `output_snapshot.py`: com a opção desligada, os 115 documentos **idênticos**.

**Entregue:** 1.278 testes, ruff limpo.

---

## 0.9.0 — Markdown e LaTeX (fase 9 do [ROADMAP](ROADMAP.md))

Dois formatos novos, sete no total. Cada um resolve o tabuleiro de um jeito
diferente, porque os dois têm restrições opostas.

### Markdown: um arquivo só

Os cinco formatos anteriores desenham o tabuleiro com uma **fonte de xadrez**.
Markdown não tem como carregar uma, e um `.md` que precisa de uma pasta de
imagens ao lado deixa de ser um arquivo só. O tabuleiro sai nas **peças Unicode**,
dentro de um bloco cercado:

````markdown
### [1](#answer-1) Mate em dois

```text
8 ♜ · · · · ♝ ♜ ♚
7 · · · · · ♟ · ♟
...
  a b c d e f g h
□ Brancas jogam
```
````

Renderiza no GitHub, no editor e em qualquer gerador de site estático, sem
instalar nada. Metadados viram front matter YAML, capítulos viram títulos, e as
respostas ligam de volta aos diagramas — com as peças em Unicode também.

### LaTeX: o pacote canônico

O `.tex` desenha cada tabuleiro com o pacote
[`chessboard`](https://ctan.org/pkg/chessboard), direto do FEN:

```latex
\chessboard[setfen={r4brk/5p1p/2bp1P2/p3p2N/1pq1P3/5N1Q/PPP4P/1K1RR3 w - - 0 1}]
```

Compila com `pdflatex` (duas passadas, para o sumário e o `{total}` assentarem) e
exige o pacote — `collection-games` no TeX Live.

**Toda escolha de estilo do tabuleiro fica numa única linha `\setchessboard` do
preâmbulo.** Por diagrama só se usa `setfen`, mais `inverse=true` quando a
posição é vista do lado das pretas. Foi uma decisão deliberada: não há LaTeX
nesta máquina para compilar e conferir, então a superfície que depende do pacote
ficou concentrada onde uma correção custa uma linha.

`fontenc` carrega **T2A** além de T1 e o `babel` entra com o idioma de `--lang`:
sem isso o PGN de exemplo, que é russo, não compilaria de jeito nenhum.

### Corrigido, de quebra

Os dois formatos novos expuseram um exagero antigo em `requested_capabilities`:

| # | Correção |
|---|---|
| — | **O layout padrão contava como pedido.** Qualquer preset com mais de uma coluna marcava a capacidade `columns`, então o Markdown avisaria "não suporta grade de colunas" em **toda** execução, inclusive nas que nunca escolheram layout. Agora só conta o que difere do padrão — a mesma regra que a fase 6 já aplicara às margens |
| — | **Ligar a seção de respostas contava como pedir fonte de figurinos.** Só pedir uma fonte diferente da padrão conta |

Nenhum dos dois mudava documento; mudavam o barulho no stderr.

### Matriz de capacidades

| | LaTeX | Markdown |
|---|---|---|
| Tudo que o PDF faz | ✅ exceto figurinos | — |
| Linhas de notação, capítulos | ✅ | ✅ |
| Metadados | ✅ `\hypersetup` | ✅ front matter |
| Figurinos nas respostas | — (texto normal) | ✅ Unicode |
| Colunas, tamanho de fonte, papel, cabeçalho | ✅ | — (não tem página) |

### Verificação

**O `.tex` não foi compilado** — não há LaTeX instalado aqui. O que foi
verificado: aninhamento de ambientes, chaves balanceadas, escape dos dez
caracteres especiais do TeX, um `\chessboard` por posição com o FEN certo,
`inverse=true` só quando devido, e todo `\hyperlink` apontando para um
`\hypertarget` existente. Uma compilação de teste continua valendo a pena.

O Markdown foi verificado decodificando o tabuleiro **de volta** para a posição
e comparando casa a casa com o FEN de origem — é o que pega um tabuleiro
espelhado, que uma comparação com arquivo salvo mostraria só como diferença
opaca.

Os cinco formatos antigos não foram tocados. O único código compartilhado que
mudou foi a extração da regra de inversão para `board_is_flipped()`, conferida
exaustivamente nas 8 combinações de lado × `--flip` × auto-inversão.

**Entregue:** 1.262 testes, ruff limpo.

---

## 0.8.0 — Perfis nomeados (fase 8 do [ROADMAP](ROADMAP.md))

Um livro são doze opções, e redigitá-las a cada capítulo é como dois capítulos
acabam não combinando. Agora elas ficam guardadas sob um nome:

```bash
diagpdf cap1.pgn -o c1.pdf --answers --answers-cols 2 --cover \
        --page-size a5 --save-profile estudos

diagpdf cap2.pgn -o c2.pdf --profile estudos
```

### O problema que precisou ser resolvido primeiro

Um perfil só é útil se uma opção digitada **vencer** o perfil por trás dela. Só
que o argparse preenche todos os padrões: o `Namespace` resultante não distingue
`--layout 2` de "`--layout` não foi dado", quando 2 já é o padrão. Sem essa
distinção, `--profile estudos --layout 2` ignoraria o `--layout`.

A mesma linha de comando passou a ser lida uma segunda vez com todos os padrões
suprimidos (`argparse.SUPPRESS`); o que sobra é exatamente o que foi digitado.
As opções são então montadas em camadas: **padrões → perfil → o que foi
digitado → o que a execução fornece** (o nome do arquivo entrando no cabeçalho
vazio, o deslocamento da numeração).

### Adicionado

| Opção | Faz |
|---|---|
| `--profile NOME` | Parte das opções salvas como NOME |
| `--save-profile NOME` | Salva as opções desta linha de comando como NOME |
| `--list-profiles` | Lista cada perfil e o que ele define |
| `--delete-profile NOME` | Remove um |

- **`diagpdf/profiles.py`** — armazenamento em `~/.diagpdf/profiles.json`,
  versionado como as configurações da interface
- **Só as escolhas são guardadas**, não os 48 campos: o arquivo continua legível
  e um padrão melhorado numa versão futura alcança os perfis que nunca o fixaram
- **Validação na hora de salvar** — o valor passa por `RenderOptions`, então um
  `--answers-cols 9` vira 2 uma vez, e não a cada uso do perfil
- **Perfil derivado de perfil** — `--profile estudos --lines 3 --save-profile
  estudos-pautado`
- **Na interface**: caixa de seleção com Carregar / Salvar como… / Excluir, lendo
  e escrevendo o mesmo arquivo. Um perfil salvo pela linha de comando aparece na
  lista da janela, e vice-versa
- **`OPTION_SOURCES`** — a tabela que liga cada opção da linha de comando ao
  campo de `RenderOptions` que ela alimenta. Um só caminho serve para montar a
  execução e para decidir o que um `--save-profile` deve lembrar

### Decisões que valem registro

- **O nome do arquivo de entrada não entra no perfil.** `header` e `doc_title`
  caem para o nome do arquivo quando ninguém os define; salvar isso carimbaria
  `capitulo1` em todo documento gerado depois. O perfil guarda o que foi pedido,
  antes dessa substituição.
- **Carregar um perfil na janela não muda o idioma nem o tema.** Os dois são da
  janela, não do estilo do documento. O resto volta aos padrões da janela, não
  ao que estava na tela — assim carregar o mesmo perfil duas vezes dá o mesmo
  resultado.
- **Nome de perfil é validado.** `../evil` é recusado com explicação: o nome
  chega perto do sistema de arquivos.

### Verificação

`output_snapshot.py` comparou os 115 documentos antes e depois da reescrita do
`_build_opts`: idênticos. A janela foi construída de verdade e inspecionada — a
linha de perfis aparece, e a caixa de seleção já vinha preenchida com o perfil
que a **linha de comando** havia salvo.

**Entregue:** 1.196 testes, ruff limpo.

---

## 0.7.0 — Opções tipadas (fase 7 do [ROADMAP](ROADMAP.md))

A dívida que a fase 3 deixou anotada: as opções viajavam como `dict` entre a
CLI, a interface e os cinco renderizadores. Nada declarava quais chaves
existiam, então **cada renderizador carregava o próprio valor padrão para cada
chave que lia** — e seis deles discordavam.

### O defeito que isso escondia

Levantando os padrões embutidos antes de mexer em qualquer coisa:

| Opção | PDF | HTML / EPUB / DOCX / RTF | Consequência |
|---|---|---|---|
| `show_footer` | `True` | `False` | O mesmo pedido saía com rodapé em PDF e sem em DOCX |
| `show_header` | `bool(header)` | `False` | Idem para o cabeçalho |
| `figurine_font` | nome real da fonte | `''` | EPUB e HTML embutiam o arquivo certo e nomeavam a família CSS a partir de `''` |
| `lang` | `''` | `'en'` / `DEFAULT_LANG` | PDF podia sair sem `/Lang` |
| `font` | nome real da fonte | `''` (pré-visualização) | — |
| `answers_section` | `False` | ausente (`None`) | Equivalente na prática |

Nenhum deles atingia a CLI nem a interface, porque as duas preenchem todas as
chaves. Quem passasse um dicionário parcial — um script, um teste, qualquer uso
como biblioteca — é que recebia um documento diferente conforme o formato. Era
exatamente a falha silenciosa que o princípio 1 do roadmap proíbe.

### Adicionado

- **`diagpdf/options.py`** — `RenderOptions`, uma dataclass com as 48 opções:
  um tipo, um padrão e uma verificação por campo, num lugar só
- **Normalização única** — o recorte de faixa (índice de layout, colunas das
  respostas, tamanhos não-negativos) saiu da CLI e dos renderizadores e passou a
  acontecer uma vez, na construção
- **Validação que fala** — um nome que não existe é nomeado num aviso e
  substituído pelo padrão, em vez de virar diagrama errado:

  ```
  Warning: symbol: 'hexagon' is not one of square, circle, triangle - using 'square'
  Warning: unknown option(s) ignored: colour_scheme
  ```

- **`header_text` / `footer_text`** — a regra "só desenha se estiver ligado e
  tiver texto" era repetida de cinco jeitos diferentes; agora é uma só
- **`_make_parser()`** — a construção do parser saiu de dentro de `main()`, então
  dá para inspecionar as opções aceitas sem rodar uma conversão
- **`tests/test_options.py`** — 59 testes: padrões, normalização, validação,
  ida-e-volta com o dicionário, e um teste estrutural que reprova qualquer
  `opts.get('x', padrão)` que reapareça num renderizador
- **`output_snapshot.py`** — o arnês que provou a saída idêntica, agora no
  repositório. A suíte verifica invariantes, de propósito; quando o objetivo de
  uma mudança é a saída **não** se mexer, isto verifica direto:

  ```bash
  python output_snapshot.py save before
  python output_snapshot.py save after
  python output_snapshot.py compare          # sai não-zero se algo mudou
  ```

  Cada snapshot guarda dois digests — um com o carimbo de versão e um sem — para
  que `--ignore-version` seja uma decisão tomada **depois** de ver a diferença,
  sem regerar os 115 documentos

### Compatibilidade

O `dict` continua aceito em toda entrada pública — os renderizadores convertem
na porta. `--no-renumber`, `lichess` e os demais nomes antigos seguem valendo.
`test_smoke.py` e `test_batch.py`, que montam dicionários à mão, rodam sem
alteração.

### Verificação

A mesma exigência da fase 3: **saída idêntica**. 23 entradas — 22 conjuntos de
opções sobre o mesmo PGN, mais um arquivo `.fen` — × 5 formatos = 115
documentos, gerados pela CLI de verdade antes e depois, iguais byte a byte,
normalizando apenas o que cada formato carimba de novo a cada build: data de
criação e `/ID` no PDF, `dcterms:modified` e o UUID no EPUB, e o GUID de
ofuscação de fonte no DOCX.

Duas rodadas do **mesmo** código vieram primeiro, para provar que a comparação
era determinística antes de ela valer como prova de qualquer coisa — sem isso,
os cinco formatos acusariam diferença sempre.

A subida de versão altera o carimbo `/Creator (DiagPDF 0.7.0)`, então os 23 PDFs
diferem nesse campo e em nenhum outro; normalizando também a versão, voltam a
ser idênticos byte a byte.

### Removido

`page_setup_from_opts` ficou sem uso quando os renderizadores passaram a pedir
`opts.page`; saiu, e os testes que a exercitavam passaram a usar o mesmo caminho
que a produção usa.

**Entregue:** 1.135 testes, ruff limpo.

---

## 0.6.0 — Funcionalidades novas (fase 6 do [ROADMAP](ROADMAP.md))

### Diagramas a partir dos lances

Era a maior limitação do programa: uma partida só virava diagrama se trouxesse a
tag `[FEN]`. Um PGN comum, de partidas completas — a entrada mais corriqueira que
existe — rendia **zero** diagramas.

```bash
python fen2rtf.py imortal.pgn -o livro.pdf --at-move 10,20,last
python fen2rtf.py partidas.pgn -o livro.pdf --every 5
python fen2rtf.py comentado.pgn -o livro.pdf --at-comment       # onde houver {#diagram}
```

O replay dos lances é delegado ao **python-chess**. Escrever um parser de SAN com
gerador de lances é fácil de começar e difícil de terminar — direitos de roque,
*en passant*, promoção e as regras de desambiguação têm de estar todos exatos, e
um erro sutil produziria um **diagrama errado**, que é a pior coisa que este
programa poderia fazer. A dependência é **opcional**: sem ela, as opções dizem o
que instalar em vez de falhar de forma obscura. O executável a inclui.

Variantes entre parênteses não são seguidas — são alternativas, não a partida. Um
lance ilegal interrompe aquela partida com aviso nomeando o lance e o número,
preservando os diagramas até ali.

### Adicionado

- **Grade livre** — `--grid 3x4` no lugar dos 7 presets fixos; o encaixe é
  recalculado, então `6x8` sai legível em vez de cortado
- **Numeração** — `--number-start N` e `--number-format "#{n}"` / `"Ex. {n}"`,
  aplicados ao título, à seção de respostas e aos links entre eles
- **Modo lote** — vários arquivos de entrada, um documento cada, ou `--merge`
  para juntar tudo num só
- **Exportação de imagens** — `--export-images DIR` grava um PNG por diagrama,
  usando o mesmo desenhista da pré-visualização
- **`--dry-run`** — relata o que sairia sem gravar nada
- **`--list-layouts`** — os presets com colunas × linhas
- **Relatório de fim de execução** — documentos gerados, imagens escritas,
  posições ignoradas por FEN inválido e opções descartadas pelo formato de
  destino; tudo respeitando `--quiet`

### Corrigido

| # | Correção |
|---|---|
| — | **Falso positivo no aviso de papel**: a CLI sempre preenche as chaves de margem, então o EPUB avisava que o tamanho de página foi ignorado mesmo sem ninguém ter pedido tamanho nenhum. Agora só conta como pedido o valor que difere do padrão |
| — | **Colisão de chave i18n** entre o rótulo do campo da interface e o título impresso do sumário (`F601` no ruff) |

### Não feito

Ficaram de fora, por ordem de valor decrescente: perfis nomeados de configuração,
exportação Markdown e LaTeX, respostas invertidas ou em página separada, e marca
d'água. Nenhum deles tem defeito por trás — são funcionalidades novas, e a lista
do roadmap já os classificava como prioridade baixa.

---

## 0.5.0 — Qualidade da saída (fase 5 do [ROADMAP](ROADMAP.md))

O documento deixou de ser sempre A4 retrato com margens fixas, e o PDF passou a
carregar o que um leitor espera: metadados, marcadores e, se pedido, capa e
sumário.

### Adicionado

- **Tamanho de papel e margens** — `--page-size {a3,a4,a5,letter,legal}`,
  `--landscape`, `--margin-lr`, `--margin-tb`. Chega ao PDF (MediaBox), ao DOCX
  (`w:pgSz`), ao RTF (`\paperw`/`\landscape`) e ao CSS de impressão do HTML
  (`@page size`). O EPUB avisa que é refluível e não tem folha própria
- **Metadados do PDF** — `--title`, `--author`, `--subject`, `--keywords`,
  idioma; o produtor é sempre carimbado como `DiagPDF <versão>`
- **Marcadores (outline)** — uma entrada por capítulo e uma para a seção de
  respostas, navegáveis no painel lateral do leitor
- **Capa** (`--cover`, `--cover-subtitle`) e **sumário** (`--contents`,
  `--contents-title`) com pontilhado de condução e numeração correta
- Os mesmos controles na interface: papel, orientação, capa, sumário e autor
- `tests/test_page.py` — 64 testes: dimensões e margens em todos os tamanhos e
  nas duas orientações, MediaBox conferida, metadados, outline, e o sumário
  lido de volta do PDF renderizado para verificar entradas e números de página

### Corrigido

| # | Correção |
|---|---|
| O6 | **O `{total}` era resolvido pintando retângulos brancos por cima do rodapé e redesenhando.** Só funcionava enquanto o fundo da página fosse branco, e custava uma segunda passada por todas as páginas. Passou a usar o *alias* de contagem do próprio fpdf2, resolvido na hora de gravar — a função `_rerender_with_total` foi removida, e um teste garante que nenhum retângulo é mais desenhado |
| — | **Colisão de chave no catálogo i18n**: o rótulo do novo campo da interface reusava a chave `contents` do título impresso do sumário, sobrescrevendo-o. O ruff apontou (`F601`) e o teste de conteúdo pegou junto |

### Nota de implementação

O sumário precisa das páginas onde cada capítulo começa, que só se sabem depois
de diagramar tudo — mas ele tem de sair na frente. A primeira tentativa foi
gerar por último e reordenar as páginas; fpdf2 guarda um índice dentro de cada
objeto de página e aborta na gravação. A solução é reservar as páginas no
início (a lista de capítulos é conhecida antes de renderizar; só os números não
são) e preenchê-las no fim.

### Simplificação

O ramo `if requested > 0 … else …` de `_compute_geometry` era um no-op: os três
caminhos calculavam `min(base, encaixe)`. Verificado nas 84 combinações de
layout × tamanho × linhas antes de reduzir a uma linha.

---

## 0.4.0 — Interface (fase 4 do [ROADMAP](ROADMAP.md))

A janela era uma função de 628 linhas que congelava durante a geração. Virou um
pacote com as partes testáveis fora do Tk — 72 testes novos rodam sem display.

```
diagpdf/gui/
  app.py         a janela
  settings.py    configuração validada e versionada
  filetypes.py   filtros do diálogo de salvar
  preview.py     desenho do diagrama de pré-visualização
  worker.py      geração em thread, com cancelamento
  theme.py       paleta clara e escura
```

### Corrigido

| # | Correção |
|---|---|
| G1 | **A janela congelava durante a geração.** O trabalho rodava na thread do Tk e o callback de progresso chamava `root.update()`, que reentra no laço de eventos — um clique no meio da geração podia disparar uma segunda por cima da primeira. Agora roda em thread de trabalho, reportando por fila que a thread principal drena via `root.after`; nenhum widget é tocado fora da thread principal |
| G3 | **O CSS do EPUB era perguntado em caixa de diálogo a cada geração.** Virou campo persistente, com botão de limpar |
| G4 | **A configuração não tinha versão nem validação.** Um nome de fonte obsoleto deixava a combobox (somente leitura) em branco; um valor de tipo errado virava erro do Tcl na hora de gerar. Agora tudo é validado na carga, com faixas e enums conferidos, e migrado da v1 |
| G5 | **O formato de saída era deduzido do rótulo traduzido do filtro** — procurava "pdf" dentro de "Arquivos PDF". O diálogo passa a ser construído a partir de uma tabela onde rótulo e extensão andam juntos |
| G6 | **Digitar letra na caixa de posições lançava `TclError` cru.** Os campos passaram a `StringVar` com validação e mensagem traduzida |
| G8 | Só havia tema claro. Alternador claro/escuro |
| G10 | Créditos fixos em português ("Criado por", "modificado por") — traduzidos |
| G12 | **Catálogo i18n em três formatos**: tuplas de 3 para en/ru/pt, um dict `T_ES` avulso e uma tupla `LAYOUTS_ES`. O espanhol era alcançado por estouro de índice, e uma chave nova podia faltar em um dos catálogos sem ninguém notar. Unificado em `dict[chave][idioma]`, com teste que exige as 4 línguas em todas as 78 chaves. `LAYOUTS_ES` era cópia byte a byte dos rótulos em português — removida |

### Adicionado

- **Barra de progresso e botão cancelar** que funciona: interrompe no próximo
  relatório de progresso e apaga o arquivo pela metade, em vez de deixá-lo
- **Pré-visualização ao vivo** do diagrama, reagindo às opções (fonte, borda,
  coordenadas, orientação, linhas de notação, símbolo)
- **Arquivos recentes** no menu ao lado do campo de entrada
- **Arrastar-e-soltar** quando `tkinterdnd2` está instalado; sem ele, nada muda
- `tests/test_gui.py` — 72 testes: catálogo i18n, configuração, filtros de
  arquivo, worker (progresso, falha, cancelamento, thread) e pré-visualização

### Descoberta

**As fontes de xadrez não têm cmap Unicode.** Elas trazem uma tabela Macintosh
Roman e uma Windows *Symbol*, com os glifos em U+F020–U+F0EF. Carregada do jeito
comum, a FreeType resolve todo caractere para um glifo vazio — largura de avanço
certa, tinta nenhuma — e o tabuleiro sai como um retângulo em branco. A
pré-visualização precisa pedir o charmap simbólico (`encoding='symb'`) e
endereçar os glifos em U+F0xx.

Isso explica por que `_render_diagram_png`, as 99 linhas de código morto
removidas na 0.2.4, nunca chegou a ser usada: do jeito que estava escrita, teria
produzido tabuleiros vazios.

---

## 0.3.0 — Arquitetura em pacote (fase 3 do [ROADMAP](ROADMAP.md))

O módulo único de 4.604 linhas virou um pacote de 22 módulos. `fen2rtf.py`
continua existindo como shim de 157 linhas que reexporta a API antiga, então
scripts, o executável congelado e `test_smoke.py` / `test_batch.py` seguem
funcionando sem alteração.

```
diagpdf/
  errors  log  model  resources  chars  layouts  paths     (base, sem dependências)
  i18n  fonts  fen  parsers  geometry  capabilities  config
  render/  common  pdf  html  epub  docx  rtf
  output  cli  gui
fen2rtf.py    shim de compatibilidade
```

### Saída preservada

A divisão foi verificada gerando os cinco formatos antes e depois, com o conjunto
completo de opções:

| Formato | Resultado |
|---|---|
| PDF, HTML, RTF | byte a byte idênticos |
| EPUB | todas as entradas do zip idênticas (o `uuid` e o `dcterms:modified` mudam por geração, como devem) |
| DOCX | todas as entradas idênticas exceto os `.odttf` — o payload da fonte é embaralhado com um GUID aleatório a cada geração; gerar duas vezes com o **mesmo** código produz a mesma divergência de 32 bytes, ou seja, é não-determinismo do formato, não da refatoração |

### Adicionado

- **Cache de descoberta de fontes** em `~/.diagpdf/fontcache.json`, chaveado por
  nome + tamanho + mtime de tudo em `Fonts/`. Import caiu de ~130-165 ms para
  ~85 ms; trocar, adicionar ou remover uma fonte invalida o cache sozinho
- **`-v/--verbose` e `-q/--quiet`**. O ruído do fontTools
  (`'modified' timestamp seems very low`) aparecia em toda execução e agora é
  silenciado por padrão — inclusive quando o DiagPDF é usado como biblioteca
- **`pyproject.toml`** com metadados, dependências, entry point `diagpdf`, e a
  configuração de ruff e pytest
- **Uso como biblioteca**: `from diagpdf import parse_pgn, generate_output`
- `tests/test_package.py` — 85 testes de layout do pacote: cada módulo importa
  sozinho, o shim ainda exporta os 48 nomes antigos, o cache faz ida e volta e
  se invalida, e importar o pacote **não** carrega o tkinter

### Interno

- `ruff` limpo com `E,F,W,I,UP,B,SIM`; as poucas regras desligadas estão
  justificadas no `pyproject.toml`
- Local morto `answers_title` em `generate_pdf`, sobra da fase 1, removido
- `fen2pdf.spec` atualizado: os renderizadores são alcançados pela tabela
  `GENERATORS`, que a análise estática do PyInstaller não enxerga — passaram a
  `hiddenimports`

### Adiado

`RenderOptions` como dataclass validado (item D2 do SPEC) ficou de fora. O
`opts: dict` é hoje a fronteira entre CLI, GUI e os cinco renderizadores;
trocá-lo mexe nos cinco ao mesmo tempo e merece fase própria, não um adendo à
refatoração estrutural.

---

## 0.2.6 — Paridade entre formatos (fase 2 do [ROADMAP](ROADMAP.md))

Sete opções valiam só para parte dos formatos e eram descartadas em silêncio
nos demais. Agora a matriz de capacidades é **declarada em código e verificada
por teste** — e o que um formato não consegue fazer é avisado, não ignorado.

### Antes e depois

| Opção | PDF | HTML | EPUB | DOCX | RTF |
|---|:--:|:--:|:--:|:--:|:--:|
| `--lines` | ✅ | ❌→✅ | ❌→✅ | ❌→✅ | ❌→✅ |
| `--header` / `--footer` | ✅ | ❌→impressão | ❌→avisa | ❌→✅ | ❌→✅ |
| colunas (`--layout`) | ✅ | ❌→✅ | ❌→✅ | ❌→✅ | ✅ |
| capítulos | ✅ | ❌→✅ | ❌→✅ | ❌→✅ | ❌→✅ |
| `--answers-cols` | ✅ | ❌→✅ | ❌→✅ | ❌→✅ | ✅ |
| fonte figurine | ✅ | ❌→✅ | ❌→✅ | ❌→✅ | ❌→✅ |
| `--font-size` | ✅ | ❌→✅ | ❌→✅ | ✅ | ✅ |

Restam duas lacunas, e as duas são propriedade do formato, não omissão:

- **EPUB é refluível** — quem pagina é o leitor, então o documento não tem
  páginas próprias para receber um cabeçalho corrente.
- **Navegador não numera página a partir do markup** — o contador vive nas
  caixas de margem do CSS *paged media*, que os navegadores não implementam. O
  cabeçalho/rodapé é emitido e se repete em toda folha impressa, mas `{page}` e
  `{total}` são removidos.

### Adicionado

- `FORMAT_CAPABILITIES` e `warn_unsupported_options()`: toda opção que o formato
  de destino não honra vira aviso explícito no stderr
  ```
  Warning: EPUB does not support page header/footer (--header/--footer) - the option will be ignored
  ```
- **HTML/EPUB**: grade CSS com as colunas do layout, linhas de notação (com o
  branco das brancas omitido quando são as pretas a jogar), fonte figurine
  embutida e aplicada às peças, `--font-size` ligado a `--board-row-size`,
  respostas em colunas via `column-count`, capítulos como `<section>` com
  título — e uma entrada de navegação por capítulo no EPUB, em vez de uma
  única linha "Diagrams"
- **DOCX**: cabeçalho e rodapé como partes `word/header*.xml` e `word/footer*.xml`
  reais, com campos `PAGE`/`NUMPAGES` vivos; diagramas em tabela quando o layout
  tem mais de uma coluna; linhas de notação com tabulação de preenchimento
  sublinhado; fonte figurine embutida e aplicada; respostas em seção de duas
  colunas; capítulos com quebra de página e título
- **RTF**: grupos `\header` e `\footer` nativos com campo de página; linhas de
  notação com tabulação de preenchimento; fonte figurine na tabela de fontes e
  aplicada às peças; capítulos com quebra de página e título
- `tests/test_parity.py` — 83 testes que exercitam cada capacidade declarada
  contra o documento gerado, e exigem aviso para cada uma não declarada

### Corrigido

| # | Correção |
|---|---|
| Q1 | **RTF declarava a fonte do tabuleiro como `\fcharset0`** (ANSI) enquanto o DOCX já usava corretamente o charset 2. Fontes de xadrez são simbólicas; a declaração errada levava o Word a mapear os glifos pela tabela ANSI |
| Q2 | **RTF era gravado com `errors='ignore'`**, descartando em silêncio qualquer caractere não-ASCII que escapasse do escape. Como `_rtf_escape` já converte tudo para `\uN`, o que sobrasse seria defeito — agora falha em vez de sumir |

### Nota

A análise inicial registrou `--answers-cols` como não suportado em RTF. Estava
errado: o RTF já dispunha as respostas em tabela de N colunas desde antes. A
matriz foi corrigida.

---

## 0.2.5 — Rede de testes (fase 1 do [ROADMAP](ROADMAP.md))

Suíte pytest com **690 testes** cobrindo os cinco formatos. Escrever os testes
revelou mais seis defeitos, corrigidos abaixo.

```bash
pip install -r requirements-dev.txt
pytest
```

### Corrigido

| # | Correção |
|---|---|
| P1 | **PGN com várias tags na mesma linha era descartado.** O formato de importação permite `[Event "E"] [Site "S"]` numa linha só (PGN §3.2); o novo cortador da 0.2.4 exigia uma tag por linha e tratava a linha inteira como lances — regressão introduzida na fase 0 |
| P2 | **`_clean_moves` nunca removia o marcador `*`.** O padrão era `\b(...\|\*)`: `*` não é caractere de palavra, então `\b` jamais casava antes dele e um `*` de partida inacabada sobrava no texto da resposta |
| P3 | **RTF não validava o nome da fonte.** Continuava aceitando fonte inexistente e declarando-a na tabela de fontes — a mesma corrupção silenciosa da C8, que só tinha sido fechada nos outros formatos |
| P4 | **Progresso em HTML/EPUB parava em 66%** quando alguma posição não tinha FEN: contava as posições lidas em vez das renderizadas. Na GUI parecia travamento |
| P5 | **Título vazio da seção de respostas ficava em branco** em HTML/EPUB, enquanto o PDF caía para "Solutions". Agora os cinco formatos usam o mesmo `_answers_heading` |
| P6 | **O título das respostas ignorava `--lang`**: o padrão do argparse era o literal inglês `Solutions`, que vencia o idioma escolhido. Agora sai `Soluções` / `Решения` / `Soluciones` conforme `--lang` |

### Adicionado

- `tests/` com 690 testes: `test_fen` (53), `test_parsers` (38), `test_moves` (57),
  `test_geometry` (271), `test_fonts` (122), `test_outputs` (100), `test_cli` (26),
  `test_regression` (22, movido da raiz)
- `tests/inspectors.py` — lê os documentos gerados de volta como fatos
  estruturais (páginas e links do PDF, âncoras e variáveis CSS do HTML,
  conformidade EPUB 3, marcadores do DOCX, chaves e campos do RTF). Os testes
  afirmam sobre estrutura, não sobre bytes: uma referência byte-a-byte quebraria
  a cada mudança inofensiva de ordenação ou de subconjunto de fonte
- Validação por `epubcheck` quando disponível (`EPUBCHECK_JAR`); sem ele, o teste
  é pulado e as mesmas regras continuam verificadas internamente
- `pytest.ini`, `requirements-dev.txt`

### Interno

- Invariante do tabuleiro testada por ida e volta: FEN → diagrama → tabuleiro tem
  de reproduzir a posição original, nas duas famílias de fonte e nos três estilos
  de borda
- Geometria verificada nas 7 × 6 combinações de layout e linhas: o conteúdo de
  uma página cheia sempre cabe entre as margens

---

## 0.2.4 — Correções críticas (fase 0 do [ROADMAP](ROADMAP.md))

Treze defeitos que produziam arquivo errado, perdiam dados ou quebravam sem
motivo. Cada um tem teste de regressão em `test_regression.py` — todos falham na
0.2.3.

### ⚠️ Mudanças de comportamento

Quatro correções alteram a saída **de propósito**. Se um arquivo seu ficou
diferente, provavelmente é uma destas:

- **Mais posições em arquivos PGN.** Partidas cuja primeira tag não era `[Event]`
  eram fundidas com a partida anterior, e a posição anterior desaparecia. Um PGN
  que rendia N diagramas pode render mais agora — a contagem de páginas muda.
- **`--font-size` passa a funcionar.** A opção era descartada pela CLI.
  Quem já a usava vai ver o tamanho mudar de fato.
- **Fonte desconhecida vira erro.** Antes servia um TTF qualquer com o mapa de
  caracteres errado, gerando diagramas ilegíveis sem avisar.
- **Quebras de linha da notação são normalizadas.** O PGN quebra o texto de
  lances na coluna 80; essa quebra é artefato do formato e cada exportador a
  tratava de um jeito. Agora vira espaço em todos.

### Corrigido

| # | Correção |
|---|---|
| C1 | **HTML: a fonte do tabuleiro nunca carregava.** O CSS pedia `../Fonts/x.ttf` relativo ao arquivo de saída, então só funcionava se o HTML ficasse exatamente um nível abaixo da pasta do programa. Agora a fonte é embutida como data URI base64 (`--html-font-mode {embed,link,none}`) |
| C2 | **CSS usava `var(--card-bg)` e `var(--card-border)` sem nunca defini-las** — moldura e fundo do diagrama não renderizavam. Definidas, com variantes para tema escuro e impressão |
| C3 | **`--font-size` era ignorado pela CLI** (`opts['font_size']` estava fixo em 0). Adicionado também `--text-size` |
| C4 | **Numeração das respostas ignorava o deslocamento no PDF**: `--from 2 --keep-numbers` gerava diagramas 2 e 3 com respostas 1 e 2. Os cinco renderizadores usam agora o mesmo `_position_number` |
| C5 | **Número de vários dígitos era cortado no título**: `"12 Mate"` com número 1 virava link só no "1". O padrão agora exige separador depois do número |
| C6 | **EPUB não conformava com EPUB 3**: sem `dcterms:modified`, sem documento de navegação e com o identificador fixo `urn:uuid:12345` em todo arquivo gerado. Adicionados também `--title`, `--author` e `--language` |
| C7 | **Sem validação de FEN**: `parse_fen('')` lançava `IndexError` e FEN inválido virava tabuleiro mudo. Novo `validate_fen` e `--on-invalid {skip,fail}` |
| C8 | **Fonte inexistente resolvia para um arquivo arbitrário** mantendo o mapa de caracteres da fonte pedida — diagrama de lixo, sem aviso. Agora erro com a lista de fontes disponíveis (`--list-fonts`) |
| C9 | **Rótulo "Analisar no Lichess" fixo em português** nos quatro renderizadores. Traduzido para EN/RU/PT/ES e configurável por `--lichess-label` |
| C10 | **PGN: partida sem `[Event]` fazia a posição anterior desaparecer.** O corte de partidas agora é feito por máquina de estados, não por `^\[Event` |
| C11 | **PGN: `[Event` na coluna 1 dentro de `{comentário}` truncava os lances** — a solução era destruída |
| C12 | **Respostas longas eram desenhadas fora da página** (322 mm numa folha de 297 mm) e o texto se perdia. A quebra de coluna/página agora é medida antes de escrever; linhas de continuação ganharam recuo pendente |
| C13 | **Título ficava azul com `link=0`** em posições sem resposta — parecia clicável e não era |
| C14 | **`--border none` ignorava "Mostrar coordenadas"** em silêncio. Agora avisa (os glifos de coordenada Merida carregam borda e não podem ser usados sem moldura) |
| C15 | **DOCX lançava exceção depois de gravar o arquivo** com `Chess Adventurer` e `Chess Cases`, cujas licenças proíbem embutir. Agora avisa e conclui com sucesso |
| C16 | **Licença de fonte (`fsType`) era verificada só no DOCX**; PDF e EPUB embutiam as mesmas fontes restritas sem checar. Política unificada, com `--allow-restricted-fonts` |
| R3 | `_clean_moves` não removia comentários `;` até fim de linha nem linhas de escape `%` (PGN §6 e §8.2.5) |
| R5 | **Arquivos em cp1252/latin-1 eram lidos como UTF-8** com `errors='replace'`: `Peão` virava `Pe<?>o`. Detecção automática, com `--encoding` para forçar |
| — | GUI: abertura do arquivo gerado via `os.startfile`/`open`/`xdg-open` em vez de `subprocess.Popen(..., shell=True)`, que quebrava com `&` ou `^` no caminho |
| — | GUI: nome de fonte obsoleto na configuração salva não deixa mais o campo em branco |
| — | GUI: título das caixas de erro passa a ser traduzido |

### Adicionado

- `--list-fonts`, `--text-size`, `--lang`, `--lichess-label`, `--html-font-mode`,
  `--title`, `--author`, `--language`, `--allow-restricted-fonts`,
  `--on-invalid`, `--encoding`
- `--no-renumber` aceito como sinônimo de `--keep-numbers` (o README documentava
  o primeiro; só o segundo existia)
- `test_regression.py` — 22 testes cobrindo todos os defeitos acima
- [ROADMAP.md](ROADMAP.md) e [SPEC.md](SPEC.md)

### Interno

- Removidas 99 linhas de código morto (`_render_diagram_png`, nunca chamada),
  `import base64` sem uso e um `pass` órfão
- Despacho de formato unificado em `generate_output` (estava duplicado entre
  CLI e GUI)
- `test_batch.py` pedia `AlphaDG` em 20 dos 25 casos — uma fonte que não existe
  em `Fonts/`. A matriz agora vem das fontes realmente instaladas

### Nota sobre fontes

`Fonts/` **não contém** `AlphaDG.ttf`, `ZurichFigurine.TTF` nem
`LinaresFigurine.TTF`, apesar de o README anunciar as três. Estão disponíveis 16
fontes de tabuleiro e 1 figurine (Hastings). Rode `--list-fonts` para ver a
lista real. Até que os arquivos sejam restaurados ou as referências removidas, a
resolução estrita (C8) evita que a ausência corrompa a saída em silêncio.
