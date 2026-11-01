from django.contrib import admin
from .models import Task, TimeEntry

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['title', 'assignee', 'status', 'deadline']
    list_filter = ['status']

@admin.register(TimeEntry)
class TimeEntryAdmin(admin.ModelAdmin):
    list_display = ['date', 'employee', 'task', 'hours']
    readonly_fields = ['task', 'employee', 'date', 'hours', 'comment', 'created_at']

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
