from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('budget', '0022_budgetallocationreclassification'),
    ]

    operations = [
        migrations.AlterField(
            model_name='budgetallocationreclassification',
            name='source_allocation',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reclassifications_out', to='budget.budgetallocation', verbose_name='Distribucion origen'),
        ),
        migrations.AlterField(
            model_name='budgetallocationreclassification',
            name='target_allocation',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reclassifications_in', to='budget.budgetallocation', verbose_name='Distribucion destino'),
        ),
        migrations.AlterField(
            model_name='budgetallocationreclassification',
            name='source_credit',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='allocation_reclassifications_out', to='budget.budgetcredit', verbose_name='Credito origen'),
        ),
        migrations.AlterField(
            model_name='budgetallocationreclassification',
            name='target_credit',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='allocation_reclassifications_in', to='budget.budgetcredit', verbose_name='Credito destino'),
        ),
    ]
