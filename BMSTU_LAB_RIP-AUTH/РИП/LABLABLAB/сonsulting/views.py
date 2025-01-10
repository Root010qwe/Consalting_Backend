from sqlite3 import IntegrityError

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

from . import models
from .models import ConsultingService, ConsultingRequest, ServiceRequest
from .serializers import (
    ServiceSerializer, RequestSerializer, RequestDetailSerializer, ServiceRequestSerializer, UserSerializer,
    LoginSerializer
)
from minio import Minio
from django.db.models import Q
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from datetime import datetime
from django.utils.timezone import now
from minio.error import S3Error
from rest_framework.permissions import IsAuthenticated
from rest_framework.permissions import AllowAny
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.db.models import Sum, F



minio_client = Minio(
    'localhost:9000',  # Укажите MinIO endpoint
    access_key='minio',  # Ваш MinIO login
    secret_key='minio124',  # Ваш MinIO password
    secure=False  # Измените на True, если MinIO настроен на HTTPS
)
BUCKET_NAME = 'images'


class ObjectDoesNotExist:
    pass


class UserSingleton:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            try:
                cls._instance = User.objects.get(id=1)
            except ObjectDoesNotExist:
                cls._instance = None
        return cls._instance

# Методы услуг
class ServiceListView(APIView):
    permission_classes = [AllowAny]  # Только авторизованные пользователи

    def get(self, request):
        user = UserSingleton.get_instance()
        # Получаем значение параметра name из запроса
        name_filter = request.query_params.get('name', None)

        # Базовый запрос для получения всех активных услуг
        services = ConsultingService.objects.filter(status="A")

        # Если передан параметр name, добавляем фильтр
        if name_filter:
            services = services.filter(name__icontains=name_filter)

        # Получаем черновую заявку текущего пользователя
        draft_request = ConsultingRequest.objects.filter(
            status="Draft", manager=user
        ).first()

        # Формируем ответ с аннотацией о количестве услуг в черновой заявке
        response_data = {
            "draft_request_id": draft_request.id if draft_request else None,
            "services_in_draft_request": (
                ServiceRequest.objects.filter(request=draft_request).count()
                if draft_request
                else 0
            ),
            "services": ServiceSerializer(services, many=True).data,
        }

        return Response(response_data, status=status.HTTP_200_OK)



class ServiceDetailView(APIView):
    def get(self, request, pk):
        service = get_object_or_404(ConsultingService, pk=pk)
        return Response(ServiceSerializer(service).data)


class ServiceCreateView(APIView):
    def post(self, request):
        user = UserSingleton.get_instance()
        serializer = ServiceSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()  # Поле `manager` убрано, т.к. оно отсутствует в модели
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



class ServiceUpdateView(APIView):
    def put(self, request, pk):
        service = get_object_or_404(ConsultingService, pk=pk)
        serializer = ServiceSerializer(service, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ServiceDeleteView(APIView):
    def delete(self, request, pk):
        service = get_object_or_404(ConsultingService, pk=pk)
        service.status = "D"
        service.save()
        return Response({"message": "Service deleted"}, status=status.HTTP_204_NO_CONTENT)


class AddServiceToDraftRequestView(APIView):
    def post(self, request, pk):
        user = UserSingleton.get_instance()
        service = get_object_or_404(ConsultingService, pk=pk)
        draft_request, created = ConsultingRequest.objects.get_or_create(
            status="Draft", manager=user, defaults={"client_name": "Guest"}
        )
        service_request, created = ServiceRequest.objects.get_or_create(
            request=draft_request, service=service
        )
        if not created:
            service_request.quantity += 1
            service_request.save()
        return Response(ServiceRequestSerializer(service_request).data)


class AddImageToServiceView(APIView):
    def post(self, request, service_id):
        # Получаем услугу по ID
        service = get_object_or_404(ConsultingService, id=service_id)

        # Проверяем, что изображение было загружено
        uploaded_file = request.FILES.get('image')
        if not uploaded_file:
            return Response({"detail": "Файл не загружен."}, status=status.HTTP_400_BAD_REQUEST)

        # Удаляем предыдущее изображение, если оно существует
        if service.image_url:
            try:
                minio_client.remove_object(BUCKET_NAME, service.image_url.split('/')[-1])
            except S3Error as e:
                return Response({"detail": f"Ошибка удаления старого изображения: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Формируем имя файла
        file_name = f"{service.id}_{uploaded_file.name}"
        try:
            # Загружаем новое изображение в MinIO
            minio_client.put_object(
                bucket_name=BUCKET_NAME,
                object_name=file_name,
                data=uploaded_file.file,
                length=uploaded_file.size,
                content_type=uploaded_file.content_type
            )
        except S3Error as e:
            return Response({"detail": f"Ошибка загрузки изображения: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Сохраняем URL нового изображения
        service.image_url = f"http://localhost:9000/{BUCKET_NAME}/{file_name}"
        service.save()

        return Response({
            "detail": "Изображение успешно загружено.",
            "image_url": service.image_url
        }, status=status.HTTP_200_OK)


# Методы заявок
class RequestListView(APIView):
    def get(self, request):
        user = UserSingleton.get_instance()
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        status_filter = request.query_params.get('status')

        requests = ConsultingRequest.objects.exclude(status__in=["Deleted", "Draft"]).filter(manager=user)

        if start_date:
            requests = requests.filter(creation_date__gte=start_date)
        if end_date:
            requests = requests.filter(creation_date__lte=end_date)
        if status_filter:
            requests = requests.filter(status=status_filter)

        return Response(RequestSerializer(requests, many=True).data)



class RequestDetailView(APIView):
    def get(self, request, pk):
        consulting_request = get_object_or_404(ConsultingRequest, pk=pk)
        return Response(RequestDetailSerializer(consulting_request).data)


class RequestUpdateView(APIView):
    def put(self, request, pk):
        consulting_request = get_object_or_404(ConsultingRequest, pk=pk)
        serializer = RequestSerializer(consulting_request, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


from django.utils.timezone import now


class RequestFormView(APIView):
    def put(self, request, pk):
        user = UserSingleton.get_instance()
        consulting_request = get_object_or_404(ConsultingRequest, pk=pk, manager=user)

        if consulting_request.status != "Draft":
            return Response(
                {"error": "Only draft requests can be formed."},
                status=status.HTTP_405_METHOD_NOT_ALLOWED
            )

        if not consulting_request.client_name:
            return Response(
                {"error": "Client name is required to form the request."},
                status=status.HTTP_400_BAD_REQUEST
            )

        consulting_request.status = "Submitted"
        consulting_request.creation_date = now()
        consulting_request.save()

        return Response(
            {
                "message": "Request successfully submitted.",
                "status": consulting_request.status,
                "submission_date": consulting_request.creation_date
            },
            status=status.HTTP_200_OK
        )



class RequestCompleteOrRejectView(APIView):
    def put(self, request, pk):
        user = UserSingleton.get_instance()
        consulting_request = get_object_or_404(ConsultingRequest, pk=pk, manager=user)

        status_value = request.data.get('status')
        if status_value not in ["Completed", "Rejected"]:
            return Response(
                {"error": "Invalid status. Allowed values are 'Completed' or 'Rejected'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if consulting_request.status != "Submitted":
            return Response(
                {"error": "Only requests with 'Submitted' status can be completed or rejected."},
                status=status.HTTP_405_METHOD_NOT_ALLOWED
            )

        if status_value == "Completed":
            total_cost = ServiceRequest.objects.filter(request=consulting_request).aggregate(
                total=Sum(F('service__price') * F('quantity'))
            )['total'] or 0
            consulting_request.total_cost = total_cost

        consulting_request.status = status_value
        consulting_request.completion_date = now()
        consulting_request.save()

        return Response(
            {
                "message": f"Request successfully {status_value.lower()}.",
                "status": consulting_request.status,
                "completion_date": consulting_request.completion_date,
                "total_cost": consulting_request.total_cost
            },
            status=status.HTTP_200_OK
        )



class RequestDeleteView(APIView):
    def delete(self, request, pk):
        user = UserSingleton.get_instance()
        consulting_request = get_object_or_404(ConsultingRequest, pk=pk, manager=user)

        if consulting_request.status != "Draft":
            return Response(
                {"error": "Only draft requests can be deleted."},
                status=status.HTTP_405_METHOD_NOT_ALLOWED
            )

        consulting_request.status = "Deleted"
        consulting_request.save()

        return Response(
            {
                "id": consulting_request.id,
                "status": consulting_request.status,
                "message": "Request successfully deleted."
            },
            status=status.HTTP_200_OK
        )



# Методы пользователей


# POST регистрация пользователя
@method_decorator(csrf_exempt, name='dispatch')
class UserRegisterView(APIView):
    permission_classes = [AllowAny]  # Разрешаем доступ для всех

    def post(self, request, *args, **kwargs):
        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            try:
                user = serializer.save()
                return Response({'message': 'User registered successfully'}, status=status.HTTP_201_CREATED)
            except IntegrityError:
                return Response({'error': 'Username already exists'}, status=status.HTTP_409_CONFLICT)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# PUT обновление данных пользователя
@method_decorator(csrf_exempt, name='dispatch')
class UserUpdateView(APIView):
    permission_classes = [IsAuthenticated]  # Только для авторизованных пользователей

    def put(self, request, *args, **kwargs):
        user = UserSingleton.get_instance()  # Получаем текущего пользователя
        serializer = UserSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            try:
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            except IntegrityError:
                return Response({'error': 'Username already exists'}, status=status.HTTP_409_CONFLICT)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# POST аутентификация
@method_decorator(csrf_exempt, name='dispatch')
class LoginView(APIView):
    permission_classes = [AllowAny]  # Разрешаем доступ для всех

    def post(self, request, *args, **kwargs):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            username = serializer.validated_data['username']
            password = serializer.validated_data['password']
            user = authenticate(username=username, password=password)
            if user:
                login(request, user)
                return Response({'message': 'User authenticated successfully'}, status=status.HTTP_200_OK)
            return Response({'error': 'Invalid data'}, status=status.HTTP_401_UNAUTHORIZED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# POST деавторизация


@method_decorator(csrf_exempt, name='dispatch')
class LogoutView(APIView):
    permission_classes = [IsAuthenticated]  # Только для авторизованных пользователей

    def post(self, request, *args, **kwargs):
        logout(request)
        return Response({'message': 'User logged out successfully'}, status=status.HTTP_200_OK)



class UpdateServiceInRequestView(APIView):
    def put(self, request, request_id, service_id):
        # Получаем объект ServiceRequest
        service_request = get_object_or_404(ServiceRequest, request_id=request_id, service_id=service_id)

        # Получаем новое значение комментария из тела запроса
        comment = request.data.get('comment')
        if not comment or not isinstance(comment, str) or len(comment.strip()) == 0:
            return Response({"error": "Invalid comment. It must be a non-empty string."}, status=status.HTTP_400_BAD_REQUEST)

        # Обновляем комментарий
        service_request.comment = comment
        service_request.save()

        return Response({"request_id": request_id,"service_id": service_id, "message": "Comment updated", "comment": service_request.comment})

class DeleteServiceFromRequestView(APIView):
    def delete(self, request, request_id, service_id):
        # Получаем объект ServiceRequest
        service_request = get_object_or_404(ServiceRequest, request_id=request_id, service_id=service_id)

        # Удаляем услугу из заявки
        service_request.delete()

        return Response({"message": f"Service {service_id} removed from request {request_id}"}, status=status.HTTP_200_OK)
