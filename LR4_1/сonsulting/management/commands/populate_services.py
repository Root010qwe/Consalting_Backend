import random
from django.core.management.base import BaseCommand
from сonsulting.models import ConsultingService

class Command(BaseCommand):
    help = 'Создать заданное количество тестовых услуг'

    def add_arguments(self, parser):
        parser.add_argument('count', type=int, nargs='?', default=100000, help='Количество услуг для создания')

    def handle(self, *args, **options):
        count = options['count']
        services = []
        for i in range(count):
            service = ConsultingService(
                name=f"Услуга {i}",
                description=f"Описание услуги {i}",
                status="A",
                price=round(random.uniform(10, 1000), 2),
                duration=random.randint(1, 10),
                image_url=""
            )
            services.append(service)
            if i % 1000 == 0:
                self.stdout.write(f"Создано {i} услуг")
        ConsultingService.objects.bulk_create(services, batch_size=1000)
        self.stdout.write(self.style.SUCCESS(f"Успешно создано {count} услуг"))
