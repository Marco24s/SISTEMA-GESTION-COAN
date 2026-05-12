from django.shortcuts import render, redirect
from django.contrib import messages
from .models import BudgetAllocation, InsufficientFundsError
from . import services

def registrar_compromiso_view(request):
    """
    Ejemplo de cómo consumir el servicio register_commitment en una vista.
    """
    if request.method == 'POST':
        allocation_id = request.POST.get('allocation_id')
        monto = request.POST.get('monto')
        referencia = request.POST.get('referencia')
        
        try:
            # Llamamos al servicio (la transacción y el bloqueo ocurren dentro)
            services.register_commitment(
                allocation_id=allocation_id,
                reference_code=referencia,
                amount=monto,
                commitment_date=timezone.now().date(),
                user=request.user
            )
            messages.success(request, "¡Éxito! El compromiso ha sido registrado.")
            return redirect('budget:list_executions')
            
        except InsufficientFundsError as e:
            # Capturamos el error de saldo específicamente
            messages.error(request, f"Error de presupuesto: {e}")
        except Exception as e:
            # Errores técnicos o de validación general
            messages.error(request, f"Ocurrió un error: {e}")
            
    return render(request, 'budget/registro.html', ...)
