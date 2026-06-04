# Instalação das automações na VM (sala cofre)

Este guia registra duas tarefas no **Agendador de Tarefas do Windows**:

1. **Servidor inicia sozinho** quando a VM liga/reinicia (sem precisar logar).
2. **Backup automático diário** do banco de dados e fotos.

> Ajuste o caminho `C:\Inspecoes\Inspecoes prediais MPDFT` abaixo se a sua
> pasta for diferente.

---

## Pré-requisito: abrir o CMD como Administrador

1. Tecla Windows → digite `cmd`
2. Clique com botão direito em **Prompt de Comando** → **Executar como administrador**

---

## 1. Inicialização automática do servidor

```cmd
schtasks /create /tn "Inspecoes MPDFT - Servidor" /tr "\"C:\Inspecoes\Inspecoes prediais MPDFT\iniciar_servidor_automatico.bat\"" /sc onstart /ru SYSTEM /rl HIGHEST /f
```

- `/sc onstart` → executa toda vez que a VM é ligada
- `/ru SYSTEM` → roda sem precisar de usuário logado
- O servidor sobe na **porta 8080**

Para iniciar **agora**, sem reiniciar a VM:
```cmd
schtasks /run /tn "Inspecoes MPDFT - Servidor"
```

---

## 2. Backup automático diário

Executa todo dia às **12:00** (ajuste o horário em `/st` se preferir):

```cmd
schtasks /create /tn "Inspecoes MPDFT - Backup Diario" /tr "\"C:\Inspecoes\Inspecoes prediais MPDFT\backup_automatico.bat\"" /sc daily /st 12:00 /ru SYSTEM /rl HIGHEST /f
```

- Os backups ficam na pasta **`Backups_Automaticos\`** dentro do projeto
- Mantém os últimos **30 dias** (os mais antigos são apagados automaticamente)

Para testar o backup **agora**:
```cmd
schtasks /run /tn "Inspecoes MPDFT - Backup Diario"
```
Depois verifique se apareceu um arquivo `.zip` na pasta `Backups_Automaticos\`.

---

## Comandos úteis de gerenciamento

Listar as tarefas criadas:
```cmd
schtasks /query /tn "Inspecoes MPDFT - Servidor"
schtasks /query /tn "Inspecoes MPDFT - Backup Diario"
```

Parar o servidor (encerrar a tarefa em execução):
```cmd
schtasks /end /tn "Inspecoes MPDFT - Servidor"
```

Remover uma tarefa (se precisar desfazer):
```cmd
schtasks /delete /tn "Inspecoes MPDFT - Servidor" /f
schtasks /delete /tn "Inspecoes MPDFT - Backup Diario" /f
```

---

## Arquivos de log (para conferir se está tudo certo)

| Arquivo | Conteúdo |
|---|---|
| `log_servidor_automatico.txt` | Saída do servidor iniciado automaticamente |
| `log_backup_automatico.txt` | Histórico de cada backup executado |

---

## Recomendação de segurança extra

Os backups ficam no mesmo disco da aplicação. Para proteção contra falha de
disco, edite o `backup_automatico.py` e aponte a variável `DESTINO` para uma
**pasta de rede** ou **outro disco**, por exemplo:

```python
DESTINO = r'\\servidor-arquivos\backups\inspecoes'
```
