import logging
import numpy as np
from django.core.management.base import BaseCommand
from clips.models import Organization, EmbeddingPattern

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Popula padrões de embedding iniciais para todas as organizações'

    def handle(self, *args, **options):
        orgs = Organization.objects.all()
        
        if not orgs.exists():
            self.stdout.write(self.style.WARNING('Nenhuma organização encontrada'))
            return

        patterns_config = [
            {
                'name': 'High Engagement',
                'category': 'engagement',
                'description': 'Padrão para clips com alto engajamento',
            },
            {
                'name': 'Viral Content',
                'category': 'viral',
                'description': 'Padrão para conteúdo viral',
            },
            {
                'name': 'Educational',
                'category': 'educational',
                'description': 'Padrão para conteúdo educacional',
            },
            {
                'name': 'Entertainment',
                'category': 'entertainment',
                'description': 'Padrão para conteúdo de entretenimento',
            },
        ]

        for org in orgs:
            for pattern_config in patterns_config:
                embedding = np.random.randn(768).tolist()
                
                pattern, created = EmbeddingPattern.objects.get_or_create(
                    organization=org,
                    name=pattern_config['name'],
                    defaults={
                        'category': pattern_config['category'],
                        'embedding': embedding,
                        'description': pattern_config['description'],
                        'confidence_score': 0.5,
                    }
                )

                if created:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'✓ Criado padrão "{pattern_config["name"]}" para {org.name}'
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f'⚠ Padrão "{pattern_config["name"]}" já existe para {org.name}'
                        )
                    )

        self.stdout.write(self.style.SUCCESS('Padrões de embedding populados com sucesso!'))
