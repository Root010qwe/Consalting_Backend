from django.db import models


from django.contrib.auth.models import (
    AbstractBaseUser,
    UserManager,
    PermissionsMixin,
)


class NewUserManager(UserManager):
    def create_user(self, username, password=None, **extra_fields):
        if not username:
            raise ValueError("User must have an username")

        user = self.model(username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self.db)

        return user

    def create_superuser(self, username, password=None, **extra_fields):
        user = self.model(username=username, **extra_fields)
        user.set_password(password)
        user.is_superuser = True
        user.save(using=self.db)

        return user


class CustomUser(AbstractBaseUser, PermissionsMixin):
    username = models.CharField(verbose_name=("Username"), unique=True, max_length=50)
    password = models.CharField(verbose_name="Password")
    is_staff = models.BooleanField(
        default=False, verbose_name="Является ли пользователь менеджером?"
    )
    is_superuser = models.BooleanField(
        default=False, verbose_name="Является ли пользователь админом?"
    )

    USERNAME_FIELD = "username"

    objects = NewUserManager()

# class UserSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = CustomUser
#         fields = [
#             "username",
#             "password",
#         ]
#         extra_kwargs = {
#             "username": {"required": True},
#             "password": {"write_only": True},
#         }
#
#     def update(self, instance, validated_data):
#         if "password" in validated_data:
#             password = validated_data.pop("password")
#             instance.set_password(password)  # Use set_password for hashing
#
#         return super().update(instance, validated_data)

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
        indexes = [
            models.Index(fields=['name'], name='service_name_idx'),
            models.Index(fields=['status'], name='service_status_idx'),
        ]


class ConsultingRequest(models.Model):
    STATUS_CHOICES = [
        ("Draft", "Draft"),
        ("Submitted", "Submitted"),
        ("Completed", "Completed"),
        ("Rejected", "Rejected"),
        ("Deleted", "Deleted"),
    ]

    PRIORITY_CHOICES = [
        ("Low", "Low"),
        ("Medium", "Medium"),
        ("High", "High"),
    ]

    status = models.CharField(max_length=9, choices=STATUS_CHOICES, default="Draft")
    priority_level = models.CharField(
        max_length=6, choices=PRIORITY_CHOICES, default="Medium"
    )  # Уровень приоритета
    formed_date = models.DateTimeField(null=True, blank=True)  # Дата оформления
    contact_phone = models.CharField(
        max_length=15, null=True, blank=True, help_text="Контактный номер телефона"
    )  # Контактный телефон

    creation_date = models.DateTimeField(auto_now_add=True)  # Дата создания
    completion_date = models.DateTimeField(null=True, blank=True)  # Дата завершения
    manager = models.ForeignKey(
        CustomUser, related_name="managed_requests", on_delete=models.SET_NULL, null=True
    )
    client = models.ForeignKey(
        CustomUser, on_delete=models.PROTECT, related_name="sender"
    )
    total_cost = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )  # Итоговая стоимость
    qr = models.TextField(null=True, blank=True)
    class Meta:
        db_table = "consulting_requests"



# Промежуточная модель для связи М-М
class ServiceRequest(models.Model):
    request = models.ForeignKey(ConsultingRequest, on_delete=models.CASCADE, related_name="service_requests")
    client_email = models.EmailField(blank=True, null=True, default="")  # Email клиента
    service = models.ForeignKey(ConsultingService, on_delete=models.CASCADE, related_name="service_requests")
    quantity = models.PositiveIntegerField(default=1)
    comment = models.TextField(blank=True, null=True, default="")  # Добавлено поле для комментариев

    class Meta:
        db_table = "service_requests"
        unique_together = ("request", "service")  # Уникальность по заявке и услуге
