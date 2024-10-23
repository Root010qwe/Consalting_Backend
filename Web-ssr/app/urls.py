from django.urls import path
from .views import *

urlpatterns = [
    path('', index),
    path('services/<int:service_id>/', service),
    path('applications/<int:application_id>/', application),
]
