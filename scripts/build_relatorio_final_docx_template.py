# -*- coding: utf-8 -*-
"""Constrói o template Jinja (.docx) do Relatório Final a partir do arquivo
real enviado pelo usuário (laudo-modelo MPDFT/SPO), substituindo cada trecho
de exemplo por um marcador {{ }} — SEM recriar formatação: a substituição
muda só o texto de runs já existentes, preservando fonte/cor/tamanho/tabulação
originais 1:1.

Uso:
    python scripts/build_relatorio_final_docx_template.py <origem.docx> <destino.docx>

Observação sobre o arquivo de origem: ele é tratado como dado de entrada
(nunca executado). Este script não deve ser colocado na mesma pasta do
arquivo de origem.
"""
import sys
from docx import Document


def substituir_em_runs(paragrafos_ou_celulas, mapa):
    """Procura cada texto de `mapa` dentro dos runs de parágrafos (ou
    células de tabela) e substitui só o run que contém o texto completo.
    Assume que cada trecho de exemplo está inteiro em um único run — os
    trechos que NÃO estão (negrito parcial, colchetes com estilo diferente
    etc.) são tratados separadamente, ver `forcar_run_unico` mais abaixo."""
    nao_encontrados = set(mapa)
    for item in paragrafos_ou_celulas:
        paragrafos = item.paragraphs if hasattr(item, 'paragraphs') else [item]
        for p in paragrafos:
            for r in p.runs:
                for antigo, novo in mapa.items():
                    if r.text == antigo:
                        r.text = novo
                        nao_encontrados.discard(antigo)
                        break
    return nao_encontrados


def todos_paragrafos(doc):
    """Todos os parágrafos do corpo + de dentro de todas as células de
    todas as tabelas (não existe API nativa para isso no python-docx)."""
    paragrafos = list(doc.paragraphs)
    for t in doc.tables:
        for row in t.rows:
            for cell in row.cells:
                paragrafos.extend(cell.paragraphs)
    return paragrafos


def forcar_run_unico(paragrafo, texto_novo):
    """Para parágrafos em que o texto de exemplo está dividido em mais de um
    run (ex.: parte em negrito + parte normal, ou um placeholder "[xxx]" com
    estilo diferente do resto da frase) e por isso nenhum run isolado bate
    com o texto completo do mapa: coloca o novo texto inteiro no primeiro
    run e esvazia os demais. Perde-se a formatação *interna* desse trecho
    específico (ex.: o negrito que destacava um número dentro da frase),
    mas a formatação do parágrafo como um todo (fonte, tamanho, cor,
    alinhamento, tabulação) é 100% preservada, pois o parágrafo em si nunca
    é recriado — só o texto dos runs existentes é alterado."""
    if not paragrafo.runs:
        return
    paragrafo.runs[0].text = texto_novo
    for r in paragrafo.runs[1:]:
        r.text = ''


def main(origem, destino):
    doc = Document(origem)

    # ── 1. Substituições simples (texto completo de um run -> variável) ────
    mapa_texto = {
        # Capa + cabeçalho (o nome da edificação aparece 2x no arquivo)
        'Promotoria de Justiça de Defesa da Infância e da Juventude': '{{ edificacao_nome }}',
        'SEPN 711/911, Bloco B, Asa Norte, Brasília-DF': '{{ edificacao_endereco }}',
        'Vistorias: 02/03, 15/03 e 06/05/2026': 'Vistorias: {{ datas_vistorias }}',
        '[mês]': '{{ mes_geracao }}',
        ' de 2026': ' de {{ ano_atual }}',
        'MPDFT  •  SECRETARIA DE PROJETOS E OBRAS  •  2026': 'MPDFT  •  SECRETARIA DE PROJETOS E OBRAS  •  {{ ano_atual }}',

        # Quadro "Identificação do Laudo" (Tabela 1)
        '4.745,52 m²': '{{ area_construida }}',
        'Três pavimentos (subsolo, térreo e 1º pavimento), além de cobertura técnica': '{{ pavimentos }}',
        '29 de julho de 2005 (construção averbada em 9 de agosto de 2006)': '{{ data_inauguracao_extenso }}',
        '02/03/2026, 15/03/2026 e 06/05/2026': '{{ datas_vistorias }}',
        # 'Equipe técnica' e 'ART nº [número]' (linhas 10 e 11 da Tabela 1) NÃO
        # entram aqui: no arquivo real, o texto está dividido em mais de um
        # run (o placeholder "[sobrenome]"/"[número]" tem estilo diferente do
        # resto da frase), então a comparação de run inteiro nunca bateria.
        # Tratados em "2b" mais abaixo com `forcar_run_unico`.

        # Sumário Executivo / Principais Constatações / Providências (LLM)
        # OBS: o parágrafo do Sumário Executivo tem negrito interno em 3
        # trechos ("condição global boa", "84 pontos em 100", "23
        # classificadas como Prioridade 1"), o que o divide em 7 runs no
        # arquivo real — por isso NÃO está neste mapa; é tratado em "2c"
        # abaixo com `forcar_run_unico`.
        'As três ocorrências de maior criticidade, com índice GUT máximo de 125, referem-se à segurança dos usuários e das instalações e possuem solução simples e de baixo custo: a possibilidade de obstrução do acesso à subestação por veículos estacionados, a botoeira de alarme de incêndio obstruída por divisória no 1º pavimento e a lâmpada de sinalização queimada na área externa. Seguem-se, em ordem de criticidade, o desempenho insuficiente do ar condicionado da Sala 118-B, o acúmulo de água no fosso da área externa leste e defeitos em válvulas de descarga.': '{{ principais_constatacoes_1 }}',
        'O subsolo concentra 34 das 83 não conformidades (41%), com predominância de problemas de drenagem, acabamentos sujeitos à umidade e equipamentos de climatização obsoletos. Esquadrias, climatização e acabamentos respondem, em conjunto, por 60% das ocorrências. As não conformidades registradas no sistema estrutura referem-se a juntas de dilatação, proteção mecânica da impermeabilização e pavimentação externa, sem indicação de comprometimento da estabilidade da edificação.': '{{ principais_constatacoes_2 }}',
        'Os sistemas elétricos apresentam elevado nível de conformidade (95% das verificações), refletindo os investimentos recentes na edificação. No sistema mecânico, destaca-se a necessidade de substituição de 14 unidades de ar condicionado do tipo split com tecnologia convencional, em grande parte operando com fluido refrigerante R22, cuja reposição é cada vez mais escassa e onerosa.': '{{ principais_constatacoes_3 }}',
        'Recomenda-se determinar a correção, no prazo de até 30 dias, das 17 não conformidades classificadas com prazo imediato, das quais 14 são de Prioridade 1, por meio dos contratos de manutenção vigentes, com prioridade para os itens de segurança contra incêndio, acesso à subestação e instalações elétricas expostas.': '{{ providencias_administracao_1 }}',
        'Recomenda-se, ainda, o acionamento das garantias de obra aplicáveis aos três itens identificados e a autorização para o planejamento das contratações necessárias ao saneamento das 35 ocorrências que excedem o escopo dos contratos vigentes, com destaque para a substituição das unidades de climatização obsoletas, cujas estimativas de custo serão consolidadas por esta Secretaria na fase de planejamento da contratação.': '{{ providencias_administracao_2 }}',

        # Resultados Gerais (LLM / determinístico)
        'As 83 não conformidades distribuem-se por todos os pavimentos, com concentração no subsolo, que reúne 41% das ocorrências e sete dos 23 itens críticos.': '{{ resultados_gerais_intro_1 }}',
        'Três sistemas – esquadrias, climatização e acabamentos – respondem por 60% das ocorrências, e cinco sistemas concentram 83% delas, o que permite direcionar os esforços de manutenção de forma objetiva.': '{{ resultados_gerais_intro_2 }}',
        'A matriz abaixo cruza o grau de risco com o prazo recomendado de intervenção. Vinte e seis ocorrências combinam risco elevado e prazo de até três meses e constituem ganhos rápidos para a Administração.': 'A matriz abaixo cruza o grau de risco com o prazo recomendado de intervenção. {{ n_ganhos_rapidos }} ocorrência(s) combinam risco elevado e prazo de até três meses e constituem ganhos rápidos para a Administração.',
        'Os dez achados de maior índice GUT são todos de Prioridade 1 e estão apresentados a seguir. A relação completa dos 23 itens críticos consta do quadro subsequente.': '{{ resultados_gerais_achados_criticos }}',

        # Itens em conformidade por especialidade (LLM)
        'Apresentaram-se conformes, entre outros, a cortina de contenção, a impermeabilização, a drenagem e as caixas de inspeção do subsolo; os conjuntos de bombas de esgoto, pluviais, de reuso, de recalque de água potável, de irrigação e de hidrantes; os hidrômetros e os dosadores de cloro; as telhas, a impermeabilização, a drenagem, os reservatórios e os elementos metálicos da cobertura; as fachadas, os brises, a urbanização e as escadas externas; e os itens de acessibilidade, escadas de emergência e guarda-corpos nos diversos pavimentos, resultado coerente com as obras de recuperação e de acessibilidade concluídas em 2022.': '{{ itens_conformidade_civil }}',
        'Apresentaram-se conformes o Sistema de Detecção e Alarme de Incêndio (SDAI), com central, detectores, acionadores, sinalizadores e linhas de sinal em todos os pavimentos; a subestação e o grupo gerador; os quadros gerais e de distribuição dos circuitos normal, nobreak e de emergência; os circuitos alimentadores e terminais; a iluminação e as tomadas; o cabeamento estruturado horizontal e vertical; e os sensores, atuadores e quadros do sistema de automação predial.': '{{ itens_conformidade_eletrica }}',
        'Apresentaram-se conformes a central de água gelada, com os chillers e as bombas de água gelada, as três Unidades de Tratamento de Ar (UTA-01, UTA-02 e UTA-03), os fancoils do subsolo, o equipamento multisplit do 1º pavimento, parte das unidades split do subsolo e os sistemas de exaustão e ventilação mecânica.': '{{ itens_conformidade_mecanica }}',

        # Conclusão (LLM) — 2 parágrafos
        'Com base nas vistorias realizadas em 2 e 15 de março e 6 de maio de 2026, conclui-se que a edificação da Promotoria de Justiça de Defesa da Infância e da Juventude apresenta condição global boa, com Índice de Qualidade de 84 pontos em 100. Foram registradas 83 não conformidades em 249 verificações, das quais 23 de Prioridade 1, 20 de Prioridade 2 e 40 de Prioridade 3.': '{{ conclusao_1 }}',
        'As ocorrências de Prioridade 1 relacionam-se principalmente à segurança dos usuários e à manutenção rotineira e podem, em sua maioria, ser corrigidas com rapidez e baixo custo pelos contratos vigentes. A manutenção foi avaliada como atendendo parcialmente aos requisitos e o uso como regular, com ressalvas. Recomenda-se a adoção do plano de ação apresentado, a verificação do saneamento dos itens críticos após o prazo de 90 dias e a realização de nova inspeção predial conforme a periodicidade definida no plano de manutenção da edificação.': '{{ conclusao_2 }}',

        # Quadro "Resumo Executivo — Consolidado" (Tabela 2)
        # (números curtos como '84', '249', '23', '20', '40', '83', '67%'
        # também aparecem em outras tabelas — mas essas outras tabelas
        # (7, 8, 9, 15) têm suas células sobrescritas ou removidas nos
        # passos 4/5/6/10 abaixo, independentemente do que a passagem
        # genérica fizer, então não há risco de corromper dados de outras
        # tabelas; verificado manualmente linha a linha antes de codar.)
        '84': '{{ iqe }}',
        'Índice de Qualidade (de 100) – faixa Bom': 'Índice de Qualidade (de 100) – faixa {{ iqe_faixa }}',
        '249': '{{ total }}',
        '67%': '{{ pct_conformidade }}%',
        'em conformidade (166)': 'em conformidade ({{ total_conformes }})',
        '83': '{{ total_nc }}',
        '23': '{{ p1_total }}',
        '20': '{{ p2_total }}',
        '40': '{{ p3_total }}',
        '21,4': '{{ gut_media }}',

        # Quadro "Encaminhamento" (Tabela 3) NÃO entra aqui: no arquivo real
        # cada célula tem 2 PARÁGRAFOS separados (número e rótulo), não um
        # único run com "\n" no meio como se assumia. Tratado explicitamente
        # por índice de célula no passo "2d" abaixo (mesma técnica robusta
        # usada na Tabela 7), para não depender de um bare '45'/'35'/'3'
        # global que colidiria com outras tabelas (Tabela 5, por exemplo,
        # tem linhas rotuladas exatamente '1'..'5', e '3' coincidiria).

        # Quadro "Avaliação da Manutenção e do Uso" (Tabela 13) — LLM + determinístico
        'Atende parcialmente': '{{ manutencao_classificacao }}',
        'Sistemas de climatização e transporte vertical cobertos por contratos vigentes e intervenções recentes relevantes; persistem, contudo, ocorrências de manutenção rotineira, como ralos obstruídos, trincos e válvulas defeituosos e lâmpada queimada': '{{ manutencao_fundamentacao }}',
        'Regular, com ressalvas': '{{ uso_classificacao }}',
        'Uso compatível com a destinação da edificação; registram-se falhas operacionais pontuais, como a obstrução da botoeira de alarme por divisória e o risco de obstrução do acesso à subestação': '{{ uso_fundamentacao }}',
        'Boa': '{{ condicao_global }}',
        'Índice de Qualidade de 84 pontos em 100 e 67% de conformidade nas verificações realizadas': 'Índice de Qualidade de {{ iqe }} pontos em 100 e {{ pct_conformidade }}% de conformidade nas verificações realizadas',

        # Anexo I — intro
        'Relação integral das 249 verificações realizadas, com indicação da situação, da não conformidade, da recomendação, do grau de risco, do índice GUT e do prazo recomendado. As linhas em destaque correspondem às não conformidades.': 'Relação integral das {{ total }} verificações realizadas, com indicação da situação, da não conformidade, da recomendação, do grau de risco, do índice GUT e do prazo recomendado. As linhas em destaque correspondem às não conformidades.',

        # "De acordo" / assinatura da Secretária de Projetos e Obras (parágrafo
        # isolado, fora de qualquer tabela, run único — não fazia parte do
        # mapa original e ficaria com o nome real "Regina Fátima Fonteles
        # Cabral" hardcoded se não fosse adicionado aqui).
        'Regina Fátima Fonteles Cabral': '{{ nome_secretaria_spo }}',

        # Assinatura (Tabela 14) — tratada célula a célula no passo 9 (nome/CREA variam por pessoa)
    }
    nao_encontrados = substituir_em_runs(todos_paragrafos(doc), mapa_texto)

    # ── 2. Cabeçalho/rodapé da seção 1 e seção 2 (corpo) ────────────────────
    # O arquivo real tem 3 seções (capa = seção 0, sem cabeçalho; e duas
    # seções internas, 1 e 2, cada uma com seu próprio cabeçalho repetindo o
    # nome da edificação — a seção 1 guarda o nome numa TABELA de cabeçalho,
    # a seção 2 guarda o nome num PARÁGRAFO de cabeçalho). As duas precisam
    # de tratamento, senão o nome do laudo-modelo fica fixo no cabeçalho de
    # metade das páginas internas.
    for sec in (doc.sections[1], doc.sections[2]):
        for p in sec.header.paragraphs:
            for r in p.runs:
                if r.text == 'Promotoria de Justiça de Defesa da Infância e da Juventude':
                    r.text = '{{ edificacao_nome }}'
        for t in sec.header.tables:
            for row in t.rows:
                for cell in row.cells:
                    for p in cell.paragraphs:
                        for r in p.runs:
                            if r.text == 'Promotoria de Justiça de Defesa da Infância e da Juventude':
                                r.text = '{{ edificacao_nome }}'

    # ── 2b. Tabela 1 — "Equipe técnica" e "Responsabilidade técnica" (ART) ──
    # Multi-run no arquivo real: "[sobrenome]" e "[número]" têm estilo
    # diferente do resto da frase, então nenhum run isolado bate com o texto
    # completo do mapa. Forçamos para um único run (ver `forcar_run_unico`).
    t1 = doc.tables[1]
    forcar_run_unico(t1.rows[10].cells[1].paragraphs[0], '{{ equipe_tecnica }}')
    forcar_run_unico(t1.rows[11].cells[1].paragraphs[0], '{{ responsabilidade_tecnica }}')

    # ── 2c. Parágrafo do Sumário Executivo — negrito interno em 3 trechos ──
    # ("condição global boa", "84 pontos em 100", "23 classificadas como
    # Prioridade 1") divide a frase em 7 runs; nenhum bate com o texto
    # completo do mapa. Localizamos o parágrafo pelo texto concatenado e
    # forçamos para um único run.
    texto_sumario = (
        'A edificação da Promotoria de Justiça de Defesa da Infância e da Juventude '
        'encontra-se em condição global boa, com Índice de Qualidade de 84 pontos em 100. '
        'Das 249 verificações realizadas, 166 (67%) estão em conformidade e 83 apresentaram '
        'não conformidades, das quais 23 classificadas como Prioridade 1, em sua maioria de '
        'baixa complexidade e passíveis de correção no prazo de até três meses.'
    )
    for p in doc.paragraphs:
        if p.text == texto_sumario:
            forcar_run_unico(p, '{{ sumario_executivo }}')
            break

    # ── 2d. Parágrafo "Caracterização da Edificação" ───────────────────────
    # Este parágrafo ("O edifício abriga a Promotoria de Justiça... possui
    # três pavimentos... 4.745,52 m²... inaugurado em 29/07/2005... 21 anos
    # de uso... averbada em 9/08/2006...") corresponde, no desenho da
    # feature, à seção "Caracterização da Edificação" do laudo — texto livre
    # já existente em `Edificacao.descritivo`, preenchido manualmente por
    # edificação na plataforma, no mesmo molde de "Metodologia"/
    # "Fundamentação Normativa" (blocos de texto fixo/manual, não decompostos
    # em sub-variáveis). Por isso o parágrafo inteiro — não só o nome da
    # edificação — é substituído por um único marcador. Não criamos
    # variáveis como `idade_edificio`/`data_averbacao`: o projeto decidiu
    # explicitamente não rastrear data de averbação.
    for p in doc.paragraphs:
        if p.text.startswith('O edifício abriga a Promotoria de Justiça'):
            forcar_run_unico(p, '{{ caracterizacao_edificacao }}')
            break

    # ── 2e. Tabela 3 (Encaminhamento) — por índice de célula ────────────────
    # Cada célula tem 2 parágrafos separados (número, depois rótulo) — não
    # um único texto com "\n" como seria preciso para a passagem genérica
    # do passo 1 funcionar. Tratado por índice, como a Tabela 7, para evitar
    # qualquer risco de um '45'/'35'/'3' solto colidir com outra tabela.
    t3 = doc.tables[3]
    mapa_t3 = [
        ('{{ direcionamento_manutencao_total }}', 'contratos de manutenção vigentes ({{ direcionamento_manutencao_pct }}%)'),
        ('{{ direcionamento_nova_contratacao_total }}', 'nova contratação ({{ direcionamento_nova_contratacao_pct }}%)'),
        ('{{ direcionamento_garantia_total }}', 'acionamento de garantia de obra ({{ direcionamento_garantia_pct }}%)'),
    ]
    for cell, (total_tag, label_tag) in zip(t3.rows[0].cells, mapa_t3):
        paras = cell.paragraphs
        paras[0].runs[0].text = total_tag
        paras[1].runs[0].text = label_tag

    # ── 3. Tabela 1 (Identificação do Laudo) — linha "Edificação"/"Endereço" ──
    # já cobertas pelo mapa_texto acima (mesmo texto da capa).

    # ── 4. Tabela 7 (Resumo por Especialidade) — números linha a linha ──────
    t7 = doc.tables[7]
    mapa_t7 = {
        ('1', '0'): '{{ civil_total }}', ('1', '1'): '{{ civil_nc }}', ('1', '2'): '{{ civil_pct_conf }}%',
        ('1', '3'): '{{ civil_p1 }}', ('1', '4'): '{{ civil_p2 }}', ('1', '5'): '{{ civil_p3 }}',
        ('2', '0'): '{{ eletrica_total }}', ('2', '1'): '{{ eletrica_nc }}', ('2', '2'): '{{ eletrica_pct_conf }}%',
        ('2', '3'): '{{ eletrica_p1 }}', ('2', '4'): '{{ eletrica_p2 }}', ('2', '5'): '{{ eletrica_p3 }}',
        ('3', '0'): '{{ mecanica_total }}', ('3', '1'): '{{ mecanica_nc }}', ('3', '2'): '{{ mecanica_pct_conf }}%',
        ('3', '3'): '{{ mecanica_p1 }}', ('3', '4'): '{{ mecanica_p2 }}', ('3', '5'): '{{ mecanica_p3 }}',
        ('4', '0'): '{{ total }}', ('4', '1'): '{{ total_nc }}', ('4', '2'): '{{ pct_conformidade }}%',
        ('4', '3'): '{{ p1_total }}', ('4', '4'): '{{ p2_total }}', ('4', '5'): '{{ p3_total }}',
    }
    for (linha, col), tag in mapa_t7.items():
        celula = t7.rows[int(linha)].cells[int(col) + 1]  # +1 porque col0 é o nome, mapeado separadamente
        for p in celula.paragraphs:
            for r in p.runs:
                r.text = tag

    # ── 5. Tabela 8 (Matriz Risco x Prazo) — loop docxtpl ───────────────────
    # IMPORTANTE sobre o loop de linha {%tr %} do docxtpl: a tag "for" tem
    # que estar ISOLADA numa linha própria, e a tag "endfor" também, cada
    # uma numa linha dedicada só para isso (o conteúdo das outras células
    # dessas 2 linhas é irrelevante — a linha inteira é descartada e
    # substituída só pela tag). A linha de DADOS (com os {{ }} de verdade)
    # tem que ficar numa linha SEPARADA, sem nenhuma tag "tr" dentro, senão
    # o mecanismo de patch de XML do docxtpl apaga a linha inteira (dados
    # inclusos) e sobra um loop vazio — confirmado empiricamente com um
    # teste isolado (ver relatório desta task) antes de aplicar ao modelo
    # real. Por isso cada tabela com loop usa 4 linhas no total: cabeçalho +
    # linha-marcador "for" (sacrificada) + linha-molde de dados (a que de
    # fato repete) + linha-marcador "endfor" (sacrificada).
    t8 = doc.tables[8]
    linha_for = t8.rows[1]
    linha_molde = t8.rows[2]
    linha_endfor = t8.rows[3]
    linha_for.cells[0].paragraphs[0].runs[0].text = '{%tr for linha in matriz_risco_prazo %}'
    for i in range(1, 7):
        for p in linha_for.cells[i].paragraphs:
            for r in p.runs:
                r.text = ''
    linha_molde.cells[0].paragraphs[0].runs[0].text = '{{ linha.rotulo }}'
    for i in range(1, 6):
        linha_molde.cells[i].paragraphs[0].runs[0].text = '{{ linha.celulas.' + str(i - 1) + ' }}'
    linha_molde.cells[6].paragraphs[0].runs[0].text = '{{ linha.total }}'
    linha_endfor.cells[0].paragraphs[0].runs[0].text = '{%tr endfor %}'
    for i in range(1, 7):
        for p in linha_endfor.cells[i].paragraphs:
            for r in p.runs:
                r.text = ''
    # Remove a linha "Total" original (soma por coluna de prazo), que é
    # descartada nesta versão — mantemos header + for + molde + endfor.
    for row in list(t8.rows[4:]):
        row._tr.getparent().remove(row._tr)

    # ── 6. Tabela 9 (Dez maiores GUT / itens críticos) — loop docxtpl ───────
    # No arquivo real esta tabela tem 23 linhas de dados (todos os itens
    # críticos, já em ordem decrescente de GUT), não literalmente 10 — mas a
    # técnica funciona igual independente da quantidade de linhas originais;
    # a variável `top_gut` resolve em tempo de render quantos itens entram.
    t9 = doc.tables[9]
    linha_for = t9.rows[1]
    linha_molde = t9.rows[2]
    linha_endfor = t9.rows[3]
    linha_for.cells[0].paragraphs[0].runs[0].text = '{%tr for item in top_gut %}'
    for i in range(1, 6):
        for p in linha_for.cells[i].paragraphs:
            for r in p.runs:
                r.text = ''
    for i, campo in enumerate(['numero', 'local', 'nao_conformidade', 'recomendacao', 'gut', 'prazo']):
        linha_molde.cells[i].paragraphs[0].runs[0].text = '{{ item.' + campo + ' }}'
    linha_endfor.cells[0].paragraphs[0].runs[0].text = '{%tr endfor %}'
    for i in range(1, 6):
        for p in linha_endfor.cells[i].paragraphs:
            for r in p.runs:
                r.text = ''
    for row in list(t9.rows[4:]):
        row._tr.getparent().remove(row._tr)

    # ── 7. Tabela 6 (Histórico de intervenções) — loop docxtpl ──────────────
    t6 = doc.tables[6]
    linha_for = t6.rows[1]
    linha_molde = t6.rows[2]
    linha_endfor = t6.rows[3]
    linha_for.cells[0].paragraphs[0].runs[0].text = '{%tr for item in historico_intervencoes %}'
    for p in linha_for.cells[1].paragraphs:
        for r in p.runs:
            r.text = ''
    linha_molde.cells[0].paragraphs[0].runs[0].text = '{{ item.ano }}'
    linha_molde.cells[1].paragraphs[0].runs[0].text = '{{ item.descricao }}'
    linha_endfor.cells[0].paragraphs[0].runs[0].text = '{%tr endfor %}'
    for p in linha_endfor.cells[1].paragraphs:
        for r in p.runs:
            r.text = ''
    for row in list(t6.rows[4:]):
        row._tr.getparent().remove(row._tr)

    # ── 8. Tabela 12 (Plano de Ação) — loop docxtpl ─────────────────────────
    t12 = doc.tables[12]
    linha_for = t12.rows[1]
    linha_molde = t12.rows[2]
    linha_endfor = t12.rows[3]
    linha_for.cells[0].paragraphs[0].runs[0].text = '{%tr for linha in plano_de_acao %}'
    for i in range(1, 4):
        for p in linha_for.cells[i].paragraphs:
            for r in p.runs:
                r.text = ''
    linha_molde.cells[0].paragraphs[0].runs[0].text = '{{ linha.horizonte }}'
    linha_molde.cells[1].paragraphs[0].runs[0].text = '{{ linha.nc }}'
    linha_molde.cells[2].paragraphs[0].runs[0].text = '{{ linha.principais_acoes }}'
    linha_molde.cells[3].paragraphs[0].runs[0].text = '{{ linha.forma_execucao }}'
    linha_endfor.cells[0].paragraphs[0].runs[0].text = '{%tr endfor %}'
    for i in range(1, 4):
        for p in linha_endfor.cells[i].paragraphs:
            for r in p.runs:
                r.text = ''
    for row in list(t12.rows[4:]):
        row._tr.getparent().remove(row._tr)

    # ── 9. Tabela 14 (Assinaturas) — 3 colunas fixas (sempre civil/elétrica/mecânica) ──
    t14 = doc.tables[14]
    assinaturas = [
        ('{{ nome_civil }}', '{{ titulo_civil }}', '{{ crea_civil }}'),
        ('{{ nome_eletrica }}', '{{ titulo_eletrica }}', '{{ crea_eletrica }}'),
        ('{{ nome_mecanica }}', '{{ titulo_mecanica }}', '{{ crea_mecanica }}'),
    ]
    for cell, tags in zip(t14.rows[0].cells, assinaturas):
        paras = cell.paragraphs
        for p, tag in zip(paras, tags):
            # Alguns parágrafos têm 2 runs no arquivo real (ex.: "Carlos
            # Eduardo " + "[sobrenome]", ou "CREA nº " + "[número]", este
            # último com estilo diferente). Usa-se a mesma técnica do
            # `forcar_run_unico`: primeiro run recebe a tag inteira, os
            # demais são esvaziados, para não sobrar texto de exemplo colado
            # depois da variável.
            forcar_run_unico(p, tag)

    # ── 10. Tabela 15 (Anexo I completo) — loop docxtpl ─────────────────────
    t15 = doc.tables[15]
    linha_for = t15.rows[1]
    linha_molde = t15.rows[2]
    linha_endfor = t15.rows[3]
    campos_anexo = ['numero', 'local', 'sistema_elemento', 'situacao',
                     'nao_conformidade', 'recomendacao', 'grau_risco', 'gut', 'prazo']
    linha_for.cells[0].paragraphs[0].runs[0].text = '{%tr for item in anexo01 %}'
    for i in range(1, 9):
        for p in linha_for.cells[i].paragraphs:
            for r in p.runs:
                r.text = ''
    for i, campo in enumerate(campos_anexo):
        linha_molde.cells[i].paragraphs[0].runs[0].text = '{{ item.' + campo + ' }}'
    linha_endfor.cells[0].paragraphs[0].runs[0].text = '{%tr endfor %}'
    for i in range(1, 9):
        for p in linha_endfor.cells[i].paragraphs:
            for r in p.runs:
                r.text = ''
    for row in list(t15.rows[4:]):
        row._tr.getparent().remove(row._tr)

    doc.save(destino)

    if nao_encontrados:
        print('AVISO — textos não encontrados (conferir manualmente no Word):')
        for t in sorted(nao_encontrados):
            print(f'  - {t[:80]!r}')
    else:
        print('OK — todos os textos do mapa foram substituídos.')


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
