from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("licitaciones", "0010_foreign_tender_summary_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="foreigntenderprocess",
            name="delivery_term_day_type",
            field=models.CharField(blank=True, choices=[("CORRIDOS", "Dias corridos"), ("HABILES", "Dias habiles (lunes a viernes)")], max_length=10, verbose_name="Tipo de dias del plazo de entrega"),
        ),
        migrations.AddField(
            model_name="foreigntenderprocess",
            name="delivery_term_days",
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name="Cantidad de dias del plazo de entrega"),
        ),
    ]
