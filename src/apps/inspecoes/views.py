import base64
import functools
import json
import io
import zipfile
import os
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.files.base import ContentFile
from django.core.paginator import Paginator
from django.core.exceptions import RequestDataTooBig
from django.db.models import Count, Q, Min, Max
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.template.loader import render_to_string
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_http_methods

from django.urls import reverse
from django.utils import timezone

from .models import (
    Inspecao, InspecaoEspecialidade, Achado, Foto, OpcaoCampo, LogAcesso,
    VisitaTecnica, VisitaFoto, EncaminhamentoHistorico, RelatorioFinalInspecao,
)
from .forms import (
    InspecaoForm, EspecialidadeForm, AchadoForm, InspecaoFilterForm,
    VisitaTecnicaForm, VisitaFilterForm, SignUpForm,
    AcompanhamentoFilterForm, ReclassificarForm, AcompanhamentoAchadoForm,
    ConclusaoEspecialidadeForm,
)
from apps.edificacoes.forms import DescritivoEdificacaoForm
from apps.edificacoes.models import Profissional
from .imagens import comprimir_imagem


def _redirect_detail(inspecao_pk, esp_pk=None):
    """Redireciona para o detalhe da inspeção abrindo a aba da especialidade correta.

    Usa query param (?aba=) — preservado de forma confiável no redirect 302 —
    em vez de fragmento (#), que alguns navegadores descartam após POST.
    """
    url = reverse('inspecoes:detail', kwargs={'pk': inspecao_pk})
    if esp_pk:
        url += f'?aba={esp_pk}'
    return redirect(url)


def _log(request, tipo, descricao):
    ip = (
        request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
        or request.META.get('REMOTE_ADDR')
    )
    LogAcesso.objects.create(
        usuario=request.user,
        tipo=tipo,
        descricao=descricao,
        ip=ip or None,
    )


# ── Erros ─────────────────────────────────────────────────────────────────────

def erro_404(request, exception=None):
    return render(request, '404.html', status=404)


def erro_403(request, exception=None):
    return render(request, '403.html', status=403)


# ── Página inicial (menu) ─────────────────────────────────────────────────────

@login_required
def home(request):
    return render(request, 'inspecoes/home.html')


# ── Cadastro de novo usuário (público) ────────────────────────────────────────

def _notificar_novo_usuario(user, request):
    """Envia e-mail informando o cadastro de um novo usuário.

    Falhas de envio são registradas e ignoradas — nunca impedem o cadastro.
    """
    from django.conf import settings
    from django.core.mail import send_mail
    from django.utils import timezone

    destinatarios = getattr(settings, 'NOTIFICAR_NOVO_USUARIO', None)
    if not destinatarios:
        return
    quando = timezone.localtime().strftime('%d/%m/%Y às %H:%M')
    assunto = '[Inspeções Prediais MPDFT] Novo usuário cadastrado'
    corpo = (
        'Um novo usuário foi cadastrado na plataforma de Inspeções Prediais do MPDFT.\n\n'
        f'Nome: {user.get_full_name() or "(não informado)"}\n'
        f'Usuário (login): {user.username}\n'
        f'E-mail: {user.email}\n'
        f'Data/hora do cadastro: {quando}\n\n'
        'Mensagem automática — não é necessário responder.'
    )
    try:
        send_mail(assunto, corpo, settings.DEFAULT_FROM_EMAIL, destinatarios, fail_silently=False)
    except Exception:
        import logging
        logging.getLogger(__name__).exception('Falha ao enviar e-mail de novo usuário.')


@require_http_methods(['GET', 'POST'])
def signup(request):
    if request.user.is_authenticated:
        return redirect('inspecoes:home')
    form = SignUpForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        from django.contrib.auth import login
        user = form.save()
        _notificar_novo_usuario(user, request)
        login(request, user)
        messages.success(request, f'Conta criada com sucesso. Bem-vindo(a), {user.get_full_name()}!')
        return redirect('inspecoes:home')
    return render(request, 'registration/signup.html', {'form': form})


# ── Inspeções (container por edificação) ──────────────────────────────────────

@login_required
def inspecao_list(request):
    form = InspecaoFilterForm(request.GET or None)
    qs = Inspecao.objects.select_related('edificacao').prefetch_related('especialidades').annotate(
        num_especialidades=Count('especialidades', distinct=True),
        num_achados=Count('especialidades__achados', distinct=True),
        data_inicio=Min('especialidades__data_inspecao'),
    )

    if form.is_valid():
        if form.cleaned_data.get('edificacao'):
            qs = qs.filter(edificacao=form.cleaned_data['edificacao'])
        if form.cleaned_data.get('especialidade'):
            qs = qs.filter(especialidades__especialidade=form.cleaned_data['especialidade']).distinct()
        if form.cleaned_data.get('profissional'):
            qs = qs.filter(especialidades__profissionais__nome__icontains=form.cleaned_data['profissional']).distinct()
        if form.cleaned_data.get('data_inicio'):
            qs = qs.filter(especialidades__data_inspecao__gte=form.cleaned_data['data_inicio']).distinct()
        if form.cleaned_data.get('data_fim'):
            qs = qs.filter(especialidades__data_inspecao__lte=form.cleaned_data['data_fim']).distinct()
        if form.cleaned_data.get('status'):
            qs = qs.filter(especialidades__status=form.cleaned_data['status']).distinct()

    paginator = Paginator(qs.order_by('-criado_em'), 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    em_andamento_count = InspecaoEspecialidade.objects.filter(status='em_andamento').count()

    return render(request, 'inspecoes/list.html', {
        'filter_form': form,
        'page_obj': page_obj,
        'total_count': paginator.count,
        'em_andamento_count': em_andamento_count,
    })


def _aplicar_data_criacao(inspecao, nova_data):
    """Ajusta a data de criação preservando o horário original."""
    from django.utils import timezone
    atual = timezone.localtime(inspecao.criado_em)
    novo = atual.replace(year=nova_data.year, month=nova_data.month, day=nova_data.day)
    inspecao.criado_em = novo
    inspecao.save(update_fields=['criado_em'])


@login_required
def inspecao_create(request):
    form = InspecaoForm(request.POST or None)
    if form.is_valid():
        inspecao = form.save()
        _aplicar_data_criacao(inspecao, form.cleaned_data['data_criacao'])
        _log(request, 'inspecao_criada', f'Inspeção criada para "{inspecao.edificacao}".')
        messages.success(request, 'Inspeção criada. Adicione as especialidades abaixo.')
        return redirect('inspecoes:detail', pk=inspecao.pk)
    return render(request, 'inspecoes/form.html', {'form': form})


@login_required
def inspecao_detail(request, pk):
    from django.conf import settings
    inspecao = get_object_or_404(
        Inspecao.objects.select_related('edificacao').prefetch_related(
            'especialidades',
            'especialidades__achados__fotos',
        ),
        pk=pk,
    )
    backup_salvo = os.path.exists(
        os.path.join(settings.MEDIA_ROOT, 'backups', f'inspecao_{pk}.zip')
    )
    # Determina qual aba (especialidade) deve abrir ativa
    esps = list(inspecao.especialidades.all())
    aba_param = request.GET.get('aba', '')
    aba_ativa_pk = None
    if aba_param.isdigit():
        pk_aba = int(aba_param)
        if any(e.pk == pk_aba for e in esps):
            aba_ativa_pk = pk_aba
    if aba_ativa_pk is None and esps:
        aba_ativa_pk = esps[0].pk
    return render(request, 'inspecoes/detail.html', {
        'inspecao': inspecao,
        'backup_salvo': backup_salvo,
        'aba_ativa_pk': aba_ativa_pk,
    })


@login_required
def inspecao_update(request, pk):
    inspecao = get_object_or_404(Inspecao, pk=pk)
    form = InspecaoForm(request.POST or None, instance=inspecao)
    if form.is_valid():
        inspecao = form.save()
        _aplicar_data_criacao(inspecao, form.cleaned_data['data_criacao'])
        messages.success(request, 'Inspeção atualizada com sucesso.')
        return redirect('inspecoes:detail', pk=pk)
    return render(request, 'inspecoes/form.html', {'form': form, 'inspecao': inspecao})


@login_required
@require_POST
def inspecao_delete(request, pk):
    inspecao = get_object_or_404(Inspecao, pk=pk)
    nome = str(inspecao)
    _log(request, 'inspecao_excluida', f'Inspeção excluída: "{nome}".')
    inspecao.excluir(request.user)
    messages.success(request, f'Inspeção "{nome}" excluída com sucesso.')
    return redirect('inspecoes:list')


# ── Especialidades ─────────────────────────────────────────────────────────────

def _profissionais_ids_do_post(request):
    """Coleta os ids dos <select> dinâmicos 'profissionais' (um por campo)."""
    return [int(i) for i in request.POST.getlist('profissionais') if i.strip()]


@login_required
def especialidade_create(request, inspecao_pk):
    inspecao = get_object_or_404(Inspecao, pk=inspecao_pk)
    form = EspecialidadeForm(request.POST or None, inspecao=inspecao)
    ids_selecionados = _profissionais_ids_do_post(request)
    erro_profissionais = None
    if request.method == 'POST' and form.is_valid():
        profissionais = Profissional.objects.filter(pk__in=ids_selecionados)
        if not profissionais:
            erro_profissionais = 'Informe ao menos um profissional responsável.'
        else:
            esp = form.save(commit=False)
            esp.inspecao = inspecao
            try:
                esp.full_clean(exclude=['profissionais'])
                esp.save()
                esp.profissionais.set(profissionais)
                _log(request, 'especialidade_criada', f'{esp.get_especialidade_display()} criada em "{inspecao.edificacao}".')
                messages.success(request, f'{esp.get_especialidade_display()} adicionada com sucesso.')
                return redirect('inspecoes:detail', pk=inspecao_pk)
            except Exception as e:
                messages.error(request, f'Erro ao salvar: {e}')
    return render(request, 'inspecoes/especialidade_form.html', {
        'form': form,
        'inspecao': inspecao,
        'profissionais_disponiveis': Profissional.objects.all(),
        'ids_selecionados': ids_selecionados or [None],
        'erro_profissionais': erro_profissionais,
    })


def _pode_editar_especialidade(user, esp):
    """Retorna True se o usuário tem permissão para editar esta especialidade."""
    if user.is_staff or user.is_superuser:
        return True
    return user.get_full_name() in esp.profissionais_lista


def _acesso_negado_especialidade(request, esp):
    messages.error(
        request,
        f'Acesso negado. Apenas os profissionais responsáveis '
        f'("{esp.profissionais_display}") podem realizar esta ação.',
    )
    return _redirect_detail(esp.inspecao_id, esp.pk)


def _pode_gerar_relatorio_final(user, inspecao):
    """Quem pode gerar/editar o Relatório Final de Inspeção: staff, superusuário,
    ou qualquer profissional listado em QUALQUER UMA das especialidades da
    inspeção (não precisa ter participado das 3 — ver glossário, Seção 5)."""
    if user.is_staff or user.is_superuser:
        return True
    nomes_permitidos = set()
    for esp in inspecao.especialidades.all():
        nomes_permitidos.update(esp.profissionais_lista)
    return user.get_full_name() in nomes_permitidos


def _copiar_fotos_para_relatorio(inspecao_pk, numero_versao, achado, fotos):
    """Copia os arquivos de imagem usados para um caminho próprio do
    relatório — independente do ciclo de vida da Foto original (ADR-07).
    Retorna a lista de caminhos salvos (relativos ao storage)."""
    from django.core.files.storage import default_storage
    caminhos = []
    for i, foto in enumerate(fotos, start=1):
        ext = foto.arquivo.name.rsplit('.', 1)[-1]
        destino = f'relatorios/{inspecao_pk}/v{numero_versao}/achado_{achado.pk}_{i}.{ext}'
        with foto.arquivo.open('rb') as origem:
            caminho_salvo = default_storage.save(destino, ContentFile(origem.read()))
        caminhos.append(caminho_salvo)
    return caminhos


def _dados_gerais_snapshot(especialidades):
    """Reaproveita o mesmo recorte de números do painel de encerramento
    (análise geral — `_analise_data`/`por_especialidade` em
    `inspecao_analise_pdf`), mas como valores simples (int/str), não
    instâncias de `Achado` — o resultado precisa ser JSON-serializável
    para entrar no snapshot."""
    todos_achados = []
    for esp in especialidades:
        todos_achados.extend(list(esp.achados.all()))
    total = len(todos_achados)
    nao_conformes = [a for a in todos_achados if a.gut_total > 0]
    total_nc = len(nao_conformes)

    por_especialidade = []
    for esp in especialidades:
        ach = [a for a in todos_achados if a.especialidade_id == esp.pk]
        nc = [a for a in ach if a.gut_total > 0]
        por_especialidade.append({
            'especialidade_nome': esp.get_especialidade_display(),
            'profissionais': esp.profissionais_display,
            'data_inspecao': esp.data_inspecao.strftime('%d/%m/%Y'),
            'status': esp.get_status_display(),
            'total': len(ach),
            'total_nc': len(nc),
            'p1': len([a for a in nc if a.prioridade_risco == 1]),
            'p2': len([a for a in nc if a.prioridade_risco == 2]),
            'p3': len([a for a in nc if a.prioridade_risco == 3]),
        })

    return {
        'total_achados': total,
        'total_nao_conformes': total_nc,
        'total_conformes': total - total_nc,
        'p1': len([a for a in nao_conformes if a.prioridade_risco == 1]),
        'p2': len([a for a in nao_conformes if a.prioridade_risco == 2]),
        'p3': len([a for a in nao_conformes if a.prioridade_risco == 3]),
        'por_especialidade': por_especialidade,
    }


def _montar_snapshot_relatorio(inspecao, numero_versao):
    """Monta o conteúdo estruturado (JSON-serializável) congelado numa
    geração do Relatório Final — ver ADR-03. Inclui os dados gerais
    (mesmos números do painel de encerramento) e, por especialidade,
    achados completos (não conformes, com fotos copiadas) e resumidos
    (conformes, sem foto). `anexo01` é a planilha com TODOS os itens
    verificados (conformes e não conformes, sem foto) — formato do laudo-
    modelo MPDFT/SPO, numeração sequencial contínua entre especialidades."""
    edificacao = inspecao.edificacao
    especialidades = list(inspecao.especialidades.all())
    especialidades_data = []
    anexo01 = []
    grupo_labels = dict(Achado.GRUPO_TECNICO_CHOICES)
    prazo_labels = dict(Achado.PRAZO_CHOICES)
    for esp in especialidades:
        achados_completos = []
        achados_resumidos = []
        for achado in esp.achados.all():
            anexo01.append({
                'numero': len(anexo01) + 1,
                'especialidade_nome': esp.get_especialidade_display(),
                'localizacao': achado.localizacao,
                'sub_localizacao': achado.sub_localizacao,
                'grupo_tecnico_nome': grupo_labels.get(achado.grupo_tecnico, achado.grupo_tecnico),
                'verificacao': achado.verificacao,
                'situacao': 'Conforme' if achado.gut_total == 0 else 'Não conforme',
                'descricao_nao_conformidade': achado.descricao_nao_conformidade,
                'recomendacao': achado.recomendacao,
                'prioridade_risco': achado.get_prioridade_risco_display(),
                'prioridade_risco_num': achado.prioridade_risco,
                'gut_total': achado.gut_total,
                'prazo_label': prazo_labels.get(achado.prazo_meses, f'{achado.prazo_meses} meses') if achado.gut_total else '',
            })
            if achado.gut_total > 0:
                fotos = list(achado.fotos.order_by('data_upload')[:2])
                caminhos_fotos = _copiar_fotos_para_relatorio(inspecao.pk, numero_versao, achado, fotos)
                achados_completos.append({
                    'localizacao': achado.localizacao,
                    'sub_localizacao': achado.sub_localizacao,
                    'verificacao': achado.verificacao,
                    'descricao_nao_conformidade': achado.descricao_nao_conformidade,
                    'gut_total': achado.gut_total,
                    'prioridade_risco': achado.get_prioridade_risco_display(),
                    'prioridade_risco_num': achado.prioridade_risco,
                    'recomendacao': achado.recomendacao,
                    'fotos': caminhos_fotos,
                })
            else:
                achados_resumidos.append({
                    'localizacao': achado.localizacao,
                    'verificacao': achado.verificacao,
                })
        titulo_profissional = {
            'civil': 'Engenheiro civil', 'eletrica': 'Engenheiro eletricista', 'mecanica': 'Engenheiro mecânico',
        }.get(esp.especialidade, esp.get_especialidade_display())
        especialidades_data.append({
            'especialidade': esp.especialidade,
            'especialidade_nome': esp.get_especialidade_display(),
            'titulo_profissional': titulo_profissional,
            'profissionais': esp.profissionais_lista,
            'data_inspecao': esp.data_inspecao.isoformat(),
            'conclusao': esp.conclusao,
            'achados_completos': achados_completos,
            'achados_resumidos': achados_resumidos,
        })
    datas_vistorias = sorted({esp.data_inspecao for esp in especialidades})
    return {
        'edificacao_nome': edificacao.nome,
        'edificacao_endereco': edificacao.endereco,
        'edificacao_descritivo': edificacao.descritivo,
        'inspecao_criada_em': inspecao.criado_em.isoformat(),
        'datas_vistorias': [d.strftime('%d/%m') for d in datas_vistorias],
        'dados_gerais': _dados_gerais_snapshot(especialidades),
        'especialidades': especialidades_data,
        'anexo01': anexo01,
    }


@login_required
def especialidade_update(request, pk):
    esp = get_object_or_404(InspecaoEspecialidade.objects.select_related('inspecao'), pk=pk)
    if not _pode_editar_especialidade(request.user, esp):
        return _acesso_negado_especialidade(request, esp)
    form = EspecialidadeForm(request.POST or None, instance=esp, inspecao=esp.inspecao)
    ids_selecionados = _profissionais_ids_do_post(request) if request.method == 'POST' else list(esp.profissionais.values_list('pk', flat=True))
    erro_profissionais = None
    if request.method == 'POST' and form.is_valid():
        profissionais = Profissional.objects.filter(pk__in=ids_selecionados)
        if not profissionais:
            erro_profissionais = 'Informe ao menos um profissional responsável.'
        else:
            esp = form.save(commit=False)
            esp.save()
            esp.profissionais.set(profissionais)
            if esp.status == 'finalizada':
                _avisar_relatorio_final_desatualizado(request, esp)
            messages.success(request, 'Especialidade atualizada com sucesso.')
            return _redirect_detail(esp.inspecao_id, esp.pk)
    return render(request, 'inspecoes/especialidade_form.html', {
        'form': form,
        'inspecao': esp.inspecao,
        'especialidade': esp,
        'profissionais_disponiveis': Profissional.objects.all(),
        'ids_selecionados': ids_selecionados or [None],
        'erro_profissionais': erro_profissionais,
    })


@login_required
def especialidade_conclusao(request, pk):
    """Tela dedicada para a conclusão e direcionamentos — separada da edição
    cadastral da especialidade (`especialidade_update`), já que é um texto
    redigido perto de finalizar, não um dado de cadastro."""
    esp = get_object_or_404(InspecaoEspecialidade.objects.select_related('inspecao'), pk=pk)
    if not _pode_editar_especialidade(request.user, esp):
        return _acesso_negado_especialidade(request, esp)
    form = ConclusaoEspecialidadeForm(request.POST or None, instance=esp)
    if request.method == 'POST' and form.is_valid():
        form.save()
        if esp.status == 'finalizada':
            _avisar_relatorio_final_desatualizado(request, esp)
        messages.success(request, 'Conclusão atualizada com sucesso.')
        return _redirect_detail(esp.inspecao_id, esp.pk)
    return render(request, 'inspecoes/especialidade_conclusao.html', {
        'form': form,
        'inspecao': esp.inspecao,
        'especialidade': esp,
    })


@login_required
@require_POST
def especialidade_delete(request, pk):
    esp = get_object_or_404(InspecaoEspecialidade.objects.select_related('inspecao'), pk=pk)
    if not _pode_editar_especialidade(request.user, esp):
        return _acesso_negado_especialidade(request, esp)
    inspecao_pk = esp.inspecao_id
    nome = esp.get_especialidade_display()
    _log(request, 'especialidade_excluida', f'{nome} excluída de "{esp.inspecao.edificacao}".')
    esp.excluir(request.user)
    messages.success(request, f'Especialidade "{nome}" excluída com sucesso.')
    return redirect('inspecoes:detail', pk=inspecao_pk)


@login_required
@require_POST
def especialidade_finalizar(request, pk):
    esp = get_object_or_404(InspecaoEspecialidade, pk=pk)
    if not _pode_editar_especialidade(request.user, esp):
        return _acesso_negado_especialidade(request, esp)
    if esp.status == 'finalizada':
        messages.error(request, 'Esta especialidade já foi finalizada.')
        return _redirect_detail(esp.inspecao_id, esp.pk)
    if not esp.achados.exists():
        messages.error(request, 'Não é possível finalizar sem achados registrados.')
        return _redirect_detail(esp.inspecao_id, esp.pk)
    if not esp.conclusao.strip():
        messages.error(request, 'Não é possível finalizar sem preencher a conclusão e os direcionamentos.')
        return _redirect_detail(esp.inspecao_id, esp.pk)
    esp.status = 'finalizada'
    esp.save(update_fields=['status', 'atualizado_em'])
    messages.success(request, f'{esp.get_especialidade_display()} finalizada.')
    # Se todas as especialidades estão finalizadas, gera backup automático
    inspecao = esp.inspecao
    if inspecao.status_geral == 'finalizada':
        try:
            _salvar_backup_em_disco(inspecao)
            messages.success(request, 'Inspeção finalizada! Backup gerado automaticamente.')
        except Exception as e:
            messages.warning(request, f'Inspeção finalizada, mas o backup automático falhou: {e}')
    return redirect('inspecoes:analise', pk=pk)


def _avisar_relatorio_final_desatualizado(request, esp):
    """Se a inspeção já tem um Relatório Final gerado, avisa (sem bloquear)
    que editar agora não atualiza retroativamente esse relatório — ver
    ADR-06. Usado tanto ao reabrir uma especialidade quanto ao editar os
    campos de uma especialidade já finalizada (ex.: conclusão), que é outra
    porta de entrada para mudar algo que alimenta o relatório."""
    ultimo_relatorio = esp.inspecao.relatorios_finais.first()
    if ultimo_relatorio:
        messages.warning(
            request,
            f'Esta inspeção já tem um Relatório Final gerado (v{ultimo_relatorio.numero_versao}, '
            f'{ultimo_relatorio.gerado_em:%d/%m/%Y}). Editar agora não altera esse relatório — '
            f'gere uma nova versão se precisar refletir esta mudança.',
        )


@login_required
@require_POST
def especialidade_reabrir(request, pk):
    esp = get_object_or_404(InspecaoEspecialidade, pk=pk)
    if not _pode_editar_especialidade(request.user, esp):
        return _acesso_negado_especialidade(request, esp)
    if esp.status == 'em_andamento':
        messages.error(request, 'Esta especialidade já está em andamento.')
        return _redirect_detail(esp.inspecao_id, esp.pk)
    _avisar_relatorio_final_desatualizado(request, esp)
    esp.status = 'em_andamento'
    esp.save(update_fields=['status', 'atualizado_em'])
    messages.success(request, f'{esp.get_especialidade_display()} reaberta.')
    return _redirect_detail(esp.inspecao_id, esp.pk)


# ── Relatório Final de Inspeção (ART/CREA) ──────────────────────────────────

@login_required
def relatorio_final_painel(request, pk):
    inspecao = get_object_or_404(
        Inspecao.objects.select_related('edificacao').prefetch_related(
            'especialidades', 'especialidades__achados__fotos', 'relatorios_finais',
        ),
        pk=pk,
    )
    if not _pode_gerar_relatorio_final(request.user, inspecao):
        messages.error(
            request,
            'Acesso negado. Apenas os profissionais responsáveis por esta '
            'inspeção podem acessar o Relatório Final.',
        )
        return redirect('inspecoes:detail', pk=pk)
    return render(request, 'inspecoes/relatorio_final_painel.html', {
        'inspecao': inspecao,
        'pendencias': inspecao.pendencias_relatorio_final(),
        'versoes': inspecao.relatorios_finais.all(),
        'descritivo_form': DescritivoEdificacaoForm(instance=inspecao.edificacao),
    })


@login_required
@require_POST
def relatorio_final_editar_descritivo(request, pk):
    inspecao = get_object_or_404(Inspecao.objects.select_related('edificacao'), pk=pk)
    if not _pode_gerar_relatorio_final(request.user, inspecao):
        messages.error(request, 'Acesso negado.')
        return redirect('inspecoes:relatorio_final_painel', pk=pk)
    form = DescritivoEdificacaoForm(request.POST, instance=inspecao.edificacao)
    if form.is_valid():
        form.save()
        messages.success(request, 'Descritivo da edificação atualizado.')
    else:
        messages.error(request, 'Não foi possível salvar o descritivo.')
    return redirect('inspecoes:relatorio_final_painel', pk=pk)


@login_required
@require_POST
def relatorio_final_gerar(request, pk):
    inspecao = get_object_or_404(
        Inspecao.objects.select_related('edificacao').prefetch_related(
            'especialidades', 'especialidades__achados__fotos', 'relatorios_finais',
        ),
        pk=pk,
    )
    if not _pode_gerar_relatorio_final(request.user, inspecao):
        messages.error(request, 'Acesso negado.')
        return redirect('inspecoes:relatorio_final_painel', pk=pk)

    pendencias = inspecao.pendencias_relatorio_final()
    if pendencias:
        messages.error(request, 'Não é possível gerar o relatório: ' + ' '.join(pendencias))
        return redirect('inspecoes:relatorio_final_painel', pk=pk)

    numero_versao = (inspecao.relatorios_finais.aggregate(m=Max('numero_versao'))['m'] or 0) + 1
    # `snapshot` (caminhos leves) é o que persiste no banco; `contexto_pdf`
    # (fotos como data URI) é só para renderizar o HTML/PDF desta vez — ver
    # a nota em `_montar_contexto_pdf_com_fotos` sobre nunca trocar os dois.
    snapshot = _montar_snapshot_relatorio(inspecao, numero_versao)
    contexto_pdf = _montar_contexto_pdf_com_fotos(snapshot)
    painel = _painel_encerramento_relatorio(inspecao, list(inspecao.especialidades.all()))
    html = render_to_string('inspecoes/relatorio_final_pdf.html', {
        'inspecao': inspecao, 'snapshot': contexto_pdf, 'numero_versao': numero_versao,
        'painel': painel, 'logo_mpdft': _logo_mpdft_data_uri(),
        'fontes_css': _fontes_pdf_css(),
    }, request=request)
    pdf_bytes = _gerar_pdf_bytes(html)
    if pdf_bytes is not None:
        gerado_em = timezone.now()
        titulo = f'Laudo Técnico de Inspeção Predial — {inspecao.edificacao.nome}'
        pdf_bytes = _aplicar_metadados_pdf(pdf_bytes, titulo, numero_versao, gerado_em)
    if pdf_bytes is None:
        # `_montar_snapshot_relatorio` já copiou as fotos para
        # relatorios/<pk>/v<numero_versao>/... antes de sabermos que o PDF
        # falharia — sem isso, ficariam órfãs (nenhuma RelatorioFinalInspecao
        # aponta pra elas) e o número de versão ficaria abandonado.
        from django.core.files.storage import default_storage
        for esp in snapshot['especialidades']:
            for achado in esp['achados_completos']:
                for caminho in achado['fotos']:
                    default_storage.delete(caminho)
        messages.error(request, 'Erro ao gerar o PDF do relatório. Tente novamente.')
        return redirect('inspecoes:relatorio_final_painel', pk=pk)

    relatorio = RelatorioFinalInspecao(
        inspecao=inspecao, numero_versao=numero_versao, snapshot=snapshot, gerado_por=request.user,
    )
    nome_arquivo = f"relatorio_final_{inspecao.edificacao.nome.replace(' ', '_')}_v{numero_versao}.pdf"
    relatorio.arquivo_pdf.save(nome_arquivo, ContentFile(pdf_bytes), save=False)
    relatorio.save()

    _log(request, 'relatorio_final_gerado',
         f'Relatório Final de Inspeção (v{numero_versao}) gerado para "{inspecao.edificacao}".')
    messages.success(request, f'Relatório Final de Inspeção (versão {numero_versao}) gerado com sucesso.')
    return redirect('inspecoes:relatorio_final_painel', pk=pk)


@login_required
def relatorio_final_download(request, pk, versao_pk):
    inspecao = get_object_or_404(Inspecao, pk=pk)
    if not _pode_gerar_relatorio_final(request.user, inspecao):
        messages.error(request, 'Acesso negado.')
        return redirect('inspecoes:detail', pk=pk)
    relatorio = get_object_or_404(RelatorioFinalInspecao, pk=versao_pk, inspecao=inspecao)
    resp = HttpResponse(relatorio.arquivo_pdf.read(), content_type='application/pdf')
    resp['Content-Disposition'] = f'attachment; filename="{os.path.basename(relatorio.arquivo_pdf.name)}"'
    return resp


# ── Achados ────────────────────────────────────────────────────────────────────

@login_required
def achado_create(request, esp_pk):
    esp = get_object_or_404(InspecaoEspecialidade.objects.select_related('inspecao'), pk=esp_pk)
    if not esp.pode_editar:
        messages.error(request, 'Não é possível adicionar achados a uma especialidade finalizada. Reabra primeiro.')
        return _redirect_detail(esp.inspecao_id, esp.pk)
    form = AchadoForm(request.POST or None)
    if form.is_valid():
        achado = form.save(commit=False)
        achado.especialidade = esp
        achado.save()
        for arquivo in request.FILES.getlist('fotos'):
            if foto_valida(arquivo.content_type, arquivo.size):
                cf, nome, tamanho = comprimir_imagem(arquivo.read(), arquivo.name)
                Foto.objects.create(
                    achado=achado,
                    arquivo=cf,
                    nome_original=nome,
                    tamanho_bytes=tamanho,
                )
        _log(request, 'achado_criado',
             f'Achado criado: "{achado.verificacao}" em {esp.get_especialidade_display()} — "{esp.inspecao.edificacao}".')
        messages.success(request, 'Achado registrado com sucesso.')
        return _redirect_detail(esp.inspecao_id, esp.pk)
    return render(request, 'inspecoes/achado_form.html', {
        'form': form,
        'especialidade': esp,
        'fotos_existentes': [],
    })


@login_required
def achado_detail(request, pk):
    achado = get_object_or_404(
        Achado.objects.select_related('especialidade__inspecao__edificacao').prefetch_related('fotos'),
        pk=pk,
    )
    return render(request, 'inspecoes/achado_detail.html', {'achado': achado})


@login_required
def achado_update(request, pk):
    achado = get_object_or_404(Achado.objects.select_related('especialidade__inspecao'), pk=pk)
    if not achado.especialidade.pode_editar:
        messages.error(request, 'Não é possível editar achados de uma especialidade finalizada. Reabra primeiro.')
        return _redirect_detail(achado.especialidade.inspecao_id, achado.especialidade_id)
    form = AchadoForm(request.POST or None, instance=achado)
    if form.is_valid():
        form.save()
        messages.success(request, 'Achado atualizado com sucesso.')
        return _redirect_detail(achado.especialidade.inspecao_id, achado.especialidade_id)
    return render(request, 'inspecoes/achado_form.html', {
        'form': form,
        'especialidade': achado.especialidade,
        'achado': achado,
        'fotos_existentes': achado.fotos.all(),
    })


@login_required
@require_POST
def achado_delete(request, pk):
    achado = get_object_or_404(Achado.objects.select_related('especialidade__inspecao'), pk=pk)
    if not achado.especialidade.pode_editar:
        messages.error(request, 'Não é possível excluir achados de uma especialidade finalizada. Reabra primeiro.')
        return _redirect_detail(achado.especialidade.inspecao_id, achado.especialidade_id)
    inspecao_pk = achado.especialidade.inspecao_id
    esp_pk = achado.especialidade_id
    _log(request, 'achado_excluido',
         f'Achado excluído: "{achado.verificacao}" em '
         f'{achado.especialidade.get_especialidade_display()} — "{achado.especialidade.inspecao.edificacao}".')
    achado.excluir(request.user)
    messages.success(request, 'Achado excluído com sucesso.')
    return _redirect_detail(inspecao_pk, esp_pk)


@login_required
def achado_duplicate(request, pk):
    original = get_object_or_404(Achado.objects.select_related('especialidade__inspecao'), pk=pk)
    esp = original.especialidade
    if not esp.pode_editar:
        messages.error(request, 'Não é possível duplicar achados de uma especialidade finalizada. Reabra primeiro.')
        return _redirect_detail(esp.inspecao_id, esp.pk)

    if request.method == 'POST':
        form = AchadoForm(request.POST)
        if form.is_valid():
            novo = form.save(commit=False)
            novo.especialidade = esp
            novo.save()
            for arquivo in request.FILES.getlist('fotos'):
                if foto_valida(arquivo.content_type, arquivo.size):
                    cf, nome, tamanho = comprimir_imagem(arquivo.read(), arquivo.name)
                    Foto.objects.create(achado=novo, arquivo=cf, nome_original=nome, tamanho_bytes=tamanho)
            _log(request, 'achado_criado',
                 f'Achado duplicado de #{original.pk}: "{novo.verificacao}" em '
                 f'{esp.get_especialidade_display()} — "{esp.inspecao.edificacao}".')
            messages.success(request, 'Achado duplicado com sucesso.')
            return _redirect_detail(esp.inspecao_id, esp.pk)
    else:
        initial = {
            'verificacao': original.verificacao,
            'grupo_tecnico': original.grupo_tecnico,
            'em_conformidade': original.em_conformidade,
            'descricao_nao_conformidade': original.descricao_nao_conformidade,
            'requisito_afetado': original.requisito_afetado,
            'gravidade': original.gravidade,
            'urgencia': original.urgencia,
            'tendencia': original.tendencia,
            'prioridade_risco': original.prioridade_risco,
            'recomendacao': original.recomendacao,
            'direcionamento': original.direcionamento,
            'prazo_meses': original.prazo_meses,
            # localizacao e sub_localizacao em branco: o usuário deve definir
        }
        form = AchadoForm(initial=initial)

    return render(request, 'inspecoes/achado_form.html', {
        'form': form,
        'especialidade': esp,
        'fotos_existentes': [],
        'duplicando_de': original,
    })


# ── Fotos ──────────────────────────────────────────────────────────────────────

ALLOWED_CONTENT_TYPES = {'image/jpeg', 'image/png'}
MAX_UPLOAD_SIZE = 10 * 1024 * 1024


def erro_validacao_foto(content_type, tamanho):
    """None se a foto é válida; senão, a mensagem explicando o motivo da rejeição."""
    if content_type not in ALLOWED_CONTENT_TYPES:
        return 'Formato inválido. Use JPEG ou PNG.'
    if tamanho > MAX_UPLOAD_SIZE:
        return 'Arquivo muito grande. Máximo: 10 MB.'
    return None


def foto_valida(content_type, tamanho):
    return erro_validacao_foto(content_type, tamanho) is None


def _criar_foto_do_upload(achado, arquivo):
    """Valida e cria uma Foto a partir de um UploadedFile.

    Retorna (foto, None) em sucesso, ou (None, mensagem_erro) se inválida.
    Compartilhado entre o upload online (foto_upload) e a fila de
    sincronização offline (achado_sincronizar_foto) — mesma validação e
    mesma compressão nos dois caminhos.
    """
    erro = erro_validacao_foto(arquivo.content_type, arquivo.size)
    if erro:
        return None, erro
    cf, nome, tamanho = comprimir_imagem(arquivo.read(), arquivo.name)
    foto = Foto.objects.create(
        achado=achado,
        arquivo=cf,
        nome_original=nome,
        tamanho_bytes=tamanho,
    )
    return foto, None


@login_required
@require_POST
def foto_upload(request, achado_pk):
    achado = get_object_or_404(Achado.objects.select_related('especialidade'), pk=achado_pk)
    arquivo = request.FILES.get('arquivo')
    if not arquivo:
        return JsonResponse({'erro': 'Nenhum arquivo enviado.'}, status=400)
    foto, erro = _criar_foto_do_upload(achado, arquivo)
    if erro:
        return JsonResponse({'erro': erro}, status=400)
    return JsonResponse({'id': foto.pk, 'url': foto.arquivo.url, 'nome': foto.nome_original})


@login_required
@require_http_methods(['DELETE'])
def foto_delete(request, pk):
    foto = get_object_or_404(Foto.objects.select_related('achado__especialidade'), pk=pk)
    foto.excluir(request.user)
    return HttpResponse(status=204)


# ── Acompanhamento — gestão do ciclo de vida dos achados ─────────────────────

@login_required
def acompanhamento_painel(request):
    achados_qs = Achado.objects.acompanhamento()
    total = achados_qs.count()

    por_categoria = achados_qs.contagem_por('direcionamento', Achado.DIRECIONAMENTO_CHOICES)
    por_status = achados_qs.contagem_por('status', Achado.STATUS_ACOMPANHAMENTO_CHOICES)
    por_especialidade = achados_qs.contagem_por('especialidade__especialidade', InspecaoEspecialidade.ESPECIALIDADE_CHOICES)
    por_localidade = achados_qs.contagem_por_localidade()

    status_totais = {row['chave']: row['total'] for row in por_status}
    finalizados = status_totais.get('finalizado', 0)
    em_andamento = status_totais.get('em_andamento', 0)
    pendentes = status_totais.get('pendente', 0)
    pct_conclusao = round(finalizados / total * 100) if total else 0

    return render(request, 'inspecoes/acompanhamento_painel.html', {
        'total': total,
        'por_categoria': por_categoria,
        'por_status': por_status,
        'por_especialidade': por_especialidade,
        'por_localidade': por_localidade,
        'finalizados': finalizados,
        'em_andamento': em_andamento,
        'pendentes': pendentes,
        'pct_conclusao': pct_conclusao,
    })


@login_required
def acompanhamento_lista(request):
    categorias_validas = dict(Achado.DIRECIONAMENTO_CHOICES)
    categoria = request.GET.get('categoria', 'manutencao')
    if categoria != 'todas' and categoria not in categorias_validas:
        categoria = 'manutencao'

    form = AcompanhamentoFilterForm(request.GET or None)
    base = Achado.objects.acompanhamento().com_filtros_acompanhamento(form)

    # Contagem por categoria (respeita os demais filtros) para os badges das abas — uma única query.
    contagens_lista = base.contagem_por('direcionamento', Achado.DIRECIONAMENTO_CHOICES)
    total_todas = sum(row['total'] for row in contagens_lista)

    achados_qs = base if categoria == 'todas' else base.filter(direcionamento=categoria)
    achados = list(
        achados_qs.prefetch_related('fotos').order_by('prioridade_risco', '-gut_total')
    )

    # Querystring dos filtros (sem 'categoria') para preservar nas abas.
    from urllib.parse import urlencode
    filtros = {key: request.GET.get(key) for key in ('localidade', 'especialidade', 'status') if request.GET.get(key)}
    filtros_qs = urlencode(filtros)

    abas = [{'chave': 'todas', 'nome': 'Todas', 'total': total_todas}] + contagens_lista
    categoria_nome = 'Todas as categorias' if categoria == 'todas' else categorias_validas[categoria]

    return render(request, 'inspecoes/acompanhamento_lista.html', {
        'categoria': categoria,
        'categoria_nome': categoria_nome,
        'abas': abas,
        'form': form,
        'achados': achados,
        'filtros_qs': filtros_qs,
        'is_manutencao': categoria == 'manutencao',
        'mostra_categoria_coluna': categoria == 'todas',
    })


@login_required
def acompanhamento_achado(request, pk):
    achado = get_object_or_404(
        Achado.objects.acompanhamento().prefetch_related('fotos', 'historico_encaminhamento__usuario'),
        pk=pk,
    )
    if request.method == 'POST':
        form = AcompanhamentoAchadoForm(request.POST, instance=achado)
        if form.is_valid():
            form.save()
            _log(request, 'achado_acompanhamento',
                 f'Acompanhamento atualizado: "{achado.verificacao}" — status {achado.get_status_display()}.')
            messages.success(request, 'Acompanhamento atualizado com sucesso.')
            return redirect('inspecoes:acompanhamento_achado', pk=achado.pk)
    else:
        form = AcompanhamentoAchadoForm(instance=achado)

    reclass_form = ReclassificarForm(atual=achado.direcionamento,
                                     initial={'para_direcionamento': achado.direcionamento})
    return render(request, 'inspecoes/acompanhamento_achado.html', {
        'achado': achado,
        'form': form,
        'reclass_form': reclass_form,
        'historico': achado.historico_encaminhamento.all(),
        'is_manutencao': achado.direcionamento == 'manutencao',
    })


@login_required
@require_POST
def achado_reclassificar(request, pk):
    achado = get_object_or_404(Achado.objects.acompanhamento(), pk=pk)
    form = ReclassificarForm(request.POST, atual=achado.direcionamento)
    if form.is_valid():
        de = achado.direcionamento
        para = form.cleaned_data['para_direcionamento']
        labels = dict(Achado.DIRECIONAMENTO_CHOICES)
        EncaminhamentoHistorico.objects.create(
            achado=achado, usuario=request.user,
            de_direcionamento=de, para_direcionamento=para,
            justificativa=form.cleaned_data['justificativa'],
        )
        achado.direcionamento = para
        achado.save()
        _log(request, 'achado_reclassificado',
             f'Achado "{achado.verificacao}" reclassificado de {labels[de]} para {labels[para]}.')
        messages.success(request, 'Encaminhamento alterado com sucesso.')
    else:
        for erros in form.errors.values():
            for e in erros:
                messages.error(request, e)
    return redirect('inspecoes:acompanhamento_achado', pk=achado.pk)


# ── PWA — Service Worker, Manifest e página offline ──────────────────────────

def service_worker(request):
    """Serve o service worker com escopo raiz e sem cache."""
    from django.contrib.staticfiles import finders
    path = finders.find('sw.js')
    if not path:
        from django.http import Http404
        raise Http404('sw.js não encontrado')
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    resp = HttpResponse(content, content_type='application/javascript')
    resp['Service-Worker-Allowed'] = '/'
    resp['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return resp


def web_manifest(request):
    """Serve o manifest.json."""
    from django.contrib.staticfiles import finders
    path = finders.find('manifest.json')
    if not path:
        from django.http import Http404
        raise Http404('manifest.json não encontrado')
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    return HttpResponse(content, content_type='application/manifest+json')


def offline_page(request):
    """Página de fallback quando o usuário está offline."""
    return render(request, 'inspecoes/offline.html')


@login_required
def diagnostico_offline(request):
    """Página de diagnóstico do PWA (sem DevTools): conexão, Service Worker,
    caches e conteúdo das filas offline; permite sincronizar e resetar o SW."""
    return render(request, 'inspecoes/diagnostico_offline.html')


# ── API — Sincronização de achados offline ────────────────────────────────────

@login_required
@csrf_exempt
@require_POST
def achado_sincronizar(request):
    """
    Recebe um achado criado offline (JSON) e persiste no banco.
    Utilizado pelo service worker e pelo pwa.js durante a sincronização.
    """
    try:
        dados = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'erro': 'JSON inválido.'}, status=400)
    except RequestDataTooBig:
        return JsonResponse(
            {'erro': 'Achado muito grande (fotos em excesso ou muito pesadas). '
                      'Tente sincronizar com menos fotos por vez.'},
            status=400,
        )

    esp_pk = dados.get('esp_pk')
    if not esp_pk:
        return JsonResponse({'erro': 'esp_pk obrigatório.'}, status=400)

    try:
        esp = InspecaoEspecialidade.objects.select_related('inspecao').get(pk=esp_pk)
    except InspecaoEspecialidade.DoesNotExist:
        return JsonResponse({'erro': 'Especialidade não encontrada.'}, status=404)

    if not esp.pode_editar:
        return JsonResponse({'erro': 'Especialidade finalizada. Reabra antes de sincronizar.'}, status=400)

    em_conformidade = bool(dados.get('em_conformidade', False))

    try:
        achado = Achado.objects.create(
            especialidade=esp,
            localizacao=dados.get('localizacao', ''),
            sub_localizacao=dados.get('sub_localizacao', ''),
            verificacao=dados.get('verificacao', ''),
            grupo_tecnico='' if em_conformidade else dados.get('grupo_tecnico', ''),
            em_conformidade=em_conformidade,
            descricao_nao_conformidade='' if em_conformidade else dados.get('descricao_nao_conformidade', ''),
            requisito_afetado='' if em_conformidade else dados.get('requisito_afetado', ''),
            gravidade=int(dados.get('gravidade', 1)),
            urgencia=int(dados.get('urgencia', 1)),
            tendencia=int(dados.get('tendencia', 1)),
            prioridade_risco=3 if em_conformidade else int(dados.get('prioridade_risco', 3)),
            recomendacao='' if em_conformidade else dados.get('recomendacao', ''),
            direcionamento=dados.get('direcionamento', 'manutencao'),
            prazo_meses=int(dados.get('prazo_meses', 12)),
        )
    except Exception as e:
        return JsonResponse({'erro': f'Erro ao criar achado: {e}'}, status=400)

    # Processar fotos enviadas como base64
    fotos_salvas = 0
    for foto_data in dados.get('fotos', []):
        try:
            nome = foto_data.get('nome', 'foto.jpg')
            tipo = foto_data.get('tipo', 'image/jpeg')
            b64 = foto_data.get('dados_b64', '')
            if not b64:
                continue
            conteudo = base64.b64decode(b64)
            if not foto_valida(tipo, len(conteudo)):
                continue
            cf, nome_c, tamanho = comprimir_imagem(conteudo, nome)
            Foto.objects.create(
                achado=achado,
                arquivo=cf,
                nome_original=nome_c,
                tamanho_bytes=tamanho,
            )
            fotos_salvas += 1
        except Exception:
            pass

    _log(request, 'achado_criado',
         f'[OFFLINE SYNC] Achado criado: "{achado.verificacao}" em '
         f'{esp.get_especialidade_display()} — "{esp.inspecao.edificacao}".')

    return JsonResponse({'ok': True, 'achado_pk': achado.pk, 'fotos_salvas': fotos_salvas}, status=201)


@login_required
def especialidade_achados_para_campo(request, pk):
    """
    Retorna JSON com todos os achados de uma especialidade para cache offline.
    """
    esp = get_object_or_404(InspecaoEspecialidade, pk=pk)
    achados = [
        {
            'pk': a.pk,
            'localizacao': a.localizacao,
            'sub_localizacao': a.sub_localizacao,
            'verificacao': a.verificacao,
            'grupo_tecnico': a.grupo_tecnico,
            'em_conformidade': a.em_conformidade,
            'descricao_nao_conformidade': a.descricao_nao_conformidade,
            'requisito_afetado': a.requisito_afetado,
            'gravidade': a.gravidade,
            'urgencia': a.urgencia,
            'tendencia': a.tendencia,
            'prioridade_risco': a.prioridade_risco,
            'recomendacao': a.recomendacao,
            'direcionamento': a.direcionamento,
            'prazo_meses': a.prazo_meses,
            'esp_pk': esp.pk,
            'editar_url': reverse('inspecoes:achado_update', args=[a.pk]),
            # URLs das fotos existentes — o SW as pré-cacheia para exibição offline.
            'fotos': [
                {'pk': f.pk, 'url': f.arquivo.url, 'nome': f.nome_original}
                for f in a.fotos.all()
            ],
        }
        for a in esp.achados.prefetch_related('fotos')
    ]
    return JsonResponse(achados, safe=False)


@login_required
@csrf_exempt
@require_http_methods(['PATCH'])
def achado_sincronizar_edicao(request, pk):
    """
    Atualiza um achado editado offline aplicando merge campo a campo.

    Só os campos de diagnóstico **presentes** no payload (os "campos tocados"
    em campo) são aplicados; os ausentes preservam o valor do servidor. Aceita
    também `fotos_excluir` (pks marcados para remoção). Fotos novas não vêm
    mais neste payload — sobem separadamente via achado_sincronizar_foto (ver
    docs/superpowers/specs/2026-07-31-sincronizacao-offline-volume-design.md,
    ADR-01); o campo `fotos` (base64) ainda é aceito aqui apenas como
    compatibilidade com itens presos na fila de sincronização no formato
    antigo (ADR-06), não é mais o caminho usado por código novo.
    Campos de identidade (localização, verificação) não são editáveis offline.
    """
    try:
        dados = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'erro': 'JSON inválido.'}, status=400)
    except RequestDataTooBig:
        return JsonResponse(
            {'erro': 'Edição muito grande (fotos em excesso ou muito pesadas). '
                      'Tente sincronizar com menos fotos por vez.'},
            status=400,
        )

    achado = get_object_or_404(
        Achado.objects.select_related('especialidade__inspecao'), pk=pk
    )

    if not achado.especialidade.pode_editar:
        return JsonResponse({'erro': 'Especialidade finalizada. Reabra antes de sincronizar.'}, status=400)

    # em_conformidade define se os campos de não conformidade são limpos (cascata).
    if 'em_conformidade' in dados:
        achado.em_conformidade = bool(dados['em_conformidade'])

    if achado.em_conformidade:
        achado.gravidade = 1
        achado.urgencia = 1
        achado.tendencia = 1
        achado.prioridade_risco = 3
        achado.descricao_nao_conformidade = ''
        achado.requisito_afetado = ''
        achado.grupo_tecnico = ''
        achado.recomendacao = ''
    else:
        for campo in ('gravidade', 'urgencia', 'tendencia', 'prioridade_risco', 'prazo_meses'):
            if campo in dados:
                try:
                    setattr(achado, campo, int(dados[campo]))
                except (TypeError, ValueError):
                    pass
        for campo in ('descricao_nao_conformidade', 'requisito_afetado',
                      'grupo_tecnico', 'recomendacao', 'direcionamento'):
            if campo in dados:
                setattr(achado, campo, dados[campo] or '')

    achado.save()

    # Exclusão de fotos marcadas offline (idempotente: ignora pks já removidos).
    fotos_excluidas = 0
    fotos_excluir = dados.get('fotos_excluir') or []
    for foto in achado.fotos.filter(pk__in=fotos_excluir):
        foto.excluir(request.user)
        fotos_excluidas += 1

    # Fotos novas anexadas em campo (base64).
    fotos_salvas = 0
    for foto_data in dados.get('fotos', []):
        try:
            nome = foto_data.get('nome', 'foto.jpg')
            tipo = foto_data.get('tipo', 'image/jpeg')
            b64 = foto_data.get('dados_b64', '')
            if not b64:
                continue
            conteudo = base64.b64decode(b64)
            if not foto_valida(tipo, len(conteudo)):
                continue
            cf, nome_c, tamanho = comprimir_imagem(conteudo, nome)
            Foto.objects.create(
                achado=achado,
                arquivo=cf,
                nome_original=nome_c,
                tamanho_bytes=tamanho,
            )
            fotos_salvas += 1
        except Exception:
            pass

    _log(request, 'achado_atualizado',
         f'[OFFLINE SYNC] Achado editado: "{achado.verificacao}" em '
         f'{achado.especialidade.get_especialidade_display()} — "{achado.especialidade.inspecao.edificacao}".')

    return JsonResponse({
        'ok': True, 'achado_pk': achado.pk,
        'fotos_salvas': fotos_salvas, 'fotos_excluidas': fotos_excluidas,
    })


@login_required
@csrf_exempt
@require_POST
def achado_sincronizar_foto(request, pk):
    """
    Recebe UMA foto (multipart) da fila de sincronização offline e a anexa
    ao achado. Desacoplada de achado_sincronizar/achado_sincronizar_edicao
    (ver docs/superpowers/specs/2026-07-31-sincronizacao-offline-volume-design.md,
    ADR-01): uma foto grande ou instável não deve impedir o texto do achado
    de chegar ao servidor, nem vice-versa.

    Não verifica `pode_editar` da especialidade — ADR-10: uma foto que já
    estava na fila local deve poder subir mesmo que a especialidade tenha
    sido finalizada nesse meio-tempo.
    """
    achado = get_object_or_404(Achado, pk=pk)
    arquivo = request.FILES.get('arquivo')
    if not arquivo:
        return JsonResponse({'erro': 'Nenhum arquivo enviado.'}, status=400)
    foto, erro = _criar_foto_do_upload(achado, arquivo)
    if erro:
        return JsonResponse({'erro': erro}, status=400)
    return JsonResponse({'ok': True, 'foto_pk': foto.pk}, status=201)


# ── Análise — helper compartilhado ────────────────────────────────────────────

# ── Sub-cálculos de _analise_data — cada um testável isoladamente ────────────

def _achados_por_direcionamento(nao_conformes):
    def por_dir(dir_key):
        result = {'p1': [], 'p2': [], 'p3': []}
        for a in nao_conformes:
            if a.direcionamento == dir_key:
                result[f'p{a.prioridade_risco}'].append(a)
        return result
    return por_dir('manutencao'), por_dir('nova_contratacao'), por_dir('garantia')


def _por_grupo_tecnico(nao_conformes, total_nc):
    """Contagem por grupo técnico + visão Pareto (80/20) do mesmo mapa."""
    grupo_labels = dict(Achado.GRUPO_TECNICO_CHOICES)
    grupo_map = {}
    for a in nao_conformes:
        g = a.grupo_tecnico
        if g not in grupo_map:
            grupo_map[g] = {'grupo_tecnico': g, 'nome': grupo_labels.get(g, g), 'p1': 0, 'p2': 0, 'p3': 0, 'total': 0}
        grupo_map[g][f'p{a.prioridade_risco}'] += 1
        grupo_map[g]['total'] += 1
    grupos = sorted(grupo_map.values(), key=lambda x: (-x['p1'], -x['total']))

    pareto = sorted(grupo_map.values(), key=lambda x: -x['total'])
    acumulado = 0
    for g in pareto:
        acumulado += g['total']
        g['acumulado'] = acumulado
        g['acumulado_pct'] = round(acumulado / total_nc * 100) if total_nc else 0
    return grupos, pareto


def _estatisticas_gut(nao_conformes):
    gut_vals = [a.gut_total for a in nao_conformes]
    media = round(sum(gut_vals) / len(gut_vals), 1) if gut_vals else 0
    maximo = max(gut_vals) if gut_vals else 0
    minimo = min(gut_vals) if gut_vals else 0
    n = len(gut_vals)
    desvio = round((sum((v - media) ** 2 for v in gut_vals) / n) ** 0.5, 1) if n > 1 else 0
    top = sorted(nao_conformes, key=lambda a: -a.gut_total)[:10]
    top_max = top[0].gut_total if top else 1
    for a in top:
        a.gut_pct = round(a.gut_total / top_max * 100)
    return {'media': media, 'max': maximo, 'min': minimo, 'desvio': desvio, 'top': top}


def _por_localizacao(nao_conformes):
    """Contagem por localização + visão por concentração de risco (soma GUT) do mesmo mapa."""
    loc_map = {}
    for a in nao_conformes:
        loc = a.localizacao
        if loc not in loc_map:
            loc_map[loc] = {'localizacao': loc, 'total': 0, 'p1': 0, 'p2': 0, 'p3': 0, 'soma_gut': 0}
        loc_map[loc]['total'] += 1
        loc_map[loc][f'p{a.prioridade_risco}'] += 1
        loc_map[loc]['soma_gut'] += a.gut_total

    por_localizacao = sorted(loc_map.values(), key=lambda x: -x['total'])

    por_localizacao_gut = sorted(loc_map.values(), key=lambda x: -x['soma_gut'])
    max_soma = por_localizacao_gut[0]['soma_gut'] if por_localizacao_gut else 1
    for l in por_localizacao_gut:
        l['gut_pct'] = round(l['soma_gut'] / max_soma * 100) if max_soma else 0
    return por_localizacao, por_localizacao_gut


def _por_prazo(nao_conformes):
    prazo_map = {}
    prazo_labels = dict(Achado.PRAZO_CHOICES)
    for a in nao_conformes:
        k = a.prazo_meses
        if k not in prazo_map:
            prazo_map[k] = {'prazo': k, 'label': prazo_labels.get(k, f'{k} meses'), 'total': 0, 'p1': 0, 'p2': 0, 'p3': 0}
        prazo_map[k]['total'] += 1
        prazo_map[k][f'p{a.prioridade_risco}'] += 1
    return sorted(prazo_map.values(), key=lambda x: x['prazo'])


def _por_requisito(nao_conformes):
    req_labels = dict(Achado.REQUISITO_CHOICES)
    req_colors = {
        'seguranca_estrutural': '#dc3545', 'acessibilidade': '#ffc107',
        'saude_qualidade_ar': '#0d6efd',   'funcionalidade': '#198754',
        'estetica': '#6f42c1',             'eficiencia_energetica': '#fd7e14',
        'sustentabilidade': '#20c997',     'durabilidade': '#7B2D00',
    }
    req_count = {k: 0 for k in req_labels}
    for a in nao_conformes:
        req_count[a.requisito_afetado] = req_count.get(a.requisito_afetado, 0) + 1
    return [
        {'requisito': k, 'label': req_labels.get(k, k), 'total': req_count.get(k, 0),
         'color': req_colors.get(k, '#adb5bd')}
        for k in req_labels
    ]


def _iqe_score(total, total_conformes, p1, p2, p3):
    """Índice de Qualidade da Edificação (0-100) + % conformidade.

    Penaliza por severidade (P1=5, P2=2, P3=1), normalizado pelo pior caso (tudo P1).
    """
    pct_conformidade = round(total_conformes / total * 100) if total else 0
    if total:
        penalidade = 5 * len(p1) + 2 * len(p2) + 1 * len(p3)
        iqe = round(100 * (1 - penalidade / (5 * total)))
    else:
        iqe = 100
    if iqe >= 80:
        faixa, cor = 'Bom', 'success'
    elif iqe >= 50:
        faixa, cor = 'Atenção', 'warning'
    else:
        faixa, cor = 'Crítico', 'danger'
    return {'iqe': iqe, 'faixa': faixa, 'cor': cor, 'pct_conformidade': pct_conformidade}


def _componentes_gut_medios(nao_conformes, total_nc):
    """Médias isoladas de Gravidade, Urgência e Tendência."""
    if total_nc:
        g = round(sum(a.gravidade for a in nao_conformes) / total_nc, 1)
        u = round(sum(a.urgencia for a in nao_conformes) / total_nc, 1)
        t = round(sum(a.tendencia for a in nao_conformes) / total_nc, 1)
    else:
        g = u = t = 0
    return g, u, t


def _matriz_risco_prazo(nao_conformes):
    prazos_ordem = [p[0] for p in Achado.PRAZO_CHOICES]
    prazo_lbls = dict(Achado.PRAZO_CHOICES)
    matriz = []
    for prio in (1, 2, 3):
        celulas = []
        for pr in prazos_ordem:
            qtd = sum(1 for a in nao_conformes
                      if a.prioridade_risco == prio and a.prazo_meses == pr)
            tipo = ''
            if qtd:
                if prio == 1 and pr >= 12:
                    tipo = 'incoerencia'    # P1 com prazo longo
                elif prio in (1, 2) and pr <= 3:
                    tipo = 'ganho_rapido'   # alto risco, prazo curto
            celulas.append({'prazo': pr, 'qtd': qtd, 'tipo': tipo})
        matriz.append({'prioridade': prio, 'celulas': celulas})
    prazos_labels = [prazo_lbls[p] for p in prazos_ordem]
    n_incoerencias = sum(1 for a in nao_conformes
                         if a.prioridade_risco == 1 and a.prazo_meses >= 12)
    n_ganhos_rapidos = sum(1 for a in nao_conformes
                           if a.prioridade_risco in (1, 2) and a.prazo_meses <= 3)
    return matriz, prazos_labels, n_incoerencias, n_ganhos_rapidos


def _por_direcionamento(nao_conformes, total_nc):
    dir_labels = dict(Achado.DIRECIONAMENTO_CHOICES)
    dir_count = {k: 0 for k in dir_labels}
    for a in nao_conformes:
        dir_count[a.direcionamento] = dir_count.get(a.direcionamento, 0) + 1
    return [
        {'key': k, 'label': dir_labels[k], 'total': dir_count.get(k, 0),
         'pct': round(dir_count.get(k, 0) / total_nc * 100) if total_nc else 0}
        for k in dir_labels
    ]


def _cobertura_fotos(nao_conformes, total_nc):
    """Conta achados com ao menos 1 foto. Usa .all() (não .exists()) para
    reaproveitar o prefetch_related feito pelo chamador, em vez de nova query."""
    com_foto = 0
    for a in nao_conformes:
        try:
            if len(a.fotos.all()) > 0:
                com_foto += 1
        except Exception:
            pass
    pct = round(com_foto / total_nc * 100) if total_nc else 0
    return com_foto, pct


def _plano_acao(nao_conformes):
    """P1 primeiro, depois maior GUT — top 15."""
    return sorted(nao_conformes, key=lambda a: (a.prioridade_risco, -a.gut_total))[:15]


def _montar_charts(p1, p2, p3, por_direcionamento, pareto, por_prazo, por_requisito):
    """JSON dos gráficos, a partir de métricas já calculadas pelas funções acima."""
    return {
        'risco': json.dumps({
            'labels': ['P1 — Crítico', 'P2 — Regular', 'P3 — Mínimo'],
            'data': [len(p1), len(p2), len(p3)],
            'colors': ['#dc3545', '#fd7e14', '#198754'],
        }),
        'direcionamento': json.dumps({
            'labels': [d['label'] for d in por_direcionamento],
            'data': [d['total'] for d in por_direcionamento],
            'colors': ['#6f42c1', '#0dcaf0', '#ffc107'],
        }),
        'pareto': json.dumps({
            'labels': [g['nome'] for g in pareto],
            'data': [g['total'] for g in pareto],
            'acumulado': [g['acumulado_pct'] for g in pareto],
        }),
        'prazo': json.dumps({
            'labels': [p['label'] for p in por_prazo],
            'data': [p['total'] for p in por_prazo],
        }),
        'requisitos': json.dumps({
            'labels': [r['label'] for r in por_requisito],
            'data':   [r['total'] for r in por_requisito],
            'colors': [r['color'] for r in por_requisito],
        }),
    }


def _analise_data(achados_list):
    """Calcula todos os dados de análise a partir de uma lista de achados.

    Composição das sub-funções acima — a interface (lista de achados -> dict)
    não muda; ver test_analise_data.py para os cálculos testados isoladamente.
    """
    nao_conformes = [a for a in achados_list if a.gut_total > 0]
    total = len(achados_list)
    total_nc = len(nao_conformes)
    total_conformes = total - total_nc

    p1 = [a for a in nao_conformes if a.prioridade_risco == 1]
    p2 = [a for a in nao_conformes if a.prioridade_risco == 2]
    p3 = [a for a in nao_conformes if a.prioridade_risco == 3]

    grupos, pareto = _por_grupo_tecnico(nao_conformes, total_nc)
    manutencao, nova_contratacao, garantia = _achados_por_direcionamento(nao_conformes)
    gut = _estatisticas_gut(nao_conformes)
    por_localizacao, por_localizacao_gut = _por_localizacao(nao_conformes)
    por_prazo = _por_prazo(nao_conformes)
    por_requisito = _por_requisito(nao_conformes)
    iqe_info = _iqe_score(total, total_conformes, p1, p2, p3)
    g_media, u_media, t_media = _componentes_gut_medios(nao_conformes, total_nc)
    matriz_risco_prazo, matriz_prazos, n_incoerencias, n_ganhos_rapidos = _matriz_risco_prazo(nao_conformes)
    por_direcionamento = _por_direcionamento(nao_conformes, total_nc)
    com_foto, cobertura_foto_pct = _cobertura_fotos(nao_conformes, total_nc)
    plano_acao = _plano_acao(nao_conformes)
    charts = _montar_charts(p1, p2, p3, por_direcionamento, pareto, por_prazo, por_requisito)

    return {
        'total': total, 'total_nc': total_nc, 'total_conformes': total_conformes,
        'p1': p1, 'p2': p2, 'p3': p3,
        'grupos': grupos,
        'manutencao': manutencao, 'nova_contratacao': nova_contratacao, 'garantia': garantia,
        'gut_media': gut['media'], 'gut_max': gut['max'], 'gut_min': gut['min'], 'gut_desvio': gut['desvio'],
        'top_gut': gut['top'],
        'por_localizacao': por_localizacao,
        'por_prazo': por_prazo,
        'por_requisito': por_requisito,
        'chart_risco': charts['risco'],
        'chart_prazo': charts['prazo'],
        'chart_requisitos': charts['requisitos'],
        # Novos insights (Dashboard de Encerramento)
        'iqe': iqe_info['iqe'], 'iqe_faixa': iqe_info['faixa'], 'iqe_cor': iqe_info['cor'],
        'pct_conformidade': iqe_info['pct_conformidade'],
        'g_media': g_media, 'u_media': u_media, 't_media': t_media,
        'matriz_risco_prazo': matriz_risco_prazo, 'matriz_prazos': matriz_prazos,
        'n_incoerencias': n_incoerencias, 'n_ganhos_rapidos': n_ganhos_rapidos,
        'por_direcionamento': por_direcionamento,
        'por_localizacao_gut': por_localizacao_gut,
        'pareto': pareto,
        'cobertura_foto_pct': cobertura_foto_pct, 'fotos_com': com_foto,
        'plano_acao': plano_acao,
        'chart_direcionamento': charts['direcionamento'],
        'chart_pareto': charts['pareto'],
    }


# ── Gráficos para PDF (renderizados como imagem, pois o xhtml2pdf não roda JS) ─

def _png_data_uri(img):
    buf = io.BytesIO()
    img.save(buf, 'PNG')
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()


@functools.lru_cache(maxsize=1)
def _logo_mpdft_data_uri():
    """Logomarca do MPDFT para o cabeçalho do Relatório Final, como PNG data
    URI — embutida porque o xhtml2pdf não resolve STATIC_URL/arquivos
    estáticos (sem link_callback configurado nesta base de código)."""
    from django.conf import settings
    caminho = settings.BASE_DIR / 'static' / 'img' / 'mpdft_logo.png'
    with open(caminho, 'rb') as f:
        dados = f.read()
    return 'data:image/png;base64,' + base64.b64encode(dados).decode()


_FONTES_PDF_CORRIGIDAS = False


def _corrigir_bug_tempfile_fontes_windows():
    """`xhtml2pdf.files.BaseFile.get_named_tmp_file` grava a fonte num
    `tempfile.NamedTemporaryFile` e mantém esse handle aberto; o reportlab
    então tenta reabrir o mesmo arquivo pelo nome para ler os bytes — no
    Windows isso é negado (`PermissionError`), então nenhuma fonte real via
    `@font-face` carrega (nem por caminho local, nem por data URI base64).
    Substitui só esse método por uma versão que fecha o arquivo antes de
    devolver o nome (padrão seguro de temp file no Windows). Idempotente —
    chamada a cada geração de PDF, mas só corrige uma vez por processo."""
    global _FONTES_PDF_CORRIGIDAS
    if _FONTES_PDF_CORRIGIDAS:
        return
    import tempfile
    from xhtml2pdf import files as xh_files

    def _get_named_tmp_file_corrigido(self):
        dados = self.get_data()
        tmp = tempfile.NamedTemporaryFile(suffix=self.suffix, delete=False)
        if dados:
            tmp.write(dados)
        tmp.close()
        if self.path is None:
            self.path = tmp.name
        return tmp

    xh_files.BaseFile.get_named_tmp_file = _get_named_tmp_file_corrigido
    _FONTES_PDF_CORRIGIDAS = True


@functools.lru_cache(maxsize=1)
def _fontes_pdf_css():
    """Regras @font-face com Arial/Arial Narrow/Calibri reais (embutidas como
    data URI base64 — mesmo motivo do `_logo_mpdft_data_uri`), para o
    Relatório Final usar as fontes do laudo-modelo em vez do Helvetica
    genérico que o xhtml2pdf usa por padrão para "Arial" no CSS. Lida apenas
    com os .ttf do Windows (ambiente de produção — ver `_fonte` acima); se
    não encontrar, devolve string vazia e o PDF cai no Helvetica/Times
    genéricos sem quebrar a geração em outros ambientes (ex. CI em Linux)."""
    base = 'C:/Windows/Fonts/'
    familias = {
        'Arial': [('normal', 'normal', 'arial.ttf'), ('bold', 'normal', 'arialbd.ttf'),
                   ('normal', 'italic', 'ariali.ttf'), ('bold', 'italic', 'arialbi.ttf')],
        'Arial Narrow': [('normal', 'normal', 'ARIALN.TTF'), ('bold', 'normal', 'ARIALNB.TTF')],
        'Calibri': [('normal', 'normal', 'calibri.ttf'), ('bold', 'normal', 'calibrib.ttf')],
    }
    regras = []
    for familia, variantes in familias.items():
        for peso, estilo, arquivo in variantes:
            caminho = base + arquivo
            if not os.path.exists(caminho):
                continue
            with open(caminho, 'rb') as f:
                b64 = base64.b64encode(f.read()).decode()
            regras.append(
                f'@font-face {{ font-family: "{familia}"; font-weight: {peso}; '
                f'font-style: {estilo}; src: url(data:font/ttf;base64,{b64}); }}'
            )
    return '\n'.join(regras)


def _aplicar_metadados_pdf(pdf_bytes, titulo, versao, gerado_em):
    """Move "Versão N — gerado em ..." do corpo visível do laudo para os
    metadados do PDF (título/assunto) — o modelo de laudo do MPDFT/SPO não
    mostra essa linha no corpo. Usa `pypdf` (já uma dependência transitiva
    nesta base), sem precisar de link_callback nem reescrever o HTML."""
    from pypdf import PdfReader, PdfWriter
    leitor = PdfReader(io.BytesIO(pdf_bytes))
    escritor = PdfWriter()
    escritor.append(leitor)
    escritor.add_metadata({
        '/Title': titulo,
        '/Subject': f'Versão {versao} — gerado em {gerado_em:%d/%m/%Y %H:%M}',
    })
    buf = io.BytesIO()
    escritor.write(buf)
    return buf.getvalue()


def _fonte(tamanho):
    from PIL import ImageFont
    for caminho in ('C:/Windows/Fonts/arial.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'):
        try:
            return ImageFont.truetype(caminho, tamanho)
        except OSError:
            continue
    return ImageFont.load_default()


def _hex_rgb(hexstr):
    hexstr = hexstr.lstrip('#')
    return tuple(int(hexstr[i:i + 2], 16) for i in (0, 2, 4))


def _grafico_rosca(valores, cores):
    """Rosca (donut) genérica: `valores` e `cores` (RGB) paralelos. data URI PNG ou None."""
    from PIL import Image, ImageDraw
    total = sum(valores)
    if total == 0:
        return None
    S = 4
    size = 340 * S
    img = Image.new('RGB', (size, size), 'white')
    d = ImageDraw.Draw(img)
    margem = 8 * S
    box = [margem, margem, size - margem, size - margem]
    ang = -90.0
    for val, cor in zip(valores, cores):
        if val <= 0:
            continue
        fim = ang + (val / total) * 360.0
        d.pieslice(box, ang, fim, fill=cor)
        ang = fim
    # furo central
    r = (size - 2 * margem) * 0.58 / 2
    c = size / 2
    d.ellipse([c - r, c - r, c + r, c + r], fill='white')
    img = img.resize((340, 340), Image.LANCZOS)
    return _png_data_uri(img)


def _grafico_rosca_risco(n1, n2, n3):
    """Rosca (donut) com a distribuição de prioridades. Retorna data URI PNG ou None."""
    return _grafico_rosca([n1, n2, n3], [(204, 0, 0), (204, 102, 0), (0, 102, 0)])


def _grafico_rosca_direcionamento(por_direcionamento):
    """Rosca (donut) com a distribuição por direcionamento (garantia/manutenção/nova
    contratação) — mesmas cores do `chartDirecionamento` do painel de encerramento."""
    valores = [d['total'] for d in por_direcionamento]
    cores = [(111, 66, 193), (13, 202, 240), (255, 193, 7)]
    return _grafico_rosca(valores, cores[:len(valores)])


def _grafico_barras_prazo(por_prazo):
    """Barras verticais com a quantidade de achados por prazo. data URI PNG ou None."""
    from PIL import Image, ImageDraw
    dados = [(p['label'], p['total']) for p in por_prazo if p.get('total', 0) > 0]
    if not dados:
        return None
    S = 4
    W, H = 520 * S, 300 * S
    img = Image.new('RGB', (W, H), 'white')
    d = ImageDraw.Draw(img)
    f = _fonte(14 * S)
    maxv = max(v for _, v in dados) or 1
    pad_l, pad_b, pad_t, pad_r = 34 * S, 42 * S, 22 * S, 12 * S
    plot_w = W - pad_l - pad_r
    plot_h = H - pad_b - pad_t
    base_y = pad_t + plot_h
    gap = plot_w / len(dados)
    bw = gap * 0.55
    cor = (13, 110, 253)
    for i, (lab, val) in enumerate(dados):
        x = pad_l + i * gap + (gap - bw) / 2
        bh = (val / maxv) * plot_h
        d.rectangle([x, base_y - bh, x + bw, base_y], fill=cor)
        d.text((x + bw / 2, base_y - bh - 6 * S), str(val), fill=(60, 60, 60), font=f, anchor='mb')
        d.text((x + bw / 2, base_y + 8 * S), lab, fill=(60, 60, 60), font=f, anchor='ma')
    d.line([pad_l, pad_t, pad_l, base_y], fill=(170, 170, 170), width=S)
    d.line([pad_l, base_y, W - pad_r, base_y], fill=(170, 170, 170), width=S)
    img = img.resize((520, 300), Image.LANCZOS)
    return _png_data_uri(img)


def _grafico_barras_horizontais(dados):
    """Barras horizontais: `dados` = [(label, valor, cor_rgb, sufixo_ou_None), ...], já
    filtrado (valor > 0). Preferível às barras verticais quando os rótulos são longos
    (nomes de grupo técnico/requisito não cabem sob uma barra estreita)."""
    from PIL import Image, ImageDraw
    if not dados:
        return None
    S = 4
    row_h = 30 * S
    W = 560 * S
    H = len(dados) * row_h + 20 * S
    img = Image.new('RGB', (W, H), 'white')
    d = ImageDraw.Draw(img)
    f = _fonte(13 * S)
    maxv = max(v for _, v, _, _ in dados) or 1
    label_w = 200 * S
    pad_r = 90 * S
    plot_w = W - label_w - pad_r
    max_label_w = label_w - 8 * S
    for i, (lab, val, cor, sufixo) in enumerate(dados):
        y0 = 10 * S + i * row_h
        yc = y0 + row_h / 2
        texto = lab
        while d.textlength(texto, font=f) > max_label_w and len(texto) > 1:
            texto = texto[:-1]
        if texto != lab:
            texto = texto[:-1].rstrip() + '…'
        d.text((label_w - 8 * S, yc), texto, fill=(60, 60, 60), font=f, anchor='rm')
        bw = (val / maxv) * plot_w
        d.rectangle([label_w, y0 + 4 * S, label_w + bw, y0 + row_h - 4 * S], fill=cor)
        d.text((label_w + bw + 6 * S, yc), f'{val}{sufixo or ""}', fill=(40, 40, 40), font=f, anchor='lm')
    img = img.resize((W // S, H // S), Image.LANCZOS)
    return _png_data_uri(img)


def _grafico_barras_requisitos(por_requisito):
    """Colunas verticais de NC por requisito de desempenho afetado, com as mesmas
    cores do `chartRequisitos` do painel de encerramento. data URI PNG ou None."""
    dados = [(r['label'], r['total'], _hex_rgb(r['color'])) for r in por_requisito if r['total'] > 0]
    return _grafico_barras_verticais_coloridas(dados)


def _grafico_barras_verticais_coloridas(dados):
    """Colunas verticais com uma cor própria por barra (ex.: Requisito Afetado
    X Quantidade do Painel de Encerramento) — `dados` = [(label, valor, cor_rgb), ...],
    já filtrado (valor > 0 fica normal, zerado some, mas a categoria continua
    aparecendo com barra vazia). data URI PNG ou None."""
    from PIL import Image, ImageDraw
    import textwrap
    if not dados:
        return None
    S = 4
    W, H = 600 * S, 300 * S
    img = Image.new('RGB', (W, H), 'white')
    d = ImageDraw.Draw(img)
    f_val = _fonte(12 * S)
    f_lab = _fonte(9 * S)
    maxv = max(v for _, v, _ in dados) or 1
    pad_l, pad_b, pad_t, pad_r = 10 * S, 54 * S, 24 * S, 10 * S
    plot_w = W - pad_l - pad_r
    plot_h = H - pad_b - pad_t
    base_y = pad_t + plot_h
    gap = plot_w / len(dados)
    bw = gap * 0.5
    for i, (lab, val, cor) in enumerate(dados):
        cx = pad_l + i * gap + gap / 2
        bh = (val / maxv) * plot_h if maxv else 0
        if val:
            d.rectangle([cx - bw / 2, base_y - bh, cx + bw / 2, base_y], fill=cor)
            d.text((cx, base_y - bh - 6 * S), str(val), fill=(40, 40, 40), font=f_val, anchor='mb')
        linhas = textwrap.wrap(lab, width=14)[:2]
        for li, linha in enumerate(linhas):
            d.text((cx, base_y + 8 * S + li * 11 * S), linha, fill=(60, 60, 60), font=f_lab, anchor='ma')
    d.line([pad_l, base_y, W - pad_r, base_y], fill=(170, 170, 170), width=S)
    img = img.resize((W // S, H // S), Image.LANCZOS)
    return _png_data_uri(img)


def _grafico_pareto_combo(pareto):
    """Combo barras (quantidade, eixo esquerdo) + linha (% acumulado, eixo
    direito) — mesmo gráfico "Pareto por Grupo Técnico (80/20)" do Painel de
    Encerramento (`chartPareto`). data URI PNG ou None."""
    from PIL import Image, ImageDraw
    import textwrap
    dados = [g for g in pareto if g['total'] > 0]
    if not dados:
        return None
    S = 4
    W, H = 580 * S, 320 * S
    img = Image.new('RGB', (W, H), 'white')
    d = ImageDraw.Draw(img)
    f_val = _fonte(10 * S)
    f_lab = _fonte(9 * S)
    f_axis = _fonte(9 * S)
    maxv = max(g['total'] for g in dados) or 1
    pad_l, pad_b, pad_t, pad_r = 28 * S, 60 * S, 16 * S, 36 * S
    plot_w = W - pad_l - pad_r
    plot_h = H - pad_b - pad_t
    base_y = pad_t + plot_h
    gap = plot_w / len(dados)
    bw = gap * 0.55
    cor_barra = (13, 110, 253)
    cor_linha = (220, 53, 69)
    pontos = []
    for i, g in enumerate(dados):
        cx = pad_l + i * gap + gap / 2
        bh = (g['total'] / maxv) * plot_h
        d.rectangle([cx - bw / 2, base_y - bh, cx + bw / 2, base_y], fill=cor_barra)
        d.text((cx, base_y - bh - 5 * S), str(g['total']), fill=(40, 40, 40), font=f_val, anchor='mb')
        linhas = textwrap.wrap(g['nome'], width=12)[:2]
        for li, linha in enumerate(linhas):
            d.text((cx, base_y + 8 * S + li * 11 * S), linha, fill=(60, 60, 60), font=f_lab, anchor='ma')
        y_linha = base_y - (g['acumulado_pct'] / 100) * plot_h
        pontos.append((cx, y_linha))
    d.line(pontos, fill=cor_linha, width=S)
    for x, y in pontos:
        r = 3.5 * S
        d.ellipse([x - r, y - r, x + r, y + r], fill=cor_linha)
    for pct in (0, 25, 50, 75, 100):
        y = base_y - (pct / 100) * plot_h
        d.text((W - pad_r + 6 * S, y), f'{pct}%', fill=(150, 150, 150), font=f_axis, anchor='lm')
    d.line([pad_l, pad_t, pad_l, base_y], fill=(170, 170, 170), width=S)
    d.line([pad_l, base_y, W - pad_r, base_y], fill=(170, 170, 170), width=S)
    img = img.resize((W // S, H // S), Image.LANCZOS)
    return _png_data_uri(img)


def _adicionar_graficos(ctx):
    """Acrescenta ao contexto as imagens dos gráficos (risco e prazo)."""
    ctx['grafico_risco_img'] = _grafico_rosca_risco(
        len(ctx.get('p1', [])), len(ctx.get('p2', [])), len(ctx.get('p3', []))
    )
    ctx['grafico_prazo_img'] = _grafico_barras_prazo(ctx.get('por_prazo', []))
    return ctx


def _fmt_decimal(valor):
    """1 casa decimal com vírgula (pt-BR) — mesmo formato do Painel de Encerramento."""
    return f'{valor:.1f}'.replace('.', ',')


def _painel_encerramento_relatorio(inspecao, especialidades):
    """Reproduz, como HTML + imagens PNG, os painéis do Dashboard de
    Encerramento (`_insights.html`) e da Análise geral (`analise.html`) — por
    pedido do usuário, o Relatório Final usa os MESMOS gráficos/paineis já
    existentes na plataforma, na mesma ordem em que aparecem lá, em vez de um
    layout próprio só para o PDF. Roda fora do navegador (sem Chart.js), por
    isso os gráficos viram imagem (PIL) e os cartões/tabelas viram HTML."""
    todos_achados = []
    for esp in especialidades:
        todos_achados.extend(list(esp.achados.all()))
    dados = _analise_data(todos_achados)
    top_gut = [{
        'localizacao': a.localizacao, 'verificacao': a.verificacao, 'gut_total': a.gut_total,
    } for a in dados['top_gut']]
    return {
        'resumo_especialidade': _dados_gerais_snapshot(especialidades),
        'total': dados['total'], 'total_nc': dados['total_nc'], 'total_conformes': dados['total_conformes'],
        'gut_media': _fmt_decimal(dados['gut_media']), 'gut_max': dados['gut_max'],
        'gut_min': dados['gut_min'], 'gut_desvio': _fmt_decimal(dados['gut_desvio']),
        'iqe': dados['iqe'], 'iqe_faixa': dados['iqe_faixa'], 'pct_conformidade': dados['pct_conformidade'],
        'g_media': _fmt_decimal(dados['g_media']), 'u_media': _fmt_decimal(dados['u_media']),
        't_media': _fmt_decimal(dados['t_media']),
        'por_direcionamento': dados['por_direcionamento'],
        'matriz_risco_prazo': dados['matriz_risco_prazo'], 'matriz_prazos': dados['matriz_prazos'],
        'n_incoerencias': dados['n_incoerencias'], 'n_ganhos_rapidos': dados['n_ganhos_rapidos'],
        'por_localizacao': dados['por_localizacao'],
        'p1_total': len(dados['p1']), 'p2_total': len(dados['p2']), 'p3_total': len(dados['p3']),
        'top_gut': top_gut,
        'img_risco': _grafico_rosca_risco(len(dados['p1']), len(dados['p2']), len(dados['p3'])),
        'img_direcionamento': _grafico_rosca_direcionamento(dados['por_direcionamento']),
        'img_pareto': _grafico_pareto_combo(dados['pareto']),
        'img_concentracao_localizacao': _grafico_barras_horizontais([
            (l['localizacao'], l['soma_gut'], (220, 53, 69), None) for l in dados['por_localizacao_gut'][:8]
        ]),
        'img_requisitos': _grafico_barras_requisitos(dados['por_requisito']),
        'img_prazo': _grafico_barras_prazo(dados['por_prazo']),
        'img_top_gut': _grafico_barras_horizontais([
            (f"{a['localizacao']} — {a['verificacao']}", a['gut_total'], (220, 53, 69), None) for a in top_gut
        ]),
    }


def _gerar_pdf(html_string, nome_arquivo):
    from xhtml2pdf import pisa
    _corrigir_bug_tempfile_fontes_windows()
    buffer = io.BytesIO()
    result = pisa.pisaDocument(io.BytesIO(html_string.encode('utf-8')), buffer, encoding='utf-8')
    if result.err:
        return HttpResponse(f'Erro ao gerar PDF: {result.err}', status=500)
    resp = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    resp['Content-Disposition'] = f'attachment; filename="{nome_arquivo}"'
    return resp


def _gerar_pdf_bytes(html_string):
    """Como `_gerar_pdf`, mas devolve os bytes do PDF em vez de um
    HttpResponse — usado quando o PDF precisa ser salvo num FileField
    (RelatorioFinalInspecao), não só servido para download direto."""
    from xhtml2pdf import pisa
    _corrigir_bug_tempfile_fontes_windows()
    buffer = io.BytesIO()
    result = pisa.pisaDocument(io.BytesIO(html_string.encode('utf-8')), buffer, encoding='utf-8')
    if result.err:
        return None
    return buffer.getvalue()


def _foto_para_data_uri(caminho):
    """Lê um arquivo de foto já copiado para o relatório (ver
    `_copiar_fotos_para_relatorio`) e devolve como data URI base64 — mesmo
    padrão já usado pelos gráficos do laudo (`_png_data_uri`), necessário
    porque o xhtml2pdf não resolve MEDIA_URL/caminhos de arquivo (sem
    link_callback configurado nesta base de código)."""
    from django.core.files.storage import default_storage
    ext = caminho.rsplit('.', 1)[-1].lower()
    mime = 'image/png' if ext == 'png' else 'image/jpeg'
    with default_storage.open(caminho, 'rb') as f:
        dados = f.read()
    return f'data:{mime};base64,' + base64.b64encode(dados).decode()


def _montar_contexto_pdf_com_fotos(snapshot):
    """Monta uma CÓPIA do snapshot só para renderizar o template do PDF, com
    os caminhos de foto trocados por data URIs embutidas. O `snapshot`
    original (com os caminhos leves, não as imagens infladas em base64)
    continua sendo o que é persistido em `RelatorioFinalInspecao.snapshot` —
    nunca passe o retorno desta função para lá, ou o JSONField no banco
    incharia com uma cópia inteira das imagens a cada versão gerada."""
    import copy
    contexto = copy.deepcopy(snapshot)
    for esp in contexto['especialidades']:
        for achado in esp['achados_completos']:
            achado['fotos'] = [_foto_para_data_uri(caminho) for caminho in achado['fotos']]
    return contexto


# ── Análise por especialidade ─────────────────────────────────────────────────

@login_required
def especialidade_analise(request, pk):
    esp = get_object_or_404(
        InspecaoEspecialidade.objects.select_related('inspecao__edificacao').prefetch_related('achados__fotos'),
        pk=pk,
    )
    ctx = _analise_data(list(esp.achados.all()))
    ctx['especialidade'] = esp
    ctx['inspecao'] = esp.inspecao
    return render(request, 'inspecoes/analise.html', ctx)


@login_required
def especialidade_analise_pdf(request, pk):
    esp = get_object_or_404(
        InspecaoEspecialidade.objects.select_related('inspecao__edificacao').prefetch_related('achados__fotos'),
        pk=pk,
    )
    ctx = _analise_data(list(esp.achados.all()))
    ctx['especialidade'] = esp
    ctx['inspecao'] = esp.inspecao
    _adicionar_graficos(ctx)
    html = render_to_string('inspecoes/analise_pdf.html', ctx, request=request)
    nome = (
        f"laudo_{esp.inspecao.edificacao.nome.replace(' ', '_')}"
        f"_{esp.get_especialidade_display().replace(' ', '_')}"
        f"_{esp.data_inspecao.strftime('%Y%m%d')}.pdf"
    )
    return _gerar_pdf(html, nome)


# ── Análise geral (por edificação) ────────────────────────────────────────────

@login_required
def inspecao_analise(request, pk):
    inspecao = get_object_or_404(
        Inspecao.objects.select_related('edificacao').prefetch_related(
            'especialidades', 'especialidades__achados__fotos',
        ),
        pk=pk,
    )
    todos_achados = []
    for esp in inspecao.especialidades.all():
        todos_achados.extend(list(esp.achados.all()))

    ctx = _analise_data(todos_achados)
    ctx['inspecao'] = inspecao

    # Breakdown por especialidade
    por_especialidade = []
    for esp in inspecao.especialidades.all():
        ach = list(esp.achados.all())
        nc = [a for a in ach if a.gut_total > 0]
        por_especialidade.append({
            'especialidade': esp,
            'total': len(ach),
            'total_nc': len(nc),
            'p1': len([a for a in nc if a.prioridade_risco == 1]),
            'p2': len([a for a in nc if a.prioridade_risco == 2]),
            'p3': len([a for a in nc if a.prioridade_risco == 3]),
        })
    ctx['por_especialidade'] = por_especialidade

    return render(request, 'inspecoes/analise_geral.html', ctx)


@login_required
def inspecao_analise_pdf(request, pk):
    inspecao = get_object_or_404(
        Inspecao.objects.select_related('edificacao').prefetch_related(
            'especialidades', 'especialidades__achados__fotos',
        ),
        pk=pk,
    )
    todos_achados = []
    for esp in inspecao.especialidades.all():
        todos_achados.extend(list(esp.achados.all()))

    ctx = _analise_data(todos_achados)
    ctx['inspecao'] = inspecao

    por_especialidade = []
    for esp in inspecao.especialidades.all():
        ach = list(esp.achados.all())
        nc = [a for a in ach if a.gut_total > 0]
        por_especialidade.append({
            'especialidade': esp,
            'total': len(ach),
            'total_nc': len(nc),
            'p1': len([a for a in nc if a.prioridade_risco == 1]),
            'p2': len([a for a in nc if a.prioridade_risco == 2]),
            'p3': len([a for a in nc if a.prioridade_risco == 3]),
        })
    ctx['por_especialidade'] = por_especialidade
    _adicionar_graficos(ctx)

    html = render_to_string('inspecoes/analise_geral_pdf.html', ctx, request=request)
    nome = f"laudo_{inspecao.edificacao.nome.replace(' ', '_')}_{inspecao.criado_em.strftime('%Y%m%d')}.pdf"
    return _gerar_pdf(html, nome)


# ── Backup da inspeção ────────────────────────────────────────────────────────

def _gerar_zip_backup(inspecao):
    """Gera o conteúdo ZIP do backup de uma inspeção. Retorna (bytes, nome_arquivo)."""
    from django.conf import settings

    dados = {
        'inspecao': {
            'id': inspecao.pk,
            'edificacao': inspecao.edificacao.nome,
            'criado_em': inspecao.criado_em.strftime('%Y-%m-%d %H:%M:%S'),
            'status_geral': inspecao.status_geral,
        },
        'especialidades': [],
    }
    fotos_paths = []

    for esp in inspecao.especialidades.all():
        esp_dict = {
            'id': esp.pk,
            'especialidade': esp.get_especialidade_display(),
            'profissional': '\n'.join(esp.profissionais_lista),
            'data_inspecao': esp.data_inspecao.strftime('%Y-%m-%d'),
            'status': esp.get_status_display(),
            'achados': [],
        }
        for achado in esp.achados.all():
            achado_dict = {
                'id': achado.pk,
                'localizacao': achado.localizacao,
                'sub_localizacao': achado.sub_localizacao or '',
                'verificacao': achado.verificacao,
                'em_conformidade': achado.em_conformidade,
                'grupo_tecnico': achado.grupo_tecnico if not achado.em_conformidade else '',
                'requisito_afetado': achado.requisito_afetado if not achado.em_conformidade else '',
                'descricao_nao_conformidade': achado.descricao_nao_conformidade or '',
                'recomendacao': achado.recomendacao or '',
                'gravidade': achado.gravidade,
                'urgencia': achado.urgencia,
                'tendencia': achado.tendencia,
                'gut_total': achado.gut_total,
                'prioridade_risco': achado.prioridade_risco,
                'prazo_meses': achado.get_prazo_meses_display() if not achado.em_conformidade else '',
                'direcionamento': achado.get_direcionamento_display() if not achado.em_conformidade else '',
                'fotos': [],
            }
            for foto in achado.fotos.all():
                nome_esp = esp.get_especialidade_display().replace(' ', '_')
                nome_no_zip = f'fotos/{nome_esp}/achado_{achado.pk}/{foto.nome_original}'
                achado_dict['fotos'].append(nome_no_zip)
                if foto.arquivo and os.path.exists(foto.arquivo.path):
                    fotos_paths.append((nome_no_zip, foto.arquivo.path))
            esp_dict['achados'].append(achado_dict)
        dados['especialidades'].append(esp_dict)

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('dados.json', json.dumps(dados, ensure_ascii=False, indent=2))
        for nome_no_zip, caminho_fisico in fotos_paths:
            zf.write(caminho_fisico, nome_no_zip)
        # Inclui cópia do banco de dados
        db_path = settings.DATABASES['default']['NAME']
        if os.path.exists(str(db_path)):
            zf.write(str(db_path), 'banco_de_dados/db.sqlite3')

    nome_edificacao = inspecao.edificacao.nome.replace(' ', '_')
    nome_arquivo = f'backup_inspecao_{nome_edificacao}_{inspecao.criado_em.strftime("%Y%m%d")}.zip'
    return buffer.getvalue(), nome_arquivo


def _salvar_backup_em_disco(inspecao):
    """Gera e salva o backup no disco. Retorna o caminho do arquivo salvo."""
    from django.conf import settings
    inspecao_com_dados = Inspecao.objects.select_related('edificacao').prefetch_related(
        'especialidades__achados__fotos',
    ).get(pk=inspecao.pk)
    zip_bytes, nome_arquivo = _gerar_zip_backup(inspecao_com_dados)
    pasta = os.path.join(settings.MEDIA_ROOT, 'backups')
    os.makedirs(pasta, exist_ok=True)
    caminho = os.path.join(pasta, f'inspecao_{inspecao.pk}.zip')
    with open(caminho, 'wb') as f:
        f.write(zip_bytes)
    return caminho


@login_required
def inspecao_backup_download(request, pk):
    """Baixa o backup salvo automaticamente ao finalizar a inspeção."""
    from django.conf import settings
    inspecao = get_object_or_404(Inspecao.objects.select_related('edificacao'), pk=pk)
    caminho = os.path.join(settings.MEDIA_ROOT, 'backups', f'inspecao_{pk}.zip')
    if not os.path.exists(caminho):
        messages.error(request, 'Backup automático não encontrado para esta inspeção.')
        return _redirect_detail(pk)
    nome_edificacao = inspecao.edificacao.nome.replace(' ', '_')
    nome_arquivo = f'backup_inspecao_{nome_edificacao}_{inspecao.criado_em.strftime("%Y%m%d")}.zip'
    with open(caminho, 'rb') as f:
        response = HttpResponse(f.read(), content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{nome_arquivo}"'
    return response


# ── Restaurar backup ──────────────────────────────────────────────────────────

def _profissional_por_nome(nome):
    """Busca um Profissional existente pelo nome (case-insensitive) ou cria um
    novo com CREA placeholder 'PENDENTE-N' — mesmo padrão da migração de dados
    0020 (ver apps/inspecoes/migrations/0020_inspecaoespecialidade_profissionais.py),
    usado aqui para restaurar backups antigos que ainda guardam os
    profissionais como texto livre."""
    prof = Profissional.objects.filter(nome__iexact=nome).first()
    if prof:
        return prof
    ultimo_n = 0
    for crea in Profissional.todos_objects.filter(crea__startswith='PENDENTE-').values_list('crea', flat=True):
        try:
            n = int(crea.split('-', 1)[1])
        except (IndexError, ValueError):
            continue
        ultimo_n = max(ultimo_n, n)
    return Profissional.objects.create(nome=nome, crea=f'PENDENTE-{ultimo_n + 1}')


def _restaurar_backup(arquivo_zip, request):
    """
    Lê um arquivo ZIP de backup e recria a inspeção no banco de dados.
    Cria uma NOVA inspeção — nunca sobrescreve dados existentes.
    Retorna o objeto Inspecao criado.
    """
    from apps.edificacoes.models import Edificacao
    from datetime import date as DateType

    # Mapeamentos de rótulo → valor de campo
    ESP_MAP = {
        'Engenharia Civil': 'civil',
        'Engenharia Mecânica': 'mecanica',
        'Engenharia Elétrica': 'eletrica',
    }
    STATUS_MAP = {
        'Em andamento': 'em_andamento',
        'Finalizada': 'finalizada',
    }
    PRAZO_MAP = {
        '1 mês': 1, '3 meses': 3, '6 meses': 6,
        '12 meses': 12, '18 meses': 18, '24 meses': 24,
    }
    DIRECAO_MAP = {
        'Garantia de obra': 'garantia',
        'Manutenção': 'manutencao',
        'Nova contratação': 'nova_contratacao',
    }

    conteudo = arquivo_zip.read()
    try:
        zf_obj = zipfile.ZipFile(io.BytesIO(conteudo), 'r')
    except zipfile.BadZipFile:
        raise ValueError('O arquivo enviado não é um ZIP válido.')

    with zf_obj as zf:
        if 'dados.json' not in zf.namelist():
            raise ValueError('Arquivo de backup inválido: dados.json não encontrado dentro do ZIP.')

        dados = json.loads(zf.read('dados.json').decode('utf-8'))

        # Localizar edificação pelo nome
        nome_edif = dados.get('inspecao', {}).get('edificacao', '')
        if not nome_edif:
            raise ValueError('Backup inválido: nome da edificação não encontrado.')
        try:
            edificacao = Edificacao.objects.get(nome__iexact=nome_edif)
        except Edificacao.DoesNotExist:
            raise ValueError(
                f'Edificação "{nome_edif}" não está cadastrada no sistema. '
                f'Cadastre-a em Edificações antes de restaurar o backup.'
            )

        # Criar nova inspeção
        inspecao = Inspecao.objects.create(edificacao=edificacao)

        for esp_data in dados.get('especialidades', []):
            esp_key = ESP_MAP.get(esp_data.get('especialidade', ''))
            if not esp_key:
                continue

            try:
                data_insp = DateType.fromisoformat(esp_data.get('data_inspecao', ''))
            except (ValueError, TypeError):
                data_insp = DateType.today()

            # Evitar duplicata se especialidade já existir na nova inspeção
            esp, _ = InspecaoEspecialidade.objects.get_or_create(
                inspecao=inspecao,
                especialidade=esp_key,
                defaults={
                    'data_inspecao': data_insp,
                    'status': STATUS_MAP.get(esp_data.get('status', ''), 'em_andamento'),
                },
            )
            nomes_profissionais = [n.strip() for n in esp_data.get('profissional', '').splitlines() if n.strip()]
            if nomes_profissionais:
                esp.profissionais.set([_profissional_por_nome(n) for n in nomes_profissionais])

            for achado_data in esp_data.get('achados', []):
                em_conf = bool(achado_data.get('em_conformidade', False))
                g = int(achado_data.get('gravidade', 1) or 1)
                u = int(achado_data.get('urgencia', 1) or 1)
                t = int(achado_data.get('tendencia', 1) or 1)
                gut = g * u * t

                # Backups novos guardam a prioridade que o profissional escolheu.
                # Backups antigos (anteriores a este campo) não têm — nesse caso,
                # cai para a mesma sugestão mostrada na tela (Achado.calcular_prioridade).
                if achado_data.get('prioridade_risco') is not None:
                    prioridade = int(achado_data['prioridade_risco'])
                else:
                    prioridade = Achado.calcular_prioridade(gut, em_conf)

                prazo = PRAZO_MAP.get(str(achado_data.get('prazo_meses', '')), 12)
                direcao = DIRECAO_MAP.get(str(achado_data.get('direcionamento', '')), 'manutencao')

                achado = Achado.objects.create(
                    especialidade=esp,
                    localizacao=achado_data.get('localizacao', ''),
                    sub_localizacao=achado_data.get('sub_localizacao', ''),
                    verificacao=achado_data.get('verificacao', ''),
                    em_conformidade=em_conf,
                    grupo_tecnico='' if em_conf else achado_data.get('grupo_tecnico', ''),
                    requisito_afetado='' if em_conf else achado_data.get('requisito_afetado', ''),
                    descricao_nao_conformidade='' if em_conf else achado_data.get('descricao_nao_conformidade', ''),
                    recomendacao='' if em_conf else achado_data.get('recomendacao', ''),
                    gravidade=g,
                    urgencia=u,
                    tendencia=t,
                    prioridade_risco=prioridade,
                    direcionamento=direcao,
                    prazo_meses=prazo,
                )

                # Restaurar fotos do ZIP
                for foto_path_zip in achado_data.get('fotos', []):
                    try:
                        foto_bytes = zf.read(foto_path_zip)
                    except KeyError:
                        continue  # foto não está no ZIP
                    nome_original = foto_path_zip.split('/')[-1]
                    ext = nome_original.rsplit('.', 1)[-1].lower()
                    tipo = 'image/jpeg' if ext in ('jpg', 'jpeg') else 'image/png'
                    if tipo not in ALLOWED_CONTENT_TYPES:
                        continue
                    Foto.objects.create(
                        achado=achado,
                        arquivo=ContentFile(foto_bytes, name=nome_original),
                        nome_original=nome_original,
                        tamanho_bytes=len(foto_bytes),
                    )

    _log(request, 'inspecao_criada',
         f'Inspeção restaurada do backup: "{edificacao.nome}" — Inspeção #{inspecao.pk}.')
    return inspecao


@login_required
@require_http_methods(['GET', 'POST'])
def inspecao_restaurar_backup(request):
    """Página de upload de backup ZIP para restaurar uma inspeção."""
    if request.method == 'POST':
        arquivo = request.FILES.get('backup_zip')
        if not arquivo:
            messages.error(request, 'Nenhum arquivo selecionado.')
            return redirect('inspecoes:restaurar_backup')
        if not arquivo.name.lower().endswith('.zip'):
            messages.error(request, 'O arquivo deve ter extensão .zip.')
            return redirect('inspecoes:restaurar_backup')
        try:
            inspecao = _restaurar_backup(arquivo, request)
            messages.success(
                request,
                f'Backup restaurado com sucesso! Inspeção #{inspecao.pk} — "{inspecao.edificacao}" criada.'
            )
            return redirect('inspecoes:detail', pk=inspecao.pk)
        except ValueError as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, f'Erro inesperado ao restaurar backup: {e}')
        return redirect('inspecoes:restaurar_backup')

    return render(request, 'inspecoes/restaurar_backup.html')


# ── Log de acesso ─────────────────────────────────────────────────────────────

@login_required
def log_acesso(request):
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, 'Acesso restrito a administradores.')
        return redirect('inspecoes:list')
    logs = LogAcesso.objects.select_related('usuario').all()
    # Filtros simples
    tipo = request.GET.get('tipo', '')
    usuario_id = request.GET.get('usuario', '')
    if tipo:
        logs = logs.filter(tipo=tipo)
    if usuario_id:
        logs = logs.filter(usuario_id=usuario_id)
    from django.contrib.auth import get_user_model
    usuarios = get_user_model().objects.filter(logs_acesso__isnull=False).distinct().order_by('first_name', 'username')
    paginator = Paginator(logs, 50)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'inspecoes/log_acesso.html', {
        'page_obj': page,
        'tipo_choices': LogAcesso.TIPO_CHOICES,
        'tipo_selecionado': tipo,
        'usuarios': usuarios,
        'usuario_selecionado': usuario_id,
    })


# ── Configurações ──────────────────────────────────────────────────────────────

@login_required
def configuracoes(request):
    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'add':
            campo = request.POST.get('campo', '').strip()
            label = request.POST.get('label', '').strip()
            campos_validos = dict(OpcaoCampo.CAMPO_CHOICES)
            if not campo or campo not in campos_validos:
                messages.error(request, 'Campo inválido.')
            elif not label:
                messages.error(request, 'A descrição não pode ficar em branco.')
            else:
                try:
                    OpcaoCampo.objects.create(campo=campo, label=label)
                    messages.success(request, f'Opção "{label}" adicionada em {campos_validos[campo]}.')
                except Exception:
                    messages.error(request, f'A opção "{label}" já existe neste campo.')

        elif action == 'delete':
            opcao_id = request.POST.get('opcao_id')
            try:
                opcao = OpcaoCampo.objects.get(pk=opcao_id, is_padrao=False)
                nome = opcao.label
                opcao.excluir(request.user)
                messages.success(request, f'Opção "{nome}" removida.')
            except OpcaoCampo.DoesNotExist:
                messages.error(request, 'Opção não encontrada ou não pode ser removida.')

        return redirect('inspecoes:configuracoes')

    opcoes_qs = OpcaoCampo.objects.all()
    grupos = {}
    for campo_key, campo_label in OpcaoCampo.CAMPO_CHOICES:
        grupos[campo_key] = {
            'label': campo_label,
            'opcoes': [o for o in opcoes_qs if o.campo == campo_key],
        }

    return render(request, 'inspecoes/configuracoes.html', {'grupos': grupos})


# ── Visitas técnicas ──────────────────────────────────────────────────────────

@login_required
def visita_localidades(request):
    from apps.edificacoes.models import Edificacao
    localidades = (
        Edificacao.objects.filter(ativo=True)
        .annotate(num_visitas=Count(
            'visitas',
            filter=Q(visitas__visita_pai__isnull=True),
            distinct=True,
        ))
        .order_by('nome')
    )
    return render(request, 'inspecoes/visita_localidades.html', {
        'localidades': localidades,
    })


@login_required
def visita_list(request, edif_pk):
    from apps.edificacoes.models import Edificacao
    from .forms import VisitaFilterForm
    edificacao = get_object_or_404(Edificacao, pk=edif_pk)
    form = VisitaFilterForm(request.GET or None)
    # Apenas visitas principais; as subvisitas aparecem dentro do detalhe da visita.
    visitas = edificacao.visitas.filter(visita_pai__isnull=True).annotate(
        num_fotos=Count('fotos', distinct=True),
        num_subvisitas=Count('subvisitas', distinct=True),
    )
    if form.is_valid():
        if form.cleaned_data.get('data_inicio'):
            visitas = visitas.filter(data_visita__gte=form.cleaned_data['data_inicio'])
        if form.cleaned_data.get('data_fim'):
            visitas = visitas.filter(data_visita__lte=form.cleaned_data['data_fim'])

    # Agrupa as visitas por disciplina, na ordem das choices
    visitas = list(visitas)
    labels = dict(VisitaTecnica.DISCIPLINA_CHOICES)
    grupos = []
    for chave, nome in VisitaTecnica.DISCIPLINA_CHOICES:
        itens = [v for v in visitas if v.disciplina == chave]
        if itens:
            grupos.append({'disciplina': nome, 'visitas': itens})
    sem_disciplina = [v for v in visitas if not v.disciplina or v.disciplina not in labels]
    if sem_disciplina:
        grupos.append({'disciplina': 'Não informada', 'visitas': sem_disciplina})

    return render(request, 'inspecoes/visita_list.html', {
        'edificacao': edificacao,
        'filter_form': form,
        'visitas': visitas,
        'grupos': grupos,
    })


def _coletar_participantes(request):
    """Lê os campos dinâmicos de participantes e retorna a lista limpa de nomes."""
    return [n.strip() for n in request.POST.getlist('participantes') if n.strip()]


@login_required
def visita_create(request, edif_pk):
    from apps.edificacoes.models import Edificacao
    edificacao = get_object_or_404(Edificacao, pk=edif_pk)
    form = VisitaTecnicaForm(request.POST or None)
    participantes = _coletar_participantes(request) if request.method == 'POST' else [request.user.get_full_name()]
    erro_participantes = None
    if request.method == 'POST' and form.is_valid():
        if not participantes:
            erro_participantes = 'Informe ao menos um profissional participante.'
        else:
            visita = form.save(commit=False)
            visita.edificacao = edificacao
            visita.criado_por = request.user
            visita.participantes = '\n'.join(participantes)
            visita.save()
            for arquivo in request.FILES.getlist('fotos'):
                if foto_valida(arquivo.content_type, arquivo.size):
                    cf, nome, tamanho = comprimir_imagem(arquivo.read(), arquivo.name)
                    VisitaFoto.objects.create(
                        visita=visita,
                        arquivo=cf,
                        nome_original=nome,
                        tamanho_bytes=tamanho,
                    )
            _log(request, 'visita_criada',
                 f'Visita técnica criada em "{edificacao.nome}" ({visita.data_visita:%d/%m/%Y}) '
                 f'por {visita.participantes_display}.')
            messages.success(request, 'Visita técnica registrada com sucesso.')
            return redirect('inspecoes:visita_detail', pk=visita.pk)
    return render(request, 'inspecoes/visita_form.html', {
        'form': form,
        'edificacao': edificacao,
        'participantes': participantes or [''],
        'erro_participantes': erro_participantes,
        'fotos_existentes': [],
    })


def _pode_editar_visita(user, visita):
    if user.is_staff or user.is_superuser:
        return True
    return visita.criado_por_id == user.id


@login_required
def visita_detail(request, pk):
    visita = get_object_or_404(
        VisitaTecnica.objects.select_related('edificacao', 'visita_pai').prefetch_related(
            'fotos', 'subvisitas__fotos',
        ),
        pk=pk,
    )
    subvisitas = visita.subvisitas.order_by('data_visita', 'criado_em')
    return render(request, 'inspecoes/visita_detail.html', {
        'visita': visita,
        'subvisitas': subvisitas,
        'pode_editar': _pode_editar_visita(request.user, visita),
    })


def _acesso_negado_visita(request, visita):
    messages.error(
        request,
        'Acesso negado. Apenas quem registrou a visita pode realizar esta ação.',
    )
    return redirect('inspecoes:visita_detail', pk=visita.pk)


@login_required
def visita_update(request, pk):
    visita = get_object_or_404(VisitaTecnica.objects.select_related('edificacao'), pk=pk)
    if not _pode_editar_visita(request.user, visita):
        return _acesso_negado_visita(request, visita)
    form = VisitaTecnicaForm(request.POST or None, instance=visita)
    participantes = _coletar_participantes(request) if request.method == 'POST' else visita.participantes_lista
    erro_participantes = None
    if request.method == 'POST' and form.is_valid():
        if not participantes:
            erro_participantes = 'Informe ao menos um profissional participante.'
        else:
            visita = form.save(commit=False)
            visita.participantes = '\n'.join(participantes)
            visita.save()
            messages.success(request, 'Visita atualizada com sucesso.')
            return redirect('inspecoes:visita_detail', pk=visita.pk)
    return render(request, 'inspecoes/visita_form.html', {
        'form': form,
        'edificacao': visita.edificacao,
        'visita': visita,
        'participantes': participantes or [''],
        'erro_participantes': erro_participantes,
        'fotos_existentes': visita.fotos.all(),
    })


@login_required
@require_POST
def visita_concluir(request, pk):
    visita = get_object_or_404(VisitaTecnica.objects.select_related('edificacao'), pk=pk)
    if not _pode_editar_visita(request.user, visita):
        return _acesso_negado_visita(request, visita)
    if visita.is_subvisita:
        messages.error(request, 'Subvisitas de acompanhamento não são concluídas isoladamente.')
        return redirect('inspecoes:visita_detail', pk=visita.pk)
    if not visita.concluida:
        visita.concluida = True
        visita.concluida_em = timezone.now()
        visita.save(update_fields=['concluida', 'concluida_em', 'atualizado_em'])
        _log(request, 'visita_concluida',
             f'Visita técnica concluída em "{visita.edificacao.nome}" ({visita.data_visita:%d/%m/%Y}).')
        messages.success(request, 'Visita marcada como concluída.')
    return redirect('inspecoes:visita_detail', pk=visita.pk)


@login_required
@require_POST
def visita_reabrir(request, pk):
    visita = get_object_or_404(VisitaTecnica.objects.select_related('edificacao'), pk=pk)
    if not _pode_editar_visita(request.user, visita):
        return _acesso_negado_visita(request, visita)
    if visita.concluida:
        visita.concluida = False
        visita.concluida_em = None
        visita.save(update_fields=['concluida', 'concluida_em', 'atualizado_em'])
        _log(request, 'visita_reaberta',
             f'Visita técnica reaberta em "{visita.edificacao.nome}" ({visita.data_visita:%d/%m/%Y}).')
        messages.success(request, 'Visita reaberta. Já é possível registrar novas subvisitas.')
    return redirect('inspecoes:visita_detail', pk=visita.pk)


@login_required
def visita_subvisita_create(request, pk):
    visita_pai = get_object_or_404(VisitaTecnica.objects.select_related('edificacao'), pk=pk)
    if not _pode_editar_visita(request.user, visita_pai):
        return _acesso_negado_visita(request, visita_pai)
    if not visita_pai.pode_receber_subvisita:
        if visita_pai.is_subvisita:
            messages.error(request, 'Não é possível criar subvisita de uma subvisita.')
            return redirect('inspecoes:visita_detail', pk=visita_pai.pk)
        messages.error(request, 'Esta visita está concluída. Reabra-a para registrar novas subvisitas.')
        return redirect('inspecoes:visita_detail', pk=visita_pai.pk)

    if request.method == 'POST':
        form = VisitaTecnicaForm(request.POST)
        participantes = _coletar_participantes(request)
    else:
        form = VisitaTecnicaForm(initial={'disciplina': visita_pai.disciplina})
        participantes = visita_pai.participantes_lista or [request.user.get_full_name()]
    erro_participantes = None
    if request.method == 'POST' and form.is_valid():
        if not participantes:
            erro_participantes = 'Informe ao menos um profissional participante.'
        else:
            sub = form.save(commit=False)
            sub.edificacao = visita_pai.edificacao
            sub.visita_pai = visita_pai
            sub.criado_por = request.user
            sub.participantes = '\n'.join(participantes)
            sub.save()
            for arquivo in request.FILES.getlist('fotos'):
                if foto_valida(arquivo.content_type, arquivo.size):
                    cf, nome, tamanho = comprimir_imagem(arquivo.read(), arquivo.name)
                    VisitaFoto.objects.create(
                        visita=sub, arquivo=cf, nome_original=nome, tamanho_bytes=tamanho,
                    )
            _log(request, 'subvisita_criada',
                 f'Subvisita de acompanhamento criada em "{visita_pai.edificacao.nome}" '
                 f'({sub.data_visita:%d/%m/%Y}) para a visita de {visita_pai.data_visita:%d/%m/%Y}.')
            messages.success(request, 'Subvisita de acompanhamento registrada com sucesso.')
            return redirect('inspecoes:visita_detail', pk=visita_pai.pk)
    return render(request, 'inspecoes/visita_form.html', {
        'form': form,
        'edificacao': visita_pai.edificacao,
        'visita_pai': visita_pai,
        'participantes': participantes or [''],
        'erro_participantes': erro_participantes,
        'fotos_existentes': [],
    })


@login_required
@require_POST
def visita_delete(request, pk):
    visita = get_object_or_404(VisitaTecnica.objects.select_related('edificacao'), pk=pk)
    if not _pode_editar_visita(request.user, visita):
        return _acesso_negado_visita(request, visita)
    edif_pk = visita.edificacao_id
    _log(request, 'visita_excluida',
         f'Visita técnica excluída de "{visita.edificacao.nome}" ({visita.data_visita:%d/%m/%Y}).')
    visita.excluir(request.user)
    messages.success(request, 'Visita excluída com sucesso.')
    return redirect('inspecoes:visita_list', edif_pk=edif_pk)


@login_required
@require_POST
def visita_foto_upload(request, visita_pk):
    visita = get_object_or_404(VisitaTecnica, pk=visita_pk)
    arquivo = request.FILES.get('arquivo')
    if not arquivo:
        return JsonResponse({'erro': 'Nenhum arquivo enviado.'}, status=400)
    erro = erro_validacao_foto(arquivo.content_type, arquivo.size)
    if erro:
        return JsonResponse({'erro': erro}, status=400)
    cf, nome, tamanho = comprimir_imagem(arquivo.read(), arquivo.name)
    foto = VisitaFoto.objects.create(
        visita=visita, arquivo=cf,
        nome_original=nome, tamanho_bytes=tamanho,
    )
    return JsonResponse({'id': foto.pk, 'url': foto.arquivo.url, 'nome': foto.nome_original})


@login_required
@require_http_methods(['DELETE'])
def visita_foto_delete(request, pk):
    foto = get_object_or_404(VisitaFoto, pk=pk)
    foto.excluir(request.user)
    return HttpResponse(status=204)
