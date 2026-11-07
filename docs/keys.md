# jwm_keys

```sh
jwm_keys ~/.jwmrc
```

A lista mostra os vínculos `Key` e `Mouse`, com busca e filtro por tipo.
Use “Novo teclado” ou “Novo mouse” para adicionar um vínculo; selecione uma
linha para editar ou excluir. “Capturar” identifica a tecla ou botão recebido
pela janela. Atalhos globais do JWM podem interceptar a captura; nesse caso,
selecione os modificadores e informe a tecla manualmente.

As alterações ficam pendentes. “Ver alterações” mostra a diferença no XML;
“Salvar” grava o arquivo, e “Salvar e reiniciar JWM” também solicita o reinício
do gerenciador. “Descartar” volta aos valores carregados.

A gravação mantém comentários, formatação, atributos desconhecidos e outras
configurações. O arquivo anterior é guardado em `.bak`. Alterações externas no
arquivo aberto ou em Includes impedem a gravação até recarregar. Ações com
conteúdo misto ou CDATA podem ter os atributos alterados, mas a reescrita do
texto da ação exige edição no arquivo de origem.

## Teclado

Aceita nomes X11, como `Return`, `F4` ou `XF86AudioRaiseVolume`, e keycodes de
8 a 255. Os modificadores são Ctrl (`C`), Shift (`S`), Alt (`A` ou `1`), Super
(`4`) e Mod2/3/5. A tecla `#` pode ser usada com `desktop#`, `send#` e `at#`.

## Mouse

Os contextos são área de trabalho (`root`), título (`title`), borda (`border`),
ícone (`icon`) e botões de fechar, maximizar e minimizar. Clique usa o número
do botão; soltura usa seu negativo. No JWM 2.4.6, duplo clique multiplica o
botão por 11: esquerdo = 11, central = 22, direito = 33.

A roda usa os botões 4/5 e, para rolagem horizontal, 6/7. Na área de trabalho,
os botões atribuídos a `RootMenu onroot` podem ter prioridade. Vínculos do
mouse dentro do conteúdo dos aplicativos não são editados por esta ferramenta.

## Ações e Includes

Escolha uma ação do JWM, como `close`, `maximize`, `move`, `resize` ou `root:1`.
Para iniciar um programa, use `exec:comando`. O editor não executa essas ações
ao abrir ou editar o arquivo.

Includes estáticos são lidos; vínculos incluídos são somente leitura na lista.
“Abrir origem” permite editar explicitamente esse arquivo. Includes com `exec:`
não são executados. Caminhos relativos seguem o diretório de execução do JWM.

Combinações repetidas são sinalizadas. A verificação considera modificadores,
nomes de teclas, expansão de `#`, keycodes e contexto/evento do mouse. Não resolve
todas as equivalências entre keycodes e nomes simbólicos em layouts X11.

Sintaxe de referência: JWM 2.4.6, `src/parse.c`, `src/binding.c` e `src/event.c`.
