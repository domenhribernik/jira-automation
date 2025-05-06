"""
URL configuration for jira_automation project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from main_app import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path("logs/", views.view_logs, name="view_logs"),
    path('import-data/', views.import_data, name='import_data'),
    path('get-scheduled-tasks/', views.get_scheduled_tasks, name='get_scheduled_tasks'),   
    path('get-sub-tasks/<str:category>/', views.get_sub_tasks, name='get_sub_tasks'),
    path('run-task/<str:task_name>/', views.run_task, name='run_task'),
    path('schedule-task/<str:task_name>/', views.schedule_task, name='schedule_task'),
    path('send-email-early/', views.send_email_early, name='send_email_early'),
    path('delete-scheduled-task/<str:task_name>/', views.delete_scheduled_task, name='delete_scheduled_task'),
    path('test-send-email/', views.test_send_email, name='test_send_email'),
]
