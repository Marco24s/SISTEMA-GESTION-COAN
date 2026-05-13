import functools
import time
from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.contrib import messages

def pin_required(system):
    """
    Decorator for views that checks if the user has verified their security PIN
    for a specific system within the allowed time frame.
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            # 1. Basic validation: User must be authenticated
            if not request.user.is_authenticated:
                return redirect(f"{settings.LOGIN_URL}?next={request.path}")

            # 2. Parameter validation
            allowed_systems = getattr(settings, 'PIN_ALLOWED_SYSTEMS', [])
            if system not in allowed_systems:
                # Configuration error, fallback to safety
                messages.error(request, "Error de configuración de seguridad.")
                return redirect('portal')

            # 3. Check if user has access to this system
            from .models import UserSystemPIN
            user_access = UserSystemPIN.objects.filter(user=request.user, system_code=system).exists()
            if not user_access:
                messages.error(request, f"No tiene permisos de acceso por PIN para el sistema {system.upper()}.")
                return redirect('portal')

            # 4. Brute force check
            pin_attempts = request.session.get('pin_attempts', {})
            blocked_until = pin_attempts.get('blocked_until')
            if blocked_until and time.time() < blocked_until:
                time_left = int((blocked_until - time.time()) / 60) + 1
                messages.error(request, f"Acceso bloqueado temporalmente por demasiados intentos fallidos. Intente en {time_left} min.")
                return redirect('portal')

            # 5. Check PIN verification status in session
            verified_pins = request.session.get('verified_pins', {})
            verification_timestamp = verified_pins.get(system)
            
            expiration_seconds = getattr(settings, 'PIN_EXPIRATION_MINUTES', 20) * 60
            
            is_verified = False
            if verification_timestamp:
                # Check if it has expired
                if (time.time() - verification_timestamp) < expiration_seconds:
                    is_verified = True
                else:
                    # Expired, clean it
                    del verified_pins[system]
                    request.session['verified_pins'] = verified_pins

            if not is_verified:
                # Redirect to verification view
                safe_next = request.path if url_has_allowed_host_and_scheme(request.path, allowed_hosts={request.get_host()}) else 'portal'
                return redirect(f"{reverse('verify_pin')}?system={system}&next={safe_next}")

            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator
