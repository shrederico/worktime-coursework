from decimal import Decimal
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils import timezone


class Task(models.Model):
    class Status(models.TextChoices):
        TODO = 'todo', 'Новая'
        ACTIVE = 'active', 'В работе'
        DONE = 'done', 'Завершена'

    title = models.CharField('Название', max_length=160)
    description = models.TextField('Описание', blank=True)
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name='Исполнитель')
    status = models.CharField('Статус', max_length=10, choices=Status.choices, default=Status.TODO)
    deadline = models.DateField('Срок', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'задача'
        verbose_name_plural = 'задачи'

    def __str__(self):
        return self.title


class TimeEntry(models.Model):
    task = models.ForeignKey(Task, on_delete=models.PROTECT, related_name='entries', verbose_name='Задача')
    employee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name='Сотрудник')
    date = models.DateField('Дата', default=timezone.localdate)
    hours = models.DecimalField('Часы', max_digits=4, decimal_places=2,
                               validators=[MinValueValidator(Decimal('0.01')), MaxValueValidator(Decimal('24'))])
    comment = models.CharField('Что сделано', max_length=300)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name = 'запись времени'
        verbose_name_plural = 'записи времени'
        constraints = [models.CheckConstraint(condition=models.Q(hours__gt=0, hours__lte=24), name='valid_hours')]
