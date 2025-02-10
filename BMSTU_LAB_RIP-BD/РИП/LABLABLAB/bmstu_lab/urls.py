"""bmstu_lab URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.2/topics/http/urls/
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
from сonsulting import views
from django.contrib import admin
from django.urls import path


from django.urls import path
from сonsulting import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.services_page, name='services_page'),
    path('description/<int:id>/', views.description, name='description'),
    path('add-to-request/<int:service_id>/', views.add_service_to_request, name='add_service_to_request'),
    path('report/<int:id>/', views.report_info, name='report_info'),
    path('complete-request/<int:id>/', views.complete_request, name='complete_request'),
    path('delete-service/<int:service_request_id>/', views.delete_service_from_request,name='delete_service_from_request'),
    path('delete-report/<int:report_id>/', views.delete_report, name='delete_report'),
    path('delete-request/<int:request_id>/', views.delete_request, name='delete_request'),
    path('all-requests/', views.all_requests, name='all_requests'),
]

