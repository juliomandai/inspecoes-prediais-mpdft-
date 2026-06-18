# -*- coding: utf-8 -*-
"""Gerador do PDF explicativo do Sistema de Inspeções Prediais — MPDFT.

Reconstrói o documento institucional (ReportLab/Platypus) já com as
funcionalidades implementadas em junho/2026: módulo Acompanhamento,
duplicação de achados, visualização somente leitura, múltiplos
profissionais por especialidade, datas futuras e conclusão/subvisitas.
"""
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, PageBreak,
    Table, TableStyle, NextPageTemplate, KeepTogether, HRFlowable,
)
from reportlab.platypus.tableofcontents import TableOfContents

AQUI = os.path.dirname(os.path.abspath(__file__))
SAIDA = os.path.join(AQUI, 'Sistema_Inspecoes_Prediais_MPDFT.pdf')

AZUL = colors.HexColor('#0b3d6b')
AZUL_CLARO = colors.HexColor('#1d5a92')
VERDE = colors.HexColor('#2e7d32')
CINZA = colors.HexColor('#4a4a4a')
CINZA_CLARO = colors.HexColor('#f1f4f8')
CINZA_BORDA = colors.HexColor('#d4dbe4')

styles = getSampleStyleSheet()


def S(name, **kw):
    base = kw.pop('parent', styles['Normal'])
    return ParagraphStyle(name, parent=base, **kw)


body = S('Body', fontName='Times-Roman', fontSize=10.5, leading=15.5,
         alignment=TA_JUSTIFY, spaceAfter=6, textColor=colors.HexColor('#1a1a1a'))
bullet = S('Bullet', parent=body, leftIndent=16, bulletIndent=2, spaceAfter=4)
h1 = S('H1', fontName='Helvetica-Bold', fontSize=16, leading=20, textColor=AZUL,
       spaceBefore=18, spaceAfter=10, keepWithNext=1)
h2 = S('H2', fontName='Helvetica-Bold', fontSize=12.5, leading=16, textColor=AZUL_CLARO,
       spaceBefore=12, spaceAfter=6, keepWithNext=1)
nota_style = S('Nota', parent=body, fontSize=9.8, leading=14, textColor=CINZA, spaceAfter=0)
cell = S('Cell', fontName='Times-Roman', fontSize=9.3, leading=12.5, alignment=TA_LEFT)
cell_b = S('CellB', parent=cell, fontName='Times-Bold')
cell_head = S('CellHead', fontName='Helvetica-Bold', fontSize=9.3, leading=12.5,
              textColor=colors.white, alignment=TA_LEFT)

cover_min = S('CoverMin', fontName='Helvetica', fontSize=11, leading=16,
              alignment=TA_CENTER, textColor=CINZA, spaceAfter=0)
cover_title = S('CoverTitle', fontName='Helvetica-Bold', fontSize=28, leading=34,
                alignment=TA_CENTER, textColor=AZUL)
cover_sub = S('CoverSub', fontName='Helvetica', fontSize=13.5, leading=19,
              alignment=TA_CENTER, textColor=AZUL_CLARO)
cover_desc = S('CoverDesc', parent=body, fontSize=10.5, alignment=TA_CENTER,
               textColor=CINZA)

benef_num = S('BenefNum', fontName='Helvetica-Bold', fontSize=15, leading=17,
              textColor=colors.white, alignment=TA_CENTER)
benef_titulo = S('BenefTit', fontName='Helvetica-Bold', fontSize=11, leading=14,
                 textColor=AZUL, spaceAfter=2)
benef_corpo = S('BenefCorpo', parent=body, fontSize=9.8, leading=13.5, spaceAfter=0)


def p(txt, st=body):
    return Paragraph(txt, st)


def lista(itens, st=bullet):
    return [Paragraph(f'<font color="#2e7d32">▪</font>&nbsp;&nbsp;{i}', st) for i in itens]


def tabela(dados, larguras, header=True):
    linhas = []
    for r, linha in enumerate(dados):
        nova = []
        for cval in linha:
            if isinstance(cval, Paragraph):
                nova.append(cval)
            else:
                est = cell_head if (header and r == 0) else cell
                nova.append(Paragraph(str(cval), est))
        linhas.append(nova)
    t = Table(linhas, colWidths=larguras, repeatRows=1 if header else 0)
    estilo = [
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('GRID', (0, 0), (-1, -1), 0.5, CINZA_BORDA),
    ]
    if header:
        estilo += [
            ('BACKGROUND', (0, 0), (-1, 0), AZUL),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, CINZA_CLARO]),
        ]
    else:
        estilo += [('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, CINZA_CLARO])]
    t.setStyle(TableStyle(estilo))
    return t


def caixa_nota(rotulo, texto):
    """Caixa de destaque (fundo claro, faixa verde à esquerda)."""
    conteudo = Paragraph(f'<b><font color="#2e7d32">{rotulo}:</font></b> {texto}', nota_style)
    t = Table([[conteudo]], colWidths=[16.4 * cm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), CINZA_CLARO),
        ('LINEBEFORE', (0, 0), (0, -1), 3, VERDE),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
    ]))
    return t


def beneficio(num, titulo, corpo):
    badge = Table([[Paragraph(num, benef_num)]], colWidths=[1.1 * cm], rowHeights=[1.1 * cm])
    badge.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), VERDE),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0), ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    texto = [Paragraph(titulo, benef_titulo), Paragraph(corpo, benef_corpo)]
    linha = Table([[badge, texto]], colWidths=[1.5 * cm, 14.9 * cm])
    linha.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (0, 0), 0),
        ('LEFTPADDING', (1, 0), (1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 2), ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    return KeepTogether(linha)


# ── Documento com cabeçalho/rodapé e TOC ──────────────────────────────────────
class Doc(BaseDocTemplate):
    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph):
            st = flowable.style.name
            txt = flowable.getPlainText()
            if st == 'H1':
                self.notify('TOCEntry', (0, txt, self.page))
            elif st == 'H2':
                self.notify('TOCEntry', (1, txt, self.page))


def header_footer(canvas, doc):
    canvas.saveState()
    w, h = A4
    canvas.setFont('Helvetica-Bold', 8.5)
    canvas.setFillColor(AZUL)
    canvas.drawString(2 * cm, h - 1.25 * cm, 'MPDFT — Sistema de Inspeções Prediais')
    canvas.setFont('Helvetica', 7.5)
    canvas.setFillColor(CINZA)
    canvas.drawString(2 * cm, h - 1.58 * cm, 'Ministério Público do Distrito Federal e Territórios')
    canvas.setFont('Helvetica', 8.5)
    canvas.setFillColor(AZUL)
    canvas.drawRightString(w - 2 * cm, h - 1.25 * cm, f'Página {doc.page}')
    canvas.setStrokeColor(CINZA_BORDA)
    canvas.setLineWidth(0.6)
    canvas.line(2 * cm, h - 1.75 * cm, w - 2 * cm, h - 1.75 * cm)
    # rodapé
    canvas.setStrokeColor(CINZA_BORDA)
    canvas.line(2 * cm, 1.4 * cm, w - 2 * cm, 1.4 * cm)
    canvas.setFont('Helvetica', 7)
    canvas.setFillColor(CINZA)
    canvas.drawCentredString(w / 2, 1.05 * cm,
                             'Documento interno — Secretaria de Engenharia / MPDFT')
    canvas.restoreState()


def cover_page(canvas, doc):
    canvas.saveState()
    w, h = A4
    canvas.setFillColor(AZUL)
    canvas.rect(0, h - 4.2 * cm, w, 4.2 * cm, fill=1, stroke=0)
    canvas.setFillColor(VERDE)
    canvas.rect(0, h - 4.35 * cm, w, 0.15 * cm, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont('Helvetica', 12)
    canvas.drawCentredString(w / 2, h - 2.0 * cm, 'MINISTÉRIO PÚBLICO DO DISTRITO FEDERAL E TERRITÓRIOS')
    canvas.setFont('Helvetica', 9.5)
    canvas.drawCentredString(w / 2, h - 2.7 * cm, 'Secretaria de Engenharia')
    canvas.restoreState()


def build():
    w, h = A4
    doc = Doc(SAIDA, pagesize=A4, title='Sistema de Inspeções Prediais — MPDFT',
              author='MPDFT — Engenharia',
              subject='Plataforma Digital de Gestão e Análise de Inspeções de Edificações',
              leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2.2 * cm, bottomMargin=1.8 * cm)

    frame_cover = Frame(2 * cm, 1.8 * cm, w - 4 * cm, h - 6 * cm, id='cover')
    frame_body = Frame(2 * cm, 1.8 * cm, w - 4 * cm, h - 4 * cm, id='body')
    doc.addPageTemplates([
        PageTemplate(id='cover', frames=[frame_cover], onPage=cover_page),
        PageTemplate(id='body', frames=[frame_body], onPage=header_footer),
    ])

    st = []
    # ── CAPA ──────────────────────────────────────────────────────────────────
    st.append(Spacer(1, 3.8 * cm))
    st.append(p('SISTEMA DE INSPEÇÕES PREDIAIS', cover_title))
    st.append(Spacer(1, 0.3 * cm))
    st.append(p('Plataforma Digital de Gestão e Análise de Inspeções de Edificações', cover_sub))
    st.append(Spacer(1, 1.4 * cm))
    st.append(HRFlowable(width='35%', thickness=2, color=VERDE, spaceAfter=18, hAlign='CENTER'))
    desc = ('Documento elaborado para apresentação interna da plataforma digital de inspeções '
            'prediais desenvolvida para o MPDFT. Destinado a gestores e servidores responsáveis '
            'pelas unidades prediais do Ministério Público.')
    cx = Table([[p(desc, cover_desc)]], colWidths=[13 * cm])
    cx.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), CINZA_CLARO),
        ('BOX', (0, 0), (-1, -1), 0.5, CINZA_BORDA),
        ('LEFTPADDING', (0, 0), (-1, -1), 18), ('RIGHTPADDING', (0, 0), (-1, -1), 18),
        ('TOPPADDING', (0, 0), (-1, -1), 14), ('BOTTOMPADDING', (0, 0), (-1, -1), 14),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ]))
    st.append(cx)
    st.append(Spacer(1, 2.2 * cm))
    st.append(p('Edição revisada — Junho de 2026', S('Ed', parent=cover_desc, fontSize=9.5,
                                                      textColor=AZUL_CLARO)))

    st.append(NextPageTemplate('body'))
    st.append(PageBreak())

    # ── SUMÁRIO ────────────────────────────────────────────────────────────────
    st.append(p('SUMÁRIO', S('TocTit', fontName='Helvetica-Bold', fontSize=15,
                             textColor=AZUL, spaceAfter=12)))
    toc = TableOfContents()
    toc.levelStyles = [
        S('TOC0', fontName='Helvetica-Bold', fontSize=10.5, leading=18, textColor=AZUL,
          spaceBefore=4),
        S('TOC1', fontName='Times-Roman', fontSize=10, leading=15, leftIndent=18,
          textColor=CINZA),
    ]
    st.append(toc)
    st.append(PageBreak())

    # ════════════════════════════════════════════════════════════════════════════
    # 1. VISÃO GERAL
    # ════════════════════════════════════════════════════════════════════════════
    st.append(p('1. Visão Geral da Aplicação', h1))
    st.append(p(
        'O <b>Sistema de Inspeções Prediais do MPDFT</b> é uma aplicação web desenvolvida em '
        'Django (Python) para gerenciar, registrar, analisar e acompanhar inspeções técnicas das '
        'edificações do Ministério Público do Distrito Federal e Territórios. A plataforma '
        'substitui planilhas e processos manuais por um fluxo digital, estruturado e rastreável, '
        'que abrange desde o cadastro dos achados em campo até a geração de análises estatísticas '
        'completas, relatórios em PDF e o acompanhamento do ciclo de vida de cada achado até sua '
        'efetiva solução.'))
    st.append(p(
        'O sistema foi projetado para ser utilizado em campo pelos servidores durante as '
        'inspeções, com suporte a funcionamento <b>offline</b> via Progressive Web App (PWA), '
        'permitindo o registro de achados mesmo sem conexão à rede MPDFT, com sincronização '
        'automática ao reconectar.'))

    st.append(p('Tecnologias Utilizadas', h2))
    st.append(tabela([
        ['Camada', 'Tecnologia', 'Função'],
        ['Back-end', 'Django 5.2 + Python', 'Lógica de negócio, modelos de dados, APIs, geração de PDFs'],
        ['Banco de dados', 'SQLite', 'Armazenamento local no servidor — simples e robusto para o volume esperado'],
        ['Front-end', 'Bootstrap 5.3 + Chart.js', 'Interface responsiva, gráficos interativos (rosca, barras, Pareto)'],
        ['Geração de PDF', 'xhtml2pdf + Pillow', 'Renderização server-side; gráficos convertidos em imagem PNG para o PDF'],
        ['Modo Offline', 'PWA (Service Worker)', 'Cache de telas, registro offline, sincronização via API REST'],
        ['Servidor Web', 'Waitress + WhiteNoise', 'Servidor WSGI nativo Windows; entrega de arquivos estáticos sem Nginx'],
        ['Ambiente', 'Windows Server 2019', 'Deploy nativo (sem Docker), compatível com a infraestrutura do MPDFT'],
    ], [3 * cm, 4 * cm, 9.4 * cm]))

    st.append(p('Principais Módulos da Plataforma', h2))
    st.extend(lista([
        '<b>Gestão de Inspeções:</b> criação, acompanhamento e finalização de inspeções por '
        'edificação, com controle de status por especialidade.',
        '<b>Registro de Achados:</b> formulário estruturado para registro de verificações em '
        'campo, com análise GUT, classificação de risco, fotos de evidência e recomendações técnicas.',
        '<b>Análise e Indicadores:</b> dashboard de análise com 16 indicadores e gráficos, '
        'incluindo IQE, Pareto, matriz risco×prazo, cobertura fotográfica e plano de ação automático.',
        '<b>Acompanhamento (novo):</b> visão consolidada de todos os achados de todas as inspeções, '
        'organizados por categoria de encaminhamento, com registro de tratativas, reclassificação '
        'rastreável e painel gerencial do ciclo de vida.',
        '<b>Relatórios PDF:</b> geração de relatórios em PDF no servidor, com gráficos renderizados '
        'como imagem e tabelas completas de achados.',
        '<b>Visitas Técnicas:</b> registro de visitas a campo (fora do ciclo de inspeção formal), '
        'com conclusão, subvisitas de acompanhamento e histórico por edificação e disciplina.',
        '<b>Backup e Restauração:</b> backup automático diário no servidor e restauração de '
        'inspeções completas (dados JSON + fotos) em qualquer ambiente.',
        '<b>Controle de Acesso:</b> autenticação obrigatória, cadastro restrito a e-mails '
        '@mpdft.mp.br e log de auditoria de todos os eventos.',
    ]))
    st.append(PageBreak())

    # ════════════════════════════════════════════════════════════════════════════
    # 2. FLUXO DE TRABALHO
    # ════════════════════════════════════════════════════════════════════════════
    st.append(p('2. Fluxo de Trabalho — Passo a Passo', h1))
    st.append(p(
        'O sistema organiza o processo de inspeção predial em etapas sequenciais, garantindo que '
        'todos os dados sejam coletados de forma padronizada antes da geração das análises e do '
        'acompanhamento das tratativas.'))

    etapas = [
        ('Etapa 1', 'Criar a Inspeção',
         'O usuário seleciona a edificação no cadastro do MPDFT e registra uma nova inspeção. A '
         'data de criação pode ser definida livremente — inclusive futura —, permitindo o '
         'pré-cadastro de uma inspeção antes do deslocamento a campo. Uma edificação pode ter '
         'múltiplas inspeções ao longo do tempo, formando um histórico.'),
        ('Etapa 2', 'Registrar Especialidades',
         'Para cada disciplina a ser inspecionada, o usuário cadastra a especialidade informando '
         'a data de realização e <b>um ou mais profissionais responsáveis</b> pela inspeção. '
         'Estão disponíveis três especialidades: Engenharia Civil, Engenharia Mecânica e '
         'Engenharia Elétrica. A inspeção permanece "Em andamento" enquanto ao menos uma '
         'especialidade não for finalizada.'),
        ('Etapa 3', 'Registrar Achados em Campo',
         'Esta é a etapa central. Dentro de cada especialidade, o servidor responsável registra os '
         'achados — todas as verificações realizadas nos sistemas prediais. Cada achado inclui '
         'localização, item verificado, grupo técnico, status de conformidade e, para os não '
         'conformes, análise GUT completa, prioridade de risco, recomendação técnica, '
         'direcionamento e fotos de evidência. Achados semelhantes podem ser <b>duplicados</b> '
         'para agilizar o preenchimento, mantendo o item de verificação e alterando apenas a '
         'localização. O formulário pode ser preenchido offline em campo.'),
        ('Etapa 4', 'Finalizar Especialidade',
         'Ao concluir o levantamento de uma disciplina, o servidor finaliza a especialidade. A '
         'partir desse momento, os achados daquela especialidade ficam bloqueados para edição, '
         'garantindo a integridade dos dados — mas permanecem disponíveis para <b>consulta '
         'somente leitura</b>. Quando todas as especialidades são finalizadas, a inspeção recebe '
         'automaticamente o status "Finalizada".'),
        ('Etapa 5', 'Análise e Relatórios',
         'Com os dados coletados, o sistema gera automaticamente o painel de análise com '
         'indicadores, gráficos e o plano de ação priorizado. Os relatórios em PDF podem ser '
         'gerados a qualquer momento e distribuídos às equipes responsáveis, à administração do '
         'MPDFT ou utilizados como embasamento para processos de contratação.'),
        ('Etapa 6', 'Acompanhamento e Tratativa',
         'Após a análise, o módulo <b>Acompanhamento</b> consolida os achados de todas as '
         'inspeções e permite controlar a tratativa de cada não conformidade — abertura de Ordem '
         'de Serviço, mudança de status de execução e reclassificação de encaminhamento — até a '
         'efetiva solução, encerrando o ciclo de vida do achado.'),
    ]
    for rot, tit, txt in etapas:
        cabec = Paragraph(f'<b>{rot}</b>', S('EtRot', fontName='Helvetica-Bold', fontSize=10,
                                             textColor=colors.white, alignment=TA_CENTER))
        titulo = Paragraph(tit, S('EtTit', fontName='Helvetica-Bold', fontSize=11.5,
                                  textColor=AZUL, spaceAfter=3))
        corpo = Paragraph(txt, benef_corpo)
        badge = Table([[cabec]], colWidths=[2.2 * cm], rowHeights=[0.8 * cm])
        badge.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), AZUL),
                                   ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')]))
        linha = Table([[badge, [titulo, corpo]]], colWidths=[2.5 * cm, 13.9 * cm])
        linha.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (1, 0), (1, 0), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ]))
        st.append(KeepTogether(linha))
    st.append(PageBreak())

    # ════════════════════════════════════════════════════════════════════════════
    # 3. MODELO DE ACHADO
    # ════════════════════════════════════════════════════════════════════════════
    st.append(p('3. Modelo de Achado — Dados Coletados em Campo', h1))
    st.append(p(
        'O <b>Achado</b> é a unidade fundamental de dado do sistema. Cada achado representa uma '
        'verificação técnica realizada durante a inspeção — seja um item em conformidade ou uma '
        'não conformidade identificada. A seguir são descritos todos os campos que compõem o '
        'modelo de achado.'))

    st.append(p('3.1 — Identificação e Localização', h2))
    st.append(tabela([
        ['Campo', 'Descrição', 'Exemplo'],
        ['Localização', 'Local físico dentro da edificação', 'Bloco A, Térreo, Cobertura'],
        ['Sub-localização', 'Detalhe complementar da localização', 'Banheiro masculino, Sala 101'],
        ['Verificação', 'Descrição do item inspecionado', 'Condição das esquadrias externas'],
    ], [3.4 * cm, 7.5 * cm, 5.5 * cm]))
    st.append(Spacer(1, 4))
    st.append(caixa_nota('Duplicação de achados',
        'Um achado já salvo pode ser duplicado: o item de verificação e os demais dados técnicos '
        'são mantidos, exigindo apenas a definição de uma nova localização. Isso acelera o '
        'registro de uma mesma não conformidade que se repete em vários pontos da edificação.'))

    st.append(p('3.2 — Classificação Técnica (Grupos)', h2))
    st.append(p('Cada achado é classificado em um grupo técnico, correspondente ao sistema '
                'construtivo ou instalação inspecionada. Os grupos disponíveis são:'))
    st.append(tabela([
        ['Grupo Técnico', 'Abrangência Típica'],
        ['Esquadrias', 'Portas, janelas, portões, fachadas envidraçadas'],
        ['Instalações Hidrossanitárias', 'Água fria, quente, esgoto, pluvial, gás'],
        ['Acabamento', 'Pisos, revestimentos, pintura, forros, louças'],
        ['Instalações Mecânicas', 'Ar-condicionado, elevadores, bombas, climatização'],
        ['Instalações Elétricas', 'Quadros, cabeamento, iluminação, SPDA, CFTV'],
        ['Estrutura', 'Fundações, lajes, pilares, vigas, estruturas de concreto e aço'],
        ['Impermeabilização', 'Coberturas, calhas, terraços, áreas molhadas, fundações'],
        ['Cobertura', 'Telhados, rufos, calhas, telhas, domos e policarbonatos'],
        ['Equipamentos Prediais', 'Geradores, no-breaks, bombas de recalque, cisternas'],
        ['Acessibilidade', 'Rampas, banheiros acessíveis, sinalizações, elevadores de acesso'],
        ['Outros', 'Itens que não se enquadram nas categorias anteriores'],
    ], [5.6 * cm, 10.8 * cm]))

    st.append(p('3.3 — Status de Conformidade', h2))
    st.append(p(
        'Cada achado indica se o item verificado está <b>em conformidade</b> ou representa uma '
        '<b>não conformidade</b>. Itens em conformidade documentam que a verificação foi realizada '
        'e o sistema está adequado, dispensando o preenchimento da análise GUT. As não '
        'conformidades exigem a avaliação técnica completa descrita a seguir.'))

    st.append(p('3.4 — Análise GUT — Gravidade, Urgência e Tendência', h2))
    st.append(p(
        'Para cada não conformidade, o servidor atribui três notas de 1 a 5 segundo a metodologia '
        '<b>GUT</b>: <b>Gravidade</b> (impacto do problema), <b>Urgência</b> (pressão do tempo '
        'para agir) e <b>Tendência</b> (evolução caso nada seja feito). O índice GUT é o produto '
        'das três notas (G × U × T), variando de 1 a 125, e ordena objetivamente a criticidade '
        'dos achados.'))

    st.append(p('3.5 — Prioridade de Risco', h2))
    st.append(p(
        'Complementarmente ao índice GUT, o achado recebe uma classificação de prioridade: '
        '<b>P1 — Crítico</b>, <b>P2 — Regular</b> ou <b>P3 — Mínimo</b>. A prioridade orienta a '
        'ordenação do plano de ação e os alertas de incoerência da matriz risco×prazo.'))

    st.append(p('3.6 — Requisito de Desempenho Afetado', h2))
    st.append(p(
        'Indica qual requisito de desempenho da edificação é comprometido pela não conformidade '
        '(segurança estrutural, acessibilidade, saúde e qualidade do ar, funcionalidade, estética, '
        'eficiência energética, sustentabilidade ou durabilidade), permitindo análises por '
        'requisito.'))

    st.append(p('3.7 — Direcionamento (Encaminhamento)', h2))
    st.append(p(
        'Define a forma de tratamento da não conformidade, em três categorias: <b>Garantia de '
        'obra</b> (acionamento da construtora), <b>Manutenção</b> (equipe própria ou contrato de '
        'manutenção) e <b>Nova contratação</b> (serviço especializado a contratar). O '
        'direcionamento é a base do módulo de Acompanhamento e <b>pode ser reclassificado</b> a '
        'qualquer momento, com registro em histórico (ver seção 6).'))

    st.append(p('3.8 — Prazo para Resolução', h2))
    st.append(p(
        'Estimativa do prazo recomendado para tratamento da não conformidade (1, 3, 6, 12, 18 ou '
        '24 meses). Combinado à prioridade de risco, alimenta a matriz risco×prazo e o '
        'planejamento orçamentário.'))
    st.append(PageBreak())

    # ════════════════════════════════════════════════════════════════════════════
    # 4. MÓDULO DE ANÁLISE
    # ════════════════════════════════════════════════════════════════════════════
    st.append(p('4. Módulo de Análise — Indicadores e Gráficos', h1))
    st.append(p(
        'Concluído o registro dos achados, o sistema gera automaticamente um painel de análise '
        'com 16 indicadores e gráficos. Todos são calculados em tempo real a partir dos dados '
        'coletados, sem qualquer pós-processamento manual. As seções a seguir resumem cada '
        'indicador.'))

    analises = [
        ('4.1 — IQE — Índice de Qualidade da Edificação',
         'Índice sintético de 0 a 100 que resume o estado geral da edificação, penalizando os '
         'achados por severidade (P1 pesa mais que P2 e P3). Apresenta faixa qualitativa '
         '(Bom / Atenção / Crítico) e permite comparação entre edificações e campanhas.'),
        ('4.2 — Percentual de Conformidade',
         'Proporção de itens verificados que estão em conformidade em relação ao total inspecionado.'),
        ('4.3 — Distribuição de Risco (Gráfico de Rosca)',
         'Gráfico de rosca com a contagem de não conformidades por prioridade (P1, P2, P3).'),
        ('4.4 — Componentes GUT Médios (G, U, T Isolados)',
         'Médias separadas de Gravidade, Urgência e Tendência, revelando qual fator predomina.'),
        ('4.5 — Estatísticas do Índice GUT',
         'Média, máximo, mínimo e desvio-padrão do índice GUT do conjunto de achados.'),
        ('4.6 — Top 10 Achados por GUT',
         'Ranking das dez não conformidades mais críticas, com barra proporcional ao índice GUT.'),
        ('4.7 — Análise por Grupo Técnico',
         'Contagem de P1/P2/P3 por sistema construtivo, identificando onde se concentram os problemas.'),
        ('4.8 — Pareto por Grupo Técnico — Análise 80/20',
         'Curva de Pareto com o percentual acumulado de não conformidades por grupo técnico.'),
        ('4.9 — Matriz Risco × Prazo',
         'Cruzamento entre prioridade de risco e prazo, destacando incoerências (P1 com prazo '
         'longo) e ganhos rápidos (P1/P2 com prazo curto).'),
        ('4.10 — Análise de Encaminhamento (Direcionamento)',
         'Distribuição dos achados entre garantia, manutenção e nova contratação.'),
        ('4.11 — Concentração de Risco por Localização',
         'Localizações ordenadas pela soma do GUT, revelando os pontos mais críticos da edificação.'),
        ('4.12 — Análise por Prazo de Resolução',
         'Distribuição das não conformidades pelos prazos recomendados.'),
        ('4.13 — Análise por Requisito Afetado',
         'Distribuição dos achados pelos requisitos de desempenho comprometidos.'),
        ('4.14 — Cobertura Fotográfica das Evidências',
         'Percentual de não conformidades com ao menos uma foto, indicador da robustez probatória.'),
        ('4.15 — Plano de Ação Priorizado',
         'Lista automática das 15 não conformidades mais críticas, ordenadas por prioridade e GUT, '
         'pronta para uso como checklist de trabalho.'),
        ('4.16 — Análise por Especialidade',
         'Todos os indicadores acima também disponíveis por disciplina (Civil, Mecânica, Elétrica), '
         'permitindo avaliação independente de cada área técnica.'),
    ]
    for tit, txt in analises:
        st.append(p(tit, h2))
        st.append(p(txt))
    st.append(Spacer(1, 4))
    st.append(caixa_nota('Pronto para usar',
        'O Plano de Ação gerado automaticamente pode ser utilizado diretamente como documento de '
        'referência para reuniões de planejamento de manutenção, briefings com contratadas ou '
        'justificativas técnicas para processos de compras, sem nenhum pós-processamento manual.'))
    st.append(PageBreak())

    # ════════════════════════════════════════════════════════════════════════════
    # 5. RELATÓRIOS EM PDF
    # ════════════════════════════════════════════════════════════════════════════
    st.append(p('5. Relatórios em PDF', h1))
    st.append(p(
        'O sistema gera relatórios em PDF diretamente no servidor, sem dependência de programas '
        'externos como Microsoft Word, LibreOffice ou Adobe Acrobat. A geração é realizada via '
        'xhtml2pdf, com gráficos convertidos em imagens PNG pelo Pillow — garantindo fidelidade '
        'visual e funcionamento confiável em ambiente Windows Server 2019.'))
    st.append(tabela([
        ['Bloco do Relatório', 'Conteúdo'],
        ['Cabeçalho', 'Nome da edificação, especialidade (ou "Análise Geral"), data de geração'],
        ['Resumo Executivo', 'IQE, % de conformidade, total de achados, contagem P1/P2/P3'],
        ['Gráficos como Imagem', 'Rosca de risco, barras por grupo técnico, Pareto, matriz '
         'risco×prazo e encaminhamento — renderizados pelo Pillow'],
        ['Tabela de Não Conformidades', 'Lista completa de achados com localização, GUT, '
         'prioridade, prazo e direcionamento'],
        ['Análise por Grupo Técnico', 'Contagem de P1/P2/P3 por sistema construtivo'],
        ['Análise por Localização', 'Locais ordenados por soma GUT'],
        ['Plano de Ação Priorizado', 'Top 15 achados críticos com dados para ação imediata'],
    ], [5.2 * cm, 11.2 * cm]))
    st.append(Spacer(1, 6))
    st.append(p(
        'O relatório PDF pode ser gerado a qualquer momento — mesmo com a inspeção ainda em '
        'andamento — e está disponível para download direto pelo navegador, sem necessidade de '
        'instalar qualquer software adicional na estação de trabalho.'))
    st.append(PageBreak())

    # ════════════════════════════════════════════════════════════════════════════
    # 6. MÓDULO DE ACOMPANHAMENTO  (NOVO)
    # ════════════════════════════════════════════════════════════════════════════
    st.append(p('6. Módulo de Acompanhamento — Ciclo de Vida dos Achados', h1))
    st.append(p(
        'O módulo <b>Acompanhamento</b>, acessível na barra superior ao lado de "Visitas", '
        'transforma a plataforma em uma ferramenta de gestão das ações decorrentes das inspeções. '
        'Ele <b>consolida automaticamente todos os achados de todas as inspeções</b> — '
        'independentemente da localidade ou da data — e permite controlar o ciclo de vida de cada '
        'não conformidade, desde sua identificação até a solução efetiva.'))

    st.append(p('6.1 — Categorias de Encaminhamento', h2))
    st.append(p(
        'Os achados são organizados em três categorias de tratamento, com navegação direta entre '
        'elas. Cada categoria exibe a quantidade de achados associados:'))
    st.extend(lista([
        '<b>Garantia de obra</b> — problemas a serem acionados junto à construtora dentro do '
        'período de garantia.',
        '<b>Manutenção</b> — itens tratáveis pela equipe própria ou por contrato de manutenção.',
        '<b>Nova contratação</b> — serviços especializados que demandam contratação específica.',
    ]))

    st.append(p('6.2 — Filtros de Pesquisa', h2))
    st.append(p(
        'Dentro de cada categoria — e também na visão consolidada de todas elas — o usuário pode '
        'filtrar os achados, de forma combinada, pelos seguintes critérios:'))
    st.extend(lista([
        '<b>Localidade</b> — edificação onde o achado foi registrado.',
        '<b>Especialidade</b> — Engenharia Civil, Mecânica ou Elétrica.',
        '<b>Status</b> — Pendente, Em andamento ou Finalizado.',
    ]))
    st.append(p(
        'Os filtros podem ser utilizados simultaneamente, permitindo, por exemplo, localizar todos '
        'os achados de manutenção, da Engenharia Elétrica, de uma promotoria específica, que ainda '
        'estão pendentes.'))

    st.append(p('6.3 — Tratativa da Categoria Manutenção', h2))
    st.append(p(
        'Para os achados classificados como <b>Manutenção</b>, o módulo registra os dados de '
        'tratativa que permitem acompanhar a ação da equipe responsável:'))
    st.append(tabela([
        ['Campo', 'Descrição'],
        ['Número da OS (Resolve)', 'Identificação da Ordem de Serviço aberta no sistema Resolve'],
        ['Data de abertura da OS', 'Data em que a Ordem de Serviço foi registrada'],
        ['Observações complementares', 'Anotações sobre o andamento da tratativa'],
        ['Status atualizado da execução', 'Pendente, Em andamento ou Finalizado'],
    ], [5.4 * cm, 11 * cm]))

    st.append(p('6.4 — Reclassificação de Encaminhamento', h2))
    st.append(p(
        'O encaminhamento de qualquer achado pode ser alterado após sua criação — por exemplo, um '
        'achado inicialmente classificado como "Manutenção" pode ser reclassificado para "Nova '
        'contratação" ou "Garantia de obra", e vice-versa. Essa flexibilidade é essencial porque, '
        'durante a análise consolidada, pode-se concluir que determinado problema não deve ser '
        'tratado pela equipe de manutenção, exigindo contratação especializada ou acionamento da '
        'garantia da obra.'))

    st.append(p('6.5 — Histórico e Rastreabilidade', h2))
    st.append(p('Toda alteração de encaminhamento é registrada em histórico, armazenando:'))
    st.extend(lista([
        'Usuário responsável pela alteração;',
        'Data e hora da modificação;',
        'Categoria anterior e nova categoria;',
        'Justificativa da alteração.',
    ]))
    st.append(Spacer(1, 4))
    st.append(caixa_nota('Rastreabilidade total',
        'O histórico de reclassificações garante transparência sobre as decisões técnicas: é '
        'sempre possível saber quem alterou o encaminhamento de um achado, quando e por quê — '
        'fortalecendo a sustentação técnica e administrativa das tratativas.'))

    st.append(p('6.6 — Painel Gerencial', h2))
    st.append(p(
        'O módulo apresenta um painel com indicadores consolidados de toda a base de achados, '
        'oferecendo visão imediata da carga de trabalho e do progresso das tratativas:'))
    st.extend(lista([
        'Quantidade total de achados;',
        'Quantidade de achados por categoria de encaminhamento;',
        'Quantidade por status (pendente, em andamento, finalizado);',
        'Quantidade por especialidade;',
        'Quantidade por localidade;',
        'Percentual de conclusão dos achados.',
    ]))
    st.append(p(
        'Os indicadores de status, especialidade e localidade são <b>clicáveis</b>: ao selecionar '
        'qualquer um deles, o sistema abre a lista de achados correspondente já filtrada, '
        'facilitando a navegação do panorama gerencial para o detalhe operacional.'))
    st.append(PageBreak())

    # ════════════════════════════════════════════════════════════════════════════
    # 7. VISITAS TÉCNICAS
    # ════════════════════════════════════════════════════════════════════════════
    st.append(p('7. Visitas Técnicas', h1))
    st.append(p(
        'Além das inspeções formais com metodologia GUT, o sistema registra <b>Visitas '
        'Técnicas</b> — deslocamentos a campo para verificações pontuais, atendimento a demandas '
        'emergenciais, acompanhamento de obras ou reuniões técnicas in loco. As visitas formam um '
        'histórico de campo rastreável por edificação e disciplina.'))
    st.append(tabela([
        ['Campo', 'Descrição'],
        ['Edificação', 'Localidade visitada (vinculada ao cadastro de edificações do MPDFT)'],
        ['Data da visita', 'Data de realização (não pode ser futura)'],
        ['Disciplina', 'Arquitetura, Engenharia Civil, Elétrica, Mecânica ou Multidisciplinar'],
        ['Profissionais participantes', 'Lista de participantes (um por linha)'],
        ['Motivo da visita', 'Descrição da motivação que originou o deslocamento'],
        ['Achados da visita', 'Observações técnicas realizadas durante a visita'],
        ['Conclusões e encaminhamentos', 'Decisões tomadas e próximos passos definidos'],
        ['Fotos', 'Registro fotográfico da visita (JPEG/PNG, compressão automática)'],
    ], [5 * cm, 11.4 * cm]))
    st.append(Spacer(1, 6))
    st.append(p('Conclusão e Subvisitas de Acompanhamento', h2))
    st.append(p(
        'Cada visita possui um botão <b>"Concluído"</b>. Enquanto a visita não for marcada como '
        'concluída, é possível criar <b>subvisitas</b> — novos registros, com data e informações '
        'próprias (incluindo fotos), que documentam a evolução da situação encontrada. Dessa '
        'forma, mantém-se o histórico completo do acompanhamento de um problema até sua solução. '
        'Visitas concluídas podem ser reabertas quando necessário. O log de auditoria registra a '
        'criação, conclusão, reabertura e exclusão de cada visita e subvisita.'))
    st.append(PageBreak())

    # ════════════════════════════════════════════════════════════════════════════
    # 8. FUNCIONALIDADES DE SUPORTE
    # ════════════════════════════════════════════════════════════════════════════
    st.append(p('8. Funcionalidades de Suporte', h1))
    st.append(p(
        'Além do fluxo principal de inspeção, análise e acompanhamento, a plataforma oferece um '
        'conjunto de funcionalidades de suporte que garantem segurança, confiabilidade e '
        'adaptabilidade ao contexto operacional do MPDFT.'))

    st.append(p('8.1 — Backup e Restauração', h2))
    st.append(p(
        'O sistema realiza <b>backup automático diário</b> no servidor, preservando todos os '
        'dados das inspeções. A restauração aceita um arquivo ZIP contendo os dados estruturados '
        'em JSON (campos da inspeção, especialidades, achados e metadados das fotos) e as próprias '
        'fotos de evidência, recriando toda a estrutura em qualquer instância do sistema. Isso '
        'garante portabilidade total dos dados e proteção contra perda acidental.'))

    st.append(p('8.2 — Modo Offline (PWA — Progressive Web App)', h2))
    st.append(p(
        'A aplicação é um Progressive Web App (PWA), permitindo funcionamento em campo mesmo sem '
        'conexão à rede MPDFT — situação comum em edificações remotas ou em andares sem cobertura '
        'de Wi-Fi interno.'))
    st.extend(lista([
        '<b>Cache de interface:</b> telas, estilos e scripts ficam disponíveis offline após a '
        'primeira visita, sem instalação de aplicativo.',
        '<b>Registro offline de achados:</b> novos achados (incluindo fotos) podem ser registrados '
        'sem conexão, ficando em fila local no navegador.',
        '<b>Sincronização automática:</b> ao restabelecer a conexão, os achados são enviados ao '
        'servidor via API REST, sem intervenção manual.',
        '<b>Página de fallback:</b> quando offline, uma página informa o status e as '
        'funcionalidades disponíveis sem rede.',
    ]))

    st.append(p('8.3 — Controle de Acesso e Auditoria', h2))
    st.extend(lista([
        '<b>Autenticação obrigatória:</b> nenhuma tela é acessível sem login.',
        '<b>Cadastro restrito:</b> apenas e-mails @mpdft.mp.br são aceitos no cadastro, '
        'restringindo o acesso ao quadro funcional do Ministério Público.',
        '<b>Permissão por profissional:</b> apenas os profissionais responsáveis pela especialidade '
        'podem editar seus achados enquanto ela estiver em andamento; após a finalização, os dados '
        'ficam bloqueados para edição, mas continuam disponíveis para consulta somente leitura.',
        '<b>Log de auditoria:</b> todos os eventos relevantes são registrados com identificação do '
        'usuário, IP e data/hora — logins, criação e exclusão de inspeções, especialidades, '
        'achados, visitas e reclassificações de encaminhamento.',
    ]))

    st.append(p('8.4 — Campos Configuráveis (Sem Intervenção de TI)', h2))
    st.append(p(
        'As opções dos campos de Localização, Grupo Técnico e Requisito Afetado são administráveis '
        'pela própria equipe gestora, diretamente na interface web, sem necessidade de intervenção '
        'de TI ou alteração de código-fonte. Isso permite adaptar a ferramenta a diferentes '
        'campanhas de inspeção e tipos de edificação.'))
    st.append(PageBreak())

    # ════════════════════════════════════════════════════════════════════════════
    # 9. BENEFÍCIOS
    # ════════════════════════════════════════════════════════════════════════════
    st.append(p('9. Benefícios para o MPDFT', h1))
    st.append(p(
        'A implantação do Sistema de Inspeções Prediais representa uma transformação significativa '
        'na gestão do patrimônio predial do Ministério Público, com impactos diretos na eficiência '
        'operacional, na qualidade técnica dos registros e na capacidade de planejamento '
        'estratégico da área de engenharia.'))

    beneficios = [
        ('01', 'Padronização dos Registros Técnicos',
         'Todos os servidores utilizam o mesmo formulário estruturado, eliminando variações de '
         'formato entre inspeções, campanhas e profissionais. A metodologia GUT é aplicada '
         'uniformemente, tornando os resultados comparáveis.'),
        ('02', 'Rastreabilidade Completa com Auditoria',
         'Cada achado é vinculado ao servidor responsável, com data, localização e fotos de '
         'evidência. O log de auditoria registra todos os eventos do sistema, inclusive as '
         'reclassificações de encaminhamento. Nada se perde, nada é anônimo.'),
        ('03', 'Análise Estatística Imediata',
         'O painel de 16 indicadores é gerado automaticamente assim que os dados são inseridos. '
         'Não há pós-processamento manual em planilhas, nem risco de erros de fórmula ou cópias '
         'desatualizadas.'),
        ('04', 'Gestão do Ciclo de Vida dos Achados',
         'O módulo de Acompanhamento consolida os achados de todas as inspeções e controla cada '
         'tratativa — abertura de OS, status de execução e reclassificação — até a solução '
         'efetiva, com visão gerencial do progresso por categoria, status, especialidade e '
         'localidade.'),
        ('05', 'Priorização Técnica — Não Subjetiva',
         'A metodologia GUT e o IQE eliminam a subjetividade na priorização de investimentos. As '
         'decisões são baseadas em métricas objetivas e auditáveis, fortalecendo a sustentação '
         'técnica de processos de compras e contratações.'),
        ('06', 'Subsídio ao Planejamento Orçamentário',
         'A análise de encaminhamento (garantia / manutenção / nova contratação) e a análise por '
         'prazo fornecem dados diretos para a elaboração do plano de manutenção e a previsão de '
         'créditos orçamentários para o exercício seguinte.'),
        ('07', 'Identificação Automática de Incoerências',
         'A Matriz Risco × Prazo alerta automaticamente quando itens P1 (críticos) estão com '
         'prazos incompatíveis com sua urgência, evitando que problemas graves sejam postergados '
         'inadvertidamente.'),
        ('08', 'Fortalecimento Jurídico dos Achados',
         'O registro fotográfico rastreado, o log de auditoria e os dados estruturados fortalecem '
         'o embasamento técnico e jurídico para acionamentos de garantia, processos de compras, '
         'autos de infração ou decisões administrativas.'),
        ('09', 'Funcionamento Offline em Campo',
         'Os servidores podem registrar achados em campo mesmo sem conexão à rede MPDFT, com '
         'sincronização automática posterior, eliminando a dependência de papéis e a transcrição '
         'manual de dados.'),
        ('10', 'Histórico e Análise de Tendências',
         'Com múltiplas campanhas registradas, é possível acompanhar a evolução do IQE de cada '
         'edificação ao longo do tempo, medir o impacto das intervenções e identificar edificações '
         'com deterioração acelerada.'),
    ]
    for num, tit, txt in beneficios:
        st.append(beneficio(num, tit, txt))
    st.append(Spacer(1, 8))
    st.append(p(
        'O Sistema de Inspeções Prediais do MPDFT representa um avanço significativo na gestão '
        'técnica e estratégica do patrimônio predial do Ministério Público, conferindo mais rigor, '
        'eficiência e transparência ao processo de inspeção, manutenção e acompanhamento das '
        'edificações que abrigam as unidades do MPDFT em todo o Distrito Federal e Territórios.',
        S('Fecho', parent=body, fontName='Times-Italic', textColor=AZUL)))

    doc.multiBuild(st)
    print('PDF gerado:', SAIDA)


if __name__ == '__main__':
    build()
