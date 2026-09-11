# DiagPDF — Roadmap

Estado analisado: **v0.2.3** (`fen2rtf.py`, 3.517 linhas, módulo único)
Data da análise: 2026-08-11

---

## 1. Diagnóstico resumido

O DiagPDF funciona bem no caminho principal (PGN com tag `[FEN]` → PDF, fonte
ChessMerida, layout 2). Fora desse caminho há falhas silenciosas: opções aceitas
e ignoradas, fontes ausentes resolvidas para o arquivo errado, e HTML/EPUB com
defeitos que só aparecem depois que o arquivo sai da máquina de quem gerou.

| Área | Estado | Observação |
|---|---|---|
| Renderização do tabuleiro (FEN → glifos) | ✅ Correto | Verificado casa a casa (cor das casas e orientação corretas) |
| Exportação PDF | ✅ Completa | Metadados, outline, tamanho de página, capa e sumário (fase 5) |
| Exportação HTML | ✅ Correta | Fonte embutida e variáveis CSS definidas (fase 0) |
| Exportação EPUB | ✅ Válida | Conforme EPUB 3, com documento de navegação (fase 0) |
| Exportação DOCX | ✅ Completa | Cabeçalho/rodapé e colunas (fase 2); marca d'água no cabeçalho (fase 13) |
| Exportação RTF | ✅ Completa | `charset2` e escape Unicode (fase 2); marca d'água no cabeçalho (fase 13) |
| Paridade entre formatos | ✅ Completa | Matriz declarada e testada; o que um formato não faz é avisado (fase 2) |
| Parsing PGN | ✅ Robusto | Corte por máquina de estados; partidas completas viram diagramas pelos lances (fases 0 e 6) |
| GUI | ✅ Responsiva | Geração em thread, pré-visualização, tema escuro (fase 4) |
| Testes | ✅ 1.425 testes | Suíte pytest sobre invariantes estruturais (fases 1, 7–13) |
| Exportação Markdown | ✅ Completa | Peças Unicode, arquivo único (fase 9) |
| Exportação LaTeX | ✅ Completa | Pacote `chessboard`; compilado e conferido (fase 13) |
| Arquitetura | ✅ Pacote | 24 módulos em `diagpdf/`; `fen2rtf.py` virou shim (fase 3) |
| Opções | ✅ Tipadas | `RenderOptions` validada; um padrão por opção, não um por renderizador (fase 7) |

**43 defeitos** (13 críticos, todos reproduzidos nesta base), **7 lacunas de
paridade**, **10 oportunidades de funcionalidade**.
Detalhamento, provas de reprodução e critérios de aceitação em [SPEC.md](SPEC.md).

---

## 2. Princípios que guiam o plano

1. **Nada de falha silenciosa.** Toda opção ignorada, FEN inválido ou fonte
   ausente vira aviso visível — nunca saída corrompida sem alerta.
2. **Compatibilidade preservada.** A CLI e o formato de config existentes
   continuam funcionando. Nomes novos são adicionados, os antigos viram alias.
3. **Refatorar atrás de testes.** Nenhuma quebra do monólito antes de existir
   uma malha de testes que detecte regressão de saída.
4. **Paridade antes de novidade.** Fechar as lacunas entre formatos vale mais
   que adicionar um sexto formato.

---

## 3. Fases

### Fase 0 — Correções críticas ✅ concluída (v0.2.4)

Defeitos que produzem arquivo errado sem o usuário perceber.

| # | Defeito | Impacto |
|---|---|---|
| C1 | HTML: fonte referenciada como `../Fonts/X.ttf` relativa ao arquivo de saída | Tabuleiro vira texto ilegível em qualquer pasta que não seja a do app |
| C2 | CSS usa `var(--card-bg)` / `var(--card-border)` nunca definidas | Moldura e fundo do diagrama não renderizam (HTML + EPUB) |
| C3 | `--font-size` da CLI é descartado (`opts['font_size'] = 0` fixo) | Opção documentada não faz nada |
| C4 | Numeração das respostas ignora `number_offset` no PDF | `--from 2 --keep-numbers` gera diagramas 2,3 e respostas 1,2 |
| C5 | `_split_title_number_prefix` corta números de vários dígitos | `"12 Mate"` com num=1 → link só no "1", "2 Mate" solto |
| C6 | EPUB 3 inválido (sem `dcterms:modified`, sem nav doc, ID `urn:uuid:12345` fixo) | Reprovado no epubcheck; rejeitado por parte dos leitores |
| C7 | `parse_fen('')` lança `IndexError`; FEN inválido gera tabuleiro mudo | Quebra ou silêncio em entrada malformada |
| C8 | Fonte inexistente resolve para arquivo arbitrário com mapa de caracteres errado | `AlphaDG` (ausente no `Fonts/`) → serve `ChessMerida.ttf` com mapa Alpha → lixo |
| C10 | PGN cuja partida não começa por `[Event]` funde blocos e a posição anterior **desaparece** | Perda de dados silenciosa |
| C11 | `[Event` na coluna 0 dentro de `{comentário}` trunca os lances | Solução destruída |
| C12 | Resposta longa é desenhada fora da página (322 mm em folha de 297 mm) | Texto perdido em livros com variantes |
| C13 | Título fica azul com `link=0` quando a posição não tem resposta | Parece clicável, não é |
| C14 | `--border none` ignora "Mostrar coordenadas" | Opção sem efeito |
| C15 | DOCX lança exceção **depois** de gravar o arquivo, com `Chess Adventurer` e `Chess Cases` | *Traceback* cru; arquivo existe mas parece falha |
| C16 | `fsType` verificado só no DOCX; PDF e EPUB embutem fontes restritas sem checar | Política inconsistente (e questão de licença) |

Inclui também: rótulo `"Analisar no Lichess"` fixo em português nos 4
renderizadores → traduzido e configurável.

**Entrega:** saída correta em todos os formatos para o conjunto de opções atual.

---

### Fase 1 — Rede de testes ✅ concluída (v0.2.5)

Pré-requisito para refatorar sem medo.

- ✅ `pytest` com 690 testes em 8 módulos.
- ✅ Testes de saída por **invariante estrutural** (nº de diagramas, âncoras
  casadas, XML/EPUB bem-formados, chaves RTF balanceadas), não por comparação de
  bytes — que quebraria a cada mudança inofensiva de ordenação ou de subconjunto
  de fonte.
- ✅ `test_batch.py` corrigido na fase 0 (pedia `AlphaDG`, que não existe).
- ✅ Validação EPUB por `epubcheck` quando disponível (`EPUBCHECK_JAR`); sem ele,
  as mesmas regras são verificadas em `tests/inspectors.py`.

**Entregue:** `690 passed, 1 skipped`. Escrever a suíte revelou **6 defeitos
novos** (P1–P6 no [CHANGELOG](CHANGELOG.md)), incluindo uma regressão que a
própria fase 0 havia introduzido no cortador de PGN.

---

### Fase 2 — Paridade entre formatos ✅ concluída (v0.2.6)

- ✅ Matriz `FORMAT_CAPABILITIES` declarada em código e **verificada por teste**:
  cada capacidade declarada é exercitada contra o documento gerado, e cada uma
  não declarada exige aviso.
- ✅ As 7 opções passaram a valer nos 5 formatos, com duas exceções que são
  propriedade do formato: EPUB é refluível (sem páginas próprias para cabeçalho
  corrente) e navegador não numera página a partir do markup.
- ✅ Avisos explícitos no lugar do descarte silencioso.
- ✅ Matriz documentada no README.

**Entregue:** 773 testes. Tabela completa no [CHANGELOG](CHANGELOG.md).

---

### Fase 3 — Arquitetura ✅ concluída (v0.3.0)

O monólito de 4.604 linhas virou pacote de 22 módulos, com `fen2rtf.py` reduzido
a um shim de 157 linhas que reexporta a API antiga.

```
diagpdf/
  errors  log  model  resources  chars  layouts  paths      (base)
  i18n  fonts  fen  parsers  geometry  capabilities  config
  render/  common  pdf  html  epub  docx  rtf
  output  cli  gui
fen2rtf.py    shim de compatibilidade
```

- ✅ **Saída idêntica** antes e depois: PDF, HTML e RTF byte-a-byte; EPUB e DOCX
  idênticos em todas as entradas do zip, exceto o payload `.odttf`, que é
  embaralhado com um GUID aleatório a cada geração — não-determinismo do próprio
  formato, verificado gerando duas vezes com o mesmo código.
- ✅ Descoberta de fontes **cacheada** em `~/.diagpdf/fontcache.json`, chaveada por
  nome + tamanho + mtime: import de ~130-165 ms para ~85 ms.
- ✅ Ruído do fontTools (`'modified' timestamp seems very low`) silenciado; `-v`
  mostra, `-q` cala os avisos.
- ✅ Código morto removido, `pyproject.toml` com entry point `diagpdf`, ruff limpo.
- ✅ `RenderOptions` como dataclass validado ficou para a **fase 7**: `opts: dict`
  era a fronteira entre CLI, GUI e renderizadores, e trocá-la mexia nos cinco
  renderizadores de uma vez.

**Entregue:** 858 testes verdes, ruff sem apontamentos.

---

### Fase 4 — GUI ✅ concluída (v0.4.0)

- ✅ Geração em **thread de trabalho**, com barra de progresso e cancelamento
  que apaga o arquivo incompleto. Verificado dirigindo a janela de verdade: 227
  ciclos do laço de eventos durante a geração, intervalo máximo de 157 ms.
- ✅ **Pré-visualização ao vivo** do diagrama, reagindo às opções.
- ✅ CSS do EPUB como campo persistente; configuração versionada e validada;
  arquivos recentes; arrastar-e-soltar opcional; tema claro/escuro.
- ✅ Tipo de arquivo resolvido por tabela, não pelo rótulo traduzido.
- ✅ Catálogo i18n unificado — 78 chaves × 4 idiomas, com teste de cobertura.
- ✅ `gui.py` (628 linhas numa função) virou pacote de 6 módulos; as partes
  testáveis não importam Tk.

**Entregue:** 930 testes, ruff limpo. Detalhes no [CHANGELOG](CHANGELOG.md),
incluindo por que o tabuleiro sai em branco no Pillow sem o charmap simbólico.

---

### Fase 5 — Qualidade da saída ✅ concluída (v0.5.0)

- ✅ Tamanho de papel (A3/A4/A5/Letter/Legal), orientação e margens, chegando ao
  PDF, DOCX, RTF e ao CSS de impressão do HTML.
- ✅ Metadados do PDF; marcadores por capítulo e para a seção de respostas.
- ✅ Capa e sumário com pontilhado e numeração correta.
- ✅ `{total}` resolvido pelo *alias* do fpdf2 — fim dos retângulos brancos.
- ✅ RTF com `charset2` e sem `errors='ignore'` (feitos na fase 2); DOCX com
  cabeçalho/rodapé e colunas (fase 2); HTML com tema escuro (fases 0 e 2);
  EPUB com metadados reais e sumário navegável (fases 0 e 2).

**Entregue:** 994 testes, ruff limpo.

---

### Fase 6 — Funcionalidades novas ✅ concluída (v0.6.0)

| Funcionalidade | Estado |
|---|---|
| Diagrama a partir do lance N | ✅ `--at-move`, `--every`, `--at-comment` (python-chess opcional) |
| Layout customizado | ✅ `--grid COLSxROWS` |
| Exportação PNG | ✅ `--export-images DIR` |
| Modo lote | ✅ vários arquivos, `--merge` |
| `--list-fonts`, `--list-layouts`, `--dry-run` | ✅ |
| Numeração: início, formato | ✅ `--number-start`, `--number-format` |
| Relatório de validação | ✅ resumo ao fim da execução |
| Perfis nomeados | ⏳ adiado |
| Markdown e LaTeX | ⏳ adiado (prioridade baixa no plano original) |
| Respostas invertidas / marca d'água | ⏳ adiado (prioridade baixa) |

**Entregue:** 1.075 testes, ruff limpo.

---

### Fase 7 — Opções tipadas ✅ concluída (v0.7.0)

A dívida anotada na fase 3. As opções viajavam como `dict`; nada declarava quais
chaves existiam, então cada renderizador carregava o próprio padrão para cada
chave que lia.

O levantamento feito antes de mexer no código encontrou **49 chaves** lidas em
13 arquivos e **6 com padrões que discordavam entre renderizadores** — entre
elas `show_footer` (`True` no PDF, `False` nos outros quatro) e `show_header`.
Nenhuma atingia a CLI ou a interface, que preenchem tudo; quem passasse um
dicionário parcial é que recebia documento diferente conforme o formato.

- ✅ `RenderOptions`: 48 campos, um tipo, um padrão e uma verificação cada.
- ✅ Recorte de faixa centralizado; valor inválido é **nomeado num aviso** e
  substituído, nunca aceito em silêncio.
- ✅ Os cinco renderizadores leem atributos; o `dict` continua aceito na porta.
- ✅ **Saída idêntica** comprovada: 115 documentos (23 entradas × 5 formatos)
  gerados pela CLI antes e depois, iguais byte a byte fora dos campos que cada
  formato carimba de novo a cada build — e do carimbo de versão no PDF.
- ✅ Teste estrutural que reprova qualquer `opts.get('x', padrão)` que reapareça
  num renderizador — é assim que os formatos se separaram da primeira vez.
- ✅ `output_snapshot.py` no repositório: o arnês que fez essa prova ficou
  disponível para as próximas mudanças, em vez de ser reinventado a cada uma.

**Entregue:** 1.135 testes, ruff limpo. Detalhes no [CHANGELOG](CHANGELOG.md).

---

### Fase 8 — Perfis nomeados ✅ concluída (v0.8.0)

O primeiro item da lista de "o que ficou para depois", e o mais barato agora que
`RenderOptions` serializa e valida o conjunto inteiro.

- ✅ `--profile`, `--save-profile`, `--list-profiles`, `--delete-profile`.
- ✅ `diagpdf/profiles.py`, em `~/.diagpdf/profiles.json`, guardando só as
  escolhas — não os 48 campos.
- ✅ **Uma opção digitada vence o perfil.** Isso exigiu descobrir o que o usuário
  realmente digitou: o argparse preenche todos os padrões, então a linha de
  comando é lida uma segunda vez com `argparse.SUPPRESS`. As opções passaram a
  ser montadas em camadas: padrões → perfil → digitado → derivado da execução.
- ✅ A janela lê e escreve o mesmo arquivo: perfil salvo na CLI aparece na lista
  da interface, e o contrário.
- ✅ Saída dos 115 documentos idêntica à de antes da reescrita do `_build_opts`.

**Entregue:** 1.196 testes, ruff limpo.

---

### Fase 9 — Markdown e LaTeX ✅ concluída (v0.9.0)

Sete formatos no total. Os dois novos resolvem o tabuleiro de formas opostas,
porque as restrições são opostas.

- ✅ **Markdown**: peças Unicode em bloco cercado — um arquivo só, sem imagens ao
  lado, renderizando no GitHub e em qualquer gerador de site estático. Metadados
  em front matter YAML, capítulos em títulos, respostas ligadas de volta.
- ✅ **LaTeX**: pacote `chessboard`, FEN direto. Compila com `pdflatex`; exige o
  `collection-games`. `babel` + `T2A` para o PGN de exemplo, que é russo.
- ✅ Matriz de capacidades declarada e **exercitada**: os dois entraram na lista
  `FORMATS` da suíte de paridade, então toda capacidade declarada é testada
  contra o documento gerado e toda ausente exige aviso.
- ✅ Dois exageros antigos em `requested_capabilities` corrigidos: layout padrão e
  seção de respostas não são mais "pedidos" — senão o Markdown avisaria em toda
  execução sobre opções que ninguém escolheu.

⚠️ **O `.tex` não foi compilado**: não há LaTeX nesta máquina. Verificado por
estrutura (aninhamento, chaves, escape, links resolvidos). Por isso tudo que
depende do pacote está concentrado numa linha `\setchessboard` do preâmbulo, onde
um ajuste custa uma edição.

> Resolvido na **fase 13**: o MiKTeX foi instalado e os 26 documentos LaTeX do
> corpus compilam. A primeira compilação encontrou um defeito que a verificação
> estrutural não tinha como pegar — ver a fase 13.

**Entregue:** 1.262 testes, ruff limpo.

---

### Fase 10 — Respostas invertidas ✅ concluída (v0.10.0)

`--answers-upside-down`: a convenção de livro de exercícios, com a solução
impressa de cabeça para baixo.

- ✅ O **bloco inteiro** gira 180° em torno do centro da folha, não cada linha —
  senão, com a página virada, as linhas correriam de baixo para cima.
- ✅ Cabeçalho e rodapé continuam de pé.
- ✅ **Links espelhados**: retângulo de link é anotação em espaço de página e a
  transformação de conteúdo não o move. Em vez de reconstruir o retângulo (duas
  tentativas erradas: o `y` do `pdf.link()` é a borda inferior, e o `cell()`
  envolve os glifos e não a célula), espelha-se o que o fpdf2 acabou de gravar.
  24/24 conferidos, erro máximo 0,09 pt.
- ✅ PDF, HTML e EPUB viram; DOCX, RTF, LaTeX e Markdown **avisam** por quê.
- ✅ Com a opção desligada, os 115 documentos idênticos aos de antes.

**Entregue:** 1.278 testes, ruff limpo.

---

### Fase 11 — Marca d'água ✅ concluída (v0.11.0)

O último item do plano original.

- ✅ `--watermark TEXT` e `--watermark-opacity PCT`.
- ✅ No PDF, carimbada **depois que todas as páginas existem**: fica sobre o
  conteúdo, e um lugar só sabe da marca em vez de um gancho em cada uma das
  quatro rotinas que abrem página. Corpo da fonte calculado para a diagonal da
  folha; opacidade como `ExtGState` de verdade.
- ✅ LaTeX via `draftwatermark`, carregado **só** quando há marca.
- ✅ HTML com elemento fixo girado.
- ✅ EPUB, DOCX, RTF e Markdown **avisam**. DOCX e RTF ficaram de fora de
  propósito: ali a marca é objeto de desenho no cabeçalho, e não há Word aqui
  para conferir que o arquivo abre.
- ✅ Um defeito **C2** (variável CSS indefinida) pego e corrigido antes de sair,
  com teste que agora roda `undefined_css_variables` com a marca ligada.
- ✅ Sem marca, os 115 documentos idênticos aos de antes.

**Entregue:** 1.294 testes, ruff limpo.

---

### Fase 12 — Respostas em página separada ✅ concluída (v0.12.0)

A outra metade da linha "respostas invertidas **ou em página separada**".

- ✅ O levantamento mostrou que **quatro dos cinco formatos paginados já
  quebravam a página** — e nenhum deixava escolher. O trabalho foi tornar isso
  controlável e trazer o **HTML**, o único que não quebrava, para a linha.
- ✅ `--answers-same-page` para o contrário; o padrão é o comportamento que PDF,
  LaTeX, DOCX e RTF já tinham.
- ✅ No PDF, continuar é preferência, não promessa: se não couber o título mais
  uma linha, a quebra acontece assim mesmo — senão a seção começaria abaixo da
  borda, que é o defeito C12 voltando por outro caminho.
- ✅ **Só o HTML mudou**: 23 arquivos, cada um por exatamente duas linhas de CSS.
  Os outros seis formatos, byte a byte idênticos.
- ✅ Não virou chave da matriz: EPUB e Markdown não têm página, mas também não
  perdem opção nenhuma — não há o que avisar.

**Entregue:** 1.307 testes, ruff limpo.

---

### Fase 13 — Pontas soltas ✅ concluída (v0.14.0)

O plano original terminou na fase 12. O que sobrou eram seis itens anotados no
caminho — quatro deles metade de alguma coisa que já existia. Compilar o LaTeX,
que era só uma pendência de *verificação*, acabou revelando dois defeitos.

| Ponta solta | O que faltava | Estado |
|---|---|---|
| Compilar o `.tex` | A fase 9 escreveu o exportador sem TeX na máquina | ✅ MiKTeX instalado; 26 de 26 documentos compilam — e a **primeira** compilação achou um defeito fatal |
| Marca d'água em DOCX e RTF | Fase 11 deixou de fora por não haver como conferir que o arquivo abre no Word | ✅ o Word **está** instalado; abre, exporta e desenha no lugar |
| Exportação SVG | `--export-images` (fase 6) só escrevia PNG | ✅ `--image-format {png,svg}`, com os contornos dos glifos |
| `--list-languages` | Os outros três de introspecção da CLI foram feitos na fase 6 | ✅ |
| `--number-restart-per-chapter` | `--number-start` e `--number-format` foram feitos na fase 6 | ✅ |
| `--answers-after-chapter` | As outras duas linhas do "livro de exercícios" foram as fases 10 e 12 | ✅ |

Seis descobertas ao longo do caminho, todas corrigidas:

- **No LaTeX o capítulo não abria página.** `\section` corre no fio do texto por
  design, então um capítulo começava no meio da página onde o anterior terminou —
  o único formato paginado que destoava. A regra virou um teste só, sobre os
  quatro formatos, em vez de um por renderizador.
- **O LaTeX não compilava com cirílico.** `\usepackage[T2A,T1]{fontenc}` deixa o
  **T1** valendo — é a última da lista que manda — e o T1 não tem cirílico: o
  `pdflatex` parava na primeira letra russa sem produzir PDF. Todo PGN russo,
  incluindo o exemplo distribuído com o programa, gerava um `.tex` que não
  compilava. Nenhum teste de estrutura podia ver isso: o arquivo estava
  bem-formado. Agora o documento decide qual das duas codificações fica por
  último, pelo que ele carrega.
- **A âncora não podia continuar sendo o número.** Com o reinício por capítulo o
  mesmo número volta, e âncoras homônimas mandariam todo link do livro para a
  primeira delas.
- **Um `[Chapter]` marca o primeiro jogo do grupo.** O PDF já tratava os jogos
  seguintes como continuação; o agrupamento comum, não — o que teria reiniciado a
  numeração no meio do capítulo. Os formatos passaram a concordar.
- **PNG exportado com o título errado**: todos saíam com o número do primeiro
  diagrama, porque o desenhista calculava o número da posição 0.
- **`--list-languages` derrubava um console cp1252** ao imprimir "Русский". Os
  avisos já sobreviviam a isso desde a fase 3; a saída pedida, não.

`output_snapshot.py`, que só cobria cinco dos sete formatos, passou a render 182
documentos. Dos 115 anteriores, 103 saem idênticos; os 12 restantes diferem
apenas no número dentro do nome da âncora.

**Entregue:** 1.425 testes, ruff limpo.

---

### Fase 14 — Higiene e git ✅ concluída (2026-08-15)

O último risco da tabela §5 e o pré-requisito do único item do plano que ainda
depende de código: a integração contínua da fase 15 não existe sem repositório.

- ✅ **Artefatos regeráveis apagados**: `build/` (28 MB), `dist/` (44 MB),
  `smoke_out/`, `test_batch_out/`, `snapshot_out/before/` (8,6 MB), as árvores
  `__pycache__` e os caches do pytest e do ruff. Mais 22 `tmp_*` na pasta acima.
- ✅ `snapshot_out/digest_before.json` **preservado**: o `compare` do
  `output_snapshot.py` lê digests guardados, não os documentos — o corpus
  renderizado custava 8,6 MB e não servia para a comparação.
- ✅ Saídas conferidas à mão removidas (`review_smoke.*`, `test.epub`,
  `test.html`). O `test.fen` ficou: é **entrada** do `output_snapshot.py`.
- ✅ `.gitignore` revisado. A regra `*.pdf`, que existia para não versionar PDF de
  usuário, engolia também o `chesswin.pdf` — a procedência das fontes recuperadas
  na 0.15.0, citada no README, no CHANGELOG e no SPEC. Três exceções abertas:
  `fonts_6a7de6c2db0e9/`, `Fonts-recovered/source-pdfs/` e
  `Caractere do Diagrama/`. Sem elas, a documentação apontaria para arquivos que
  quem clonasse não receberia.
- ✅ `.gitattributes`: LF no repositório e no checkout, inclusive no Windows,
  porque a CI da fase 15 roda também no Linux. `*.pgn` e `*.fen` marcados `-text`
   — são a entrada do corpus e os digests são tirados sobre o que elas produzem.
- ✅ `git init` e primeiro commit: **193 arquivos, 6,0 MB**, árvore limpa.

**Entregue:** 1.427 testes verdes e ruff limpo depois da limpeza.

---

## 4. Ordem de execução

```
Fase 0 (críticos) ──► Fase 1 (testes) ──► Fase 2 (paridade)
                                    └──► Fase 3 (arquitetura) ──► Fase 4 (GUI)
                                                             ├──► Fase 5 (saída)
                                                             │           └──► Fase 6 (novidades)
                                                             └──► Fase 7 (opções tipadas)
                                                                            ├──► Fase 8 (perfis)
                                                                            ├──► Fase 9 (Markdown, LaTeX)
                                                                            ├──► Fase 10 (respostas invertidas)
                                                                            ├──► Fase 11 (marca d'água)
                                                                            └──► Fase 12 (respostas em página nova)
```

Fase 0 primeiro porque hoje o programa entrega arquivo errado sem avisar.
Fase 1 antes da 3 porque refatorar 3.517 linhas sem teste é aposta.
Fases 4/5/6 são independentes entre si depois da 3.

---

## 5. Riscos

| Risco | Mitigação |
|---|---|
| Fontes `AlphaDG`, `Zurich`, `Linares` ausentes do `Fonts/` mas referenciadas em README, código e testes | **Fechado.** `ZurichFigurine.TTF` e `LinaresFigurine.TTF` recuperadas na 0.15.0 do `chesswin.pdf`; a `AlphaDG.ttf` remontada na 0.16.0 das cópias embutidas nos exemplos de 2011. Os três nomes que a documentação citava têm arquivo. Resolução estrita continua valendo (Fase 0/C8) |
| Refatoração alterar saída sem ninguém notar | Golden tests da Fase 1 são bloqueantes para a Fase 3 |
| Alias de CLI antigos quebrarem scripts de usuários | `--no-renumber` (documentado no README) ≠ `--keep-numbers` (real): aceitar ambos |
| `build/`, `dist/`, `tmp_*`, `test_batch_out/` poluindo o diretório | **Fechado na fase 14.** Limpos, `.gitignore` revisado e árvore sob git |

---

## 6. O que ficou para depois

O plano original terminou na fase 12, as pontas soltas na 13, a higiene na 14 e a
`AlphaDG` na 16. **Nenhuma funcionalidade continua por implementar**, e a única
coisa em aberto é uma verificação: o workflow da fase 15 existe mas nunca rodou,
porque não há remoto configurado.

### Fase 15 — CI e verificação externa ✅ concluída (2026-08-15)

> **Primeiro run verde**, em `DarcioAlberico/DiagPDF-source` (privado), 3m30s:
> as seis tarefas passaram. `1.400 passed, 25 skipped` no Ubuntu e no Windows,
> em 3.10 e 3.12 — 25 pulos porque o runner não tem TeX no job de teste (os
> quatro que compilam rodam no job próprio) e as fontes recuperadas não estão lá.
> **O epubcheck rodou de verdade**: `EPUBCHECK_JAR` apontou para o 5.3.0 e o
> passo-guarda reexecutou aquele teste sozinho — `1 passed`, sem skip. O job de
> LaTeX compilou o corpus no Ubuntu (`4 passed`), o que confirmou que o
> `chessboard` vem mesmo do `texlive-games`. O `.exe` saiu como artefato, 27,6 MB.

O item D6 do [SPEC](SPEC.md), aberto desde a fase 3. `.github/workflows/ci.yml`
com três tarefas:

| Tarefa | O que faz |
|---|---|
| `pytest` | A suíte no Ubuntu **e** no Windows, em Python 3.10 e 3.12, mais o ruff. Busca o epubcheck 5.3.0 (versão fixada), aponta `EPUBCHECK_JAR` para o jar e **confere que aquele teste rodou** — validador ausente faz o teste pular, e teste pulado é verde. No Linux roda sob Xvfb: dois testes de GUI abrem uma janela Tk de verdade |
| `latex` | Instala o TeX Live e compila o corpus. Fora da matriz de propósito — é instalação lenta e pesada que mais nada na suíte usa |
| `windows-exe` | Constrói o `DiagPDF.exe` com o PyInstaller e o publica como artefato do run. Depende do `pytest` passar |

Dois buracos de cobertura fechados no caminho, os dois da mesma família — teste
que se pula sozinho e passa por verde:

- **`pypdfium2` não estava em `requirements-dev.txt`.** Está instalado nesta
  máquina, então os cinco testes que releem o PDF gerado (papel, margens,
  metadados, sumário, capa) passavam aqui e teriam **pulado em silêncio** no
  runner. Entrou no arquivo e no extra `dev` do `pyproject.toml`.
- **O `ruff` também não estava**, embora o CHANGELOG diga "ruff limpo" a cada
  versão. A tarefa de lint não teria a ferramenta.

⚠️ **O workflow nunca rodou.** Não há remoto configurado: o arquivo está escrito
e validado localmente (YAML analisado, e os três trechos de shell — a guarda do
epubcheck, o localizador do jar e a conferência do `.exe` — executados aqui para
ver se falham quando devem), mas verde no Ubuntu e no Windows é coisa que só o
primeiro run prova. **Aceitação:** os 1.427 testes verdes nos dois sistemas, sem
o skip do epubcheck, e o `.exe` baixável do run.

### Fase 16 — `AlphaDG` ✅ concluída (v0.16.0)

Não precisou de compra. `build_alphadg.py` junta os subconjuntos embutidos nos
exemplos de 2011, devolve o `cmap` e deriva o que falta.

- ✅ **56/56** em `_ALPHA_REQUIRED_CHARS`; `Fonts/AlphaDG.ttf` instalada, 57
  glifos, `fsType` 0.
- ✅ `'` e `$` **derivados por espelhamento**, com a regra testada antes de ser
  usada: vale exata para os dois pares de canto que a Alpha tem, e para o par de
  preenchimento da Leipzig e da Kingdom. Só os dois triângulos são desenho.
- ⚠️ O caminho errado óbvio — tratar o código do texto do PDF como glyph id —
  produz uma fonte **bem-formada** em que o rei é uma tira de borda. O que pegou
  isso foi comparar as caixas por caractere com a `LeipzigDG`, que ainda tem
  `cmap`. Estes PDFs trazem `/CIDToGIDMap` de verdade.
- ✅ **Prova pixel a pixel**: o primeiro diagrama dos três exemplos regerados sai
  idêntico ao do arquivo de 2011 — 0 pixels divergentes em ~57 mil de tinta.
- ✅ Um defeito achado no caminho: `_ALPHA_REQUIRED_CHARS` **pedia 55 onde o
  programa usa 56**. O `fen.py` escrevia `'$'` literal para a borda esquerda, que
  ninguém exigia — uma fonte Alpha sem esse glifo passava na verificação e
  desenhava tabuleiro aberto à esquerda com `--no-coords`.
- ✅ **Nada da fonte é versionado** — nem ela, nem os subconjuntos extraídos, nem
  os PDFs de 2011 que os embutem, porque subconjunto extraído de PDF é a fonte.
  Versionado fica o método: `build_alphadg.py` e o `Fonts-recovered/README.md`.
  Um clone tem 17 fontes e a suíte fica verde (1.403 testes); a CI não constrói a
  fonte e o `.exe` sai com as 17. Sem o material, o script diz o que falta e para.
  Duas construções dão o mesmo arquivo byte a byte (o fontTools carimbava a hora
  do `save`).
- ✅ Os **182 documentos do corpus idênticos** aos de antes: a fonte padrão
  continua `ChessMerida`.
- ✅ 12 testes usavam `'AlphaDG'` como nome de fonte inexistente; passaram a usar
  `MISSING_FONT`, afirmado ausente na carga do `conftest.py`.

**Entregue:** 1.414 testes verdes, ruff limpo.

> **Epílogo (0.16.1).** As três fontes originais estavam no repositório público
> `DarcioAlberico/DiagPDF`, no release v0.2.3 — encontradas quando este código ia
> ser publicado e o nome já estava ocupado. Estão instaladas no lugar das
> remontadas. A comparação com a original julgou a fase 16: **54 dos 56
> caracteres idênticos**, os dois espelhados inclusive; só os dois triângulos
> desenhados diferem. A distinção entre *deduzido* e *desenhado*, que o README
> fazia caractere a caractere, era a certa.

### As três fontes recuperadas, e por que não são distribuídas

Nenhuma delas está no repositório: subconjunto extraído de PDF é a tipografia, e
o PDF que o carrega também. Um clone tem 17 fontes de tabuleiro e uma figurina —
a `Hastings`, original e sempre presente. Versionado fica o método, para que cada
recuperação possa ser julgada e repetida por quem tiver os originais.

| Fonte | O que ela é | O que não é |
|---|---|---|
| `AlphaDG.ttf` | Os 56 caracteres do layout Alpha: 52 recuperados dos PDFs de 2011 e 4 derivados (0.16.0), com receita em `build_alphadg.py` | Os dois triângulos são desenho novo, não o traço do autor. O resto da tipografia nunca esteve nos exemplos |
| `ZurichFigurine.TTF`, `LinaresFigurine.TTF` | Os cinco glifos de peça (`K Q R B N`) que a notação usa, recuperados do `chesswin.pdf` (0.15.0) | Alfabeto completo e peças minúsculas |
