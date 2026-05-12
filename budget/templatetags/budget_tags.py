from django import template

register = template.Library()

@register.filter
def credit_type_badge_color(credit_type_code):
    """
    Retorna la clase de color del badge según el tipo de crédito.
    - ASIGNACION: bg-primary (azul)
    - REFUERZO: bg-warning (amarillo)
    - Otros: bg-secondary (gris)
    """
    if not credit_type_code:
        return 'bg-secondary'
    
    code = str(credit_type_code).upper().strip()
    
    if code == 'ASIGNACION':
        return 'bg-primary'
    elif code == 'REFUERZO':
        return 'bg-warning'
    else:
        return 'bg-secondary'
