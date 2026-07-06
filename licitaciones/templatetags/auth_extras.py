from django import template

register = template.Library()

@register.filter(name='has_group')
def has_group(user, group_name):
    if user.is_superuser:
        return True
    return user.groups.filter(name=group_name).exists()

@register.filter(name='has_any_group')
def has_any_group(user, group_names_str):
    if user.is_superuser:
        return True
    group_names = [name.strip() for name in group_names_str.split(',')]
    return user.groups.filter(name__in=group_names).exists()
