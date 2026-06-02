import time
from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages
from django.utils.http import url_has_allowed_host_and_scheme

class PINSecurityMiddleware:
    """
    Middleware que protege todos los accesos a SGMG, SIGERA y SGP.
    Verifica si el usuario tiene permiso (UserSystemPIN) y si ya validó su sesión.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 1. Ignorar si el usuario no está logueado (Django ya maneja login_required)
        if not request.user.is_authenticated:
            return self.get_response(request)

        path = request.path
        
        # 2. Determinar a qué sistema pertenece la URL actual
        system = None
        if path.startswith('/sigera/'):
            system = 'sigera'
        elif path.startswith('/budget/'):
            system = 'sgp'
        elif path.startswith('/licitaciones/') or path.startswith('/licitas/'):
            system = 'licitaciones'
        elif path.startswith('/supervivencia/'):
            system = 'supervivencia'
        # Rutas de SGMG (core) que no son el portal, admin o seguridad
        elif not any(path.startswith(p) for p in ['/admin/', '/accounts/', '/security/', '/static/', '/media/', '/__debug__/']):
            # Excluir archivos comunes que el navegador pide automáticamente en la raíz
            ignored_extensions = ['.ico', '.png', '.jpg', '.jpeg', '.gif', '.json', '.txt', '.xml', '.webmanifest']
            if not any(path.lower().endswith(ext) for ext in ignored_extensions):
                if path != '/' and path != reverse('portal'):
                    system = 'sgmg'

        # Si no es una ruta protegida por PIN, dejar pasar
        if not system:
            return self.get_response(request)

        # 3. Excepciones: Permitir acceso a las vistas de validación propiamente dichas
        if path.startswith(reverse('verify_pin')) or path.startswith(reverse('create_pin')):
            return self.get_response(request)

        # 4. Verificar si el usuario tiene el permiso de acceso (registro en UserSystemPIN)
        from core.models import UserSystemPIN
        has_access = UserSystemPIN.objects.filter(user=request.user, system_code=system).exists()
        
        if not has_access:
            messages.error(request, f"Acceso denegado: No tiene permisos de PIN para el sistema {system.upper()}.")
            return redirect('portal')

        # 5. Verificar si el PIN ya fue validado en esta sesión y no ha expirado
        verified_pins = request.session.get('verified_pins', {})
        verification_timestamp = verified_pins.get(system)
        expiration_seconds = getattr(settings, 'PIN_EXPIRATION_MINUTES', 20) * 60
        
        is_verified = False
        if verification_timestamp:
            if (time.time() - verification_timestamp) < expiration_seconds:
                is_verified = True
            else:
                # Expiró, limpiar sesión de este sistema
                del verified_pins[system]
                request.session['verified_pins'] = verified_pins

        # 6. Si no está verificado, redirigir a la pantalla de ingreso de PIN
        if not is_verified:
            safe_next = request.path if url_has_allowed_host_and_scheme(request.path, allowed_hosts={request.get_host()}) else 'portal'
            return redirect(f"{reverse('verify_pin')}?system={system}&next={safe_next}")

        return self.get_response(request)
