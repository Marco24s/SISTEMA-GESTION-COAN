from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def backfill_reclassification_targets(apps, schema_editor):
    Reclassification = apps.get_model('budget', 'BudgetAllocationReclassification')
    for item in Reclassification.objects.select_related('target_credit').all():
        target = item.target_credit
        if target:
            item.target_ff_id = target.ff_id
            item.target_subprog_id = target.subprog_id
            item.target_inc_id = target.inc_id
            item.target_ppp_inc_id = target.ppp_inc_id
            item.target_pp_inc_id = target.pp_inc_id
            item.target_pre_inc_id = target.pre_inc_id
            item.target_incisos_agrupado_id = target.incisos_agrupado_id
        item.requested_by_id = item.user_id
        item.executed_by_id = item.user_id
        item.status = 'EJECUTADO'
        item.save(update_fields=[
            'target_ff', 'target_subprog', 'target_inc', 'target_ppp_inc',
            'target_pp_inc', 'target_pre_inc', 'target_incisos_agrupado',
            'requested_by', 'executed_by', 'status'
        ])


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('budget', '0023_allow_reclassification_cleanup'),
    ]

    operations = [
        migrations.AddField(
            model_name='budgetallocationreclassification',
            name='approved_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reclasificaciones_aprobadas', to=settings.AUTH_USER_MODEL, verbose_name='Aprobado por'),
        ),
        migrations.AddField(
            model_name='budgetallocationreclassification',
            name='executed_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reclasificaciones_ejecutadas', to=settings.AUTH_USER_MODEL, verbose_name='Ejecutado por'),
        ),
        migrations.AddField(
            model_name='budgetallocationreclassification',
            name='requested_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reclasificaciones_solicitadas', to=settings.AUTH_USER_MODEL, verbose_name='Solicitado por'),
        ),
        migrations.AddField(
            model_name='budgetallocationreclassification',
            name='status',
            field=models.CharField(choices=[('PENDIENTE', 'Pendiente'), ('APROBADO', 'Aprobado (Listo para Ejecutar)'), ('RECHAZADO', 'Rechazado'), ('EJECUTADO', 'Ejecutado')], default='PENDIENTE', max_length=20, verbose_name='Estado'),
        ),
        migrations.AddField(
            model_name='budgetallocationreclassification',
            name='target_ff',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='budget.budgetff', verbose_name='FF destino'),
        ),
        migrations.AddField(
            model_name='budgetallocationreclassification',
            name='target_inc',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='budget.budgetinc', verbose_name='Inciso destino'),
        ),
        migrations.AddField(
            model_name='budgetallocationreclassification',
            name='target_incisos_agrupado',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='budget.budgetincisosagrupado', verbose_name='Moneda destino'),
        ),
        migrations.AddField(
            model_name='budgetallocationreclassification',
            name='target_pp_inc',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='budget.budgetppinc', verbose_name='Parcial destino'),
        ),
        migrations.AddField(
            model_name='budgetallocationreclassification',
            name='target_ppp_inc',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='budget.budgetpppinc', verbose_name='PPAL destino'),
        ),
        migrations.AddField(
            model_name='budgetallocationreclassification',
            name='target_pre_inc',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='budget.budgetpreinc', verbose_name='SUBPC destino'),
        ),
        migrations.AddField(
            model_name='budgetallocationreclassification',
            name='target_subprog',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='budget.budgetsubprog', verbose_name='Subprograma destino'),
        ),
        migrations.AddField(
            model_name='budgetallocationreclassification',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, null=True, verbose_name='Ultima actualizacion'),
        ),
        migrations.RunPython(backfill_reclassification_targets, migrations.RunPython.noop),
    ]
