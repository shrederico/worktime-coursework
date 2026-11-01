import csv
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import connection, transaction
from django.db.models import Sum
from django.http import HttpResponse, JsonResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from prometheus_client import CollectorRegistry, Gauge, generate_latest, CONTENT_TYPE_LATEST
from .forms import TaskForm, TimeForm, PeriodForm
from .models import Task, TimeEntry


def visible_tasks(user):
    tasks = Task.objects.select_related('assignee')
    return tasks if user.is_staff else tasks.filter(assignee=user)


def visible_entries(user):
    entries = TimeEntry.objects.select_related('employee', 'task')
    return entries if user.is_staff else entries.filter(employee=user)


@login_required
def dashboard(request):
    tasks = visible_tasks(request.user)
    status = request.GET.get('status', '')
    shown = tasks.filter(status=status) if status in Task.Status.values else tasks
    today = timezone.localdate()
    week = today - timezone.timedelta(days=today.weekday())
    hours = visible_entries(request.user).filter(date__gte=week, date__lte=today).aggregate(total=Sum('hours'))['total'] or 0
    return render(request, 'dashboard.html', {
        'tasks': shown.annotate(total_hours=Sum('entries__hours')), 'status': status,
        'statuses': Task.Status.choices, 'active': tasks.exclude(status='done').count(),
        'done': tasks.filter(status='done').count(), 'hours': hours,
        'overdue': tasks.filter(deadline__lt=today).exclude(status='done').count(),
        'recent': visible_entries(request.user)[:5],
    })


@login_required
def task_create(request):
    if not request.user.is_staff:
        return HttpResponseForbidden('Создавать задачи может руководитель.')
    form = TaskForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        task = form.save()
        messages.success(request, 'Задача создана.')
        return redirect('task_detail', pk=task.pk)
    return render(request, 'form.html', {'form': form, 'title': 'Новая задача', 'subtitle': 'Назначьте исполнителя и укажите срок.'})


@login_required
def task_detail(request, pk):
    task = get_object_or_404(visible_tasks(request.user), pk=pk)
    if request.method == 'POST':
        status = request.POST.get('status')
        if status not in Task.Status.values:
            return HttpResponse('Неизвестный статус', status=400)
        task.status = status
        task.save(update_fields=['status'])
        messages.success(request, 'Статус обновлён.')
        return redirect('task_detail', pk=pk)
    return render(request, 'task.html', {'task': task, 'statuses': Task.Status.choices,
                  'entries': task.entries.select_related('employee'),
                  'total': task.entries.aggregate(total=Sum('hours'))['total'] or 0})


@login_required
def time_create(request):
    form = TimeForm(request.POST or None, user=request.user, initial={'task': request.GET.get('task'), 'date': timezone.localdate()})
    if request.method == 'POST' and form.is_valid():
        # Блокируем строку сотрудника: два одновременных запроса не должны превысить 24 часа за день.
        with transaction.atomic():
            get_user_model().objects.select_for_update().get(pk=request.user.pk)
            used = TimeEntry.objects.filter(employee=request.user, date=form.cleaned_data['date']).aggregate(total=Sum('hours'))['total'] or Decimal('0')
            if used + form.cleaned_data['hours'] > 24:
                form.add_error('hours', 'Суммарное время за сутки не может превышать 24 часа.')
            else:
                entry = form.save(commit=False)
                entry.employee = request.user
                entry.save()
                messages.success(request, 'Рабочее время записано.')
                return redirect('report')
    return render(request, 'form.html', {'form': form, 'title': 'Записать время', 'subtitle': 'Укажите задачу, дату и фактически затраченные часы.'})


@login_required
def report(request):
    form = PeriodForm(request.GET)
    entries = visible_entries(request.user)
    valid = form.is_valid()
    if valid:
        if form.cleaned_data['start']:
            entries = entries.filter(date__gte=form.cleaned_data['start'])
        if form.cleaned_data['end']:
            entries = entries.filter(date__lte=form.cleaned_data['end'])
    else:
        entries = entries.none()
    if request.GET.get('export') == 'csv' and valid:
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="worktime.csv"'
        response.write('\ufeff')
        writer = csv.writer(response, delimiter=';')
        writer.writerow(['Дата', 'Сотрудник', 'Задача', 'Часы', 'Комментарий'])
        for entry in entries:
            # Не позволяем пользовательскому тексту превратиться в формулу Excel.
            cells = [str(entry.date), entry.employee.username, entry.task.title, str(entry.hours), entry.comment]
            writer.writerow(["'" + cell if cell.startswith(('=', '+', '-', '@', '\t', '\r')) else cell for cell in cells])
        return response
    return render(request, 'report.html', {'form': form, 'entries': entries,
                  'total': entries.aggregate(total=Sum('hours'))['total'] or 0,
                  'summary': entries.order_by().values('employee__username').annotate(hours=Sum('hours')).order_by('employee__username')})


def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
    except Exception:
        return JsonResponse({'status': 'unavailable'}, status=503)
    return JsonResponse({'status': 'ok'})


def metrics(request):
    registry = CollectorRegistry()
    tasks = Gauge('worktime_tasks', 'Number of tasks by status', ['status'], registry=registry)
    for status in Task.Status.values:
        tasks.labels(status=status).set(Task.objects.filter(status=status).count())
    Gauge('worktime_hours_total', 'Total recorded hours', registry=registry).set(TimeEntry.objects.aggregate(total=Sum('hours'))['total'] or 0)
    return HttpResponse(generate_latest(registry), content_type=CONTENT_TYPE_LATEST)
