# Sistema de Skills Persistentes

## Objetivo

El proyecto cuenta con una capa de conocimiento operativo interno para consultar reglas, parametros, convenciones y flujos conocidos antes de improvisar logica o buscar informacion externa.

## Arquitectura

- `system/skills/project_skills.json`: archivo central versionado con skills habilitadas.
- `core/skills.py`: loader, parser, cache en memoria, busqueda y deteccion de conflictos.
- `core/apps.py`: carga automatica de skills al iniciar Django.
- `core/management/commands/skills.py`: comando interno para validar, listar y buscar skills.

## Flujo Deterministico

1. Cargar skills habilitadas desde `system/skills`.
2. Resolver herencia y composicion mediante `extends`.
3. Ordenar por prioridad y version.
4. Buscar por tags, dominio o texto.
5. Aplicar la skill con mayor prioridad.
6. Si hay conflictos, reportarlos antes de tomar una decision.

## Prioridades

Orden de mayor a menor:

1. `critical`
2. `high`
3. `medium`
4. `low`

Si dos skills empatan en prioridad, se prioriza la version mas nueva.

## Busqueda

La busqueda es deterministica y sin dependencias externas:

- Coincidencia exacta por tags.
- Coincidencia por dominio.
- Puntaje por palabras presentes en nombre, descripcion, reglas y parametros.

## Integracion con el flujo principal

Antes de resolver una tarea, el flujo interno puede pedir un contexto operativo:

```python
from core.skills import resolve_operational_context

context = resolve_operational_context(
    query="crear modulo con acceso por PIN",
    tags=["django", "security"],
)

for skill in context["skills"]:
    aplicar(skill.rules)
```

Ese contexto devuelve:

- `defaults`: parametros del proyecto combinados con los defaults de las skills aplicables.
- `skills`: skills habilitadas ordenadas por prioridad.
- `conflicts`: conflictos activos detectados.

## Extensibilidad

Para agregar una skill:

1. Editar `system/skills/project_skills.json`.
2. Agregar un objeto a `skills`.
3. Definir `name`, `version`, `enabled`, `priority`, `domain`, `tags`, `rules` y `defaults`.
4. Validar con `python manage.py skills validate`.

## Ejemplo

```json
{
  "name": "api_request_standard",
  "version": "1.0.0",
  "enabled": true,
  "priority": "medium",
  "tags": ["api", "networking"],
  "rules": [
    "usar timeout de 30 segundos",
    "retry maximo 3 veces",
    "loggear errores HTTP",
    "validar JSON de respuesta"
  ],
  "defaults": {
    "timeout": 30,
    "retries": 3
  }
}
```
