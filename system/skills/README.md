# Skills operativas del proyecto

Este directorio contiene conocimiento operativo interno para evitar decisiones improvisadas.

Flujo esperado:

1. Consultar skills internas.
2. Aplicar parametros estandar.
3. Verificar si ya existe una solucion conocida.
4. Crear logica nueva o buscar afuera solo si no hay una skill aplicable.

Formato principal: `project_skills.json`.

Cada skill puede definir:

- `name`: identificador unico.
- `version`: version semantica.
- `enabled`: habilita o deshabilita la skill.
- `priority`: `critical`, `high`, `medium` o `low`.
- `domain`: area funcional.
- `tags`: palabras para busqueda deterministica.
- `rules`: reglas operativas.
- `defaults`: parametros por defecto.
- `extends`: nombres de skills base a componer.
- `conflicts_with`: skills incompatibles.

Uso desde codigo:

```python
from core.skills import find_skills, get_skill_registry, resolve_operational_context

skills = find_skills(tags=["django", "security"])
context = resolve_operational_context(query="nuevo modulo con PIN", tags=["django"])
registry = get_skill_registry()
conflicts = registry.detect_conflicts()
```

Uso desde consola Django:

```powershell
python manage.py skills validate
python manage.py skills list
python manage.py skills search --tag django --query pin
```
