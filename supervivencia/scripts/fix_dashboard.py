import os

filepath = r"c:\Materias-Grasas\supervivencia\templates\supervivencia\dashboard.html"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

start_idx = content.find('<div class="row g-3 mb-4">')
end_idx = content.find('<div class="row g-4">')

new_grid = """<div class="row g-3 mb-4">
        <!-- MATERIAL ACTIVO -->
        <div class="col-md-6 col-xl-3">
            <a href="{% url 'supervivencia:physical_item_list' %}" class="text-decoration-none text-dark">
                <div class="card border-0 shadow-sm h-100">
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-start">
                            <div>
                                <div class="text-muted small text-uppercase fw-bold">Material activo</div>
                                <div class="display-6 fw-bold">{{ total_active_material }}</div>
                            </div>
                            <i class="fa-solid fa-barcode text-danger fs-3"></i>
                        </div>
                    </div>
                </div>
            </a>
        </div>
        <!-- MONTADOS -->
        <div class="col-md-6 col-xl-3">
            <a href="{% url 'supervivencia:physical_item_list' %}?status=INSTALLED" class="text-decoration-none text-dark">
                <div class="card border-0 shadow-sm h-100">
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-start">
                            <div>
                                <div class="text-muted small text-uppercase fw-bold">Montados</div>
                                <div class="display-6 fw-bold">{{ mounted_count }}</div>
                            </div>
                            <i class="fa-solid fa-link text-danger fs-3"></i>
                        </div>
                    </div>
                </div>
            </a>
        </div>
        <!-- EN DEPOSITO / STOCK -->
        <div class="col-md-6 col-xl-3">
            <a href="{% url 'supervivencia:physical_item_list' %}?status=STOCK" class="text-decoration-none">
                <div class="card border-0 shadow-sm h-100">
                    <div class="card-body">
                        <div class="text-muted small text-uppercase fw-bold">En deposito / stock</div>
                        <div class="display-6 fw-bold text-primary">{{ stock_count }}</div>
                    </div>
                </div>
            </a>
        </div>
        <!-- OTROS ESTADOS -->
        <div class="col-md-6 col-xl-3">
            <a href="{% url 'supervivencia:physical_item_list' %}" class="text-decoration-none">
                <div class="card border-0 shadow-sm h-100">
                    <div class="card-body">
                        <div class="text-muted small text-uppercase fw-bold">Otros (Removidos, etc)</div>
                        <div class="display-6 fw-bold text-secondary">{{ other_status_count }}</div>
                    </div>
                </div>
            </a>
        </div>
    </div>

    <div class="row g-3 mb-4">
        <!-- VENCIDOS -->
        <div class="col-md-6 col-xl-2">
            <a href="{% url 'supervivencia:physical_item_list' %}?expiration=expired" class="text-decoration-none">
                <div class="card border-0 shadow-sm h-100 border-start border-danger border-4">
                    <div class="card-body p-3">
                        <div class="text-muted small text-uppercase fw-bold">Vencidos</div>
                        <div class="h3 mb-0 text-danger">{{ expired_count }}</div>
                    </div>
                </div>
            </a>
        </div>
        <!-- VENCEN EN 6 MESES -->
        <div class="col-md-6 col-xl-2">
            <a href="{% url 'supervivencia:physical_item_list' %}?expiration=next_6_months" class="text-decoration-none">
                <div class="card border-0 shadow-sm h-100 border-start border-warning border-4">
                    <div class="card-body p-3">
                        <div class="text-muted small text-uppercase fw-bold">Próx. 6 meses</div>
                        <div class="h3 mb-0 text-warning">{{ next_6_months_count }}</div>
                    </div>
                </div>
            </a>
        </div>
        <!-- VENCEN 6 A 12 MESES -->
        <div class="col-md-6 col-xl-2">
            <a href="{% url 'supervivencia:physical_item_list' %}?expiration=next_1_year" class="text-decoration-none">
                <div class="card border-0 shadow-sm h-100 border-start border-info border-4">
                    <div class="card-body p-3">
                        <div class="text-muted small text-uppercase fw-bold">6 a 12 meses</div>
                        <div class="h3 mb-0 text-info">{{ next_1_year_count }}</div>
                    </div>
                </div>
            </a>
        </div>
        <!-- VENCEN 1 A 2 AÑOS -->
        <div class="col-md-6 col-xl-2">
            <a href="{% url 'supervivencia:physical_item_list' %}?expiration=next_2_years" class="text-decoration-none">
                <div class="card border-0 shadow-sm h-100 border-start border-secondary border-4">
                    <div class="card-body p-3">
                        <div class="text-muted small text-uppercase fw-bold">1 a 2 años</div>
                        <div class="h3 mb-0 text-secondary">{{ next_2_years_count }}</div>
                    </div>
                </div>
            </a>
        </div>
        
        <!-- MEDIOS Y CATALOGO (MENOS PRINCIPALES) -->
        <div class="col-md-12 col-xl-4">
            <div class="card border-0 shadow-sm h-100 bg-light">
                <div class="card-body p-2 d-flex flex-column justify-content-center">
                    <div class="text-muted small text-uppercase fw-bold mb-2 px-2"><i class="fa-solid fa-database me-1"></i> Registros</div>
                    <div class="d-flex gap-2 px-2">
                        <a href="{% url 'supervivencia:medium_list' %}" class="flex-fill d-flex justify-content-between align-items-center text-decoration-none text-dark p-2 bg-white rounded border">
                            <span class="small fw-semibold"><i class="fa-solid fa-helicopter text-muted me-1"></i> Medios</span>
                            <span class="badge bg-secondary">{{ medium_count }}</span>
                        </a>
                        <a href="{% url 'supervivencia:catalog_list' %}" class="flex-fill d-flex justify-content-between align-items-center text-decoration-none text-dark p-2 bg-white rounded border">
                            <span class="small fw-semibold"><i class="fa-solid fa-boxes-stacked text-muted me-1"></i> Catálogo</span>
                            <span class="badge bg-secondary">{{ catalog_count }}</span>
                        </a>
                    </div>
                </div>
            </div>
        </div>
    </div>

    """

new_content = content[:start_idx] + new_grid + content[end_idx:]

with open(filepath, "w", encoding="utf-8") as f:
    f.write(new_content)
