from django.contrib import admin
from django.urls import path
from сonsulting.views import (
    ServiceListView, ServiceDetailView, ServiceCreateView, ServiceUpdateView, ServiceDeleteView,
    AddServiceToDraftRequestView, AddImageToServiceView, UpdateServiceInRequestView, DeleteServiceFromRequestView,
    RequestListView, RequestDetailView, RequestUpdateView, RequestFormView, RequestCompleteOrRejectView, RequestDeleteView,
    UserRegisterView, UserUpdateView, LoginView, LogoutView,
)

urlpatterns = [
    # Панель администратора
    path('admin/', admin.site.urls),

    # Методы услуг
    path('api/services/', ServiceListView.as_view(), name='service-list'),
    path('api/services/<int:pk>/', ServiceDetailView.as_view(), name='service-detail'),
    path('api/services/create/', ServiceCreateView.as_view(), name='service-create'),
    path('api/services/<int:pk>/update/', ServiceUpdateView.as_view(), name='service-update'),
    path('api/services/<int:pk>/delete/', ServiceDeleteView.as_view(), name='service-delete'),
    path('api/services/<int:pk>/add-to-draft/', AddServiceToDraftRequestView.as_view(), name='add-service-to-draft'),
    path('api/services/<int:service_id>/update-image/', AddImageToServiceView.as_view(), name='update-service-image'),

    # Методы заявок
    path('api/requests/', RequestListView.as_view(), name='request-list'),
    path('api/requests/<int:pk>/', RequestDetailView.as_view(), name='request-detail'),
    path('api/requests/<int:pk>/update/', RequestUpdateView.as_view(), name='request-update'),
    path('api/requests/<int:pk>/form/', RequestFormView.as_view(), name='request-form'),
    path('api/requests/<int:pk>/complete-or-reject/', RequestCompleteOrRejectView.as_view(), name='request-complete-or-reject'),
    path('api/requests/<int:pk>/delete/', RequestDeleteView.as_view(), name='request-delete'),

    # Методы м-м
    path('api/request-items/<int:request_id>/<int:service_id>/delete/', DeleteServiceFromRequestView.as_view(), name='delete-service-from-request'),
    path('api/request-items/<int:request_id>/<int:service_id>/update/', UpdateServiceInRequestView.as_view(), name='update-service-in-request'),

    # Методы пользователей
    path('api/users/register/', UserRegisterView.as_view(), name='user-register'),
    path('api/users/update/', UserUpdateView.as_view(), name='user-update'),
    path('api/users/login/', LoginView.as_view(), name='user-login'),
    path('api/users/logout/', LogoutView.as_view(), name='user-logout'),
]
