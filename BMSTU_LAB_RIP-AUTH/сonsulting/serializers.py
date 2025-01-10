from rest_framework import serializers
from .models import ConsultingService, ConsultingRequest, ServiceRequest, CustomUser
from django.contrib.auth.models import User


class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConsultingService
        fields = ['id', 'name', 'description', 'status', 'price', 'duration', 'image_url']


class RequestSerializer(serializers.ModelSerializer):
    manager_username = serializers.CharField(source='manager.username', read_only=True)

    class Meta:
        model = ConsultingRequest
        fields = [
            'id',
            'client',
            'status',
            'creation_date',
            'completion_date',
            'manager_username',
            'total_cost',
        ]

class ServiceRequestSerializer(serializers.ModelSerializer):
    service = ServiceSerializer(read_only=True)

    class Meta:
        model = ServiceRequest
        fields = ['id', 'service', 'comment']




class RequestDetailSerializer(serializers.ModelSerializer):
    service_requests = ServiceRequestSerializer(many=True, read_only=True)

    class Meta:
        model = ConsultingRequest
        fields = ['id', 'client', 'manager', 'status', 'creation_date', 'completion_date', 'service_requests',  'total_cost']

    def to_representation(self, instance):
        repr = super().to_representation(instance)
        repr["client"] = CustomUser.objects.get(id=repr["client"]).username
        if repr["manager"]:
            repr["manager"] = CustomUser.objects.get(id=repr["manager"]).username

        return repr

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = [
            "username",
            "password",
        ]
        extra_kwargs = {
            "username": {"required": True},
            "password": {"write_only": True},
        }


    def update(self, instance, validated_data):
        if "password" in validated_data:
            password = validated_data.pop("password")
            instance.set_password(password)  # Use set_password for hashing

        return super().update(instance, validated_data)


# class UserSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = User
#         fields = ['id', 'username', 'email', 'password']
#         extra_kwargs = {
#             'password': {'write_only': True},  # Пароль не будет возвращаться в ответе
#         }
#
#     def create(self, validated_data):
#         user = User(**validated_data)
#         user.set_password(validated_data['password'])  # Хешируем пароль перед сохранением
#         user.save()
#         return user


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)
