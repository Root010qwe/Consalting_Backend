from django.contrib.auth import get_user_model
User = get_user_model()
u = User.objects.get(username="admin")
print(u.is_staff, u.is_active, u.is_superuser)