from django import forms
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import Task, TimeEntry


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ['title', 'description', 'assignee', 'deadline']
        widgets = {'deadline': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}), 'description': forms.Textarea(attrs={'rows': 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['assignee'].queryset = get_user_model().objects.filter(is_active=True).order_by('username')


class TimeForm(forms.ModelForm):
    class Meta:
        model = TimeEntry
        fields = ['task', 'date', 'hours', 'comment']
        widgets = {'date': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
                   'hours': forms.NumberInput(attrs={'step': '0.01', 'min': '0.01', 'max': '24'})}

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['task'].queryset = Task.objects.filter(assignee=user)

    def clean_date(self):
        day = self.cleaned_data['date']
        if day > timezone.localdate():
            raise forms.ValidationError('Нельзя записать отработанное время на будущую дату.')
        return day


class PeriodForm(forms.Form):
    start = forms.DateField(label='С', required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    end = forms.DateField(label='По', required=False, widget=forms.DateInput(attrs={'type': 'date'}))

    def clean(self):
        values = super().clean()
        if values.get('start') and values.get('end') and values['start'] > values['end']:
            raise forms.ValidationError('Начало периода не может быть позже окончания.')
        return values
