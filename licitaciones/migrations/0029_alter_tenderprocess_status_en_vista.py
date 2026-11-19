from django.db import migrations, models


def migrate_en_apertura_to_en_vista(apps, schema_editor):
    TenderProcess = apps.get_model('licitaciones', 'TenderProcess')
    TenderProcess.objects.filter(status='EN_APERTURA').update(status='EN_VISTA')


def migrate_en_vista_to_en_apertura(apps, schema_editor):
    TenderProcess = apps.get_model('licitaciones', 'TenderProcess')
    TenderProcess.objects.filter(status='EN_VISTA').update(status='EN_APERTURA')


class Migration(migrations.Migration):

    dependencies = [
        ('licitaciones', '0028_alter_tenderprocess_status'),
    ]

    operations = [
        migrations.RunPython(
            migrate_en_apertura_to_en_vista,
            migrate_en_vista_to_en_apertura,
        ),
        migrations.AlterField(
            model_name='tenderprocess',
            name='status',
            field=models.CharField(
                choices=[
                    ('PUBLICADO', 'Publicado'),
                    ('EN_VISTA', 'En vista'),
                    ('EN_EVALUACION', 'Evaluacion / apertura'),
                    ('PREADJUDICADO_DISPONIBLE', 'Preadjudicado / Disponible para adjudicar'),
                    ('ADJUDICADO', 'Adjudicado'),
                    ('FRACASADO', 'Fracasado'),
                    ('DESIERTO', 'Desierto'),
                    ('DEJADO_SIN_EFECTO', 'Dejado sin efecto'),
                ],
                default='PUBLICADO',
                max_length=30,
                verbose_name='Estado',
            ),
        ),
    ]
