from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from .models import Edificacao, Profissional
from .forms import EdificacaoForm, ProfissionalForm


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


@staff_member_required
def profissional_list(request):
    profissionais = Profissional.objects.all()
    return render(request, 'edificacoes/profissional_list.html', {'profissionais': profissionais})


@staff_member_required
def profissional_create(request):
    form = ProfissionalForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, 'Profissional cadastrado com sucesso.')
        return redirect('edificacoes:profissional_list')
    return render(request, 'edificacoes/profissional_form.html', {'form': form, 'titulo': 'Novo Profissional'})


@staff_member_required
def profissional_update(request, pk):
    profissional = get_object_or_404(Profissional, pk=pk)
    form = ProfissionalForm(request.POST or None, instance=profissional)
    if form.is_valid():
        form.save()
        messages.success(request, 'Profissional atualizado com sucesso.')
        return redirect('edificacoes:profissional_list')
    return render(request, 'edificacoes/profissional_form.html', {'form': form, 'titulo': f'Editar — {profissional.nome}'})
