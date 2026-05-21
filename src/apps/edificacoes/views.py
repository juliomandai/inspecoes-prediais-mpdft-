from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from .models import Edificacao
from .forms import EdificacaoForm


@staff_member_required
def edificacao_list(request):
    edificacoes = Edificacao.objects.all()
    return render(request, 'edificacoes/list.html', {'edificacoes': edificacoes})


@staff_member_required
def edificacao_create(request):
    form = EdificacaoForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, 'Edificação cadastrada com sucesso.')
        return redirect('edificacoes:list')
    return render(request, 'edificacoes/form.html', {'form': form, 'titulo': 'Nova Edificação'})


@staff_member_required
def edificacao_update(request, pk):
    edificacao = get_object_or_404(Edificacao, pk=pk)
    form = EdificacaoForm(request.POST or None, instance=edificacao)
    if form.is_valid():
        form.save()
        messages.success(request, 'Edificação atualizada com sucesso.')
        return redirect('edificacoes:list')
    return render(request, 'edificacoes/form.html', {'form': form, 'titulo': f'Editar — {edificacao.nome}'})
