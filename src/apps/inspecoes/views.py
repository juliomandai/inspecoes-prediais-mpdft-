import base64
import json
import io
import zipfile
import os
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.files.base import ContentFile
from django.core.paginator import Paginator
from django.db.models import Count, Q, Min
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.template.loader import render_to_string
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_http_methods

from django.urls import reverse

from .models import Inspecao, InspecaoEspecialidade, Achado, Foto, OpcaoCampo, LogAcesso, VisitaTecnica, VisitaFoto
from .forms import InspecaoForm, EspecialidadeForm, AchadoForm, InspecaoFilterForm, VisitaTecnicaForm, VisitaFilterForm, SignUpForm
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
            qs = qs.filter(especialidades__profissional__icontains=form.cleaned_data['profissional']).distinct()
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
    inspecao.delete()
    messages.success(request, f'Inspeção "{nome}" excluída com sucesso.')
    return redirect('inspecoes:list')


# ── Especialidades ─────────────────────────────────────────────────────────────

@login_required
def especialidade_create(request, inspecao_pk):
    inspecao = get_object_or_404(Inspecao, pk=inspecao_pk)
    form = EspecialidadeForm(request.POST or None, inspecao=inspecao)
    if form.is_valid():
        esp = form.save(commit=False)
        esp.inspecao = inspecao
        try:
            esp.full_clean()
            esp.save()
            _log(request, 'especialidade_criada', f'{esp.get_especialidade_display()} criada em "{inspecao.edificacao}".')
            messages.success(request, f'{esp.get_especialidade_display()} adicionada com sucesso.')
        except Exception as e:
            messages.error(request, f'Erro ao salvar: {e}')
        return redirect('inspecoes:detail', pk=inspecao_pk)
    return render(request, 'inspecoes/especialidade_form.html', {
        'form': form,
        'inspecao': inspecao,
    })


def _pode_editar_especialidade(user, esp):
    """Retorna True se o usuário tem permissão para editar esta especialidade."""
    if user.is_staff or user.is_superuser:
        return True
    return user.get_full_name() == esp.profissional


def _acesso_negado_especialidade(request, esp):
    messages.error(
        request,
        f'Acesso negado. Apenas o profissional responsável '
        f'("{esp.profissional}") pode realizar esta ação.',
    )
    return _redirect_detail(esp.inspecao_id, esp.pk)


@login_required
def especialidade_update(request, pk):
    esp = get_object_or_404(InspecaoEspecialidade.objects.select_related('inspecao'), pk=pk)
    if not _pode_editar_especialidade(request.user, esp):
        return _acesso_negado_especialidade(request, esp)
    form = EspecialidadeForm(request.POST or None, instance=esp, inspecao=esp.inspecao)
    if form.is_valid():
        form.save()
        messages.success(request, 'Especialidade atualizada com sucesso.')
        return _redirect_detail(esp.inspecao_id, esp.pk)
    return render(request, 'inspecoes/especialidade_form.html', {
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
    esp.delete()
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


@login_required
@require_POST
def especialidade_reabrir(request, pk):
    esp = get_object_or_404(InspecaoEspecialidade, pk=pk)
    if not _pode_editar_especialidade(request.user, esp):
        return _acesso_negado_especialidade(request, esp)
    if esp.status == 'em_andamento':
        messages.error(request, 'Esta especialidade já está em andamento.')
        return _redirect_detail(esp.inspecao_id, esp.pk)
    esp.status = 'em_andamento'
    esp.save(update_fields=['status', 'atualizado_em'])
    messages.success(request, f'{esp.get_especialidade_display()} reaberta.')
    return _redirect_detail(esp.inspecao_id, esp.pk)


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
            if arquivo.content_type in ALLOWED_CONTENT_TYPES and arquivo.size <= MAX_UPLOAD_SIZE:
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
    achado.delete()
    messages.success(request, 'Achado excluído com sucesso.')
    return _redirect_detail(inspecao_pk, esp_pk)


# ── Fotos ──────────────────────────────────────────────────────────────────────

ALLOWED_CONTENT_TYPES = {'image/jpeg', 'image/png'}
MAX_UPLOAD_SIZE = 10 * 1024 * 1024


@login_required
@require_POST
def foto_upload(request, achado_pk):
    achado = get_object_or_404(Achado.objects.select_related('especialidade'), pk=achado_pk)
    arquivo = request.FILES.get('arquivo')
    if not arquivo:
        return JsonResponse({'erro': 'Nenhum arquivo enviado.'}, status=400)
    if arquivo.content_type not in ALLOWED_CONTENT_TYPES:
        return JsonResponse({'erro': 'Formato inválido. Use JPEG ou PNG.'}, status=400)
    if arquivo.size > MAX_UPLOAD_SIZE:
        return JsonResponse({'erro': 'Arquivo muito grande. Máximo: 10 MB.'}, status=400)

    cf, nome, tamanho = comprimir_imagem(arquivo.read(), arquivo.name)
    foto = Foto.objects.create(
        achado=achado,
        arquivo=cf,
        nome_original=nome,
        tamanho_bytes=tamanho,
    )
    return JsonResponse({'id': foto.pk, 'url': foto.arquivo.url, 'nome': foto.nome_original})


@login_required
@require_http_methods(['DELETE'])
def foto_delete(request, pk):
    foto = get_object_or_404(Foto.objects.select_related('achado__especialidade'), pk=pk)
    foto.delete()
    return HttpResponse(status=204)


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
            if tipo not in ALLOWED_CONTENT_TYPES:
                continue
            b64 = foto_data.get('dados_b64', '')
            if not b64:
                continue
            conteudo = base64.b64decode(b64)
            if len(conteudo) > MAX_UPLOAD_SIZE:
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


# ── Análise — helper compartilhado ────────────────────────────────────────────

def _analise_data(achados_list):
    """Calcula todos os dados de análise a partir de uma lista de achados."""
    nao_conformes = [a for a in achados_list if a.gut_total > 0]
    total = len(achados_list)
    total_nc = len(nao_conformes)
    total_conformes = total - total_nc

    p1 = [a for a in nao_conformes if a.prioridade_risco == 1]
    p2 = [a for a in nao_conformes if a.prioridade_risco == 2]
    p3 = [a for a in nao_conformes if a.prioridade_risco == 3]

    # Grupos
    grupo_labels = dict(Achado.GRUPO_TECNICO_CHOICES)
    grupo_map = {}
    for a in nao_conformes:
        g = a.grupo_tecnico
        if g not in grupo_map:
            grupo_map[g] = {'grupo_tecnico': g, 'nome': grupo_labels.get(g, g), 'p1': 0, 'p2': 0, 'p3': 0, 'total': 0}
        grupo_map[g][f'p{a.prioridade_risco}'] += 1
        grupo_map[g]['total'] += 1
    grupos = sorted(grupo_map.values(), key=lambda x: (-x['p1'], -x['total']))

    # Direcionamento
    def achados_por_dir(dir_key):
        result = {'p1': [], 'p2': [], 'p3': []}
        for a in nao_conformes:
            if a.direcionamento == dir_key:
                result[f'p{a.prioridade_risco}'].append(a)
        return result

    manutencao = achados_por_dir('manutencao')
    nova_contratacao = achados_por_dir('nova_contratacao')
    garantia = achados_por_dir('garantia')

    # GUT
    gut_vals = [a.gut_total for a in nao_conformes]
    gut_media = round(sum(gut_vals) / len(gut_vals), 1) if gut_vals else 0
    gut_max = max(gut_vals) if gut_vals else 0
    gut_min = min(gut_vals) if gut_vals else 0
    n = len(gut_vals)
    gut_desvio = round((sum((v - gut_media) ** 2 for v in gut_vals) / n) ** 0.5, 1) if n > 1 else 0
    top_gut_raw = sorted(nao_conformes, key=lambda a: -a.gut_total)[:10]
    top_gut_max = top_gut_raw[0].gut_total if top_gut_raw else 1
    for a in top_gut_raw:
        a.gut_pct = round(a.gut_total / top_gut_max * 100)

    # Por localização
    loc_map = {}
    for a in nao_conformes:
        loc = a.localizacao
        if loc not in loc_map:
            loc_map[loc] = {'localizacao': loc, 'total': 0, 'p1': 0, 'p2': 0, 'p3': 0}
        loc_map[loc]['total'] += 1
        loc_map[loc][f'p{a.prioridade_risco}'] += 1
    por_localizacao = sorted(loc_map.values(), key=lambda x: -x['total'])

    # Por prazo
    prazo_map = {}
    prazo_labels = dict(Achado.PRAZO_CHOICES)
    for a in nao_conformes:
        k = a.prazo_meses
        if k not in prazo_map:
            prazo_map[k] = {'prazo': k, 'label': prazo_labels.get(k, f'{k} meses'), 'total': 0, 'p1': 0, 'p2': 0, 'p3': 0}
        prazo_map[k]['total'] += 1
        prazo_map[k][f'p{a.prioridade_risco}'] += 1
    por_prazo = sorted(prazo_map.values(), key=lambda x: x['prazo'])

    # Por requisito afetado
    _req_labels = dict(Achado.REQUISITO_CHOICES)
    _req_colors = {
        'seguranca_estrutural': '#dc3545', 'acessibilidade': '#ffc107',
        'saude_qualidade_ar': '#0d6efd',   'funcionalidade': '#198754',
        'estetica': '#6f42c1',             'eficiencia_energetica': '#fd7e14',
        'sustentabilidade': '#20c997',     'durabilidade': '#7B2D00',
    }
    req_count = {k: 0 for k in _req_labels}
    for a in nao_conformes:
        req_count[a.requisito_afetado] = req_count.get(a.requisito_afetado, 0) + 1
    por_requisito = [
        {'requisito': k, 'label': _req_labels.get(k, k), 'total': req_count.get(k, 0),
         'color': _req_colors.get(k, '#adb5bd')}
        for k in _req_labels
    ]

    # ── Índice de Saúde da Edificação (IQE 0–100) + % conformidade ────────────
    pct_conformidade = round(total_conformes / total * 100) if total else 0
    # Penaliza por severidade (P1=5, P2=2, P3=1), normalizado pelo pior caso (tudo P1).
    if total:
        penalidade = 5 * len(p1) + 2 * len(p2) + 1 * len(p3)
        iqe = round(100 * (1 - penalidade / (5 * total)))
    else:
        iqe = 100
    if iqe >= 80:
        iqe_faixa, iqe_cor = 'Bom', 'success'
    elif iqe >= 50:
        iqe_faixa, iqe_cor = 'Atenção', 'warning'
    else:
        iqe_faixa, iqe_cor = 'Crítico', 'danger'

    # ── Componentes GUT médios (G, U, T isolados) ─────────────────────────────
    if total_nc:
        g_media = round(sum(a.gravidade for a in nao_conformes) / total_nc, 1)
        u_media = round(sum(a.urgencia for a in nao_conformes) / total_nc, 1)
        t_media = round(sum(a.tendencia for a in nao_conformes) / total_nc, 1)
    else:
        g_media = u_media = t_media = 0

    # ── Matriz Risco × Prazo ──────────────────────────────────────────────────
    prazos_ordem = [p[0] for p in Achado.PRAZO_CHOICES]
    prazo_lbls = dict(Achado.PRAZO_CHOICES)
    matriz_risco_prazo = []
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
        matriz_risco_prazo.append({'prioridade': prio, 'celulas': celulas})
    matriz_prazos = [prazo_lbls[p] for p in prazos_ordem]
    n_incoerencias = sum(1 for a in nao_conformes
                         if a.prioridade_risco == 1 and a.prazo_meses >= 12)
    n_ganhos_rapidos = sum(1 for a in nao_conformes
                           if a.prioridade_risco in (1, 2) and a.prazo_meses <= 3)

    # ── Encaminhamento (direcionamento) ───────────────────────────────────────
    dir_labels = dict(Achado.DIRECIONAMENTO_CHOICES)
    dir_count = {k: 0 for k in dir_labels}
    for a in nao_conformes:
        dir_count[a.direcionamento] = dir_count.get(a.direcionamento, 0) + 1
    por_direcionamento = [
        {'key': k, 'label': dir_labels[k], 'total': dir_count.get(k, 0),
         'pct': round(dir_count.get(k, 0) / total_nc * 100) if total_nc else 0}
        for k in dir_labels
    ]

    # ── Concentração de risco por localização (soma GUT) ──────────────────────
    for l in loc_map.values():
        l['soma_gut'] = 0
    for a in nao_conformes:
        loc_map[a.localizacao]['soma_gut'] += a.gut_total
    por_localizacao_gut = sorted(loc_map.values(), key=lambda x: -x['soma_gut'])
    _max_soma = por_localizacao_gut[0]['soma_gut'] if por_localizacao_gut else 1
    for l in por_localizacao_gut:
        l['gut_pct'] = round(l['soma_gut'] / _max_soma * 100) if _max_soma else 0

    # ── Pareto por grupo técnico (80/20) ──────────────────────────────────────
    pareto = sorted(grupo_map.values(), key=lambda x: -x['total'])
    _acum = 0
    for g in pareto:
        _acum += g['total']
        g['acumulado'] = _acum
        g['acumulado_pct'] = round(_acum / total_nc * 100) if total_nc else 0

    # ── Cobertura fotográfica das evidências (sobre as não conformidades) ─────
    com_foto = 0
    for a in nao_conformes:
        try:
            if len(a.fotos.all()) > 0:
                com_foto += 1
        except Exception:
            pass
    cobertura_foto_pct = round(com_foto / total_nc * 100) if total_nc else 0

    # ── Plano de ação priorizado (P1 primeiro, depois maior GUT) ──────────────
    plano_acao = sorted(nao_conformes, key=lambda a: (a.prioridade_risco, -a.gut_total))[:15]

    # Charts JSON
    chart_risco = json.dumps({
        'labels': ['P1 — Crítico', 'P2 — Regular', 'P3 — Mínimo'],
        'data': [len(p1), len(p2), len(p3)],
        'colors': ['#dc3545', '#fd7e14', '#198754'],
    })
    chart_direcionamento = json.dumps({
        'labels': [d['label'] for d in por_direcionamento],
        'data': [d['total'] for d in por_direcionamento],
        'colors': ['#6f42c1', '#0dcaf0', '#ffc107'],
    })
    chart_pareto = json.dumps({
        'labels': [g['nome'] for g in pareto],
        'data': [g['total'] for g in pareto],
        'acumulado': [g['acumulado_pct'] for g in pareto],
    })
    chart_prazo = json.dumps({
        'labels': [p['label'] for p in por_prazo],
        'data': [p['total'] for p in por_prazo],
    })
    chart_requisitos = json.dumps({
        'labels': [r['label'] for r in por_requisito],
        'data':   [r['total'] for r in por_requisito],
        'colors': [r['color'] for r in por_requisito],
    })

    return {
        'total': total, 'total_nc': total_nc, 'total_conformes': total_conformes,
        'p1': p1, 'p2': p2, 'p3': p3,
        'grupos': grupos,
        'manutencao': manutencao, 'nova_contratacao': nova_contratacao, 'garantia': garantia,
        'gut_media': gut_media, 'gut_max': gut_max, 'gut_min': gut_min, 'gut_desvio': gut_desvio,
        'top_gut': top_gut_raw,
        'por_localizacao': por_localizacao,
        'por_prazo': por_prazo,
        'por_requisito': por_requisito,
        'chart_risco': chart_risco,
        'chart_prazo': chart_prazo,
        'chart_requisitos': chart_requisitos,
        # Novos insights (Dashboard de Encerramento)
        'iqe': iqe, 'iqe_faixa': iqe_faixa, 'iqe_cor': iqe_cor,
        'pct_conformidade': pct_conformidade,
        'g_media': g_media, 'u_media': u_media, 't_media': t_media,
        'matriz_risco_prazo': matriz_risco_prazo, 'matriz_prazos': matriz_prazos,
        'n_incoerencias': n_incoerencias, 'n_ganhos_rapidos': n_ganhos_rapidos,
        'por_direcionamento': por_direcionamento,
        'por_localizacao_gut': por_localizacao_gut,
        'pareto': pareto,
        'cobertura_foto_pct': cobertura_foto_pct, 'fotos_com': com_foto,
        'plano_acao': plano_acao,
        'chart_direcionamento': chart_direcionamento,
        'chart_pareto': chart_pareto,
    }


# ── Gráficos para PDF (renderizados como imagem, pois o xhtml2pdf não roda JS) ─

def _png_data_uri(img):
    buf = io.BytesIO()
    img.save(buf, 'PNG')
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()


def _fonte(tamanho):
    from PIL import ImageFont
    for caminho in ('C:/Windows/Fonts/arial.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'):
        try:
            return ImageFont.truetype(caminho, tamanho)
        except OSError:
            continue
    return ImageFont.load_default()


def _grafico_rosca_risco(n1, n2, n3):
    """Rosca (donut) com a distribuição de prioridades. Retorna data URI PNG ou None."""
    from PIL import Image, ImageDraw
    total = n1 + n2 + n3
    if total == 0:
        return None
    S = 4
    size = 340 * S
    img = Image.new('RGB', (size, size), 'white')
    d = ImageDraw.Draw(img)
    margem = 8 * S
    box = [margem, margem, size - margem, size - margem]
    ang = -90.0
    for val, cor in ((n1, (204, 0, 0)), (n2, (204, 102, 0)), (n3, (0, 102, 0))):
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


def _adicionar_graficos(ctx):
    """Acrescenta ao contexto as imagens dos gráficos (risco e prazo)."""
    ctx['grafico_risco_img'] = _grafico_rosca_risco(
        len(ctx.get('p1', [])), len(ctx.get('p2', [])), len(ctx.get('p3', []))
    )
    ctx['grafico_prazo_img'] = _grafico_barras_prazo(ctx.get('por_prazo', []))
    return ctx


def _gerar_pdf(html_string, nome_arquivo):
    from xhtml2pdf import pisa
    buffer = io.BytesIO()
    result = pisa.pisaDocument(io.BytesIO(html_string.encode('utf-8')), buffer, encoding='utf-8')
    if result.err:
        return HttpResponse(f'Erro ao gerar PDF: {result.err}', status=500)
    resp = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    resp['Content-Disposition'] = f'attachment; filename="{nome_arquivo}"'
    return resp


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
            'profissional': esp.profissional,
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
def inspecao_backup(request, pk):
    inspecao = get_object_or_404(
        Inspecao.objects.select_related('edificacao').prefetch_related(
            'especialidades__achados__fotos',
        ),
        pk=pk,
    )
    zip_bytes, nome_arquivo = _gerar_zip_backup(inspecao)
    response = HttpResponse(zip_bytes, content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{nome_arquivo}"'
    return response


@login_required
def inspecao_backup_download(request, pk):
    """Baixa o backup salvo automaticamente ao finalizar a inspeção."""
    from django.conf import settings
    inspecao = get_object_or_404(Inspecao.objects.select_related('edificacao'), pk=pk)
    caminho = os.path.join(settings.MEDIA_ROOT, 'backups', f'inspecao_{pk}.zip')
    if not os.path.exists(caminho):
        messages.error(request, 'Backup automático não encontrado. Use o botão "Backup" para gerar um agora.')
        return _redirect_detail(pk)
    nome_edificacao = inspecao.edificacao.nome.replace(' ', '_')
    nome_arquivo = f'backup_inspecao_{nome_edificacao}_{inspecao.criado_em.strftime("%Y%m%d")}.zip'
    with open(caminho, 'rb') as f:
        response = HttpResponse(f.read(), content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{nome_arquivo}"'
    return response


# ── Restaurar backup ──────────────────────────────────────────────────────────

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
                    'profissional': esp_data.get('profissional', ''),
                    'data_inspecao': data_insp,
                    'status': STATUS_MAP.get(esp_data.get('status', ''), 'em_andamento'),
                },
            )

            for achado_data in esp_data.get('achados', []):
                em_conf = bool(achado_data.get('em_conformidade', False))
                g = int(achado_data.get('gravidade', 1) or 1)
                u = int(achado_data.get('urgencia', 1) or 1)
                t = int(achado_data.get('tendencia', 1) or 1)
                gut = g * u * t

                if em_conf:
                    prioridade = 3
                elif gut >= 27:
                    prioridade = 1
                elif gut >= 8:
                    prioridade = 2
                else:
                    prioridade = 3

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
                opcao.delete()
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
        .annotate(num_visitas=Count('visitas', distinct=True))
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
    visitas = edificacao.visitas.annotate(num_fotos=Count('fotos'))
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
                if arquivo.content_type in ALLOWED_CONTENT_TYPES and arquivo.size <= MAX_UPLOAD_SIZE:
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
        VisitaTecnica.objects.select_related('edificacao').prefetch_related('fotos'),
        pk=pk,
    )
    return render(request, 'inspecoes/visita_detail.html', {
        'visita': visita,
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
def visita_delete(request, pk):
    visita = get_object_or_404(VisitaTecnica.objects.select_related('edificacao'), pk=pk)
    if not _pode_editar_visita(request.user, visita):
        return _acesso_negado_visita(request, visita)
    edif_pk = visita.edificacao_id
    _log(request, 'visita_excluida',
         f'Visita técnica excluída de "{visita.edificacao.nome}" ({visita.data_visita:%d/%m/%Y}).')
    visita.delete()
    messages.success(request, 'Visita excluída com sucesso.')
    return redirect('inspecoes:visita_list', edif_pk=edif_pk)


@login_required
@require_POST
def visita_foto_upload(request, visita_pk):
    visita = get_object_or_404(VisitaTecnica, pk=visita_pk)
    arquivo = request.FILES.get('arquivo')
    if not arquivo:
        return JsonResponse({'erro': 'Nenhum arquivo enviado.'}, status=400)
    if arquivo.content_type not in ALLOWED_CONTENT_TYPES:
        return JsonResponse({'erro': 'Formato inválido. Use JPEG ou PNG.'}, status=400)
    if arquivo.size > MAX_UPLOAD_SIZE:
        return JsonResponse({'erro': 'Arquivo muito grande. Máximo: 10 MB.'}, status=400)
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
    foto.delete()
    return HttpResponse(status=204)
