from django.http import HttpResponse
from сonsulting.views import session_storage
from сonsulting.models import CustomUser


def session_middleware(get_response):
    def middleware(request):
        # Code to be executed for each request before
        # the view (and later middleware) are called.

        session_id = request.META.get("HTTP_SESSION_ID")
        if session_id is None:
            session_id = request.COOKIES.get("session_id")
        if session_id and session_storage.exists(session_id):
            user_id = session_storage.get(session_id).decode("utf-8")
            request.user = CustomUser.objects.get(id=user_id)
        else:
            request.user = (
                None  # Устанавливаем пользователя в None, если сессия недействительна
            )

        response = get_response(request)

        # Code to be executed for each request/response after
        # the view is called.

        return response

    return middleware