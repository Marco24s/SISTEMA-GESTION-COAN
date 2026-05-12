from django import template
from decimal import Decimal

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
