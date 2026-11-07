# JWM Tools

Ferramentas para o JWM em Linux/X11.

| Ferramenta | Função | Uso |
| --- | --- | --- |
| `jwm_audio` | Volume geral, volume por aplicativo e seleção de saída e microfone. | `jwm_audio` |
| `jwm_menu` | Gera `~/.jwm-menu` a partir dos aplicativos instalados. | `jwm_menu` |
| `jwm_ram` | Indicadores de RAM, swap, CPU, temperatura e bateria para a bandeja. | `jwm_ram --width 72 --height 30` |
| `jwm_style` | Edita cores, fontes e decorações do JWM, com prévia e estilos pessoais. | `jwm_style ~/.jwmrc` |
| `jwm_keys` | Edita atalhos de teclado e vínculos do mouse, com backup do arquivo. | `jwm_keys ~/.jwmrc` |
| `jwm_startup` | Gerencia comandos de início, reinício e encerramento da sessão. | `jwm_startup ~/.jwmrc` |

## Instalação

Baixe o `.deb` em [Releases](https://github.com/lucianobianc/JWM-Tools/releases):

```sh
sudo apt install ./jwm-tools_0.1.1-1_all.deb
```

O pacote contém as seis ferramentas. O áudio usa PulseAudio ou PipeWire com suporte a PulseAudio.

## Pelo código-fonte

No Debian e derivados:

```sh
sudo apt install python3 python3-gi python3-gi-cairo python3-cairo python3-tk python3-pulsectl gir1.2-gtk-3.0 libfontconfig1 jwm
python3 tools/install.py
```

Os comandos ficam em `~/.local/bin`. Essa pasta precisa estar no seu `PATH`.
Use `--help` em cada comando para ver as opções.

[Configuração e nomes anteriores](docs/usage.md) · [Editor de estilos](docs/style.md) · [Editor de atalhos](docs/keys.md) · [Comandos da sessão](docs/startup.md)

## Desenvolvimento

```sh
python3 tools/build_release.py
python3 -m unittest discover -s tests -v
```

Os arquivos de distribuição ficam em `dist/`. Os testes gráficos precisam de X11;
as comparações com JWM real usam `JWM_REAL_TESTS=1`, `Xvfb` e `xwininfo`.

Licença: [GPL v2](LICENSE).
