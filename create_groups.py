import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import Group

groups = ['Admin', 'Supervisor', 'Capturista', 'Solicitante', 'Consulta']
for group_name in groups:
    group, created = Group.objects.get_or_create(name=group_name)
    if created:
        print(f"Created group: {group_name}")
    else:
        print(f"Group already exists: {group_name}")
