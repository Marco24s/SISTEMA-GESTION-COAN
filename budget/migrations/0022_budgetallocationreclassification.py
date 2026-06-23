from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('budget', '0021_alter_budgetclassification_options_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='BudgetAllocationReclassification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('q1_amount', models.DecimalField(decimal_places=2, default=0, max_digits=18, verbose_name='Monto T1')),
                ('q2_amount', models.DecimalField(decimal_places=2, default=0, max_digits=18, verbose_name='Monto T2')),
                ('q3_amount', models.DecimalField(decimal_places=2, default=0, max_digits=18, verbose_name='Monto T3')),
                ('q4_amount', models.DecimalField(decimal_places=2, default=0, max_digits=18, verbose_name='Monto T4')),
                ('notes', models.TextField(blank=True, null=True, verbose_name='Observaciones')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Fecha y hora')),
                ('source_allocation', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='reclassifications_out', to='budget.budgetallocation', verbose_name='Distribucion origen')),
                ('source_credit', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='allocation_reclassifications_out', to='budget.budgetcredit', verbose_name='Credito origen')),
                ('target_allocation', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='reclassifications_in', to='budget.budgetallocation', verbose_name='Distribucion destino')),
                ('target_credit', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='allocation_reclassifications_in', to='budget.budgetcredit', verbose_name='Credito destino')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL, verbose_name='Realizado por')),
            ],
            options={
                'verbose_name': 'Reclasificacion de distribucion',
                'verbose_name_plural': 'Reclasificaciones de distribuciones',
                'ordering': ['-created_at'],
            },
        ),
    ]
