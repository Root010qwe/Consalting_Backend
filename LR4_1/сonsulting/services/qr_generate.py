import segno
import base64
from io import BytesIO
from datetime import datetime


def generate_request_qr(consulting_request):
    """
    Генерирует QR-код с информацией о заявке.
    """
    info = f"Консультационная заявка №{consulting_request.id}\n"
    info += f"Статус: {consulting_request.status}\n"
    info += f"Приоритет: {consulting_request.priority_level}\n"
    info += f"Дата создания: {consulting_request.creation_date.strftime('%Y-%m-%d %H:%M:%S')}\n"

    if consulting_request.completion_date:
        info += f"Дата завершения: {consulting_request.completion_date.strftime('%Y-%m-%d %H:%M:%S')}\n"

    if consulting_request.manager:
        info += f"Менеджер: {consulting_request.manager.username}\n"

    if consulting_request.client:
        info += f"Клиент: {consulting_request.client.username}\n"

    info += f"Итоговая стоимость: {consulting_request.total_cost} руб.\n"

    # Генерация QR-кода
    qr = segno.make(info)
    buffer = BytesIO()
    qr.save(buffer, kind='png')
    buffer.seek(0)

    # Конвертация изображения в base64
    qr_image_base64 = base64.b64encode(buffer.read()).decode('utf-8')

    return qr_image_base64
