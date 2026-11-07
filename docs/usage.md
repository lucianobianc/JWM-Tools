# Configuração

## jwm_audio

Execute `jwm_audio` em uma sessão com bandeja de sistema e servidor PulseAudio,
ou PipeWire com `pipewire-pulse`. Clique no ícone para abrir o controle rápido;
use “Abrir mixer” para ajustar os aplicativos.

## jwm_menu

Execute `jwm_menu` para atualizar `~/.jwm-menu`. Inclua o arquivo no menu do JWM:

```xml
<RootMenu>
    <Include>~/.jwm-menu</Include>
</RootMenu>
```

## jwm_ram

Para colocar o indicador na bandeja do JWM:

```xml
<Tray>
    <Swallow name="jwm_ram" width="72" height="30">jwm_ram --width 72 --height 30</Swallow>
</Tray>
```

## jwm_style

Execute `jwm_style ~/.jwmrc`. O editor usa a configuração aberta e os estilos
que você salvar; não inclui presets internos.

## jwm_keys

Execute `jwm_keys ~/.jwmrc` para editar vínculos de teclado e mouse.
Vínculos de Includes mostram o arquivo de origem. Consulte [o editor de atalhos](keys.md).

## Mudança de nomes

| Anterior | Atual |
| --- | --- |
| `audiotray` | `jwm_audio` |
| `jwm-menu-gen` | `jwm_menu` |
| `jwm-ram` | `jwm_ram` |
| `jwm-style-editor` | `jwm_style` |

Atualize atalhos, autostart e o nome do `Swallow` para os comandos novos.
O menu continua em `~/.jwm-menu`. Os estilos pessoais continuam em
`~/.config/jwm-style-editor/styles/`, ou no caminho equivalente de
`XDG_CONFIG_HOME`.

O pacote Debian `jwm-tools` substitui o antigo `jwm-style-editor`. A versão 0.1
marca a primeira distribuição conjunta das quatro ferramentas.

## jwm_startup

Execute `jwm_startup` para editar os comandos da sessão em `~/.jwmrc`.
Também aceita outro arquivo: `jwm_startup /caminho/jwmrc`.
Consulte [Comandos da sessão](startup.md).
