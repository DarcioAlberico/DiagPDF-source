# DiagPDF — Especificação técnica

Complemento do [ROADMAP.md](ROADMAP.md). Cada item traz: **local**, **como
reproduzir**, **causa**, **correção** e **critério de aceitação**.

Referências de linha são da versão analisada (`fen2rtf.py` @ v0.2.3, 3.517 linhas).

Os achados ficam como foram encontrados — é o registro da auditoria, e reescrevê-lo
apagaria o que ela apurou. Onde o texto faz uma afirmação **no presente** que o
tempo tornou falsa (inventário de fontes, estado de um arquivo), vem logo abaixo
uma nota `> **Situação em X.Y.Z:**`. O que foi corrigido em cada versão está no
[CHANGELOG.md](CHANGELOG.md); o que falta, no [ROADMAP.md](ROADMAP.md).

---

# Parte A — Defeitos críticos (Fase 0)

## C1 · HTML: a fonte do tabuleiro nunca carrega

**Local:** `generate_html` (L1732-1739), `_render_html_document` (L1604-1605)

```python
if font_url is None:
    font_url = f'../Fonts/{fname}'      # relativo AO ARQUIVO DE SAÍDA
```

**Reprodução**
```bash
python fen2rtf.py exemplo.pgn -o ~/Documentos/saida.html
```
O CSS embutido pede `../Fonts/ChessMerida.ttf`, resolvido a partir de
`~/Documentos/`. O arquivo não existe ali. O navegador cai para a fonte padrão e
o tabuleiro aparece como `À +k+ + +5` — texto Latin-1 cru.

Só funciona se o HTML for salvo exatamente um nível abaixo da pasta do app.

**Causa:** HTML autônomo herdou o caminho relativo do EPUB, onde ele é correto
(o CSS mora em `OEBPS/Styles/` e a fonte em `OEBPS/Fonts/`).

**Correção:** embutir a fonte como data URI base64 no `@font-face` do HTML
autônomo. O `import base64` já existe em L1473 — e está sem uso, o que indica
que essa era a intenção original.

```python
def _font_data_uri(font_path: Path) -> str:
    mime = 'font/otf' if font_path.suffix.lower() == '.otf' else 'font/ttf'
    return f'data:{mime};base64,{base64.b64encode(font_path.read_bytes()).decode("ascii")}'
```

Opção `--html-font-mode {embed,link,none}` (padrão `embed`). O EPUB continua
usando caminho relativo, que é o correto lá.

**Aceitação:** HTML gerado em pasta arbitrária renderiza o tabuleiro
corretamente sem nenhum arquivo externo. Teste verifica que a saída contém
`data:font/ttf;base64,` e nenhum `url("../`.

---

## C2 · CSS: variáveis usadas mas nunca definidas

**Local:** `_build_diagram_css` (L1488-1515)

```css
:root {
  --board-row-size: 36px;
  --side-indicator-scale: 0.8;
  --side-indicator-gap: 0.12rem;
}
.diagram {
  border: 1px solid var(--card-border);   /* nunca definida */
  background: var(--card-bg);             /* nunca definida */
}
```

**Reprodução:** `grep -- '--card-bg\s*:' saida.html` → nada.

**Causa:** referência sobrevivente de outra folha de estilo.

**Efeito:** ambas as declarações são inválidas e descartadas. O diagrama fica sem
moldura e sem fundo, em HTML e EPUB.

**Correção:** definir no `:root` com suporte a tema claro/escuro:

```css
:root { --card-bg: #ffffff; --card-border: #cbd5e1; --text: #0f172a; --link: #0645ad; }
@media (prefers-color-scheme: dark) {
  :root { --card-bg: #1e1e1e; --card-border: #3f3f46; --text: #e5e5e5; --link: #6ea8fe; }
}
@media print { :root { --card-bg: #fff; --card-border: #000; --text: #000; } }
```

`.board { color: #000 }` (L1549) também vira `var(--text)` — hoje o tabuleiro
fica preto no preto em tema escuro.

**Aceitação:** moldura visível; teste confirma que toda `var(--x)` usada tem
definição correspondente.

---

## C3 · `--font-size` da CLI é descartado

**Local:** `main()` L3475

```python
opts = {
    'font_size':   0,        # ← ignora args.font_size (definido em L3405)
```

**Reprodução**
```bash
python fen2rtf.py t.pgn -o a.pdf
python fen2rtf.py t.pgn -o b.pdf --font-size 30
# a.pdf e b.pdf são byte-a-byte idênticos (37.785 bytes cada) — confirmado
```

**Correção:** `'font_size': max(0, args.font_size)`.

Auditar os demais: `text_size` está fixo em `0` e não tem flag na CLI — adicionar
`--text-size`.

**Aceitação:** teste gera com `--font-size 12` e `--font-size 30` e afirma que os
arquivos diferem e que o tamanho pedido é respeitado (dentro do limite de
encaixe calculado por `_compute_geometry`).

---

## C4 · Numeração das respostas ignora `number_offset` (só no PDF)

**Local:** `generate_pdf`, seção de respostas L1431

```python
_num_label = f'{_ai + 1}. '          # errado
# título do diagrama, L1242:
num = pos_idx + 1 + number_offset    # certo
```

**Reprodução** (`--from 2 --keep-numbers --answers`, verificado por instrumentação
das chamadas a `pdf.cell`):

```
título:   '2 ' 'Second puzzle'   '3 ' 'Third puzzle'
resposta: '1. '                  '2. '                 ← divergente
```

HTML, DOCX e RTF fazem certo (`pos_idx + 1 + number_offset`). Só o PDF erra.
Os links continuam corretos (são por índice); o número **exibido** é que mente.

**Correção:** usar `_ai + 1 + number_offset` no rótulo. Extrair o cálculo para
um helper `_position_number(idx, opts)` usado pelos 5 renderizadores, para o
erro não voltar.

**Aceitação:** teste parametrizado nos 5 formatos afirma que o número do título
e o número da resposta correspondente são iguais, com e sem `number_offset`.

---

## C5 · `_split_title_number_prefix` corta números de vários dígitos

**Local:** L955-964

```python
m = re.match(rf'^({re.escape(str(num))}(?:[.)])?\s*)(.*)$', title)
```

O padrão não exige fronteira após o número.

**Reprodução** (saída real):

| título | num | resultado | esperado |
|---|---|---|---|
| `'1 Some text'` | 1 | `('1 ', 'Some text')` | ✅ |
| `'12 Some text'` | 1 | `('1', '2 Some text')` | ❌ |
| `'1st example'` | 1 | `('1', 'st example')` | ❌ |
| `'100 x'` | 10 | `('10', '0 x')` | ❌ |

**Efeito:** o hyperlink cobre só parte do número e o resto do título aparece
como texto solto, em PDF, HTML, DOCX e RTF.

**Correção:** exigir fim de string ou separador não-dígito depois do número:

```python
m = re.match(rf'^({re.escape(str(num))}(?:[.)])?)(\s+|$)(.*)$', title)
```

**Aceitação:** os quatro casos da tabela passam a devolver o esperado
(`('', título)` quando não há prefixo legítimo).

---

## C6 · EPUB 3 inválido

**Local:** `generate_epub` L2697-2729

Verificado no arquivo gerado:

| Requisito EPUB 3 | Presente |
|---|:--:|
| `<meta property="dcterms:modified">` | ❌ — **erro** no epubcheck |
| Documento de navegação (`properties="nav"`) | ❌ — **erro** no epubcheck |
| `dc:identifier` único por publicação | ❌ — `urn:uuid:12345` fixo em todo arquivo |
| `dc:title` / `dc:language` reais | ❌ — sempre `Chess Diagrams` / `en` |
| `dc:creator` | ❌ ausente |
| `toc.ncx` | ✅ (legado EPUB 2, aceitável como complemento) |

**Correção**
- `dc:identifier` = `urn:uuid:` + `uuid.uuid4()` por geração.
- `<meta property="dcterms:modified">` com UTC ISO-8601 (`%Y-%m-%dT%H:%M:%SZ`).
- `nav.xhtml` com `epub:type="toc"`, listado no manifesto com `properties="nav"`.
- Metadados a partir de opções novas: `--title`, `--author`, `--language`
  (padrão: nome do arquivo de entrada, vazio, idioma da UI).
- Ordem de elementos do manifesto/espinha conforme o esquema.

**Aceitação:** `epubcheck` sem erros. Sem `epubcheck` disponível, o teste valida
o XML e a presença de todos os itens da tabela.

---

## C7 · Validação de FEN ausente

**Local:** `parse_fen` L527-543

```python
parts = fen_str.strip().split()
board_str = parts[0]          # IndexError quando fen_str é vazio
```

**Reprodução**
```python
parse_fen('')          # IndexError: list index out of range
parse_fen('invalid')   # devolve tabuleiro com 'n' em a8 e nada mais, sem aviso
parse_fen('8/8/8 w')   # 3 fileiras, resto vazio, sem aviso
```

Os chamadores filtram FEN vazio (`[p for p in positions if p.get('fen','').strip()]`),
então o `IndexError` não aparece no fluxo normal — mas `parse_fen` é API pública
(importada por `test_smoke.py`) e a entrada malformada passa em silêncio.

**Correção:** `validate_fen(fen) -> list[str]` (lista de problemas), chamada
pelos parsers. Verifica: campo de posição presente; 8 fileiras; cada fileira
somando 8 colunas; caracteres em `[pnbrqkPNBRQK1-8/]`; lado a mover em `{w,b}`;
exatamente um rei de cada cor. `parse_fen` lança `ValueError` com mensagem clara
em entrada vazia/irrecuperável.

Comportamento configurável, porque **pular altera a numeração** de todos os
diagramas seguintes:

```
--on-invalid skip         (padrão) avisa, pula, e informa no resumo final
--on-invalid fail         aborta na primeira posição inválida
--on-invalid placeholder  gera um quadro "posição inválida" preservando a numeração
```

`skip` é o padrão por manter o comportamento atual para FEN vazio (já filtrado
em `[p for p in positions if p.get('fen','').strip()]`), mas agora com aviso.

**Aceitação:** cada caso da tabela produz erro ou aviso identificável; nenhum
FEN inválido gera diagrama silenciosamente; os três modos são testados.

---

## C8 · Fonte inexistente resolve para arquivo arbitrário

**Local:** `get_chess_font_path` L784-789

```python
fname = FONT_FILES.get(font_name, _default_board_font_file())
#                                  ↑ primeiro arquivo do dicionário
```

**Reprodução**
```python
>>> 'AlphaDG' in FONT_FILES
False
>>> get_chess_font_path('AlphaDG', Path('Fonts'))
'.../Fonts/ChessMerida.ttf'
>>> 'AlphaDG' in MERIDA_COMPATIBLE_FONTS
False        # → fen_to_diagram usa o mapa ALPHA_DG…
```

Serve o arquivo ChessMerida mas desenha com o mapa de caracteres do AlphaDG.
Resultado: diagrama de lixo, sem nenhum aviso.

**Contexto agravante:** `Fonts/` **não contém** `AlphaDG.ttf`,
`ZurichFigurine.TTF` nem `LinaresFigurine.TTF`, apesar de:
- README documentar AlphaDG como fonte principal e Zurich como figurine padrão;
- `_FALLBACK_FONT_FILES` / `_FALLBACK_FIGURINE_FILES` (L168-179) listarem as três;
- `test_batch.py` usar `font='AlphaDG'` em 20 dos 25 casos de teste.

Presentes hoje: 16 fontes de tabuleiro (13 tipo Merida, 3 legado DG) e 1 figurine
(Hastings).

> **Situação em 0.15.0:** 17 fontes de tabuleiro (13 tipo Merida, 4 de layout
> Alpha — `LeipzigDG`, `CondalDG`, `KingdomDG` e a `chess-alpha` acrescentada em
> 0.13.0) e 3 figurines (`Zurich`, `Hastings`, `Linares`).
>
> `ZurichFigurine.TTF` e `LinaresFigurine.TTF` foram recuperadas das cópias
> embutidas em `fonts_6a7de6c2db0e9/chesswin.pdf` — subconjuntos, com apenas os
> glifos que aquele PDF usava, o que cobre os cinco (`K Q R B N`) que o programa
> pede de uma figurine. A fidelidade da extração foi medida contra a
> `HastingsFigurine` original, que a mesma pasta também traz: 33 das 36
> assinaturas de contorno idênticas.
>
> A `AlphaDG.ttf` **continua ausente de `Fonts/`**, e não está naquela pasta:
> comparados todos os contornos das 76 fontes de lá contra `chess-alpha`,
> `LeipzigDG`, `CondalDG`, `KingdomDG` e `ChessMerida`, o número de glifos em
> comum é zero. A `chess-alpha.ttf` não a substitui — faltam o `z` (topo da
> borda) e os seis glifos de indicador (`F G I M f i`).
>
> Estava, porém, embutida nos PDFs de exemplo de 2011: 52 dos 55 caracteres
> exigidos, extraídos para `Fonts-recovered/` antes de aqueles arquivos serem
> regerados. Não foi instalada — uma fonte 52/55 anunciada em `FONT_NAMES`
> renderiza errado com `--no-coords` e `--symbol triangle` sem dizer nada, que é
> exatamente o defeito descrito aqui.

**Correção**
1. `resolve_board_font(name)` lança `UnknownFontError` com a lista de fontes
   disponíveis, em vez de cair para um arquivo qualquer.
2. Fallback só entre fontes do **mesmo mapa de caracteres**.
3. `--list-fonts` para descoberta.
4. Decisão a tomar: restaurar os TTFs ausentes **ou** limpar README,
   `_FALLBACK_*` e `test_batch.py`. Até lá, resolução estrita evita a corrupção.

> **Situação em 0.15.0:** itens 1-3 feitos na 0.2.4 (e estendidos ao RTF na
> 0.2.5, que ainda aceitava fonte inexistente na tabela de fontes — item P3).
> O item 4 acabou resolvido pelos dois lados: `test_batch.py` e o README foram
> corrigidos, e dois dos três TTFs restaurados. `_FALLBACK_FIGURINE_FILES` casa
> agora com o que existe; `_FALLBACK_FONT_FILES` ainda cita `AlphaDG.ttf`, que
> segue por comprar.

**Aceitação:** nome desconhecido produz erro acionável; teste confirma que toda
fonte anunciada em `FONT_NAMES` renderiza com o mapa correto.

---

## C9 · Rótulo do Lichess fixo em português

**Local:** L1350 (PDF), L1700 (HTML), L2316 (DOCX), L2533 (RTF)

```python
text="Analisar no Lichess"
```

Aparece em português mesmo com a interface em EN/RU/ES.

**Correção:** chave `lichess_label` no catálogo i18n (4 idiomas) e opção
`--lichess-label TEXT` para sobrepor. Valor obtido de um único helper
compartilhado pelos 4 renderizadores.

**Aceitação:** rótulo acompanha o idioma; `--lichess-label` sobrepõe em todos os
formatos.

---

## C10 · PGN: partida sem `[Event]` faz a posição anterior desaparecer

**Local:** `parse_pgn` L697-707

```python
game_re = re.compile(r'(?=^\[Event\b)', re.IGNORECASE | re.MULTILINE)
...
tags = dict(tag_re.findall(block))     # dict → mantém a ÚLTIMA ocorrência
fen = tags.get('FEN')
```

**Reprodução**
```
[Event "G1"]
[FEN "POSITION-ONE w - - 0 1"]
1.Ke2 *

[White "Nobody"]                    ← primeira tag não é [Event]
[FEN "POSITION-TWO w - - 0 1"]
1.Kf2 *
```
```
posições lidas: 1   (esperado 2)
fen sobrevivente: POSITION-TWO      ← a posição da partida 1 SUMIU
```

**Causa:** sem `[Event]`, a segunda partida não gera ponto de corte; os dois
blocos viram um só. `dict(tag_re.findall(block))` então sobrescreve `FEN`,
`White`, `Event`… com os valores da **última** partida do bloco.

**Gravidade:** perda de dados silenciosa. `[Event]` é a primeira tag do
*Seven Tag Roster*, mas PGN exportado por vários programas (e arquivos
editados à mão) frequentemente não o traz.

**Correção:** cortar por blocos tag/movimento com máquina de estados — uma
partida começa quando uma linha de tag aparece **depois** de texto de lances —
em vez de casar `^\[Event`.

**Aceitação:** o exemplo devolve 2 posições, `POSITION-ONE` e `POSITION-TWO`.

---

## C11 · PGN: `[Event` na coluna 0 dentro de comentário destrói os lances

**Local:** mesma expressão de corte (L697)

**Reprodução**
```
[Event "Real"]
[FEN "4k3/8/8/8/8/8/8/4K3 w - - 0 1"]
{see
[Event "fake"] in comment}
1.Ke2 Kd7 *
```
```
event  : 'Real'          ✅
moves  : '{see'          ❌  esperado '1.Ke2 Kd7'
comment: ''              ❌
```

O corte acontece dentro do comentário; tudo depois dele — inclusive a solução —
vai para um bloco sem tag `[FEN]`, que é descartado.

**Correção:** mesma da C10 (corte ciente de `{}` e `;`).

**Aceitação:** `moves == '1.Ke2 Kd7'`.

---

## C12 · Seção de respostas transborda a página

**Local:** `generate_pdf` L1160 (`set_auto_page_break(auto=False)`) e L1413

```python
if pdf.get_y() > PH - MT - _ans_lh * 2:   # verifica só ENTRE respostas
```

Depois disso, `pdf.write()` escreve a resposta inteira sem poder quebrar página
(quebra automática desligada no documento todo, necessário para a grade de
diagramas).

**Reprodução:** uma resposta de ~200 lances, seção de respostas ativa.
```
página 2: y máximo alcançado = 322,3 mm    (A4 tem 297 mm; margem inferior em 282)
```
O texto é desenhado **fora da página** e some do arquivo final.

**Gravidade:** alta para livros de táticas com variantes longas — caso comum.

**Correção:** medir a altura da resposta antes de escrever
(`pdf.multi_cell(..., dry_run=True, output='LINES')`) e quebrar coluna/página
por conta própria; ou reativar a quebra automática só durante a seção de
respostas, restaurando o estado depois.

**Aceitação:** nenhum conteúdo desenhado além de `PH - MT`; teste com resposta
de 200 lances gera páginas suficientes e não perde texto.

---

## C13 · Número azul não clicável quando a posição não tem resposta

**Local:** `generate_pdf` L1288-1310

```python
_title_link = ans_links[pos_idx] if ans_links else link_url
if ans_links and title:          # verdadeiro para TODAS as posições
    ...
    pdf.set_text_color(0, 0, 255)   # azul
    pdf.cell(..., link=_title_link) # link=0 quando não há resposta
```

`ans_links[i]` vale `0` quando a posição não tem lances. `ans_links` (a lista)
continua não-vazia, então o ramo "com link" é usado mesmo assim.

**Reprodução** (instrumentação de `pdf.cell`, 2 posições, só a primeira com solução):
```
text='1 '  link=2  color=azul     ✅ clicável
text='2 '  link=0  color=azul     ❌ azul, mas link=0 → não clica
```

**Correção:** condicionar ao link daquela posição: `if ans_links and ans_links[pos_idx] and title`.

**Aceitação:** apenas títulos com resposta correspondente saem em azul.

---

## C14 · `border_style='none'` ignora a opção "Mostrar coordenadas"

**Local:** `fen_to_diagram` L580-587

```python
if border_style == 'none':
    for ri in rank_order:        # nenhuma referência a `coords`
```

**Reprodução**
```python
a = fen_to_diagram(fen, coords=True,  border_style='none', font_name='ChessMerida')
b = fen_to_diagram(fen, coords=False, border_style='none', font_name='ChessMerida')
a == b   # True — a caixa de seleção não faz nada
```

**Correção:** ou desenhar coordenadas sem moldura (glifos de coordenada
existem nos dois conjuntos Merida), ou desabilitar a caixa na GUI e emitir aviso
na CLI quando `--border none` for combinado com coordenadas. Preferência: a
primeira, com fallback para a segunda se a fonte não tiver os glifos soltos.

**Aceitação:** a opção passa a ter efeito observável, ou o usuário é avisado.

---

## C15 · DOCX quebra com fonte de `fsType` restrito — depois de gravar o arquivo

**Local:** `generate_docx` L2348-2351 / `_docx_prepare_font_payload` L1926-1928

```python
doc.save(str(out_path))                       # arquivo já está no disco
if docx_font_path.exists():
    _docx_embed_font(...)                     # ← levanta RuntimeError aqui
```

**Reprodução**
```bash
python fen2rtf.py t.pgn -o saida.docx -f "Chess Cases"
```
```
RuntimeError: Font embedding is not permitted for Chess Cases.ttf.
$ ls saida.docx      → existe (37 KB), sem a fonte embutida
```

Duas das 16 fontes distribuídas têm `fsType` restrito:

| Fonte | Pode embutir |
|---|:--:|
| Chess Adventurer | ❌ |
| Chess Cases | ❌ |
| outras 14 + Hastings | ✅ |

> **Situação em 0.15.0:** continuam sendo essas duas, agora entre 20 fontes
> distribuídas (17 de tabuleiro + 3 figurines). `Zurich` e `Linares` têm
> `fsType` 8 (*editable embedding*): embutem e permitem subconjunto.

Na CLI o usuário vê um *traceback* cru; na GUI, uma `messagebox` com a exceção —
em ambos os casos parecendo falha total, embora o arquivo exista e seja usável
(o Word substitui a fonte).

**Correção:** capturar a falha de embutimento, gravar aviso
(`fonte X não permite embutimento — o documento dependerá da fonte instalada`)
e concluir com sucesso. Erro só se o próprio `doc.save` falhar.

**Aceitação:** as duas fontes restritas geram DOCX com código de saída 0 e um
aviso; nenhuma exceção escapa.

---

## C16 · Política de `fsType` aplicada só no DOCX

**Local:** `_docx_font_embed_policy` L1908-1921 (único ponto de verificação)

O PDF (via fpdf2) e o EPUB (cópia bruta do TTF para `OEBPS/Fonts/`) embutem as
mesmas fontes restritas sem qualquer verificação — confirmado:

```
python fen2rtf.py t.pgn -o saida.epub -f "Chess Cases"
→ OEBPS/Fonts/Chess Cases.ttf  (fsType restrito, embutida assim mesmo)
```

**Correção:** centralizar a política em `font_embedding_policy(path)` e aplicá-la
nos três formatos que embutem. Opção `--allow-restricted-fonts` para o usuário
assumir a decisão conscientemente; por padrão, avisar.

**Nota:** decisão de produto, não só técnica — documentos redistribuídos com
fontes de licença restrita são responsabilidade de quem publica.

**Aceitação:** os três formatos aplicam a mesma regra e produzem o mesmo aviso.

---

# Parte A-bis — Riscos de regressão da Fase 0

Quatro das correções **mudam a saída de propósito**. Precisam de CHANGELOG e de
uma nota de versão, senão parecem regressão:

| Correção | Mudança visível | Mitigação |
|---|---|---|
| C10 / C11 | Arquivos PGN que hoje rendem N diagramas passam a render **mais** — a contagem de páginas muda | Anunciar como correção de perda de dados; `--legacy-pgn-split` por uma versão para quem depender do comportamento antigo |
| C5 | A extensão do hyperlink no título muda em diagramas de número ≥ 10 | Só afeta o que já estava errado |
| C3 | `--font-size` passa a ter efeito para quem já usava a flag sem saber que era ignorada | CHANGELOG |
| C8 | Nome de fonte desconhecido vira **erro** em vez de saída silenciosamente errada | Mensagem lista as fontes disponíveis; `test_batch.py` precisa ser corrigido **no mesmo commit**, pois pede `AlphaDG` em 20 de 25 casos |

**Ordem obrigatória dentro da Fase 0:** C8 e a correção do `test_batch.py`
entram juntos; caso contrário a própria suíte do repositório passa a falhar.

**Viabilidade verificada** na fpdf2 2.8.7 instalada:
`multi_cell(dry_run=True, output=LINES)` ✓ (correção da C12),
`start_section` ✓ (O2), `set_title`/`set_author` ✓ (O1), `text_columns` ✓ (paridade).

---

# Parte B — Testes (Fase 1)

## T1 · Suíte pytest

```
tests/
  test_fen.py         parse_fen, validate_fen, fen_to_diagram (cor das casas, flip, coords)
  test_parsers.py     PGN/FEN/EPD, incluindo malformados
  test_moves.py       _clean_moves, _apply_title_template, _split_title_number_prefix
  test_geometry.py    _compute_geometry: encaixe, limites, todos os 7 layouts
  test_outputs.py     golden tests dos 5 formatos
  conftest.py         fixtures de PGN
```

**Invariantes verificadas em vez de comparação de bytes**
- PDF: nº de páginas, nº de links, texto extraído contém títulos e números.
- HTML/EPUB: XML bem-formado; toda `href="#id"` tem alvo; toda `var(--x)` tem definição.
- EPUB: validação da Parte A/C6.
- DOCX: pacote OOXML válido; bookmarks casam com hyperlinks.
- RTF: chaves balanceadas; grupos `\field` bem formados.

**Caso de regressão obrigatório:** os 8 defeitos da Parte A ganham teste que
falha na versão atual e passa depois da correção.

## T2 · `test_batch.py` corrigido

Hoje pede `AlphaDG` (ausente) em 20 casos e passa fontes figurine inexistentes
(`Zurich`, `Linares`), sem detectar nada porque só imprime `OK`/`ERR`.
Reescrever sobre `FONT_NAMES` reais e transformar em teste parametrizado.

> **Situação em 0.15.0:** feito na fase 0 — `test_batch.py` roda sobre
> `FONT_NAMES`/`FIGURINE_NAMES` reais. As duas figurines que ele pedia sem
> existir passaram a existir na 0.15.0, mas por outro caminho: o arquivo já não
> depende disso.

---

# Parte C — Paridade entre formatos (Fase 2)

## P1 · Matriz de capacidades explícita

```python
FORMAT_CAPABILITIES: dict[str, frozenset[str]] = {
    'pdf':  frozenset({'lines', 'header_footer', 'columns', 'chapters',
                       'answers_cols', 'figurine', 'font_size', 'page_setup'}),
    'html': frozenset({'lines', 'columns', 'answers_cols', 'figurine', 'font_size'}),
    ...
}
```

`validate_options(opts, fmt)` devolve a lista de opções pedidas e não suportadas
→ aviso `Aviso: --lines não é suportado em RTF e será ignorado`.

## P2 · Implementações a fazer

| Opção | Onde falta | Como |
|---|---|---|
| `lines_count`/`lines_mode` | HTML, EPUB, DOCX, RTF | HTML/EPUB: `<div class="notation-line">` com `border-bottom`; DOCX: parágrafos com borda inferior; RTF: `\brdrb` |
| `header`/`footer` | DOCX, RTF | DOCX: `w:hdr`/`w:ftr` com campo `PAGE`/`NUMPAGES`; RTF: `\header`/`\footer` com `\chpgn` |
| `layout_idx` (colunas) | HTML, EPUB, DOCX | HTML/EPUB: `grid-template-columns: repeat(N, 1fr)`; DOCX: tabela sem bordas |
| capítulos | HTML, EPUB, DOCX, RTF | Quebra de seção + título; entradas de navegação no EPUB |
| `answers_cols` | HTML, EPUB, DOCX | `column-count` / tabela |
| fonte figurine | HTML, EPUB, DOCX, RTF | Mesmo particionamento por caractere do PDF (L1441-1458), extraído para helper comum |

**Aceitação:** a matriz é testada — para cada par (opção, formato) suportado
existe teste que confirma o efeito na saída; para os não suportados, teste que
confirma o aviso.

---

# Parte D — Arquitetura (Fase 3)

## D1 · Estrutura em pacote

Ver árvore no ROADMAP §3, Fase 3. `fen2rtf.py` permanece como shim que reexporta
a API pública (`generate_pdf`, `parse_pgn`, `FONT_NAMES`, …) para não quebrar
`test_smoke.py` nem scripts existentes.

## D2 · `RenderOptions`

Substitui `opts: dict` (hoje cada renderizador relê ~15 chaves com defaults
próprios — 5 cópias que já divergiram, ver C4).

```python
@dataclass(frozen=True)
class RenderOptions:
    layout_idx: int = DEFAULT_LAYOUT
    font: str = ''                      # '' = padrão resolvido em __post_init__
    font_size: int = 0                  # 0 = automático
    ...
    @classmethod
    def from_dict(cls, d: dict) -> RenderOptions: ...   # compatibilidade
    def __post_init__(self): ...                        # valida faixas e enums
```

## D3 · Descoberta de fontes cacheada

`_discover_fonts()` roda **no import** e abre 17 TTFs com fontTools:
**~350 ms** medidos, pagos até por `python fen2rtf.py --version`.

Cache em JSON (`~/.diagpdf/fontcache.json`) chaveado por caminho + mtime +
tamanho, com invalidação automática. Descoberta preguiçosa via `functools.cache`.

**Aceitação:** import a frio < 60 ms com cache quente; cache invalida quando um
TTF muda.

## D4 · Logging

`logging` com `-v/--verbose` e `-q/--quiet`. Silenciar o ruído do fontTools que
hoje vaza para o usuário em toda execução:
```
'modified' timestamp seems very low; regarding as unix timestamp
```

## D5 · Código morto e desarrumação

| Item | Local | Ação |
|---|---|---|
| `_render_diagram_png` — 99 linhas, zero chamadas | L1753-1851 | Reaproveitar na exportação PNG (Fase 6) ou remover |
| `import base64` sem uso | L1473 | Passa a ser usado por C1 |
| `import zipfile` no meio do arquivo | L2639 | Mover para o topo |
| `pass # Replaced and mapped early on` | L3317 | Remover |
| `FONTS_WITHOUT_EMBEDDED_INDICATOR = frozenset(MERIDA_COMPATIBLE_FONTS)` | L282 | Alias redundante — unificar |
| `title_mode`/`title_custom` inalcançáveis (GUI e CLI sempre mandam template) | L943-952 | Manter só em `from_dict` para compatibilidade |
| Ramo `if requested > 0 … else …` de `_compute_geometry` é **no-op**: os três caminhos calculam `min(chess_pt_base, chess_pt_fit)` (verificado nas 84 combinações de layout × tamanho × linhas). `MIN_FONT_PT` fica sem efeito | L898-908 | Reduzir a uma linha; decidir se `MIN_FONT_PT` deve mesmo ser um piso (hoje não é) |
| Comentário "Lichess goes on symbol" e README "embedded in the to-move symbol" — o link virou rótulo de texto sob o tabuleiro (L1344-1351) | L1286-1287 | Atualizar comentário e README |
| `PAGE_W`… definidos **depois** de `_compute_geometry`, que os usa | L867 vs L932 | Reordenar |
| `generate_html(font_url: str = None)` | L1732 | `str \| None` |
| `font_url` passado ao EPUB e nunca usado (o EPUB usa `stylesheet_hrefs`) | L2664 | Remover parâmetro morto |
| `build/`, `dist/`, `tmp_*`, `test_batch_out/`, `smoke_out/`, `review_smoke.*` no diretório | — | Limpar + revisar `.gitignore` |

## D6 · Empacotamento

`pyproject.toml` (metadados, deps, entry point `diagpdf`), ruff, GitHub Actions
rodando pytest em Windows/Linux e construindo o `.exe`.

---

# Parte E — GUI (Fase 4)

| # | Problema | Local | Correção |
|---|---|---|---|
| G1 | Geração na thread principal do Tk; `root.update()` reentrante no callback de progresso | L2984-3072, L3053-3055 | `threading.Thread` + fila; UI atualizada por `root.after`; barra de progresso; botão cancelar |
| G2 | `subprocess.Popen(['start','',str(p)], shell=True)` — só Windows e superfície de injeção com `&`/`^` no caminho | L2905-2909 | `os.startfile` (Win) / `open` (macOS) / `xdg-open` (Linux), sem shell |
| G3 | CSS do EPUB perguntado em modal a **cada** geração | L3044-3052 | Campo persistente com botão "…" |
| G4 | Config `~/.diagpdf.json` sem versão nem validação; nome de fonte obsoleto deixa o combobox `readonly` em branco | L2789-2801 | `{"version": 2, ...}`, validação na carga, migração |
| G5 | Tipo de arquivo deduzido do **nome localizado** do filtro ("Arquivos PDF") | `_ext_from_save_filter` L319-329 | Mapear filtro → extensão por índice, não por texto |
| G6 | Spinbox de intervalo com `IntVar`: texto não numérico lança `TclError` cru | L3007-3008 | `StringVar` + validação com mensagem traduzida |
| G7 | Sem preview | — | Painel com o primeiro diagrama, reagindo às opções |
| G8 | Só tema claro | L2756 | Alternador claro/escuro (sv_ttk já suporta) |
| G9 | `messagebox.showerror('Error', …)` com título não traduzido | L2990, L3002… | Usar catálogo |
| G10 | Créditos fixos em português ("Criado por", "modificado por") | L3088-3091 | Catálogo i18n |
| G11 | Sem arrastar-e-soltar, sem recentes | — | `tkinterdnd2` opcional; lista de recentes na config |

## G12 · Catálogo i18n unificado

Hoje: `T` com tuplas de **3** (en, ru, pt) + `T_ES` dict separado + `LAYOUTS_ES`
tupla separada + `t()` que depende de estouro de índice para o espanhol
(`'lang_btn'` tem 3 entradas e `_lang_index('es')` devolve 3 → cai no `entry[0]`).

Unificar em `dict[str, dict[str, str]]` com as 4 línguas, teste que garante
cobertura completa de chaves em todos os idiomas.

---

# Parte F — Qualidade da saída (Fase 5)

| # | Item | Local | Correção |
|---|---|---|---|
| O1 | PDF sem metadados | `generate_pdf` | `set_title/set_author/set_subject/set_keywords/set_creator` |
| O2 | PDF sem outline | — | `pdf.start_section()` por capítulo e na seção de respostas |
| O3 | Só A4 retrato, margens fixas | L932-940 | `--page-size {A4,A5,Letter,Legal}`, `--landscape`, `--margin-*` |
| O4 | RTF declara `\fcharset0` para fonte de símbolos, enquanto o DOCX usa corretamente charset 2 | L2594 vs L1991 | Detectar fonte simbólica e emitir `\fcharset2` |
| O5 | RTF escrito com `encoding='ascii', errors='ignore'` — descarta silenciosamente nomes de fonte não-ASCII | L2637 | `_rtf_escape` no nome da fonte e `errors='strict'` |
| O6 | `{total}` redesenhado por cima de retângulos brancos | `_rerender_with_total` L1024-1055 | Duas passadas (contar páginas, depois renderizar) ou placeholder de largura fixa |
| O7 | DOCX sem cabeçalho/rodapé nem colunas | `generate_docx` | Ver Parte C |
| O8 | Sem capa nem sumário | — | `--cover-title`, `--cover-author`, `--toc` |
| O9 | HTML sem tema escuro | `_build_diagram_css` | Coberto por C2 |

---

# Parte G — Robustez dos parsers

| # | Item | Local | Correção |
|---|---|---|---|
| R1 | Corte de partidas por `(?=^\[Event\b)` | L697-698 | **Promovido a crítico** — ver C10 e C11 (perda de dados silenciosa) |
| R2 | Só partidas **com** tag `[FEN]` viram diagrama → PGN normal gera **zero** diagramas | L702-704 | Fase 6/N1: diagrama após o lance N |
| R3 | `_clean_moves` ignora comentário `;` até fim de linha e linha de escape `%` | L642-665 | Tokenizador PGN conforme §6 e §8.2.5 |
| R4 | EPD: `line.split(None, 4)` quebra com contagem de campos diferente; `bm` guardado no campo `black` | L729-753 | Parser de operandos EPD; campos próprios (`id`, `bm`, `am`, `c0`) |
| R5 | Leitura sempre `utf-8-sig` com `errors='replace'` — PGN em Latin-1/cp1252 (muito comum) vira texto corrompido em silêncio | L2994, L3443 | Tentar UTF-8; em falha, cp1252; `--encoding` para forçar |

### R3 · comprovação

```python
_clean_moves('1.e4 ; comentário até o fim da linha\n1...e5')
# → '1.e4 ; comentário até o fim da linha 1...e5'    comentário ';' não removido
```

A prosa entra na notação e aparece na seção de respostas.

> **Não é defeito:** `_clean_moves('1.e4 {outer {inner} still} e5')` → `'1.e4 still} e5'`
> foi levantado na primeira revisão como corrupção de chaves aninhadas. A norma
> PGN (§8.2.5) determina que comentários `{}` **não aninham** — a entrada é que
> está malformada e o comportamento atual está conforme. Retratado.

### R5 · comprovação

```
PGN em cp1252, lido como utf-8-sig com errors='replace':
  [Event "Partida do Peão"]  →  event = 'Partida do Pe�o'
```

---

# Parte H — Funcionalidades novas (Fase 6)

## N1 · Diagrama a partir do lance N — *maior lacuna do programa*

Hoje um PGN de partidas completas (sem tag `[FEN]`) produz **zero** diagramas:
`parse_pgn` descarta todo bloco sem FEN (L702-704).

**Proposta:** motor de lances mínimo (SAN → posição) ou dependência opcional
`python-chess`, com:
```
--at-move N[,N…]     diagrama após o lance N
--at-move last       posição final
--every N            a cada N lances
--at-comment MARCA   onde houver {#diagram} no comentário
```
Dependência **opcional**: sem ela, mensagem clara em vez de erro obscuro.

## N2 · Layout customizado
`--grid COLSxROWS` livre, substituindo os 7 presets fixos (dois dos quais —
índices 3 e 6 — só diferem no nº de linhas com notação).

## N3 · Perfis nomeados
`--profile "Livro A5"`, salvos na config; combobox na GUI.

## N4 · Exportação PNG/SVG
`_render_diagram_png` (L1753-1851) já está escrito e nunca é chamado — é a base.
`--export-images DIR --image-format {png,svg}`.

## N5 · Modo lote
`diagpdf *.pgn -o saida/` e `--merge` para juntar num só documento.

## N6 · Introspecção da CLI
`--list-fonts`, `--list-layouts`, `--list-languages`, `--dry-run`.

## N7 · Numeração
`--number-start N`, `--number-format "{n}."`, `--number-restart-per-chapter`.

## N8 · Relatório de validação
Resumo ao fim: posições lidas, ignoradas e por quê; opções ignoradas por formato.

## N9 · Markdown e LaTeX
Markdown com diagramas em Unicode ou imagem; LaTeX usando `chessboard`/`skak`.

## N10 · Formato de livro de exercícios
`--answers-upside-down`, `--answers-new-page`, `--answers-after-chapter`.

---

# Parte I — Documentação

| # | Item | Correção |
|---|---|---|
| Doc1 | README documenta `--no-renumber`; a flag real é `--keep-numbers` | Aceitar ambas; corrigir o texto |
| Doc2 | README anuncia "4 fontes"; existem 16 | Gerar a lista a partir de `FONT_NAMES` |
| Doc3 | README cita `AlphaDG.ttf`, `ZurichFigurine.TTF`, `LinaresFigurine.TTF` — ausentes do `Fonts/` | Restaurar arquivos ou corrigir README (ver C8) |
| Doc4 | README só fala de PDF; existem HTML, EPUB, DOCX e RTF | Documentar os 5 + matriz de capacidades |
| Doc5 | `--border`, `--no-header`, `--no-footer`, `--epub-css`, `--text-size` não documentados | Documentar |
| Doc6 | README_RU desatualizado igual | Sincronizar; avaliar README_PT |
| Doc7 | Sem CHANGELOG | Criar, a partir da 0.2.4 |

> **Situação em 0.15.0 (Doc2 e Doc3):** são 17 fontes de tabuleiro e 3 figurines.
> Do trio que o README citava sem existir, `ZurichFigurine.TTF` e
> `LinaresFigurine.TTF` foram restauradas na 0.15.0 e o texto passou a descrevê-las
> como o que são — subconjuntos recuperados de `chesswin.pdf`. Só a `AlphaDG.ttf`
> continua citada e ausente, agora com a ressalva explícita no README.
>
> **Situação em 0.15.0 (Doc6):** o `README_RU.md` estava parado no release
> original — anunciava saída só em PDF, 4 fontes de tabuleiro, `AlphaDG` como
> padrão de `-f` e `fen2rtf.py` como script principal. Reescrito na 0.15.0 sobre
> o estado real do programa: os 7 formatos, a matriz de capacidades, a referência
> de CLI completa, os perfis e a tabela de fontes correta. Não é tradução linha a
> linha do `README.md` — é a versão russa condensada, e diz isso no cabeçalho.

---

# Apêndice — Índice de defeitos por gravidade

Todos os itens marcados ✓ foram reproduzidos nesta base de código; os demais
vêm de leitura do fonte.

**Críticos (12)** — produzem arquivo errado ou perdem dados sem aviso:

| # | Defeito | Comprovado |
|---|---|:--:|
| C1 | Fonte do HTML nunca carrega | ✓ |
| C2 | Variáveis CSS indefinidas | ✓ |
| C3 | `--font-size` descartado | ✓ (saídas byte-idênticas) |
| C4 | Numeração das respostas ignora offset | ✓ (instrumentação) |
| C5 | Corte de número de vários dígitos no título | ✓ (4 casos) |
| C6 | EPUB 3 não conforme | ✓ |
| C7 | Sem validação de FEN | ✓ (`IndexError`) |
| C8 | Fonte desconhecida → arquivo errado + mapa errado | ✓ |
| C10 | PGN sem `[Event]` → posição anterior desaparece | ✓ |
| C11 | `[Event` em comentário destrói os lances | ✓ |
| C12 | Respostas transbordam a página (322 mm em folha de 297 mm) | ✓ |
| C13 | Número azul não clicável | ✓ (instrumentação) |
| C15 | DOCX lança exceção depois de gravar, com 2 das 16 fontes | ✓ |

**Altos (10):** C9 rótulo fixo em português · C14 `border=none` ignora coordenadas ✓ ·
C16 política de `fsType` só no DOCX ✓ ·
P1/P2 paridade entre formatos (7 opções) · R2 PGN sem FEN gera zero diagramas ·
G1 congelamento da GUI · O4 charset RTF ✓ · R5 codificação de entrada ✓ ·
D3 custo de import (~350 ms) ✓ · T1 ausência de testes

**Médios (13):** G2-G6, G9-G11 · O1, O2, O5, O6 · R3 ✓ · R4 · D2 · D5 · Doc1-Doc5

**Baixos (7):** O3, O8 · G7, G8 · D6 · Doc6, Doc7

## Retratações da revisão

- **Transbordo horizontal do tabuleiro** (`x_pad` negativo) foi levantado como
  hipótese e **não se confirmou**: medido nas 16 fontes × 3 layouts, a largura
  do tabuleiro nunca excedeu a coluna. Não consta da lista.
- **EPUB "rejeitado por leitores"**: o pacote é XML bem-formado, `mimetype` está
  armazenado sem compressão como primeira entrada e todas as âncoras internas
  resolvem. O problema da C6 é de **conformidade com a norma EPUB 3**
  (erros no epubcheck), não de abertura no leitor.
