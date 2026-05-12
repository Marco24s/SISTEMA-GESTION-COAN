import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('budget', '0003_budgetexecution_external_id'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='BudgetActivity',
            new_name='BudgetProg',
        ),
        migrations.AlterModelOptions(
            name='BudgetProg',
            options={'verbose_name': 'Programa', 'verbose_name_plural': 'Programas'},
        ),
        migrations.AlterField(
            model_name='BudgetProg',
            name='code',
            field=models.CharField(max_length=50, unique=True, verbose_name='Código PROG'),
        ),
        migrations.AlterField(
            model_name='BudgetProg',
            name='name',
            field=models.CharField(max_length=255, verbose_name='Nombre Programa'),
        ),
        migrations.RenameField(
            model_name='BudgetCredit',
            old_name='actividad',
            new_name='programa',
        ),
        migrations.AlterField(
            model_name='BudgetCredit',
            name='programa',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='budget.budgetprog', verbose_name='Programa'),
        ),
        migrations.AlterUniqueTogether(
            name='BudgetCredit',
            unique_together={('fiscal_year', 'ff', 'programa', 'subprog', 'inc', 'ppai')},
        ),
        migrations.AlterField(
            model_name='budgetexecution',
            name='external_id',
            field=models.CharField(blank=True, help_text='Código para evitar registros duplicados (Ej: Nro. Factura, ID de sistema externo, etc).', max_length=100, null=True, unique=True, verbose_name='ID de Control Único (Opcional)'),
        ),
    ]
