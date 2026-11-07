# jwm_startup

```sh
jwm_startup              # abre ~/.jwmrc
jwm_startup outro.jwmrc
```

| Momento | Tag do JWM | Quando executa |
| --- | --- | --- |
| Início de sessão | `StartupCommand` | Ao abrir uma nova sessão, sem repetir no reinício. |
| Reinício | `RestartCommand` | Ao reiniciar o gerenciador JWM. |
| Encerramento | `ShutdownCommand` | Ao sair do JWM, sem reinício. |

Adicione um comando, escolha um aplicativo instalado ou selecione um programa ou
script. Use o comando direto, sem `exec:`. Argumentos e operadores seguem a sintaxe
do shell. O JWM inicia os comandos de forma assíncrona; a lista não garante uma
sequência de execução.

Desmarque **Ativo** para desativar uma entrada sem apagá-la. **Ver alterações**
mostra o XML antes de salvar. Salvar cria um backup `<arquivo>.bak` e não executa
nenhum comando. Alterações externas exigem recarregar o arquivo antes de salvar.

Entradas de arquivos incluídos aparecem para consulta; use **Abrir origem** para
editá-las. Includes dinâmicos `exec:` não são executados pelo editor.
O editor cuida dos comandos do JWM, não de `~/.config/autostart` ou serviços.

Comandos desativados ficam em comentários XML com o marcador
`jwm_startup:disabled` e conteúdo em Base64. Isso permite guardar comandos com
`--argumentos` e restaurar seu XML. Comentários simples contendo apenas uma tag de
comando também são reconhecidos como desativados.
