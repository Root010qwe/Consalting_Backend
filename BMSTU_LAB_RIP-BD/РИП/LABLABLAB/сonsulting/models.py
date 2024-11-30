from django.db import models
from django.contrib.auth.models import User


class ConsultingService(models.Model):
    STATUS_CHOICES = [
        ("A", "Active"),
        ("D", "Deleted"),
    ]
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=1, choices=STATUS_CHOICES, default="A")
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration = models.PositiveIntegerField(help_text="Длительность в часах", null=True, blank=True)
    image_url = models.URLField(blank=True, null=True, help_text="Ссылка на изображение услуги")

    class Meta:
        db_table = "consulting_services"


class ConsultingRequest(models.Model):
    STATUS_CHOICES = [
        ("Draft", "Draft"),
        ("Submitted", "Submitted"),
        ("Completed", "Completed"),
        ("Rejected", "Rejected"),
    ]
    client_name = models.CharField(max_length=100)  # Имя клиента
    client_email = models.EmailField(blank=True, null=True, default="")  # Email клиента
    status = models.CharField(max_length=9, choices=STATUS_CHOICES, default="Draft")
    creation_date = models.DateTimeField(auto_now_add=True)  # Дата создания
    completion_date = models.DateTimeField(null=True, blank=True)  # Дата завершения
    manager = models.ForeignKey(User, related_name="managed_requests", on_delete=models.SET_NULL, null=True)

    class Meta:
        db_table = "consulting_requests"


# Промежуточная модель для связи М-М
class ServiceRequest(models.Model):
    request = models.ForeignKey(ConsultingRequest, on_delete=models.CASCADE, related_name="service_requests")
    service = models.ForeignKey(ConsultingService, on_delete=models.CASCADE, related_name="service_requests")
    quantity = models.PositiveIntegerField(default=1)
    comment = models.TextField(blank=True, null=True, default="")  # Добавлено поле для комментариев

    class Meta:
        db_table = "service_requests"
        unique_together = ("request", "service")  # Уникальность по заявке и услуге
