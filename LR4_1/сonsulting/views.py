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
    LoginSerializer, ServiceAddSerializer
)
from minio import Minio
from django.db.models import Q
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from datetime import datetime
from django.utils.timezone import now
from minio.error import S3Error

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
from сonsulting.services.qr_generate import generate_request_qr
import time
from rest_framework.pagination import PageNumberPagination


minio_client = Minio(
    '91.135.156.74:9000',  # Укажите MinIO endpoint
    access_key='admin',  # Ваш MinIO login
    secret_key='adminadmin',  # Ваш MinIO password
    secure=False  # Измените на True, если MinIO настроен на HTTPS
)

# Connect to our Redis instance
session_storage = redis.StrictRedis(host=settings.REDIS_HOST, port=settings.REDIS_PORT)

BUCKET_NAME = 'images'


class CsrfExemptSessionAuthentication(SessionAuthentication):
    def enforce_csrf(self, request):
        pass


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20  # число элементов на странице по умолчанию
    page_size_query_param = 'page_size'
    max_page_size = 100


# Методы услуг
class ServiceListView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_description="Возвращает список активных услуг с пагинацией. Можно передать параметр 'name' для фильтрации.",
        manual_parameters=[
            openapi.Parameter(
                'name',
                openapi.IN_QUERY,
                description="Фильтровать по подстроке в имени услуги",
                type=openapi.TYPE_STRING,
                required=False
            ),
            openapi.Parameter(
                'page',
                openapi.IN_QUERY,
                description="Номер страницы",
                type=openapi.TYPE_INTEGER,
                required=False
            ),
            openapi.Parameter(
                'page_size',
                openapi.IN_QUERY,
                description="Число элементов на странице",
                type=openapi.TYPE_INTEGER,
                required=False
            ),
        ]
    )
    def get(self, request):
        start_time = time.time()  # начало замера времени

        name_filter = request.query_params.get('name', None)
        services_qs = ConsultingService.objects.filter(status="A").order_by('id')
        if name_filter:
            services_qs = services_qs.filter(name__icontains=name_filter)

        # Пагинация
        paginator = StandardResultsSetPagination()
        paginated_services = paginator.paginate_queryset(services_qs, request)

        query_duration = time.time() - start_time  # время выполнения запроса

        # Работа с черновой заявкой (при наличии)
        user = request.user
        draft_request_id = None
        services_in_draft_request = 0
        if user.is_authenticated:
            draft_request = ConsultingRequest.objects.filter(status="Draft", client=user).first()
            if draft_request:
                draft_request_id = draft_request.id
                services_in_draft_request = ServiceRequest.objects.filter(request=draft_request).count()

        response_data = {
            "duration": query_duration,  # время выполнения запроса добавлено в ответ
            "draft_request_id": draft_request_id,
            "services_in_draft_request": services_in_draft_request,
            "services": ServiceSerializer(paginated_services, many=True).data,
        }
        return paginator.get_paginated_response(response_data)


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
        request_body=ServiceAddSerializer,  # указываем, что в теле запроса JSON по схеме ServiceSerializer
        responses={
            201: openapi.Response(
                description="Успешное создание услуги",
                schema=ServiceAddSerializer
            ),
            400: "Плохой запрос или невалидные данные"
        }
    )
    def post(self, request):
        user = request.user
        serializer = ServiceAddSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
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
        try:
            service = get_object_or_404(ConsultingService, pk=pk)
            service.status = "D"
            service.save()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


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


from rest_framework.parsers import MultiPartParser, FormParser

class AddImageToServiceView(APIView):
    permission_classes = [IsManager]
    parser_classes = (MultiPartParser, FormParser)  # Добавлено для обработки multipart/form-data

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
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

class RequestListView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Получает список заявок. Доступно менеджеру/админу - все заявки; обычному пользователю - только свои",
        manual_parameters=[
            openapi.Parameter(
                name='start_date',
                in_=openapi.IN_QUERY,
                description='Начальная дата (формат: YYYY-MM-DD)',
                type=openapi.TYPE_STRING,
                required=False
            ),
            openapi.Parameter(
                name='end_date',
                in_=openapi.IN_QUERY,
                description='Конечная дата (формат: YYYY-MM-DD)',
                type=openapi.TYPE_STRING,
                required=False
            ),
            openapi.Parameter(
                name='status',
                in_=openapi.IN_QUERY,
                description='Фильтр по статусу',
                type=openapi.TYPE_STRING,
                required=False
            ),
        ],
        responses={
            200: openapi.Response(
                description="Список заявок",
                schema=RequestSerializer(many=True)
            )
        }
    )
    def get(self, request):
        user = request.user
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')
        status_filter = request.query_params.get('status')

        if user.is_staff or user.is_superuser:
            requests_qs = ConsultingRequest.objects.all()
        else:
            requests_qs = ConsultingRequest.objects.exclude(status__in=["Deleted"]).filter(client=user)

        from datetime import datetime, timedelta

        # Если заданы обе даты, парсим их и корректно фильтруем заявки
        if start_date_str and end_date_str:
            try:
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
                end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
                # Если конечная дата раньше начальной, считаем их равными
                if end_date < start_date:
                    end_date = start_date
                # Если даты равны (или end_date была исправлена на start_date), фильтруем по указанному дню
                if start_date.date() == end_date.date():
                    day_start = datetime.combine(start_date.date(), datetime.min.time())
                    day_end = datetime.combine(start_date.date(), datetime.max.time())
                    requests_qs = requests_qs.filter(creation_date__gte=day_start, creation_date__lte=day_end)
                else:
                    # Фильтруем по диапазону: от начала start_date до конца end_date
                    day_start = datetime.combine(start_date.date(), datetime.min.time())
                    day_end = datetime.combine(end_date.date(), datetime.max.time())
                    requests_qs = requests_qs.filter(creation_date__gte=day_start, creation_date__lte=day_end)
            except ValueError:
                # Если формат даты неверный, фильтр по датам игнорируется
                pass
        else:
            if start_date_str:
                try:
                    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
                    day_start = datetime.combine(start_date.date(), datetime.min.time())
                    requests_qs = requests_qs.filter(creation_date__gte=day_start)
                except ValueError:
                    pass
            if end_date_str:
                try:
                    end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
                    day_end = datetime.combine(end_date.date(), datetime.max.time())
                    requests_qs = requests_qs.filter(creation_date__lte=day_end)
                except ValueError:
                    pass

        if status_filter:
            requests_qs = requests_qs.filter(status=status_filter)

        return Response(RequestSerializer(requests_qs, many=True).data)


class RequestDetailView(APIView):
    @swagger_auto_schema(
        operation_description="Возвращает детальную информацию о заявке по ID",
        responses={
            200: openapi.Response(
                description="OK",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "id": openapi.Schema(type=openapi.TYPE_INTEGER, description="ID заявки"),
                        "client": openapi.Schema(type=openapi.TYPE_STRING, description="Имя клиента"),
                        "manager": openapi.Schema(type=openapi.TYPE_STRING, description="Имя менеджера (может быть null)"),
                        "status": openapi.Schema(type=openapi.TYPE_STRING, description="Статус заявки"),
                        "priority_level": openapi.Schema(type=openapi.TYPE_STRING, description="Уровень приоритета"),
                        "formed_date": openapi.Schema(
                            type=openapi.TYPE_STRING, format=openapi.FORMAT_DATETIME, description="Дата формирования"
                        ),
                        "contact_phone": openapi.Schema(type=openapi.TYPE_STRING, description="Контактный телефон клиента"),
                        "creation_date": openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_DATETIME, description="Дата создания"),
                        "completion_date": openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_DATETIME, description="Дата завершения (может быть null)"),
                        "service_requests": openapi.Schema(
                            type=openapi.TYPE_ARRAY,
                            items=openapi.Schema(
                                type=openapi.TYPE_OBJECT,
                                properties={
                                    "id": openapi.Schema(type=openapi.TYPE_INTEGER, description="ID услуги в заявке"),
                                    "service": openapi.Schema(
                                        type=openapi.TYPE_OBJECT,
                                        properties={
                                            "id": openapi.Schema(type=openapi.TYPE_INTEGER, description="ID услуги"),
                                            "name": openapi.Schema(type=openapi.TYPE_STRING, description="Название услуги"),
                                            "description": openapi.Schema(type=openapi.TYPE_STRING, description="Описание услуги"),
                                            "status": openapi.Schema(type=openapi.TYPE_STRING, description="Статус услуги"),
                                            "price": openapi.Schema(type=openapi.TYPE_STRING, format="decimal", description="Цена услуги"),
                                            "duration": openapi.Schema(type=openapi.TYPE_INTEGER, description="Продолжительность услуги в часах"),
                                            "image_url": openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_URI, description="Ссылка на изображение услуги"),
                                        },
                                    ),
                                    "comment": openapi.Schema(type=openapi.TYPE_STRING, description="Комментарий к услуге (может быть пустым)"),
                                },
                            ),
                        ),
                        "total_cost": openapi.Schema(type=openapi.TYPE_STRING, format="decimal", description="Общая стоимость заявки"),
                    },
                ),
            ),
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

        # Проверяем права доступа
        if (
            not request.user.is_staff
            and not request.user.is_superuser
            and request.user != consulting_request.client
        ):
            return Response(
                {"error": "You do not have permission to view this transfer"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Проверяем статус заявки
        if consulting_request.status != "Draft":
            return Response(
                {"error": "Only draft requests can be formed."},
                status=status.HTTP_405_METHOD_NOT_ALLOWED
            )

        # Проверяем наличие клиента
        if not consulting_request.client:
            return Response(
                {"error": "Client name is required to form the request."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Обновляем статус, дату формирования и сохраняем заявку
        consulting_request.status = "Submitted"
        consulting_request.formed_date = now()  # Устанавливаем дату формирования
        consulting_request.save()

        return Response(
            {
                "message": "Request successfully submitted.",
                "status": consulting_request.status,
                "formed_date": consulting_request.formed_date,
            },
            status=status.HTTP_200_OK
        )





class RequestCompleteOrRejectView1(APIView):
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

            # Генерация QR-кода
            qr_code_base64 = generate_request_qr(consulting_request)
            consulting_request.qr = qr_code_base64

        elif status_value == "Rejected":
            consulting_request.total_cost = 0  # Обнуление суммы
            consulting_request.qr = None  # QR-код не нужен для отклонённой заявки

        consulting_request.status = status_value
        consulting_request.completion_date = now()
        consulting_request.save()

        return Response(
            {
                "message": f"Request successfully {status_value.lower()}.",
                "status": consulting_request.status,
                "completion_date": consulting_request.completion_date,
                "total_cost": consulting_request.total_cost,
                "qr": consulting_request.qr,  # Отправляем QR в ответе
            },
            status=status.HTTP_200_OK
        )



from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from .models import ConsultingRequest
from drf_yasg.utils import swagger_auto_schema

class RequestDeleteView(APIView):
    permission_classes = [IsAuthenticated]  # Разрешено только авторизованным пользователям

    @swagger_auto_schema(
        operation_description="Удаляет заявку только если она в статусе Draft. Доступно автору заявки или администратору.",
        responses={
            200: "Успешно удалено (статус = Deleted)",
            403: "Нет прав доступа / чужая заявка",
            405: "Не подходит статус (не Draft)",
            404: "Заявка не найдена",
        }
    )
    def delete(self, request, pk):
        # Ищем заявку по ID
        consulting_request = get_object_or_404(ConsultingRequest, pk=pk)

        # Проверяем права доступа: либо клиент заявки, либо админ/менеджер
        if (
            not request.user.is_staff
            and not request.user.is_superuser
            and request.user != consulting_request.client
        ):
            return Response(
                {"error": "You do not have permission to delete this request."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Проверяем статус заявки
        if consulting_request.status != "Draft":
            return Response(
                {"error": "Only draft requests can be deleted."},
                status=status.HTTP_405_METHOD_NOT_ALLOWED,
            )

        # Удаляем заявку, меняя её статус на "Deleted"
        consulting_request.status = "Deleted"
        consulting_request.save()

        return Response(
            {
                "id": consulting_request.id,
                "status": consulting_request.status,
                "message": "Request successfully deleted.",
            },
            status=status.HTTP_200_OK,
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
    request_body=LoginSerializer,
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

class UpdateRequestFieldsView(APIView):
    permission_classes = [IsAuthenticated]  # Только для авторизованных пользователей

    @swagger_auto_schema(
        operation_description="Обновляет дополнительные поля заявки (contact_phone, priority_level)",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'contact_phone': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Контактный телефон"
                ),
                'priority_level': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Уровень приоритета заявки"
                )
            },
            required=['contact_phone', 'priority_level']
        ),
        responses={
            200: "Поля заявки обновлены",
            400: "Некорректные данные",
            404: "Заявка не найдена",
            405: "Изменение заявки запрещено, если её статус не 'Draft'"
        }
    )
    def put(self, request, pk):
        # Получаем заявку
        consulting_request = get_object_or_404(ConsultingRequest, pk=pk)

        # Проверяем статус заявки
        if consulting_request.status != "Draft":
            return Response(
                {"error": "Only Draft requests can be modified."},
                status=status.HTTP_405_METHOD_NOT_ALLOWED
            )

        # Получаем данные из тела запроса
        contact_phone = request.data.get('contact_phone')
        priority_level = request.data.get('priority_level')

        # Проверяем наличие и валидность данных
        if not contact_phone or not isinstance(contact_phone, str) or len(contact_phone.strip()) == 0:
            return Response(
                {"error": "Invalid contact_phone. It must be a non-empty string."},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not priority_level or not isinstance(priority_level, str) or len(priority_level.strip()) == 0:
            return Response(
                {"error": "Invalid priority_level. It must be a non-empty string."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Обновляем поля заявки
        consulting_request.contact_phone = contact_phone
        consulting_request.priority_level = priority_level
        consulting_request.save()

        return Response(
            {
                "message": "Request fields updated successfully.",
                "contact_phone": consulting_request.contact_phone,
                "priority_level": consulting_request.priority_level,
            },
            status=status.HTTP_200_OK
        )

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



import threading
import requests
from django.utils.timezone import now
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
# Импортируйте свои модели, permission и прочее
from .models import ConsultingRequest



class UpdateConsultingRequestResultView(APIView):
    """
    Эндпоинт, который вызывается асинхронным сервисом для обновления заявки.
    Ожидается JSON с полями: token, pk, total_cost.
    """
    def put(self, request, *args, **kwargs):
        data = request.data
        token = data.get("token")
        if token != AUTH_TOKEN:
            return Response({"error": "Unauthorized"}, status=status.HTTP_401_UNAUTHORIZED)
        
        pk = data.get("pk")
        if not pk:
            return Response({"error": "Missing pk"}, status=status.HTTP_400_BAD_REQUEST)
        
        consulting_request = get_object_or_404(ConsultingRequest, pk=pk)
        total_cost = data.get("total_cost")
        if total_cost is None:
            return Response({"error": "Missing total_cost"}, status=status.HTTP_400_BAD_REQUEST)
        
        consulting_request.total_cost = total_cost
        consulting_request.save()
        
        return Response({"message": "Result updated"}, status=status.HTTP_200_OK)

# Константный токен (используется в UpdateConsultingRequestResultView)
AUTH_TOKEN = "My8Byte"
# URL Go‑сервиса – убедитесь, что этот URL доступен из среды Django
ASYNC_SERVICE_URL = "http://localhost:8080/set_status"

class RequestCompleteOrRejectView(APIView):
    permission_classes = [IsManager]

    def put(self, request, pk, *args, **kwargs):
        consulting_request = get_object_or_404(ConsultingRequest, pk=pk)
        status_value = request.data.get('status')
        if status_value not in ["Completed", "Rejected"]:
            return Response({"error": "Invalid status. Allowed values are 'Completed' or 'Rejected'."},
                            status=status.HTTP_400_BAD_REQUEST)
        if consulting_request.status != "Submitted":
            return Response({"error": "Only requests with 'Submitted' status can be completed or rejected."},
                            status=status.HTTP_405_METHOD_NOT_ALLOWED)

        if status_value == "Completed":
            # Очищаем total_cost и qr, чтобы их обновил асинхронный сервис
            consulting_request.total_cost = None
            qr_code_base64 = generate_request_qr(consulting_request)
            consulting_request.qr = qr_code_base64
            consulting_request.status = status_value
            consulting_request.completion_date = now()
            consulting_request.save()

            # Запускаем асинхронный вызов Go‑сервиса в отдельном потоке
            def call_async_service(pk_value):
                print("Async call: sending pk =", pk_value)
                try:
                    # Передаем pk как строку через form-data
                    response = requests.post(ASYNC_SERVICE_URL, data={"pk": str(pk_value)})
                    print("Async service response:", response.status_code, response.text)
                except Exception as e:
                    print("Error calling async service:", e)
            threading.Thread(target=call_async_service, args=(pk,)).start()

        elif status_value == "Rejected":
            consulting_request.total_cost = 0
            consulting_request.qr = None
            consulting_request.status = status_value
            consulting_request.completion_date = now()
            consulting_request.save()

        return Response({
            "message": f"Request successfully {status_value.lower()}.",
            "status": consulting_request.status,
            "completion_date": consulting_request.completion_date,
            "total_cost": consulting_request.total_cost,
            "qr": consulting_request.qr,
        }, status=status.HTTP_200_OK)