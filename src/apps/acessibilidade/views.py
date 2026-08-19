import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.edificacoes.models import Edificacao
from .forms import AvaliacaoEditForm, AvaliacaoEdicaoLoteForm
from .models import Avaliacao, Regiao
from .services import aplicar_edicao, aplicar_edicao_lote


def _avaliacoes_filtradas(request):
    qs = Avaliacao.objects.select_related('local', 'local__edificacao', 'criterio')
    edificacao_id = request.GET.get('edificacao')
    regiao = request.GET.get('regiao')
    status = request.GET.get('status')
    busca = request.GET.get('q')
    if edificacao_id:
        qs = qs.filter(local__edificacao_id=edificacao_id)
    if regiao:
        qs = qs.filter(local__regiao=regiao)
    if status:
        qs = qs.filter(status=status)
    if busca:
        qs = qs.filter(
            Q(criterio__nome__icontains=busca)
            | Q(local__nome__icontains=busca)
            | Q(observacao__icontains=busca)
        )
    return qs.order_by('local__edificacao__nome', 'local__regiao', 'local__nome', 'criterio__nome')


@login_required
def dashboard(request):
    stats = (
        Avaliacao.objects.values('local__edificacao__nome', 'local__edificacao_id')
        .annotate(
            total=Count('id'),
            ok=Count('id', filter=Q(status=Avaliacao.Status.OK)),
            pendente=Count('id', filter=Q(status=Avaliacao.Status.PENDENTE)),
            nao_se_aplica=Count('id', filter=Q(status=Avaliacao.Status.NAO_SE_APLICA)),
        )
        .order_by('local__edificacao__nome')
    )
    return render(request, 'acessibilidade/dashboard.html', {'stats': stats})


@login_required
def lista(request):
    qs = _avaliacoes_filtradas(request)
    paginator = Paginator(qs, 30)
    pagina = paginator.get_page(request.GET.get('pagina'))
    edificacoes = (
        Edificacao.objects.filter(locais_acessibilidade__isnull=False).distinct().order_by('nome')
    )
    filtros = request.GET.copy()
    filtros.pop('pagina', None)
    return render(request, 'acessibilidade/lista.html', {
        'pagina': pagina,
        'edificacoes': edificacoes,
        'regioes': Regiao.choices,
        'status_choices': Avaliacao.Status.choices,
        'query_string': filtros.urlencode(),
    })


@login_required
def editar(request, pk):
    avaliacao = get_object_or_404(Avaliacao, pk=pk)
    if request.method == 'POST':
        form = AvaliacaoEditForm(request.POST)
        if form.is_valid():
            aplicar_edicao(avaliacao, form.cleaned_data, request.user)
            messages.success(request, 'Avaliação atualizada com sucesso.')
            return redirect('acessibilidade:lista')
    else:
        form = AvaliacaoEditForm(initial={
            'status': avaliacao.status,
            'resolucao_diagnostico': avaliacao.resolucao_diagnostico,
            'observacao': avaliacao.observacao,
            'status_acao': avaliacao.status_acao,
            'responsavel': avaliacao.responsavel,
            'prazo': avaliacao.prazo,
            'resolucao_prevista': avaliacao.resolucao_prevista,
            'ordem_servico': avaliacao.ordem_servico,
            'data_os': avaliacao.data_os,
            'notas': avaliacao.notas,
        })
    return render(request, 'acessibilidade/editar.html', {'form': form, 'avaliacao': avaliacao})


@login_required
def editar_lote(request):
    if request.method != 'POST':
        return redirect('acessibilidade:lista')
    form = AvaliacaoEdicaoLoteForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Não foi possível aplicar a edição em lote: dados inválidos.')
        return redirect('acessibilidade:lista')
    avaliacoes = list(Avaliacao.objects.filter(pk__in=form.ids_list()))
    patch = form.patch()
    if not patch:
        messages.warning(request, 'Nenhum campo preenchido para aplicar em lote.')
        return redirect('acessibilidade:lista')
    aplicar_edicao_lote(avaliacoes, patch, request.user)
    messages.success(request, f'{len(avaliacoes)} avaliações atualizadas.')
    return redirect('acessibilidade:lista')


def _csv_seguro(valor):
    """Neutraliza injeção de fórmula CSV (OWASP): prefixa com aspas simples
    quando o valor começa com um caractere que Excel/LibreOffice interpretam
    como início de fórmula ou comando."""
    texto = str(valor or '')
    if texto[:1] in ('=', '+', '-', '@', '\t', '\r'):
        return "'" + texto
    return texto


@login_required
def exportar_csv(request):
    qs = _avaliacoes_filtradas(request)
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="acessibilidade.csv"'
    writer = csv.writer(response, delimiter=';')
    writer.writerow([
        'Edificação', 'Região', 'Local', 'Critério', 'Status', 'Resolução (diagnóstico)',
        'Status da ação', 'Responsável', 'Prazo', 'Resolução prevista',
        'Ordem de serviço', 'Data da OS', 'Notas', 'Observação',
        'Atualizado por', 'Atualizado em',
    ])
    for a in qs:
        writer.writerow([
            a.local.edificacao.nome, a.local.get_regiao_display(), a.local.nome, a.criterio.nome,
            a.get_status_display(), _csv_seguro(a.resolucao_diagnostico), a.get_status_acao_display(),
            _csv_seguro(a.responsavel), a.prazo.strftime('%d/%m/%Y') if a.prazo else '',
            _csv_seguro(a.resolucao_prevista), _csv_seguro(a.ordem_servico),
            a.data_os.strftime('%d/%m/%Y') if a.data_os else '',
            _csv_seguro(a.notas), _csv_seguro(a.observacao), a.atualizado_por.get_username(),
            a.atualizado_em.strftime('%d/%m/%Y %H:%M'),
        ])
    return response


@login_required
def alertas(request):
    hoje = timezone.localdate()
    qs = (
        Avaliacao.objects.select_related('local', 'local__edificacao', 'criterio')
        .filter(prazo__lt=hoje)
        .exclude(status_acao=Avaliacao.StatusAcao.CONCLUIDA)
        .order_by('prazo')
    )
    return render(request, 'acessibilidade/alertas.html', {'avaliacoes': qs, 'hoje': hoje})
