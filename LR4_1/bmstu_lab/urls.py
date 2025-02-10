from django.contrib import admin
from django.urls import path
from rest_framework import permissions
from сonsulting.views import (
    ServiceListView, ServiceDetailView, ServiceCreateView, ServiceUpdateView, ServiceDeleteView,
    AddServiceToDraftRequestView, AddImageToServiceView, UpdateServiceInRequestView, DeleteServiceFromRequestView,
    RequestListView, RequestDetailView, RequestUpdateView, RequestFormView, RequestCompleteOrRejectView, RequestDeleteView,
    UserUpdateView, login, LogoutView, UserViewSet,UpdateRequestFieldsView, UpdateConsultingRequestResultView,
)
from django.contrib import admin
from сonsulting import views
from rest_framework import permissions
from django.urls import path, include
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework import routers
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

schema_view = get_schema_view(
   openapi.Info(
      title="Snippets API",
      default_version='v1',
      description="Test description",
      terms_of_service="https://www.google.com/policies/terms/",
      contact=openapi.Contact(email="contact@snippets.local"),
      license=openapi.License(name="BSD License"),
   ),
   public=True,
   permission_classes=(permissions.AllowAny,),
)
router = routers.DefaultRouter()
router.register(r'user', views.UserViewSet, basename='user')

urlpatterns = [
    # Панель администратора
    path('admin/', admin.site.urls),
    # Методы услуг
    path('services/', ServiceListView.as_view(), name='service-list'),
    path('services/<int:pk>/', ServiceDetailView.as_view(), name='service-detail'),
    path('services/create/', ServiceCreateView.as_view(), name='service-create'),
    path('services/<int:pk>/update/', ServiceUpdateView.as_view(), name='service-update'),
    path('services/<int:pk>/delete/', ServiceDeleteView.as_view(), name='service-delete'),
    path('services/<int:pk>/add-to-draft/', AddServiceToDraftRequestView.as_view(), name='add-service-to-draft'),
    path('services/<int:service_id>/update-image/', AddImageToServiceView.as_view(), name='update-service-image'),

    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    # Методы заявок
    path('requests/', RequestListView.as_view(), name='request-list'),
    path('requests/<int:pk>/', RequestDetailView.as_view(), name='request-detail'),
    path('requests/<int:pk>/update/', RequestUpdateView.as_view(), name='request-update'),
    path('requests/<int:pk>/form/', RequestFormView.as_view(), name='request-form'),
    path('requests/<int:pk>/complete-or-reject/', RequestCompleteOrRejectView.as_view(), name='request-complete-or-reject'),
    path('requests/<int:pk>/delete/', RequestDeleteView.as_view(), name='request-delete'),
    path('requests/<int:pk>/update-fields/', UpdateRequestFieldsView.as_view(), name='request-update-fields'),
    # Методы м-м
    path('request-items/<int:request_id>/<int:service_id>/delete/', DeleteServiceFromRequestView.as_view(), name='delete-service-from-request'),
    path('request-items/<int:request_id>/<int:service_id>/update/', UpdateServiceInRequestView.as_view(), name='update-service-in-request'),

    # Методы пользователей
    path('api/users/update/', UserUpdateView.as_view(), name='user-update'),
    path('api/users/login/', login, name='user-login'),
    path('api/users/logout/', LogoutView.as_view(), name='user-logout'),

    #asinc
    path('requests/update_result/', UpdateConsultingRequestResultView.as_view(), name='update-request-result'),
]

urlpatterns += router.urls
#python manage.py runserver 192.168.0.18:8000