from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.utils import timezone
from .models import Task, TimeEntry


class WorkflowTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.manager = User.objects.create_user('manager', password='test-pass', is_staff=True)
        self.anna = User.objects.create_user('anna', password='test-pass')
        self.ivan = User.objects.create_user('ivan', password='test-pass')
        self.task = Task.objects.create(title='Задача Анны', assignee=self.anna)
        self.other = Task.objects.create(title='Задача Ивана', assignee=self.ivan)
        self.client.force_login(self.anna)

    def entry(self, **changes):
        data = {'task': self.task.pk, 'date': timezone.localdate(), 'hours': '2.50', 'comment': 'Работа выполнена'}
        data.update(changes)
        return self.client.post('/time/', data)

    def test_login_required(self):
        self.client.logout()
        self.assertRedirects(self.client.get('/'), '/login/?next=/')

    def test_employee_only_sees_own_tasks(self):
        self.assertContains(self.client.get('/'), self.task.title)
        self.assertNotContains(self.client.get('/'), self.other.title)
        self.assertEqual(self.client.get(f'/tasks/{self.other.pk}/').status_code, 404)

    def test_employee_cannot_create_task(self):
        self.assertEqual(self.client.post('/tasks/new/', {'title': 'X', 'assignee': self.anna.pk}).status_code, 403)

    def test_manager_creates_and_assigns_task(self):
        self.client.force_login(self.manager)
        response = self.client.post('/tasks/new/', {'title': 'Новая', 'description': '', 'assignee': self.ivan.pk, 'deadline': ''})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Task.objects.filter(title='Новая', assignee=self.ivan).exists())

    def test_status_update_and_invalid_status(self):
        self.client.post(f'/tasks/{self.task.pk}/', {'status': 'done'})
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, 'done')
        self.assertEqual(self.client.post(f'/tasks/{self.task.pk}/', {'status': 'invalid'}).status_code, 400)
        self.assertEqual(self.client.post(f'/tasks/{self.other.pk}/', {'status': 'done'}).status_code, 404)

    def test_valid_time_and_report(self):
        self.assertRedirects(self.entry(), '/report/')
        self.assertEqual(str(TimeEntry.objects.get().hours), '2.50')
        self.assertContains(self.client.get('/report/'), 'Работа выполнена')

    def test_time_form_has_browser_compatible_default_date(self):
        response = self.client.get('/time/')
        self.assertContains(response, f'value="{timezone.localdate().isoformat()}"')

    def test_cannot_log_for_other_employee(self):
        self.entry(task=self.other.pk)
        self.assertEqual(TimeEntry.objects.count(), 0)

    def test_invalid_hours_and_future_date(self):
        for value in ['0', '-1', '24.01', 'abc']:
            self.entry(hours=value)
        self.entry(date=timezone.localdate() + timedelta(days=1))
        self.assertEqual(TimeEntry.objects.count(), 0)

    def test_daily_total_limit(self):
        self.entry(hours='23')
        response = self.entry(hours='2')
        self.assertContains(response, 'не может превышать 24')
        self.assertEqual(TimeEntry.objects.count(), 1)

    def test_report_period_and_access(self):
        self.entry()
        yesterday = timezone.localdate() - timedelta(days=1)
        self.assertNotContains(self.client.get('/report/', {'end': yesterday}), 'Работа выполнена')
        self.client.force_login(self.ivan)
        self.assertNotContains(self.client.get('/report/'), 'Работа выполнена')
        self.client.force_login(self.manager)
        self.assertContains(self.client.get('/report/'), 'Работа выполнена')

    def test_invalid_period(self):
        response = self.client.get('/report/', {'start': '2026-12-01', 'end': '2026-01-01'})
        self.assertContains(response, 'Начало периода')

    def test_csv_formula_is_escaped(self):
        self.entry(comment='=1+1')
        response = self.client.get('/report/?export=csv')
        self.assertIn("'=1+1", response.content.decode('utf-8-sig'))

    def test_csrf_required(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.anna)
        self.assertEqual(client.post(f'/tasks/{self.task.pk}/', {'status': 'done'}).status_code, 403)

    def test_health_and_metrics(self):
        self.assertEqual(self.client.get('/health/').json(), {'status': 'ok'})
        self.assertContains(self.client.get('/metrics/'), 'worktime_tasks')
