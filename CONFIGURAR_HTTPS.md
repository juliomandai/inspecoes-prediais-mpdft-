# Configurar HTTPS (necessário para o PWA offline)

O modo PWA offline (Service Worker) **só funciona em HTTPS** com certificado
**confiável**. Este guia configura o servidor por HTTPS na VM com um certificado
autoassinado e explica como torná-lo confiável nos dispositivos.

> ⚠️ **MUITO IMPORTANTE:** com certificado autoassinado, **clicar em
> "aceitar o risco" no navegador NÃO é suficiente** para o PWA offline. O
> Service Worker exige um certificado confiável. Por isso a **etapa 5
> (instalar o certificado nos dispositivos) é obrigatória** — sem ela, a
> aplicação abre por HTTPS mas o modo offline continua bloqueado.

Ajuste o caminho `C:\Inspecoes\Inspecoes prediais MPDFT` se a sua pasta for diferente.

---

## 1. Atualizar o código e instalar dependências (na VM)

```cmd
cd "C:\Inspecoes\Inspecoes prediais MPDFT"
git pull
.venv\Scripts\activate
pip install -r src\requirements.txt
```
(o `pip install` adiciona o **cheroot**, servidor que fornece o HTTPS)

---

## 2. Gerar o certificado (com o IP da VM)

Descubra o IP com `ipconfig` e gere o certificado:

```cmd
python gerar_certificado.py 10.34.233.23
```
Troque pelo IP real da VM. Isso cria:
```
src\certs\cert.pem   (certificado — será instalado nos dispositivos)
src\certs\key.pem    (chave privada — fica só na VM, nunca compartilhe)
```

---

## 3. Ajustar o .env

Abra `src\.env` e adicione/ajuste a linha de origens confiáveis (com o IP e a
porta HTTPS 8443):

```
CSRF_TRUSTED_ORIGINS=https://10.34.233.23:8443
```
Mantenha `ALLOWED_HOSTS=*` (ou liste o IP).

---

## 4. Liberar a porta 8443 e iniciar o servidor HTTPS

Libere no firewall (CMD como Administrador):
```cmd
netsh advfirewall firewall add rule name="Inspecoes MPDFT HTTPS 8443" dir=in action=allow protocol=TCP localport=8443 profile=any
```

Teste manualmente:
```cmd
iniciar_servidor_https.bat
```
Acesse na própria VM: `https://localhost:8443`
(vai aparecer aviso de certificado — normal por enquanto, resolvido na etapa 5)

---

## 5. ⭐ Instalar o certificado como CONFIÁVEL nos dispositivos (OBRIGATÓRIO)

Copie o arquivo `src\certs\cert.pem` para cada dispositivo e instale:

### Windows (computadores)
1. Renomeie `cert.pem` para `cert.crt` e dê duplo clique
2. **Instalar Certificado** → **Computador Local** → Avançar
3. **Colocar todos os certificados no repositório a seguir** →
   **Autoridades de Certificação Raiz Confiáveis** → OK → Concluir
4. Reinicie o Chrome/Edge

### Android (tablets/celulares)
1. Copie o `cert.pem` para o aparelho
2. **Configurações → Segurança → Mais → Criptografia e credenciais →
   Instalar um certificado → Certificado CA**
3. Selecione o arquivo e confirme
4. Reinicie o Chrome

### iOS / iPadOS (iPhone/iPad)
1. Envie o `cert.pem` (por e-mail/AirDrop) e abra no aparelho
2. **Ajustes → Geral → VPN e Gerenciamento de Dispositivo** → instale o perfil
3. **Ajustes → Geral → Sobre → Configurações de Confiança de Certificado** →
   **ative** a confiança total para o certificado
4. Use o **Safari** (no iOS, o PWA/Service Worker só funciona pelo Safari)

> Depois de instalado e confiável, o endereço `https://<IP>:8443` abre **sem
> aviso** e o PWA offline passa a funcionar.

---

## 6. Inicialização automática por HTTPS

Atualize a tarefa do Agendador para usar a versão HTTPS (CMD como Administrador):

```cmd
schtasks /delete /tn "Inspecoes MPDFT - Servidor" /f
schtasks /create /tn "Inspecoes MPDFT - Servidor" /tr "\"C:\Inspecoes\Inspecoes prediais MPDFT\iniciar_servidor_automatico_https.bat\"" /sc onstart /ru SYSTEM /rl HIGHEST /f
```

Para iniciar agora sem reiniciar:
```cmd
schtasks /run /tn "Inspecoes MPDFT - Servidor"
```

---

## 7. Avisar os colegas

O novo endereço passa a ser:
```
https://<IP-DA-VM>:8443
```
(antes era `http://<IP>:8080`)

---

## Resumo das portas

| Protocolo | Porta | Quando usar |
|---|---|---|
| HTTP  | 8080 | Versão antiga (sem PWA offline) — pode desativar |
| HTTPS | 8443 | Nova versão (com PWA offline funcionando) |

## Observações

- A chave `key.pem` **nunca** deve ser compartilhada nem enviada ao GitHub
  (já está no `.gitignore`).
- O certificado vale **10 anos** — não precisa renovar tão cedo.
- Se um dia a TI do MPDFT emitir um certificado da CA interna, basta substituir
  `cert.pem`/`key.pem` e os dispositivos do MPDFT já confiarão automaticamente
  (sem a etapa 5 em cada aparelho).
