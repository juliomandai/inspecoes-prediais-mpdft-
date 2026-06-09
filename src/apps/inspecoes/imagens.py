"""Compressão e otimização de imagens no momento do salvamento.

As fotos vindas da câmera de celulares/tablets chegam na resolução original
(vários MB cada). Aqui elas são reorientadas (EXIF), redimensionadas e
recodificadas como JPEG otimizado, reduzindo drasticamente o tamanho sem
perda perceptível para os registros técnicos de inspeção.
"""
import io
import os

from PIL import Image, ImageOps
from django.core.files.base import ContentFile

# Maior lado da imagem (em pixels). 2000 px preserva detalhes para leitura
# técnica (trincas, etiquetas, displays) e ainda gera arquivos pequenos.
MAX_DIMENSAO = 2000

# Qualidade JPEG (0–95). 80 é visualmente quase indistinguível do original.
QUALIDADE_JPEG = 80


def comprimir_imagem(dados_bytes, nome_original):
    """Comprime/otimiza uma imagem.

    Recebe os ``bytes`` da imagem e o nome original; devolve uma tupla
    ``(ContentFile, nome, tamanho_bytes)`` pronta para gravar num ImageField.

    Se a imagem não puder ser processada (formato exótico, arquivo corrompido),
    devolve o conteúdo original intacto — nunca perde a foto.
    """
    try:
        img = Image.open(io.BytesIO(dados_bytes))

        # Corrige a orientação gravada nos metadados EXIF da câmera, senão a
        # foto pode aparecer deitada após a recodificação.
        img = ImageOps.exif_transpose(img)

        # JPEG não tem canal alfa: achata transparência sobre fundo branco.
        if img.mode in ('RGBA', 'LA', 'P'):
            img = img.convert('RGBA')
            fundo = Image.new('RGB', img.size, (255, 255, 255))
            fundo.paste(img, mask=img.split()[-1])
            img = fundo
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        # Reduz o maior lado para MAX_DIMENSAO (mantém proporção). Só encolhe,
        # nunca amplia.
        img.thumbnail((MAX_DIMENSAO, MAX_DIMENSAO), Image.LANCZOS)

        buffer = io.BytesIO()
        img.save(
            buffer,
            format='JPEG',
            quality=QUALIDADE_JPEG,
            optimize=True,
            progressive=True,
        )
        dados_saida = buffer.getvalue()

        base = os.path.splitext(nome_original or 'foto')[0] or 'foto'
        nome = f'{base}.jpg'
        return ContentFile(dados_saida, name=nome), nome, len(dados_saida)
    except Exception:
        # Fallback: preserva o arquivo original sem alteração.
        nome = nome_original or 'foto.jpg'
        return ContentFile(dados_bytes, name=nome), nome, len(dados_bytes)
