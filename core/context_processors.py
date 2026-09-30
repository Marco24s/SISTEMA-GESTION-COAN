from django.conf import settings
from django.utils import timezone


def app_version(request):
    version = getattr(settings, "APP_VERSION", None)
    if not version:
        now = timezone.now()
        year_2digit = now.strftime("%y")
        month_2digit = now.strftime("%m")
        build = getattr(settings, "APP_VERSION_BUILD", 1)
        version = f"v{year_2digit}13.{month_2digit}.{build}"
    return {
        "APP_VERSION": version
    }
