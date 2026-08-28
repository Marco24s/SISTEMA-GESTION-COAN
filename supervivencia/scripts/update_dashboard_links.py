import os

filepath = r"c:\Materias-Grasas\supervivencia\templates\supervivencia\dashboard.html"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# Replace links in dashboard
content = content.replace(
    """<a href="{% url 'supervivencia:physical_item_list' %}" class="text-decoration-none text-dark">
                <div class="card border-0 shadow-sm h-100">
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-start">
                            <div>
                                <div class="text-muted small text-uppercase fw-bold">Material activo</div>""",
    """<a href="{% url 'supervivencia:physical_item_list' %}?active=1" class="text-decoration-none text-dark">
                <div class="card border-0 shadow-sm h-100">
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-start">
                            <div>
                                <div class="text-muted small text-uppercase fw-bold">Material activo</div>"""
)

content = content.replace(
    """<a href="{% url 'supervivencia:physical_item_list' %}?status=INSTALLED" class="text-decoration-none text-dark">""",
    """<a href="{% url 'supervivencia:physical_item_list' %}?active=1&status=INSTALLED" class="text-decoration-none text-dark">"""
)

content = content.replace(
    """<a href="{% url 'supervivencia:physical_item_list' %}?status=STOCK" class="text-decoration-none">""",
    """<a href="{% url 'supervivencia:physical_item_list' %}?active=1&status=STOCK" class="text-decoration-none">"""
)

content = content.replace(
    """<a href="{% url 'supervivencia:physical_item_list' %}" class="text-decoration-none">
                <div class="card border-0 shadow-sm h-100">
                    <div class="card-body">
                        <div class="text-muted small text-uppercase fw-bold">Otros (Removidos, etc)</div>""",
    """<a href="{% url 'supervivencia:physical_item_list' %}?active=1&status=OTHER" class="text-decoration-none">
                <div class="card border-0 shadow-sm h-100">
                    <div class="card-body">
                        <div class="text-muted small text-uppercase fw-bold">Otros (Removidos, etc)</div>"""
)

content = content.replace(
    """<a href="{% url 'supervivencia:physical_item_list' %}?expiration=expired" class="text-decoration-none">""",
    """<a href="{% url 'supervivencia:physical_item_list' %}?active=1&expiration=expired" class="text-decoration-none">"""
)

content = content.replace(
    """<a href="{% url 'supervivencia:physical_item_list' %}?expiration=next_6_months" class="text-decoration-none">""",
    """<a href="{% url 'supervivencia:physical_item_list' %}?active=1&expiration=next_6_months" class="text-decoration-none">"""
)

content = content.replace(
    """<a href="{% url 'supervivencia:physical_item_list' %}?expiration=next_1_year" class="text-decoration-none">""",
    """<a href="{% url 'supervivencia:physical_item_list' %}?active=1&expiration=next_1_year" class="text-decoration-none">"""
)

content = content.replace(
    """<a href="{% url 'supervivencia:physical_item_list' %}?expiration=next_2_years" class="text-decoration-none">""",
    """<a href="{% url 'supervivencia:physical_item_list' %}?active=1&expiration=next_2_years" class="text-decoration-none">"""
)


with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)
