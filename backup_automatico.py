"""
Backup automático do sistema de Inspeções Prediais MPDFT.

Gera um arquivo ZIP contendo o banco de dados (db.sqlite3) e todas as
fotos (pasta media). Mantém apenas os backups dos últimos DIAS_MANTER dias,
removendo automaticamente os mais antigos.

Uso manual:  python backup_automatico.py
Uso agendado: chamado pelo backup_automatico.bat via Agendador de Tarefas.
"""
import os
import sys
import glob
import zipfile
import datetime

# ── Configurações (ajuste se necessário) ──────────────────────────────────────
BASE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(BASE, 'src')
DB = os.path.join(SRC, 'db.sqlite3')
MEDIA = os.path.join(SRC, 'media')

# Pasta onde os backups são salvos.
# DICA: para mais segurança, aponte para outro disco ou pasta de rede,
# por exemplo: DESTINO = r'\\servidor\backups\inspecoes'
DESTINO = os.path.join(BASE, 'Backups_Automaticos')

# Quantos dias de backups manter (os mais antigos são apagados)
DIAS_MANTER = 30
# ──────────────────────────────────────────────────────────────────────────────


def log(msg):
    carimbo = datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')
    print(f'[{carimbo}] {msg}')


def gerar_backup():
    os.makedirs(DESTINO, exist_ok=True)
    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    nome = f'backup_inspecoes_{ts}.zip'
    caminho = os.path.join(DESTINO, nome)

    if not os.path.exists(DB):
        log(f'ERRO: banco de dados não encontrado em {DB}')
        return None

    with zipfile.ZipFile(caminho, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.write(DB, 'db.sqlite3')
        if os.path.isdir(MEDIA):
            for root, _, files in os.walk(MEDIA):
                for f in files:
                    full = os.path.join(root, f)
                    rel = os.path.relpath(full, SRC)
                    zf.write(full, rel)

    tamanho_kb = os.path.getsize(caminho) // 1024
    log(f'Backup criado: {nome} ({tamanho_kb} KB)')
    return caminho


def limpar_antigos():
    limite = datetime.datetime.now() - datetime.timedelta(days=DIAS_MANTER)
    removidos = 0
    for antigo in glob.glob(os.path.join(DESTINO, 'backup_inspecoes_*.zip')):
        mtime = datetime.datetime.fromtimestamp(os.path.getmtime(antigo))
        if mtime < limite:
            try:
                os.remove(antigo)
                removidos += 1
                log(f'Backup antigo removido: {os.path.basename(antigo)}')
            except OSError as e:
                log(f'Não foi possível remover {os.path.basename(antigo)}: {e}')
    if removidos == 0:
        log('Nenhum backup antigo para remover.')


def main():
    log('=== Iniciando backup automático ===')
    try:
        caminho = gerar_backup()
        if caminho:
            limpar_antigos()
            log('=== Backup concluído com sucesso ===')
            return 0
        else:
            log('=== Backup FALHOU ===')
            return 1
    except Exception as e:
        log(f'ERRO inesperado: {e}')
        return 1


if __name__ == '__main__':
    sys.exit(main())
