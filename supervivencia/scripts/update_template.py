import os

filepath = r"c:\Materias-Grasas\supervivencia\templates\supervivencia\physical_item_list.html"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# Replace the search form
old_form = """        <form method="get" class="row g-2 align-items-end">
            <div class="col-md-3">
                <label class="form-label small text-muted mb-1">Buscar</label>
                <input type="search" name="q" value="{{ search_query }}" class="form-control" placeholder="Serie, lote, material, ubicación">
            </div>
            <div class="col-md-2">
                <label class="form-label small text-muted mb-1">Condición</label>
                <select name="condition" class="form-select">
                    <option value="">Todas</option>
                    {% for value,label in condition_choices %}
                        <option value="{{ value }}" {% if selected_condition == value %}selected{% endif %}>{{ label }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="col-md-2">
                <label class="form-label small text-muted mb-1">Estado</label>
                <select name="status" class="form-select">
                    <option value="">Todos</option>
                    {% for value,label in status_choices %}
                        <option value="{{ value }}" {% if selected_status == value %}selected{% endif %}>{{ label }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="col-md-2">
                <label class="form-label small text-muted mb-1">Vencimiento</label>
                <select name="expiration" class="form-select">
                    <option value="">Todos</option>
                    <option value="expired" {% if selected_expiration == "expired" %}selected{% endif %}>Vencidos</option>
                    <option value="next_6_months" {% if selected_expiration == "next_6_months" %}selected{% endif %}>Próx. 6 meses</option>
                    <option value="next_1_year" {% if selected_expiration == "next_1_year" %}selected{% endif %}>6 meses a 1 año</option>
                    <option value="next_2_years" {% if selected_expiration == "next_2_years" %}selected{% endif %}>1 a 2 años</option>
                </select>
            </div>
            <div class="col-md-2">
                <label class="form-label small text-muted mb-1">Ubicacion</label>
                <select name="location" class="form-select">
                    <option value="">Todas</option>
                    {% for location in locations %}
                        <option value="{{ location.id }}" {% if selected_location == location.id|stringformat:"s" %}selected{% endif %}>{{ location.code }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="col-md-1 d-grid">
                <button type="submit" class="btn btn-outline-danger"><i class="fa-solid fa-filter me-1"></i> Filtrar</button>
            </div>
        </form>"""

new_form = """        <form method="get" class="row g-2 align-items-end">
            <div class="col-md-4 col-lg-3">
                <label class="form-label small text-muted mb-1">Buscar</label>
                <input type="search" name="q" value="{{ search_query }}" class="form-control" placeholder="NSN, Serie, lote, material...">
            </div>
            <div class="col-md-4 col-lg-3">
                <label class="form-label small text-muted mb-1">Sistema</label>
                <select name="system" class="form-select">
                    <option value="">Todos</option>
                    {% for sys in systems %}
                        <option value="{{ sys.id }}" {% if selected_system == sys.id|stringformat:"s" %}selected{% endif %}>{{ sys.classification.name }} - {{ sys.name }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="col-md-4 col-lg-2">
                <label class="form-label small text-muted mb-1">Uso / Medio</label>
                <select name="medium" class="form-select">
                    <option value="">Todos</option>
                    {% for med in mediums %}
                        <option value="{{ med.name }}" {% if selected_medium == med.name %}selected{% endif %}>{{ med.name }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="col-md-4 col-lg-2">
                <label class="form-label small text-muted mb-1">Vencimiento</label>
                <select name="expiration" class="form-select">
                    <option value="">Todos</option>
                    <option value="expired" {% if selected_expiration == "expired" %}selected{% endif %}>Vencidos</option>
                    <option value="next_6_months" {% if selected_expiration == "next_6_months" %}selected{% endif %}>Próx. 6 meses</option>
                    <option value="next_1_year" {% if selected_expiration == "next_1_year" %}selected{% endif %}>6 meses a 1 año</option>
                    <option value="next_2_years" {% if selected_expiration == "next_2_years" %}selected{% endif %}>1 a 2 años</option>
                </select>
            </div>
            <div class="col-md-4 col-lg-2">
                <label class="form-label small text-muted mb-1">Condición</label>
                <select name="condition" class="form-select">
                    <option value="">Todas</option>
                    {% for value,label in condition_choices %}
                        <option value="{{ value }}" {% if selected_condition == value %}selected{% endif %}>{{ label }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="col-md-4 col-lg-2">
                <label class="form-label small text-muted mb-1">Estado</label>
                <select name="status" class="form-select">
                    <option value="">Todos</option>
                    {% for value,label in status_choices %}
                        <option value="{{ value }}" {% if selected_status == value %}selected{% endif %}>{{ label }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="col-md-4 col-lg-2">
                <label class="form-label small text-muted mb-1">Ubicación</label>
                <select name="location" class="form-select">
                    <option value="">Todas</option>
                    {% for location in locations %}
                        <option value="{{ location.id }}" {% if selected_location == location.id|stringformat:"s" %}selected{% endif %}>{{ location.code }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="col-md-4 col-lg-2 d-grid">
                <button type="submit" class="btn btn-outline-danger"><i class="fa-solid fa-filter me-1"></i> Filtrar</button>
            </div>
        </form>"""

content = content.replace(old_form, new_form)

# Replace table head
old_thead = """                <thead class="table-light">
                    <tr>
                        <th>Material</th>
                        <th>Serie / Lote</th>
                        <th>Fabricante</th>
                        <th>Vencimiento</th>
                        <th>Condición</th>
                        <th>Estado</th>
                        <th>Ubicación</th>
                        <th>Activo</th>
                        <th class="text-end">Acciones</th>
                    </tr>
                </thead>"""

new_thead = """                <thead class="table-light">
                    <tr>
                        <th>Material</th>
                        <th>Clasificación / Sistema</th>
                        <th>Medios / Unidades Compatibles</th>
                        <th>Serie / Lote</th>
                        <th>Vencimiento</th>
                        <th>Condición / Estado</th>
                        <th>Ubicación</th>
                        <th>Activo</th>
                        <th class="text-end">Acciones</th>
                    </tr>
                </thead>"""

content = content.replace(old_thead, new_thead)

# Replace table body
old_tbody = """                    <tr>
                        <td>
                            <strong>{{ item.catalog_item.nomenclature }}</strong>
                            <br><small class="text-muted">Sis: {{ item.catalog_item.system }}</small>
                            {% if item.catalog_item.part_number %}<br><small class="text-muted">N°: {{ item.catalog_item.part_number }}</small>{% endif %}
                        </td>
                        <td>
                            {% if item.serial_number %}<div>Serie: <strong>{{ item.serial_number }}</strong></div>{% endif %}
                            {% if item.lot_number %}<div>Lote: <strong>{{ item.lot_number }}</strong></div>{% endif %}
                            <div>Cantidad: <strong>{{ item.lot_quantity }}</strong></div>
                            {% if not item.serial_number and not item.lot_number %}<span class="text-muted">Sin identificar</span>{% endif %}
                        </td>
                        <td>{{ item.manufacturer|default:"-" }}</td>
                        <td>
                            <strong class="{% if item.is_expired %}text-danger{% endif %}">{{ item.expiration_date|date:"d/m/Y" }}</strong>
                            {% if item.is_expired %}<br><span class="badge bg-danger">Vencido</span>{% endif %}
                        </td>
                        <td><span class="badge bg-light text-dark border">{{ item.get_condition_display }}</span></td>
                        <td><span class="badge bg-secondary">{{ item.get_operational_status_display }}</span></td>
                        <td>
                            {% if item.current_storage_location %}
                                <span class="badge bg-light text-dark border">{{ item.current_storage_location.code }}</span>
                                <br><small class="text-muted">{{ item.current_storage_location.name }}</small>
                            {% else %}
                                {{ item.current_location }}
                            {% endif %}
                        </td>
                        <td>{% if item.is_active %}<span class="badge bg-success">Si</span>{% else %}<span class="badge bg-secondary">No</span>{% endif %}</td>
                        <td class="text-end">"""

new_tbody = """                    <tr>
                        <td>
                            <strong>{{ item.catalog_item.nomenclature }}</strong>
                            {% if item.catalog_item.part_number %}<br><small class="text-muted">N°: {{ item.catalog_item.part_number }}</small>{% endif %}
                            {% if item.catalog_item.nsn %}<br><small class="text-muted" title="N.S.N">NSN: {{ item.catalog_item.nsn }}</small>{% endif %}
                            {% if item.catalog_item.alternate_part_number or item.catalog_item.alternate_nsn %}
                            <br><small class="text-info" title="Alt PN: {{ item.catalog_item.alternate_part_number|default:'-' }} | Alt NSN: {{ item.catalog_item.alternate_nsn|default:'-' }}"><i class="fa-solid fa-circle-info"></i> Reemplazos</small>
                            {% endif %}
                        </td>
                        <td>
                            <span class="badge bg-light text-dark border">{{ item.catalog_item.system.classification.name }}</span>
                            <br><small class="text-muted">{{ item.catalog_item.system.name }}</small>
                        </td>
                        <td>
                            {% if item.catalog_item.compatible_medium_names %}
                                <small class="text-muted">{{ item.catalog_item.compatible_medium_names }}</small>
                            {% else %}
                                <span class="text-muted">-</span>
                            {% endif %}
                        </td>
                        <td>
                            {% if item.serial_number %}<div>Serie: <strong>{{ item.serial_number }}</strong></div>{% endif %}
                            {% if item.lot_number %}<div>Lote: <strong>{{ item.lot_number }}</strong></div>{% endif %}
                            <div>Cantidad: <strong>{{ item.lot_quantity }}</strong></div>
                            {% if item.manufacturer %}<div><small class="text-muted">Fab: {{ item.manufacturer }}</small></div>{% endif %}
                            {% if not item.serial_number and not item.lot_number %}<span class="text-muted">Sin identificar</span>{% endif %}
                        </td>
                        <td>
                            <strong class="{% if item.is_expired %}text-danger{% endif %}">{{ item.expiration_date|date:"d/m/Y" }}</strong>
                            {% if item.is_expired %}<br><span class="badge bg-danger">Vencido</span>{% endif %}
                            {% if item.manufacture_date %}<br><small class="text-muted">Fab: {{ item.manufacture_date|date:"d/m/Y" }}</small>{% endif %}
                        </td>
                        <td>
                            <div><span class="badge bg-light text-dark border">{{ item.get_condition_display }}</span></div>
                            <div class="mt-1"><span class="badge bg-secondary">{{ item.get_operational_status_display }}</span></div>
                        </td>
                        <td>
                            {% if item.current_storage_location %}
                                <span class="badge bg-light text-dark border">{{ item.current_storage_location.code }}</span>
                                <br><small class="text-muted">{{ item.current_storage_location.name }}</small>
                            {% else %}
                                {{ item.current_location }}
                            {% endif %}
                            {% if item.certificate_reference %}<br><small class="text-info"><i class="fa-solid fa-file-contract"></i> {{ item.certificate_reference }}</small>{% endif %}
                        </td>
                        <td>{% if item.is_active %}<span class="badge bg-success">Si</span>{% else %}<span class="badge bg-secondary">No</span>{% endif %}</td>
                        <td class="text-end">"""

content = content.replace(old_tbody, new_tbody)

# also replace colspan="9" with colspan="9" since columns count didn't change (9 columns)

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)
