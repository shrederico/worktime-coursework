from django.contrib import admin
from django.contrib.auth import views as auth
from django.urls import path
from tracker import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', auth.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', auth.LogoutView.as_view(), name='logout'),
    path('', views.dashboard, name='dashboard'),
    path('tasks/new/', views.task_create, name='task_create'),
    path('tasks/<int:pk>/', views.task_detail, name='task_detail'),
    path('time/', views.time_create, name='time_create'),
    path('report/', views.report, name='report'),
    path('health/', views.health),
    path('metrics/', views.metrics),
]
