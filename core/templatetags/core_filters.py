from django import template
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP

register = template.Library()

@register.filter
def smart_number(value):
    """
    Format a number to drop decimal part if it's zero, 
    but preserve true decimal precision (e.g. 0.2000 -> 0.2).
    """
    try:
        if isinstance(value, Decimal):
            d = value.normalize()
            if d == d.to_integral():
                return int(d)
            return d
            
        f_val = float(value)
        rounded_val = round(f_val, 4)
        if rounded_val.is_integer():
            return int(rounded_val)
        return rounded_val
    except (ValueError, TypeError):
        return value

@register.filter
def quantity_2(value):
    """
    Format quantities with at most 2 decimals, dropping trailing zeros.
    """
    try:
        d = Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP).normalize()
        if d == d.to_integral():
            return int(d)
        return d
    except Exception:
        return value

@register.filter
def container_label(quantity, batch):
    """
    Return an approximate container count label for a batch quantity.
    """
    try:
        if not batch or not getattr(batch, 'container_size', None):
            return ''

        container_size = Decimal(str(batch.container_size))
        if container_size <= 0:
            return ''

        count = int((Decimal(str(quantity)) / container_size).to_integral_value(rounding=ROUND_CEILING))
        unit = "lata" if count == 1 else "latas"
        return f"{count} {unit}"
    except Exception:
        return ''

@register.filter
def abs_val(value):
    """
    Returns the absolute value of a number.
    """
    try:
        return abs(value)
    except TypeError:
        return value
@register.filter
def add_decimal_inverse(value, arg):
    """
    Substracts the argument from the value (value - arg).
    Used to calculate shortfalls.
    """
    try:
        return Decimal(str(value)) - Decimal(str(arg))
    except Exception:
        return value
