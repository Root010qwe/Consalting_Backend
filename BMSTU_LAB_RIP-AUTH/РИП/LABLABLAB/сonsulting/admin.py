from django.contrib import admin
from .models import ConsultingService, ConsultingRequest, ServiceRequest

class ConsultingServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "status", "price", "duration", "image_url")
    search_fields = ("name", "status")
    list_filter = ("status",)
    ordering = ("name",)

class RequestServiceInline(admin.TabularInline):
    model = ServiceRequest
    extra = 1  # Количество пустых строк для добавления новых записей в админке

class ConsultingRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "client_name", "status", "creation_date", "manager")
    search_fields = ("client_name", "status")
    list_filter = ("status", "creation_date")
    ordering = ("-creation_date",)
    inlines = [RequestServiceInline]  # Добавление RequestService как встроенной таблицы

admin.site.register(ConsultingService, ConsultingServiceAdmin)
admin.site.register(ConsultingRequest, ConsultingRequestAdmin)
