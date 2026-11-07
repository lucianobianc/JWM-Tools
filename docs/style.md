# jwm_style

Abra `jwm_style ~/.jwmrc` para editar o estilo atual. As alterações aparecem na
prévia e só são gravadas ao clicar em “Apply and restart JWM”. “Discard changes”
volta aos valores do arquivo aberto.

“Save style” salva um estilo pessoal. O seletor lista a configuração atual e
seus estilos salvos. Também é possível renomear ou excluir esses estilos.
Não há coleções ou presets internos.

O editor altera os valores selecionados no XML, preservando o restante do
arquivo. Antes de gravar, verifica alterações externas e cria um arquivo `.bak`.
A gravação é atômica; links simbólicos são resolvidos para o arquivo de destino.

Includes de arquivos são lidos na ordem do JWM. Caminhos relativos seguem o
diretório de execução. Includes com `exec:` não são executados pela prévia.
Arquivos incluídos não são alterados implicitamente. Se um Include posterior
sobrepõe a propriedade local, abra esse arquivo para editá-la. Blocos ambíguos
são recusados ao salvar.

A escolha de fontes usa o seletor GTK. A decoração pode ser Flat ou Motif.
O ícone do botão do menu pode ser escolhido pelo seletor de arquivos.

A prévia usa imagens globais de botões, variantes de foco, `IconPath` e
`TitleButtonOrder`. A geometria dos botões nativos segue o
[JWM 2.4.6](https://github.com/joewing/jwm/blob/v2.4.6/src/border.c).
O conteúdo das janelas é ilustrativo. Regras Group, composição, DPI e ícones
fornecidos por aplicativos podem produzir diferenças no desktop real.
