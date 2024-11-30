from django.shortcuts import render, get_object_or_404, redirect
from django.http import Http404
from django.db import connection
from .models import ConsultingService, ConsultingRequest, ServiceRequest


def add_service_to_request(request, service_id):
    service = get_object_or_404(ConsultingService, id=service_id)
    # Получаем или создаем текущую заявку
    consulting_request, created = ConsultingRequest.objects.get_or_create(
        status="Draft",
        client_name="Гость"  # Используем анонимного пользователя
    )

    # Проверяем, есть ли уже эта услуга в заявке
    service_request, created = ServiceRequest.objects.get_or_create(
        request=consulting_request,
        service=service
    )

    if not created:  # Если услуга уже есть, увеличиваем количество
        service_request.quantity += 1
        service_request.save()

    return redirect(services_page)


def services_page(request):
    service_name = request.GET.get("service_name", "")
    services = ConsultingService.objects.filter(status="A")
    if service_name:
        services = services.filter(name__icontains=service_name)

    current_request = ConsultingRequest.objects.filter(status='Draft').first()
    request_count = ServiceRequest.objects.filter(request=current_request).count() if current_request else 0

    return render(request, 'main_page.html', {
        'services': services,
        'filter': service_name or "Название услуги",
        'currentRequest': current_request,
        'count': request_count,

    })

def description(request, id):
    service = get_object_or_404(ConsultingService, id=id)
    return render(request, 'description.html', {'service': service})


def report_info(request, id):
    # Получаем заявку по ID или вызываем 404
    try:
        report = ConsultingRequest.objects.get(id=id)
    except ConsultingRequest.DoesNotExist:
        raise Http404("Заявка не найдена")

    # Проверяем статус заявки
    if report.status in ["Completed", "Rejected"]:
        raise Http404("Эта заявка недоступна")

    # Если отправлен POST-запрос, обновляем данные
    if request.method == "POST":
        contact_email = request.POST.get("contact_email")
        if contact_email:
            report.client_email = contact_email
            report.save()

        # Обновление комментариев для каждой услуги
        for service_request in report.service_requests.all():
            comment = request.POST.get(f"comment_{service_request.id}")
            if comment:
                service_request.comment = comment
                service_request.save()

    # Получаем связанные услуги
    services = ServiceRequest.objects.filter(request=report)

    return render(request, 'report_page.html', {
        'report': report,
        'services': services,
        'report_date': report.creation_date.strftime("%d.%m.%Y %H:%M"),
    })



def delete_report(request, report_id):
    report = get_object_or_404(ConsultingRequest, id=report_id)
    report.status = "Completed"  # Меняем статус на "Completed"
    report.save()
    return redirect('services_page')  # Возврат на главную страницу




def delete_request(request, request_id):
    service_request = get_object_or_404(ServiceRequest, id=request_id)
    service_request.delete()
    return redirect('services_page')  # Возврат на главную страницу

def complete_request(request, id):
    # Завершить заявку (сменить статус на "Completed")
    report = get_object_or_404(ConsultingRequest, id=id)
    report.status = "Completed"
    report.save()
    return redirect('services_page')  # После завершения перенаправляем на главную страницу


def delete_service_from_request(request, service_request_id):
    # Удалить услугу из заявки
    service_request = get_object_or_404(ServiceRequest, id=service_request_id)
    service_request.delete()
    return redirect('report_info', id=service_request.request.id)



def custom_404(request, exception):
    return render(request, '404.html', status=404)
