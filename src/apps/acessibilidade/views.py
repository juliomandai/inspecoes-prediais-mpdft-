from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render

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
