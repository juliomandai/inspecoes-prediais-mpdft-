"""
Carrega a inspeção predial da Promotoria da Infância e Juventude (PJIJ).
Dados extraídos da planilha: Planilha de Laudo de Inspeçaõ Predial - Infância.xlsx

Uso:
    python manage.py carregar_inspecao_pjij
    python manage.py carregar_inspecao_pjij --limpar   # remove inspeção existente antes de recarregar
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from datetime import date

EDIFICACAO_NOME = 'Promotoria de Justiça da Defesa da Infância e Juventude'
DATA_INSPECAO_CIV = date(2026, 5, 1)
DATA_INSPECAO_MEC = date(2026, 5, 1)

GRUPOS_CUSTOMIZADOS = [
    'Instalações de Incêndio',
    'Inst. Aproveitamento Água Pluvial',
    'Sinalização',
]

# ── Formato dos achados ────────────────────────────────────────────────────────
#
# Não conformidade (14 campos):
#   (loc, sub_loc, verif, grupo, False,
#    descricao, requisito, G, U, T, prioridade, recomendacao, direcionamento, prazo_meses)
#
# Em conformidade (5 campos):
#   (loc, sub_loc, verif, grupo, True)
#
# ── ACHADOS CIV (134 itens) ───────────────────────────────────────────────────

ACHADOS_CIV = [
    # ── GERAL ─────────────────────────────────────────────────────────────────
    ('Geral', '', 'Geral', 'instalacoes_eletricas', False,
     'Fixação de tampas dos quadros elétricos.',
     'seguranca_estrutural', 3, 3, 1, 2,
     'Revisão de todas tampas dos quadros elétricos da edificação.',
     'manutencao', 6),

    # ── ÁREA EXTERNA ──────────────────────────────────────────────────────────
    ('Área externa', '', 'Drenagem', 'impermeabilizacao', True),

    ('Área externa', '', 'Pintura', 'acabamento', False,
     'Pintura desgastada.',
     'durabilidade', 2, 3, 3, 3,
     'Executar nova pintura nas paredes externas.',
     'nova_contratacao', 12),

    ('Área externa', 'Norte', 'Piso externo', 'estrutura', False,
     'Junta de dilatação deteriorada.',
     'funcionalidade', 3, 3, 3, 2,
     'Reexecutar junta de dilatação.',
     'manutencao', 3),

    ('Área externa', 'Granitina', 'Piso externo', 'acabamento', False,
     'Revestimento de granitina desplacando próximo à junta de dilatação.',
     'funcionalidade', 2, 2, 2, 3,
     'Executar novo revestimento na área da junta de dilatação externa.',
     'nova_contratacao', 12),

    ('Área externa', '', 'Escada externa', 'estrutura', True),

    ('Área externa', '', 'Guarita', 'estrutura', True),

    ('Área externa', 'Rampa oeste', 'Pavimento', 'estrutura', False,
     'Acúmulo de resíduos.',
     'funcionalidade', 2, 3, 2, 3,
     'Renivelar terreno, e reexecutar pavimento.',
     'nova_contratacao', 12),

    ('Área externa', 'Estacionamento externo', 'Pavimento', 'estrutura', False,
     'Parte do pavimento externo apresentando recalque, provocando acúmulo de resíduos '
     'e prejudicando escoamento de água pluvial.',
     'funcionalidade', 3, 3, 2, 3,
     'Remover blocos da área, compactar substrato, reinstalar blocos com nivelamento do escoamento.',
     'manutencao', 6),

    ('Área externa', '', 'Jardim', 'outros', True),

    ('Área externa', '', 'Fachada', 'estrutura', True),

    ('Área externa', '', 'Portas', 'esquadrias', True),

    ('Área externa', '', 'Comporta', 'esquadrias', False,
     'Pintura desgastada.',
     'funcionalidade', 2, 2, 2, 3,
     'Executar nova pintura.',
     'nova_contratacao', 12),

    ('Área externa', '', 'Comporta', 'esquadrias', False,
     'Comporta emperrada, o que dificulta operação.',
     'seguranca_estrutural', 4, 4, 2, 1,
     'Trocar sistema deslizante.',
     'nova_contratacao', 6),

    ('Área externa', '', 'Brises', 'esquadrias', True),

    ('Área externa', '', 'Fosso — telas', 'esquadrias', False,
     'Telas danificadas.',
     'funcionalidade', 2, 2, 3, 3,
     'Recompor telas.',
     'manutencao', 12),

    ('Área externa', 'Leste', 'Fosso', 'instalacoes', False,
     'Fosso com acúmulo de água.',
     'funcionalidade', 4, 5, 5, 1,
     'Verificar obstrução de ralos.',
     'manutencao', 1),

    ('Área externa', 'Leste', 'Luminária de alerta', 'Sinalização', False,
     'Lâmpada queimada.',
     'seguranca_estrutural', 5, 5, 5, 1,
     'Substituir lâmpada queimada.',
     'manutencao', 1),

    ('Área externa', '', 'Placas / letreiro', 'Sinalização', True),

    ('Área externa', '', 'Elementos metálicos (guarda-corpo, corrimão)', 'esquadrias', True),

    ('Área externa', 'Sul', 'Pele de vidro', 'esquadrias', False,
     'Vidro trincado.',
     'durabilidade', 2, 3, 2, 2,
     'Trocar vidro trincado.',
     'manutencao', 3),

    ('Área externa', '', 'Urbanização', 'estrutura', True),

    ('Área externa', '', 'Instalações hidráulicas', 'instalacoes', True),

    ('Área externa', '', 'Acessibilidade', 'outros', True),

    # ── TÉRREO ────────────────────────────────────────────────────────────────
    ('Térreo', 'Oeste', 'Revestimentos - laminado', 'acabamento', False,
     'Fórmicas soltando.',
     'funcionalidade', 2, 3, 2, 3,
     'Recomposição do revestimento laminado nas áreas danificadas.',
     'nova_contratacao', 12),

    ('Térreo', '', 'Revestimentos - pintura', 'acabamento', True),

    ('Térreo', '', 'Bancadas', 'outros', True),

    ('Térreo', '', 'Tampas de teto', 'instalacoes_mecanicas', False,
     'Tampas ar-condicionado desencaixadas.',
     'funcionalidade', 2, 2, 2, 3,
     'Revisão de todas as tampas.',
     'manutencao', 6),

    ('Térreo', '', 'Brise interno', 'outros', True),

    ('Térreo', '', 'Escada interna', 'estrutura', True),

    ('Térreo', '', 'Escada - rota de fuga', 'estrutura', True),

    ('Térreo', '', 'Piso interno', 'acabamento', False,
     'Piso vinílico danificado.',
     'funcionalidade', 2, 1, 1, 3,
     'Recomposição dos revestimento de piso danificado.',
     'manutencao', 24),

    ('Térreo', 'Sala 118-B', 'Ar condicionado', 'instalacoes_mecanicas', False,
     'Ar condicionado ineficiente.',
     'saude_qualidade_ar', 5, 5, 4, 1,
     'Verificação e manutenção no sistema condicionante.',
     'manutencao', 1),

    ('Térreo', 'Sala 118-B', 'Janelas', 'esquadrias', False,
     'Sala sem janela que abre.',
     'saude_qualidade_ar', 4, 4, 3, 1,
     'Instalação de janela com abertura.',
     'nova_contratacao', 12),

    ('Térreo', 'Sala 104-A', 'Porta', 'esquadrias', False,
     'Porta pegando no chão ao abrir.',
     'funcionalidade', 3, 2, 1, 3,
     'Regulagem da porta.',
     'manutencao', 3),

    ('Térreo', 'Sala 101', 'Janela', 'esquadrias', False,
     'Trinco janela danificado.',
     'funcionalidade', 2, 3, 1, 2,
     'Troca de trinco danificado.',
     'nova_contratacao', 12),

    ('Térreo', 'Leste', 'Janela', 'esquadrias', False,
     'Alça da janela danificada.',
     'durabilidade', 2, 3, 1, 2,
     'Troca das alças danificadas.',
     'nova_contratacao', 12),

    ('Térreo', '', 'Elementos metálicos (guarda-corpo, corrimão)', 'esquadrias', True),

    ('Térreo', '', 'Piso', 'acabamento', False,
     'Parte das tomadas de piso com sujeira e fios expostos.',
     'seguranca_estrutural', 5, 5, 1, 1,
     'Reparo e recomposição das tomadas de piso.',
     'manutencao', 1),

    ('Térreo', '', 'Piso', 'estrutura', False,
     'Acabamento da junta de dilatação soltando.',
     'funcionalidade', 2, 2, 2, 3,
     'Recomposição das juntas de dilatação.',
     'manutencao', 12),

    ('Térreo', '', 'Teto', 'instalacoes_eletricas', False,
     'Luminárias sem fixação.',
     'funcionalidade', 1, 1, 1, 3,
     'Fixação de luminárias.',
     'manutencao', 12),

    ('Térreo', 'Banheiro Masculino NO', 'Divisórias sanitárias', 'esquadrias', False,
     'Portas das divisórias empenadas. Trinco desalinhado e com problema de fechamento.',
     'funcionalidade', 3, 5, 1, 1,
     'Desempeno das portas ou troca, caso necessário.',
     'manutencao', 1),

    ('Térreo', 'Banheiro Feminino NE', 'Válvulas', 'instalacoes', False,
     'Descarga sanitária com defeito.',
     'funcionalidade', 4, 5, 1, 1,
     'Manutenção nas válvulas.',
     'manutencao', 1),

    ('Térreo', '', 'Instalações de incêndio', 'Instalações de Incêndio', True),

    ('Térreo', 'Banheiro Masculino NO', 'Louças e metais sanitários', 'instalacoes', False,
     'Torneira emperrada.',
     'funcionalidade', 2, 3, 1, 2,
     'Reparo da torneira.',
     'manutencao', 3),

    ('Térreo', '', 'Impermeabilização', 'impermeabilizacao', True),

    ('Térreo', '', 'Acessibilidade', 'outros', True),

    # ── 1º PAVIMENTO ──────────────────────────────────────────────────────────
    ('1º pavimento', '', 'Revestimentos de parede', 'estrutura', True),

    ('1º pavimento', '', 'Revestimentos - laminado', 'estrutura', True),

    ('1º pavimento', '', 'Bancadas', 'acabamento', True),

    ('1º pavimento', 'Hall central', 'Luminárias', 'instalacoes_eletricas', False,
     'Fixação inadequada de luminárias.',
     'seguranca_estrutural', 2, 1, 1, 3,
     'Recomposição da visita de forro danificada.',
     'manutencao', 12),

    ('1º pavimento', 'Sala 209', 'Forro', 'acabamento', False,
     'Visita do Forro de gesso danificada.',
     'funcionalidade', 2, 1, 1, 3,
     'Recomposição da visita de forro danificada.',
     'manutencao', 12),

    ('1º pavimento', 'Sala 207', 'Forro', 'acabamento', False,
     'Forro de gesso danificado.',
     'funcionalidade', 2, 1, 1, 3,
     'Recomposição da área de forro danificada.',
     'manutencao', 12),

    ('1º pavimento', '', 'Escada interna', 'outros', True),

    ('1º pavimento', '', 'Escada - emergência', 'outros', True),

    ('1º pavimento', '', 'Piso', 'estrutura', False,
     'Juntas de dilatação danificada.',
     'funcionalidade', 1, 1, 1, 3,
     '',
     'manutencao', 12),

    ('1º pavimento', '', 'Divisórias sanitárias', 'outros', True),

    ('1º pavimento', 'Corredor central - oeste', 'Janela', 'esquadrias', False,
     'Trinco danificado.',
     'funcionalidade', 2, 3, 1, 2,
     'Troca do trinco danificado.',
     'nova_contratacao', 12),

    ('1º pavimento', 'Sala 213', 'Janela', 'esquadrias', False,
     'Trinco danificado.',
     'funcionalidade', 2, 3, 1, 2,
     'Troca do trinco danificado.',
     'nova_contratacao', 12),

    ('1º pavimento', 'Sala 209', 'Janela', 'esquadrias', False,
     'Trincos danificados.',
     'funcionalidade', 2, 3, 1, 2,
     'Troca do trinco danificado.',
     'nova_contratacao', 12),

    ('1º pavimento', 'Sala 206', 'Janela', 'esquadrias', False,
     'Trincos com limitação, travando.',
     'funcionalidade', 2, 3, 1, 2,
     'Troca do trinco danificado.',
     'nova_contratacao', 12),

    ('1º pavimento', 'Corredor central - oeste', 'Janela', 'esquadrias', False,
     'Trincos danificados.',
     'funcionalidade', 2, 3, 1, 2,
     'Troca do trinco danificado.',
     'nova_contratacao', 12),

    ('1º pavimento', 'Hall escada de serviço', 'Janela', 'esquadrias', False,
     'Janelas sem limitação de abertura.',
     'funcionalidade', 4, 5, 1, 1,
     'Instalação de peça que limita abertura.',
     'manutencao', 1),

    ('1º pavimento', 'Copa', 'Janela', 'esquadrias', False,
     'Janelas sem limitação de abertura.',
     'funcionalidade', 4, 5, 1, 1,
     'Instalação de peça que limita abertura.',
     'manutencao', 1),

    ('1º pavimento', 'Banheiro SE', 'Janela', 'esquadrias', False,
     'Trincos danificados.',
     'funcionalidade', 2, 3, 1, 3,
     'Troca do trinco danificado.',
     'nova_contratacao', 12),

    ('1º pavimento', '', 'Elementos metálicos (guarda-corpo, corrimão)', 'esquadrias', True),

    ('1º pavimento', '', 'Portas', 'esquadrias', True),

    ('1º pavimento', '', 'Divisórias', 'esquadrias', True),

    ('1º pavimento', 'Banheiro SO', 'Válvulas', 'instalacoes', False,
     '2 Válvulas de descarga com defeito.',
     'funcionalidade', 5, 5, 3, 1,
     'Substituir válvulas danificadas.',
     'manutencao', 1),

    ('1º pavimento', 'Sul', 'Botoeira', 'Instalações de Incêndio', False,
     'Botoeira de alarme de incêndio obstruída por divisória.',
     'seguranca_estrutural', 5, 5, 5, 1,
     'Desobstrução e remanejamento de divisória.',
     'manutencao', 1),

    ('1º pavimento', '', 'Acessibilidade', 'outros', True),

    # ── COBERTURA ─────────────────────────────────────────────────────────────
    ('Cobertura', '', 'Telhas', 'estrutura', True),

    ('Cobertura', 'Barrilete', 'Tubulações', 'instalacoes', False,
     'Vazamento em tubulação.',
     'durabilidade', 3, 4, 4, 1,
     'Reparo no vazamento.',
     'manutencao', 1),

    ('Cobertura', 'Barrilete', 'Tubulações — identificação', 'instalacoes', False,
     'Tubulações sem pintura de identificação.',
     'seguranca_estrutural', 4, 5, 1, 1,
     'Pintura das tubulações de acordo com a utilização.',
     'manutencao', 3),

    ('Cobertura', '', 'Bombas de Hidrantes', 'Instalações de Incêndio', True),

    ('Cobertura', '', 'Bomba 01 - HID', 'Instalações de Incêndio', True),

    ('Cobertura', '', 'Drenagem', 'impermeabilizacao', True),

    ('Cobertura', 'Barrilete', 'Proteção mecânica', 'estrutura', False,
     'Proteção mecânica da impermeabilização danificada.',
     'durabilidade', 3, 4, 4, 1,
     'Recompor proteção mecânica.',
     'manutencao', 3),

    ('Cobertura', '', 'Impermeabilização', 'impermeabilizacao', True),

    ('Cobertura', '', 'Reservatórios', 'instalacoes', True),

    ('Cobertura', '', 'Piso', 'estrutura', True),

    ('Cobertura', '', 'Alçapões', 'esquadrias', True),

    ('Cobertura', '', 'Pintura', 'acabamento', False,
     "Pintura das paredes externas da caixa d'água com desgaste.",
     'funcionalidade', 2, 2, 2, 3,
     'Executar nova pintura.',
     'manutencao', 6),

    ('Cobertura', '', 'Vedação', 'estrutura', True),

    ('Cobertura', '', 'Elementos metálicos (escada, apoio, etc)', 'esquadrias', True),

    ('Cobertura', '', 'Ventilação de elementos de fachada', 'outros', True),

    ('Cobertura', '', 'Esquadrias', 'esquadrias', True),

    # ── SUBSOLO ───────────────────────────────────────────────────────────────
    ('Subsolo', '', 'Piso do estacionamento', 'acabamento', False,
     'Piso RAD desplacando pontualmente.',
     'funcionalidade', 2, 3, 5, 2,
     'Recomposição do substrato e camadas do piso RAD.',
     'manutencao', 3),

    ('Subsolo', 'Sala SECOA', 'Tomadas de piso', 'instalacoes_eletricas', False,
     'Tomadas com padrão antigo.',
     'funcionalidade', 3, 3, 1, 2,
     'Instalar tomadas padrão atual.',
     'manutencao', 6),

    ('Subsolo', 'Subestação', 'Salas técnicas', 'instalacoes_eletricas', False,
     'Possibilidade de obstrução de acesso à subestação.',
     'acessibilidade', 5, 5, 5, 1,
     'Isolar vaga com sinalização adequada e fixa.',
     'manutencao', 1),

    ('Subsolo', 'Sala Arquivo', 'Câmeras de vigilância', 'outros', False,
     'Câmeras de vigilância não estão funcionando.',
     'seguranca_estrutural', 4, 4, 1, 2,
     'Verificação do estado dos equipamentos. Ativar câmeras.',
     'manutencao', 3),

    ('Subsolo', 'Sala Arquivo', 'Instalações elétricas', 'instalacoes_eletricas', False,
     'Instalações elétricas expostas.',
     'seguranca_estrutural', 3, 5, 2, 1,
     'Instalar eletroduto em local mais apropriado.',
     'manutencao', 1),

    ('Subsolo', 'Sala Arquivo', 'Janelas', 'esquadrias', False,
     'Janelas e telas danificadas.',
     'funcionalidade', 2, 3, 1, 2,
     'Reparar janelas e telas.',
     'nova_contratacao', 12),

    ('Subsolo', 'Sala SECOA', 'Piso geral', 'acabamento', False,
     'Piso com desgaste e mofo.',
     'seguranca_estrutural', 4, 4, 4, 1,
     'Executar nova base do piso e novo revestimento de piso.',
     'nova_contratacao', 6),

    ('Subsolo', '', 'Paredes — pintura', 'acabamento', False,
     'Pintura danificada.',
     'funcionalidade', 2, 2, 2, 3,
     'Aplicação nova pintura nos fossos.',
     'nova_contratacao', 6),

    ('Subsolo', 'Norte', 'Paredes — infiltração', 'acabamento', False,
     'Pintura danificada e infiltração ascendente.',
     'durabilidade', 3, 2, 4, 2,
     'Aplicação de impermeabilizante e nova pintura.',
     'nova_contratacao', 6),

    ('Subsolo', '', 'Portas', 'esquadrias', True),

    ('Subsolo', 'Copa', 'Janelas', 'esquadrias', False,
     'Janelas sem trava.',
     'funcionalidade', 2, 3, 1, 3,
     'Recomposição das janelas danificadas.',
     'nova_contratacao', 12),

    ('Subsolo', 'DML', 'Janelas', 'esquadrias', False,
     'Janelas danificadas: não fecha.',
     'funcionalidade', 2, 3, 1, 3,
     'Recomposição das janelas danificadas.',
     'nova_contratacao', 12),

    ('Subsolo', 'Vestiário Masculino', 'Janelas', 'esquadrias', False,
     'Janelas danificadas: apresentam empeno.',
     'funcionalidade', 2, 3, 1, 3,
     'Recomposição das janelas danificadas.',
     'nova_contratacao', 12),

    ('Subsolo', '', 'Gradil / telas', 'esquadrias', True),

    ('Subsolo', 'Vestiário Masculino', 'Ralos', 'instalacoes', False,
     'Ralo obstruído e sem acabamento/tampa.',
     'funcionalidade', 4, 5, 3, 1,
     'Limpeza de ralos.',
     'manutencao', 3),

    ('Subsolo', '', 'Ralos gerais', 'instalacoes', False,
     'Ralos sujos e obstruídos.',
     'funcionalidade', 4, 5, 3, 1,
     'Limpeza de ralos.',
     'manutencao', 3),

    ('Subsolo', '', 'Torneiras externas', 'instalacoes', False,
     'Torneiras sem limitação de acesso (cadeado).',
     'seguranca_estrutural', 5, 5, 1, 1,
     'Troca do tipo de torneira por modelo que tenha cadeado.',
     'manutencao', 1),

    ('Subsolo', '', 'Tubulações', 'instalacoes', False,
     'Tubulações sem pintura de identificação.',
     'seguranca_estrutural', 4, 5, 1, 1,
     'Pintura das tubulações de acordo com a utilização.',
     'manutencao', 3),

    ('Subsolo', '', 'Bombas de Recalque Água potável', 'instalacoes', True),

    ('Subsolo', '', 'Bomba 01 - REC', 'instalacoes', True),

    ('Subsolo', '', 'Bomba 02 - REC', 'instalacoes', True),

    ('Subsolo', '', 'Bomba de irrigação', 'instalacoes', True),

    ('Subsolo', '', 'Bombas de Reuso Estágio 01 (Bomba Transferência)',
     'Inst. Aproveitamento Água Pluvial', True),

    ('Subsolo', '', 'Bomba 01 - REU EST 1', 'Inst. Aproveitamento Água Pluvial', True),

    ('Subsolo', '', 'Bomba 02 - REU EST 1', 'Inst. Aproveitamento Água Pluvial', True),

    ('Subsolo', '', 'Bombas de Reuso - Estágio 02', 'Inst. Aproveitamento Água Pluvial', True),

    ('Subsolo', '', 'Bomba 01 — REU EST 2', 'Inst. Aproveitamento Água Pluvial', True),

    ('Subsolo', '', 'Bomba 02 — REU EST 2', 'Inst. Aproveitamento Água Pluvial', True),

    ('Subsolo', '', 'Bombas Pluviais - PLU', 'instalacoes', True),

    ('Subsolo', '', 'Bombas de Esgoto - ESG', 'instalacoes', True),

    ('Subsolo', '', 'Filtro de Areia (Filtro de Piscina)',
     'Inst. Aproveitamento Água Pluvial', True),

    ('Subsolo', '', 'Hidrômetro Ultrassônico Hydrus DN 40mm',
     'Inst. Aproveitamento Água Pluvial', True),

    ('Subsolo', '', 'Hidrômetro Ultrassônico Hydrus DN 25mm',
     'Inst. Aproveitamento Água Pluvial', True),

    ('Subsolo', '', 'Hidrômetros Horizontais', 'instalacoes', True),

    ('Subsolo', '', 'Dosadores de Cloro em Pastilhas',
     'Inst. Aproveitamento Água Pluvial', True),

    ('Subsolo', '', 'Bombas Pluviais - PLU (2)', 'instalacoes', True),

    ('Subsolo', '', 'Bombas de Esgoto (2)', 'instalacoes', True),

    ('Subsolo', 'Sala de reservatórios', 'Instalações de reúso',
     'Inst. Aproveitamento Água Pluvial', False,
     'Sem quadro esquema de funcionamento do sistema.',
     'seguranca_estrutural', 3, 3, 2, 2,
     'Confeccionar e instalar quadro esquema de funcionamento do sistema.',
     'manutencao', 6),

    ('Subsolo', 'Sala de reservatórios', 'Instalações de reúso — tubulações',
     'Inst. Aproveitamento Água Pluvial', False,
     'Tubulações sem pintura de identificação.',
     'seguranca_estrutural', 3, 3, 2, 2,
     'Executar pintura de identificação das tubulações.',
     'manutencao', 6),

    ('Subsolo', 'Sala de reservatórios', 'Instalações de reúso — grelhas',
     'Inst. Aproveitamento Água Pluvial', False,
     'Grelhas sem saída de água.',
     'seguranca_estrutural', 3, 3, 2, 2,
     'Instalar ralo com saída de água.',
     'manutencao', 6),

    ('Subsolo', '', 'Bancadas', 'acabamento', True),

    ('Subsolo', '', 'Louças e metais sanitários', 'instalacoes', True),

    ('Subsolo', '', 'Divisórias sanitárias', 'outros', True),

    ('Subsolo', '', 'Drenagem', 'impermeabilizacao', True),

    ('Subsolo', '', 'Caixas de inspeção / passagem', 'impermeabilizacao', True),

    ('Subsolo', '', 'Impermeabilização', 'impermeabilizacao', True),

    ('Subsolo', '', 'Cortina de contenção', 'estrutura', True),
]

# ── ACHADOS MEC (28 itens) ────────────────────────────────────────────────────

ACHADOS_MEC = [
    ('Geral', 'Área interna', 'Elevador', 'instalacoes_mecanicas', False,
     'Guarda corpo parcialmente solto. Presença de óleo no fundo do poço.',
     'seguranca_estrutural', 5, 5, 1, 1,
     'Reaperto do guarda corpo e instalação de coletor de óleo.',
     'manutencao', 3),

    ('Geral', 'Área interna', 'Exaustores e ventilação mecânica',
     'instalacoes_mecanicas', True),

    ('Térreo', 'Área externa', 'Chillers', 'instalacoes_mecanicas', True),

    ('Térreo', 'Área externa', 'Tubulação hidráulica — chiller',
     'instalacoes_mecanicas', False,
     'Proteção mecânica e isolamento térmico danificados.',
     'funcionalidade', 2, 2, 1, 3,
     'Troca da proteção mecânica e do isolamento térmico.',
     'manutencao', 6),

    ('Térreo', 'Área externa', 'Bomba de água gelada 1',
     'instalacoes_mecanicas', True),

    ('Térreo', 'Área externa', 'Bomba de água gelada 2',
     'instalacoes_mecanicas', True),

    ('Subsolo', 'UTA 1', 'Fancoil', 'instalacoes_mecanicas', True),

    ('Subsolo', 'UTA 2', 'Fancoil', 'instalacoes_mecanicas', True),

    ('Subsolo', 'UTA 3', 'Fancoil', 'instalacoes_mecanicas', True),

    ('Subsolo', 'Nobreak', 'Split hiwall 18.000 btu/h', 'instalacoes_mecanicas', False,
     'Equipamento antigo / tecnologia convencional de compressão.',
     'eficiencia_energetica', 2, 2, 2, 3,
     'Substituição do equipamento.',
     'nova_contratacao', 12),

    ('Subsolo', 'Nobreak', 'Split hiwall 18.000 btu/h (2)',
     'instalacoes_mecanicas', True),

    ('Subsolo', 'Telefonia/CPD', 'Split hiwall 18.000 btu/h',
     'instalacoes_mecanicas', True),

    ('Subsolo', 'Telefonia/CPD', 'Split hiwall 9.000 btu/h',
     'instalacoes_mecanicas', False,
     'Equipamento inoperante / falha em componente.',
     'funcionalidade', 2, 2, 2, 3,
     'Reparo do equipamento.',
     'manutencao', 3),

    ('Subsolo', 'Seg. Institucional', 'Split hiwall 9.000 btu/h',
     'instalacoes_mecanicas', True),

    ('Subsolo', 'Múltiplo uso — 1', 'Split cassete 18.000 btu/h',
     'instalacoes_mecanicas', False,
     'Equipamento antigo / tecnologia convencional de compressão.',
     'eficiencia_energetica', 2, 2, 2, 3,
     'Substituição do equipamento.',
     'nova_contratacao', 12),

    ('Subsolo', 'Múltiplo uso — 2', 'Split cassete 18.000 btu/h',
     'instalacoes_mecanicas', False,
     'Equipamento antigo / tecnologia convencional de compressão.',
     'eficiencia_energetica', 2, 2, 2, 3,
     'Substituição do equipamento.',
     'nova_contratacao', 12),

    ('Subsolo', 'Múltiplo uso — 3', 'Split cassete 18.000 btu/h',
     'instalacoes_mecanicas', False,
     'Equipamento antigo / tecnologia convencional de compressão.',
     'eficiencia_energetica', 2, 2, 2, 3,
     'Substituição do equipamento.',
     'nova_contratacao', 12),

    ('Subsolo', 'Múltiplo uso — 4', 'Split cassete 18.000 btu/h',
     'instalacoes_mecanicas', False,
     'Equipamento antigo / tecnologia convencional de compressão.',
     'eficiencia_energetica', 2, 2, 2, 3,
     'Substituição do equipamento.',
     'nova_contratacao', 12),

    ('Subsolo', 'Sala Transporte', 'Split hiwall 9.000 btu/h',
     'instalacoes_mecanicas', True),

    ('Térreo', 'Guarita 1', 'Split hiwall 9.000 btu/h',
     'instalacoes_mecanicas', False,
     'Equipamento antigo / tecnologia convencional de compressão.',
     'eficiencia_energetica', 2, 2, 2, 3,
     'Substituição do equipamento.',
     'nova_contratacao', 12),

    ('Térreo', 'Guarita 2', 'Split hiwall 9.000 btu/h',
     'instalacoes_mecanicas', False,
     'Equipamento antigo / tecnologia convencional de compressão.',
     'eficiencia_energetica', 2, 2, 2, 3,
     'Substituição do equipamento.',
     'nova_contratacao', 12),

    ('Subsolo', 'Arquivo — split 1', 'Split hiwall 18.000 btu/h',
     'instalacoes_mecanicas', False,
     'Equipamento antigo / tecnologia convencional de compressão.',
     'eficiencia_energetica', 2, 2, 2, 3,
     'Substituição do equipamento.',
     'nova_contratacao', 12),

    ('Subsolo', 'Arquivo — split 2', 'Split hiwall 18.000 btu/h',
     'instalacoes_mecanicas', False,
     'Equipamento antigo / tecnologia convencional de compressão.',
     'eficiencia_energetica', 2, 2, 2, 3,
     'Substituição do equipamento.',
     'nova_contratacao', 12),

    ('Subsolo', 'Arquivo — split 3', 'Split hiwall 18.000 btu/h',
     'instalacoes_mecanicas', False,
     'Equipamento antigo / tecnologia convencional de compressão.',
     'eficiencia_energetica', 2, 2, 2, 3,
     'Substituição do equipamento.',
     'nova_contratacao', 12),

    ('Subsolo', 'Arquivo — cassete 1', 'Split cassete 24.000 btu/h',
     'instalacoes_mecanicas', False,
     'Equipamento inoperante / falha em componente.',
     'funcionalidade', 2, 2, 2, 3,
     'Substituição do equipamento.',
     'nova_contratacao', 12),

    ('Subsolo', 'Arquivo — cassete 2', 'Split cassete 24.000 btu/h',
     'instalacoes_mecanicas', False,
     'Equipamento inoperante / falha em componente.',
     'funcionalidade', 2, 2, 2, 3,
     'Substituição do equipamento.',
     'nova_contratacao', 12),

    ('Subsolo', 'Arquivo — cassete 3', 'Split cassete 24.000 btu/h',
     'instalacoes_mecanicas', False,
     'Equipamento inoperante / falha em componente.',
     'funcionalidade', 2, 2, 2, 3,
     'Substituição do equipamento.',
     'nova_contratacao', 12),

    ('1º pavimento', 'Salas 216/218/220', 'Multisplit 27.000 btu/h',
     'instalacoes_mecanicas', True),
]


class Command(BaseCommand):
    help = 'Carrega a inspeção predial da PJIJ a partir dos dados da planilha Excel'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limpar',
            action='store_true',
            help='Remove a inspeção existente da PJIJ antes de recarregar',
        )
        parser.add_argument(
            '--restaurar-mecanica',
            action='store_true',
            help='Remove e recria APENAS a especialidade de Mecânica (preserva Civil, Elétrica e demais dados)',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        from apps.edificacoes.models import Edificacao
        from apps.inspecoes.models import Inspecao, InspecaoEspecialidade, OpcaoCampo

        # ── 1. Edificação ─────────────────────────────────────────────────────
        edificacao = Edificacao.objects.filter(nome__icontains='Infância').first()
        if not edificacao:
            self.stderr.write(f'Edificação "{EDIFICACAO_NOME}" não encontrada. Crie-a primeiro.')
            return
        self.stdout.write(f'Edificação: {edificacao.nome} (id={edificacao.pk})')

        # ── 2. Limpeza opcional ───────────────────────────────────────────────
        if options['limpar']:
            removidas = Inspecao.objects.filter(edificacao=edificacao).delete()
            self.stdout.write(f'Inspeções removidas: {removidas}')

        # ── 2b. Restaurar apenas Mecânica ─────────────────────────────────────
        if options['restaurar_mecanica']:
            inspecao = Inspecao.objects.filter(edificacao=edificacao).first()
            if not inspecao:
                self.stderr.write('Nenhuma inspeção encontrada para esta edificação.')
                return
            removidas = InspecaoEspecialidade.objects.filter(
                inspecao=inspecao, especialidade='mecanica'
            ).delete()
            self.stdout.write(f'Especialidade mecânica removida: {removidas}')
            esp_mec = InspecaoEspecialidade.objects.create(
                inspecao=inspecao,
                especialidade='mecanica',
                profissional='Engenheiro Mecânico (a definir)',
                data_inspecao=DATA_INSPECAO_MEC,
                status='finalizada',
            )
            self._criar_achados(esp_mec, ACHADOS_MEC)
            nc = sum(1 for r in ACHADOS_MEC if not r[4])
            cf = sum(1 for r in ACHADOS_MEC if r[4])
            self.stdout.write(self.style.SUCCESS(
                f'Especialidade mecânica restaurada com {len(ACHADOS_MEC)} achados '
                f'({nc} não conformidades + {cf} em conformidade).'
            ))
            self.stdout.write(self.style.SUCCESS('Concluído! Civil, Elétrica e demais especialidades não foram alteradas.'))
            return

        # ── 3. Grupos técnicos customizados ───────────────────────────────────
        for label in GRUPOS_CUSTOMIZADOS:
            _, criado = OpcaoCampo.objects.get_or_create(
                campo='grupo_tecnico', label=label,
                defaults={'is_padrao': False},
            )
            if criado:
                self.stdout.write(f'  OpcaoCampo criada: Grupo técnico → {label}')

        # ── 4. Container Inspeção ─────────────────────────────────────────────
        inspecao, criada = Inspecao.objects.get_or_create(
            edificacao=edificacao,
        )
        if not criada:
            self.stdout.write(self.style.WARNING(
                f'Inspeção container já existia (id={inspecao.pk}). Use --limpar para recriar.'
            ))
        else:
            self.stdout.write(f'Inspeção container criada (id={inspecao.pk})')

        # ── 5. Especialidade CIVIL ────────────────────────────────────────────
        esp_civ, criada = InspecaoEspecialidade.objects.get_or_create(
            inspecao=inspecao,
            especialidade='civil',
            defaults={
                'profissional': 'Eng. Civil Jader Mendes Santana Pereira',
                'data_inspecao': DATA_INSPECAO_CIV,
                'status': 'finalizada',
            },
        )
        if not criada:
            self.stdout.write(self.style.WARNING(
                f'Especialidade civil já existia (id={esp_civ.pk}). Use --limpar para recriar.'
            ))
        else:
            self.stdout.write(f'Especialidade civil criada (id={esp_civ.pk})')
            self._criar_achados(esp_civ, ACHADOS_CIV)
            nc = sum(1 for r in ACHADOS_CIV if not r[4])
            cf = sum(1 for r in ACHADOS_CIV if r[4])
            self.stdout.write(self.style.SUCCESS(
                f'  {len(ACHADOS_CIV)} achados CIV: {nc} não conformidades + {cf} em conformidade.'
            ))

        # ── 6. Especialidade MECÂNICA ─────────────────────────────────────────
        esp_mec, criada = InspecaoEspecialidade.objects.get_or_create(
            inspecao=inspecao,
            especialidade='mecanica',
            defaults={
                'profissional': 'Engenheiro Mecânico (a definir)',
                'data_inspecao': DATA_INSPECAO_MEC,
                'status': 'finalizada',
            },
        )
        if not criada:
            self.stdout.write(self.style.WARNING(
                f'Especialidade mecânica já existia (id={esp_mec.pk}). Use --limpar para recriar.'
            ))
        else:
            self.stdout.write(f'Especialidade mecânica criada (id={esp_mec.pk})')
            self._criar_achados(esp_mec, ACHADOS_MEC)
            nc = sum(1 for r in ACHADOS_MEC if not r[4])
            cf = sum(1 for r in ACHADOS_MEC if r[4])
            self.stdout.write(self.style.SUCCESS(
                f'  {len(ACHADOS_MEC)} achados MEC: {nc} não conformidades + {cf} em conformidade.'
            ))

        self.stdout.write(self.style.SUCCESS('\nConcluído!'))

    def _criar_achados(self, especialidade, lista):
        from apps.inspecoes.models import Achado
        for row in lista:
            em_conf = row[4]
            if em_conf:
                loc, sub_loc, verif, grupo, _ = row
                Achado.objects.create(
                    especialidade=especialidade,
                    localizacao=loc,
                    sub_localizacao=sub_loc,
                    verificacao=verif,
                    grupo_tecnico=grupo,
                    em_conformidade=True,
                    requisito_afetado='funcionalidade',
                    prioridade_risco=3,
                    direcionamento='manutencao',
                    prazo_meses=12,
                )
            else:
                (loc, sub_loc, verif, grupo, _,
                 desc, req, g, u, t, prior, rec, dire, prazo) = row
                Achado.objects.create(
                    especialidade=especialidade,
                    localizacao=loc,
                    sub_localizacao=sub_loc,
                    verificacao=verif,
                    grupo_tecnico=grupo,
                    em_conformidade=False,
                    descricao_nao_conformidade=desc,
                    requisito_afetado=req,
                    gravidade=g,
                    urgencia=u,
                    tendencia=t,
                    prioridade_risco=prior,
                    recomendacao=rec,
                    direcionamento=dire,
                    prazo_meses=prazo,
                )
