from sqlite3 import IntegrityError

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.middleware.csrf import get_token
from . import models
from .models import ConsultingService, ConsultingRequest, ServiceRequest, CustomUser
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

from django.contrib.auth import get_user_model
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.permissions import AllowAny
from rest_framework.decorators import permission_classes, authentication_classes
from rest_framework.authentication import SessionAuthentication, BasicAuthentication
from rest_framework.permissions import IsAuthenticatedOrReadOnly, IsAuthenticated
from django.contrib.auth import authenticate, login
from django.http import HttpResponse
import uuid
from django.utils.decorators import method_decorator
from rest_framework.decorators import api_view, permission_classes
from сonsulting.permissions import IsAdmin, IsManager
from rest_framework import viewsets
import redis
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from bmstu_lab import settings

minio_client = Minio(
    '91.135.156.74:9000',  # Укажите MinIO endpoint
    access_key='admin',  # Ваш MinIO login
    secret_key='minio124',  # Ваш MinIO password
    secure=False  # Измените на True, если MinIO настроен на HTTPS
)

# Connect to our Redis instance
session_storage = redis.StrictRedis(host=settings.REDIS_HOST, port=settings.REDIS_PORT)

BUCKET_NAME = 'images'


class CsrfExemptSessionAuthentication(SessionAuthentication):
    def enforce_csrf(self, request):
        pass


# Методы услуг
class ServiceListView(APIView):
    permission_classes = [AllowAny]  # Только авторизованные пользователи

    @swagger_auto_schema(
        operation_description="Возвращает список активных услуг. Можно передать параметр 'name' для фильтрации.",
        manual_parameters=[
            openapi.Parameter(
                'name',
                openapi.IN_QUERY,
                description="Фильтровать по подстроке в имени услуги",
                type=openapi.TYPE_STRING,
                required=False
            ),
        ]
    )
    def get(self, request):
        user = request.user
        # Получаем значение параметра name из запроса
        name_filter = request.query_params.get('name', None)

        # Базовый запрос для получения всех активных услуг )
        services = ConsultingService.objects.filter(status="A")

        # Если передан параметр name, добавляем фильтр)
        if name_filter:
            services = services.filter(name__icontains=name_filter)

        # Получаем черновую заявку текущего пользователя)
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
    @swagger_auto_schema(
        operation_description="Возвращает детальную информацию об услуге по ID",
        responses={
            200: openapi.Response(
                description="Информация об услуге",
                schema=ServiceSerializer
            ),
            404: "Услуга не найдена"
        }
    )
    def get(self, request, pk):
        service = get_object_or_404(ConsultingService, pk=pk)
        return Response(ServiceSerializer(service).data)


class ServiceCreateView(APIView):
    permission_classes = [IsManager]
    @swagger_auto_schema(
        operation_description="Создаёт новую услугу",
        request_body=ServiceSerializer,  # указываем, что в теле запроса JSON по схеме ServiceSerializer
        responses={
            201: openapi.Response(
                description="Успешное создание услуги",
                schema=ServiceSerializer
            ),
            400: "Плохой запрос или невалидные данные"
        }
    )
    def post(self, request):
        user = request.user
        serializer = ServiceSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()  # Поле `manager` убрано, т.к. оно отсутствует в модели
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ServiceUpdateView(APIView):
    permission_classes = [IsManager]

    def put(self, request, pk):
        service = get_object_or_404(ConsultingService, pk=pk)
        serializer = ServiceSerializer(service, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ServiceDeleteView(APIView):
    permission_classes = [IsManager]
    @swagger_auto_schema(
        operation_description="Помечает услугу как 'Deleted'",
        responses={
            204: "Услуга помечена как удалённая",
            404: "Услуга не найдена"
        }
    )
    def delete(self, request, pk):
        service = get_object_or_404(ConsultingService, pk=pk)
        service.status = "D"
        service.save()
        return Response({"message": "Service deleted"}, status=status.HTTP_204_NO_CONTENT)


class AddServiceToDraftRequestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        user = request.user
        service = get_object_or_404(ConsultingService, pk=pk)
        draft_request, created = ConsultingRequest.objects.get_or_create(
            status="Draft", client=user
        )
        service_request, created = ServiceRequest.objects.get_or_create(
            request=draft_request, service=service
        )
        if not created:
            service_request.quantity += 1
            service_request.save()
        return Response(ServiceRequestSerializer(service_request).data)


class AddImageToServiceView(APIView):
    permission_classes = [IsManager]

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
                return Response({"detail": f"Ошибка удаления старого изображения: {e}"},
                                status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
            return Response({"detail": f"Ошибка загрузки изображения: {e}"},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Сохраняем URL нового изображения
        service.image_url = f"http://91.135.156.74:9000/{BUCKET_NAME}/{file_name}"
        service.save()

        return Response({
            "detail": "Изображение успешно загружено.",
            "image_url": service.image_url
        }, status=status.HTTP_200_OK)


# Методы заявок
class RequestListView(APIView):
    permission_classes = [IsAuthenticated]
    @swagger_auto_schema(
        operation_description="Получает список заявок. Доступно менеджеру/админу - все заявки; обычному пользователю - только свои",
        responses={
            200: openapi.Response(
                description="Список заявок",
                schema=RequestSerializer(many=True)  # список
            )
        }
    )
    def get(self, request):
        user = request.user
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        status_filter = request.query_params.get('status')

        if request.user.is_staff or request.user.is_superuser:
            requests = ConsultingRequest.objects.all()
        else:
            requests = ConsultingRequest.objects.exclude(status__in=["Deleted", "Draft"]).filter(client=user)

        if start_date:
            requests = requests.filter(creation_date__gte=start_date)
        if end_date:
            requests = requests.filter(creation_date__lte=end_date)
        if status_filter:
            requests = requests.filter(status=status_filter)

        return Response(RequestSerializer(requests, many=True).data)


class RequestDetailView(APIView):
    @swagger_auto_schema(
        operation_description="Возвращает детальную информацию о заявке по ID",
        responses={
            200: openapi.Response("OK", RequestDetailSerializer),
            404: "Заявка не найдена",
        }
    )
    def get(self, request, pk):
        consulting_request = get_object_or_404(ConsultingRequest, pk=pk)
        return Response(RequestDetailSerializer(consulting_request).data)


class RequestUpdateView(APIView):
    permission_classes = [IsManager]
    @swagger_auto_schema(
        operation_description="Обновляет заявку (для менеджера)",
        request_body=RequestSerializer,
        responses={
            200: openapi.Response("OK", RequestSerializer),
            400: "Ошибка валидации",
            404: "Заявка не найдена",
        }
    )
    def put(self, request, pk):
        print(list(ConsultingRequest.objects.all()))
        consulting_request = get_object_or_404(ConsultingRequest, pk=pk)
        serializer = RequestSerializer(consulting_request, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


from django.utils.timezone import now


class RequestFormView(APIView):
    permission_classes = [IsAuthenticated]
    @swagger_auto_schema(
        operation_description="Переводит черновую заявку в 'Submitted', если все условия выполнены",
        responses={
            200: "Заявка успешно оформлена",
            400: "Не все поля заполнены / неверные данные",
            403: "Нет прав доступа / чужая заявка",
            405: "Статус не позволяет перевести",
        }
    )
    def put(self, request, pk):
        # Ищем нужную заявку по ее id
        consulting_request = get_object_or_404(ConsultingRequest, pk=pk)

        # Если пользователь -- НЕ (автор заявки или модератор/админ), то запрещаем доступ
        if (
                not request.user.is_staff
                and not request.user.is_superuser
                and request.user != consulting_request.client
        ):
            return Response(
                {"error": "You do not have permission to view this transfer"},
                status.HTTP_403_FORBIDDEN,
            )

        if consulting_request.status != "Draft":
            return Response(
                {"error": "Only draft requests can be formed."},
                status=status.HTTP_405_METHOD_NOT_ALLOWED
            )

        if not consulting_request.client:
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
    permission_classes = [IsManager]
    @swagger_auto_schema(
        operation_description="Менеджер меняет статус заявки на Completed или Rejected",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'status': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Допустимые значения: 'Completed' или 'Rejected'"
                )
            },
            required=['status']
        ),
        responses={
            200: "Успешно обновлён статус",
            400: "Неверный статус",
            405: "Заявка не в 'Submitted'"
        }
    )
    def put(self, request, pk):
        user = request.user
        consulting_request = get_object_or_404(ConsultingRequest, pk=pk)

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
    permission_classes = [IsManager]
    @swagger_auto_schema(
        operation_description="Удаляет заявку только если она в статусе Draft",
        responses={
            200: "Успешно удалено (статус = Deleted)",
            405: "Не подходит статус (не Draft)",
            404: "Заявка не найдена",
        }
    )
    def delete(self, request, pk):
        user = request.user
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


# PUT обновление данных пользователя
@method_decorator(csrf_exempt, name='dispatch')
class UserUpdateView(APIView):
    permission_classes = [IsAuthenticated]  # Только для авторизованных пользователей
    @swagger_auto_schema(
        operation_description="Обновляет данные текущего пользователя (partial=True)",
        request_body=UserSerializer,
        responses={
            200: openapi.Response("Успешно обновлён", UserSerializer),
            400: "Ошибка валидации",
            409: "Username уже занят"
        }
    )
    def put(self, request, *args, **kwargs):
        user = request.user  # Получаем текущего пользователя
        serializer = UserSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            try:
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            except IntegrityError:
                return Response({'error': 'Username already exists'}, status=status.HTTP_409_CONFLICT)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# POST аутентификация
@swagger_auto_schema(
    method="post",
    request_body=UserSerializer,
    operation_description="Signs the user in",
)
@api_view(["POST"])
@permission_classes([AllowAny])
@authentication_classes([CsrfExemptSessionAuthentication])
def login(request):
    username = request.data.get("username", None)
    password = request.data.get("password", None)
    user = authenticate(request, username=username, password=password)
    if user is not None:
        random_key = str(uuid.uuid4())
        session_storage.set(random_key, user.id)

        serializer = UserSerializer(user)
        response = Response(serializer.data)
        response.set_cookie("session_id", random_key)
        response.set_cookie("csrftoken", get_token(request))

        if request.user.is_authenticated:
            session_id = request.COOKIES.get("session_id")
            session_storage.delete(session_id)

        return response
    else:
        return Response(
            {"status": "error", "error": "login failed"},
            status=status.HTTP_401_UNAUTHORIZED,
        )


# POST деавторизация





@method_decorator(csrf_exempt, name='dispatch')
class LogoutView(APIView):
    permission_classes = [IsAuthenticated]  # Только для авторизованных пользователей

    @swagger_auto_schema(
        operation_description="Деавторизирует текущего пользователя.",
        responses={
            200: "Успешный логаут"
        }
    )
    def post(self, request, *args, **kwargs):
        # Шаг 1. Вызываем стандартный logout от Django
        logout(request)

        # Шаг 2. Удаляем запись в Redis и куку, если мы используем самописную session_id
        session_id = request.COOKIES.get("session_id")
        response = Response({'message': 'User logged out successfully'}, status=status.HTTP_200_OK)

        if session_id:
            # удаляем запись из Redis
            session_storage.delete(session_id)
            # удаляем куку session_id
            response.delete_cookie("session_id")

        return response


class UpdateServiceInRequestView(APIView):
    permission_classes = [IsAuthenticated]  # Только для авторизованных пользователей
    @swagger_auto_schema(
        operation_description="Обновляет комментарий к услуге (service_id) в заявке (request_id)",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'comment': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Комментарий к услуге"
                )
            },
            required=['comment']
        ),
        responses={
            200: "Комментарий обновлён",
            400: "Некорректный комментарий",
            404: "Не найден serviceRequest по указанным ID",
        }
    )
    def put(self, request, request_id, service_id):
        # Получаем объект ServiceRequest
        service_request = get_object_or_404(ServiceRequest, request_id=request_id, service_id=service_id)

        # Получаем новое значение комментария из тела запроса
        comment = request.data.get('comment')
        if not comment or not isinstance(comment, str) or len(comment.strip()) == 0:
            return Response({"error": "Invalid comment. It must be a non-empty string."},
                            status=status.HTTP_400_BAD_REQUEST)

        # Обновляем комментарий
        service_request.comment = comment
        service_request.save()

        return Response({"request_id": request_id, "service_id": service_id, "message": "Comment updated",
                         "comment": service_request.comment})


class DeleteServiceFromRequestView(APIView):
    permission_classes = [IsAuthenticated]  # Только для авторизованных пользователей

    def delete(self, request, request_id, service_id):
        # Получаем объект ServiceRequest
        service_request = get_object_or_404(ServiceRequest, request_id=request_id, service_id=service_id)

        # Удаляем услугу из заявки
        service_request.delete()

        return Response({"message": f"Service {service_id} removed from request {request_id}"},
                        status=status.HTTP_200_OK)


class UserViewSet(viewsets.ModelViewSet):
    """Класс, описывающий методы работы с пользователями
    Осуществляет связь с таблицей пользователей в базе данных
    """
    queryset = CustomUser.objects.all()
    serializer_class = UserSerializer
    model_class = CustomUser

    def get_permissions(self):
        if self.action in ['create']:
            permission_classes = [AllowAny]
        elif self.action in ['list']:
            permission_classes = [IsAdmin | IsManager]
        else:
            permission_classes = [IsAdmin]
        return [permission() for permission in permission_classes]
    @swagger_auto_schema(
        operation_description="Создаёт нового пользователя",
        request_body=UserSerializer,
        responses={
            200: "Успешно",
            400: "Ошибки валидации"
        }
    )
    @csrf_exempt
    @permission_classes([AllowAny])
    def create(self, request):
        """
        Функция регистрации новых пользователей
        Если пользователя c указанным в request username ещё нет,
        в БД будет добавлен новый пользователь.
        """
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            if self.model_class.objects.filter(
                    username=request.data["username"]
            ).exists():
                return Response({"status": "Exist"}, status=400)

            self.model_class.objects.create_user(
                username=serializer.validated_data["username"],
                password=serializer.validated_data["password"],
            )
            return Response({"status": "Success"}, status=200)
        return Response(
            {"status": "Error", "error": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )
