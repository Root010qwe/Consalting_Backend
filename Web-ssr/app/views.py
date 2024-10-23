from django.shortcuts import render

services = [
    {
        "id": 1,
        "name": "Аудит безопасности сети",
        "description": "Проведение комплексного аудита вашей ИТ-инфраструктуры для выявления уязвимостей в сетевых протоколах, конфигурации оборудования и программного обеспечения. Этот процесс позволяет заблаговременно обнаружить потенциальные угрозы и предложить меры по их устранению. Наша команда специалистов применяет новейшие технологии и подходы для проверки безопасности ваших сетевых систем.",
        "production_date": "29.03.2020",
        "image": "http://localhost:9000/images/1.png",
        "duration": "7-10 рабочих дней, в зависимости от объема сети.",
        "price": "от 120 000 рублей, в зависимости от сложности сетевой инфраструктуры."
    },
    {
        "id": 2,
        "name": "Защита данных",
        "description": "Консультационные услуги по защите персональных и корпоративных данных от несанкционированного доступа и утечек. Мы помогаем внедрить передовые решения для защиты конфиденциальной информации и соблюдения норм законодательства в области защиты данных (GDPR, ФЗ-152 и другие).",
        "production_date": "31.09.2020",
        "image": "http://localhost:9000/images/2.png",
        "duration": "5-7 рабочих дней.",
        "price": "от 100 000 рублей, в зависимости от объема данных и уровня защиты."
    },
    {
        "id": 3,
        "name": "Пентест",
        "description": "Имитация хакерских атак с целью выявления уязвимостей в ИТ-инфраструктуре. Это позволяет заблаговременно определить слабые места системы безопасности и получить рекомендации по их устранению. Наша команда экспертов применяет самые современные методики тестирования, чтобы минимизировать риски и подготовить вашу компанию к будущим угрозам.",
        "production_date": "17.04.2020",
        "image": "http://localhost:9000/images/3.png",
        "duration": "10-14 рабочих дней, в зависимости от сложности проекта.",
        "price": "от 150 000 рублей, в зависимости от размера и сложности ИТ-инфраструктуры."
    },
    {
        "id": 4,
        "name": "Управление инцидентами безопасности",
        "description": "Консультации и поддержка при реагировании на киберинциденты. Мы помогаем оперативно выявить и устранить последствия атак, минимизировать убытки и восстановить нормальную работу ИТ-систем. В рамках услуги мы также обучаем персонал правильным действиям в случае инцидента и разрабатываем план реагирования.",
        "production_date": "05.02.2022",
        "image": "http://localhost:9000/images/4.png",
        "duration": "3-5 рабочих дней для подготовки плана реагирования.",
        "price": "от 80 000 рублей."
    },
    {
        "id": 5,
        "name": "Обучение сотрудников по ИТ безопасности",
        "description": "Практический курс по повышению осведомленности и навыков сотрудников в области кибербезопасности. Наши тренеры научат ваших сотрудников выявлять фишинг, понимать основы безопасного обращения с данными и минимизировать риски информационной безопасности в повседневной работе.",
        "production_date": "05.04.2023",
        "image": "http://localhost:9000/images/5.png",
        "duration": "1-3 рабочих дня, в зависимости от количества сотрудников и выбранной программы.",
        "price": "от 50 000 рублей, в зависимости от количества участников."
    }
]

draft_application = {
    "id": 1,
    "status": "Черновик",
    "date_created": "12 сентября 2024г",
    "start_date": "18 сентября 2024г",
    "services": [
        {
            "id": 3,
            "name": "Пентест",
            "description": "Имитация хакерских атак с целью выявления уязвимостей в ИТ-инфраструктуре. Это позволяет заблаговременно определить слабые места системы безопасности и получить рекомендации по их устранению. Наша команда экспертов применяет самые современные методики тестирования, чтобы минимизировать риски и подготовить вашу компанию к будущим угрозам.",
            "production_date": "17.04.2020",
            "image": "http://localhost:9000/images/3.png",
            "value": 100
        },
        {
            "id": 4,
            "name": "Управление инцидентами безопасности",
            "description": "Консультации и поддержка при реагировании на киберинциденты. Мы помогаем оперативно выявить и устранить последствия атак, минимизировать убытки и восстановить нормальную работу ИТ-систем.",
            "production_date": "05.02.2022",
            "image": "http://localhost:9000/images/4.png",
            "value": 150
        },
        {
            "id": 5,
            "name": "Обучение сотрудников по ИТ безопасности",
            "description": "Практический курс по повышению осведомленности и навыков сотрудников в области кибербезопасности. Наши тренеры научат ваших сотрудников выявлять фишинг, понимать основы безопасного обращения с данными и минимизировать риски информационной безопасности в повседневной работе.",
            "production_date": "05.04.2023",
            "image": "http://localhost:9000/images/5.png",
            "value": 125
        }
    ]
}

def getServiceById(service_id):
    for service in services:
        if service["id"] == service_id:
            return service


def searchServices(service_name):
    res = []

    for service in services:
        if service_name.lower() in service["name"].lower():
            res.append(service)

    return res


def getDraftApplication():
    return draft_application


def getApplicationById(application_id):
    return draft_application


def index(request):
    name = request.GET.get("name", "")
    services = searchServices(name)
    draft_application = getDraftApplication()

    context = {
        "services": services,
        "name": name,
        "services_count": len(draft_application["services"]),
        "draft_application": draft_application
    }

    return render(request, "home_page.html", context)


def service(request, service_id):
    context = {
        "id": service_id,
        "service": getServiceById(service_id),
    }

    return render(request, "ship_page.html", context)


def application(request, application_id):
    context = {
        "application": getApplicationById(application_id),
    }

    return render(request, "flight_page.html", context)