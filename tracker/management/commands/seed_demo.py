import os
from decimal import Decimal
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from tracker.models import Task, TimeEntry


class Command(BaseCommand):
    help = 'Создать учебных пользователей и примеры задач (существующие данные не удаляются).'

    @transaction.atomic
    def handle(self, *args, **options):
        password = os.getenv('DEMO_PASSWORD')
        if not password or len(password) < 12:
            raise CommandError('Задайте DEMO_PASSWORD длиной не менее 12 символов.')
        users = {}
        for login, first, last, staff in [('manager', 'Арсений', 'Доббнев', True),
                                           ('anna', 'Анна', 'Соколова', False), ('ivan', 'Иван', 'Петров', False)]:
            user, created = get_user_model().objects.get_or_create(username=login,
                defaults={'first_name': first, 'last_name': last, 'is_staff': staff, 'is_superuser': staff})
            if created:
                user.set_password(password)
                user.save()
            users[login] = user
        today = timezone.localdate()
        examples = [
            ('Подготовить макет страницы задач', 'anna', 'active', 2, 'Продумать список задач и форму записи рабочего времени.', '2.50'),
            ('Проверить сохранение рабочих часов', 'ivan', 'todo', 3, 'Проверить запись времени и сохранность данных после перезапуска.', '0'),
            ('Описать роли пользователей', 'anna', 'done', 0, 'Разделить возможности руководителя и сотрудника.', '1.75'),
            ('Подготовить план демонстрации', 'manager', 'active', 5, 'Составить последовательность действий для показа платформы.', '1.00'),
            ('Проверить выгрузку отчёта', 'ivan', 'active', -1, 'Открыть CSV и сверить сумму часов с отчётом в браузере.', '3.00'),
        ]
        for title, login, status, days, description, hours in examples:
            task, created = Task.objects.get_or_create(title=title, assignee=users[login],
                defaults={'description': description, 'status': status, 'deadline': today + timedelta(days=days)})
            if created and Decimal(hours):
                TimeEntry.objects.create(task=task, employee=users[login], date=today,
                    hours=Decimal(hours), comment='Учебная запись для демонстрации интерфейса')
        self.stdout.write(self.style.SUCCESS('Готово: manager, anna, ivan. Пароль взят из DEMO_PASSWORD.'))
