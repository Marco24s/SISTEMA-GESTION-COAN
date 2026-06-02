from django.core.management.base import BaseCommand, CommandError

from core.skills import SkillValidationError, get_skill_registry


class Command(BaseCommand):
    help = "Gestiona el registro interno de skills operativas."

    def add_arguments(self, parser):
        subparsers = parser.add_subparsers(dest="action")

        subparsers.add_parser("validate", help="Valida estructura, prioridades y conflictos.")

        list_parser = subparsers.add_parser("list", help="Lista skills cargadas.")
        list_parser.add_argument("--all", action="store_true", help="Incluye skills deshabilitadas.")

        search_parser = subparsers.add_parser("search", help="Busca skills por texto, tag o dominio.")
        search_parser.add_argument("--query", default="", help="Texto a buscar.")
        search_parser.add_argument("--tag", action="append", default=[], help="Tag requerido. Puede repetirse.")
        search_parser.add_argument("--domain", default="", help="Dominio requerido.")
        search_parser.add_argument("--limit", type=int, default=10, help="Cantidad maxima de resultados.")

        show_parser = subparsers.add_parser("show", help="Muestra el detalle de una skill.")
        show_parser.add_argument("name", help="Nombre de la skill.")

    def handle(self, *args, **options):
        action = options.get("action")
        if not action:
            raise CommandError("Indique una accion: validate, list, search o show.")

        registry = get_skill_registry()

        try:
            registry.load(force=True)
        except SkillValidationError as exc:
            raise CommandError(str(exc)) from exc

        if action == "validate":
            self._validate(registry)
        elif action == "list":
            self._list(registry, include_disabled=options["all"])
        elif action == "search":
            self._search(registry, options)
        elif action == "show":
            self._show(registry, options["name"])
        else:
            raise CommandError(f"Accion desconocida: {action}")

    def _validate(self, registry):
        errors = registry.validate()
        if errors:
            for error in errors:
                self.stderr.write(f"ERROR: {error}")
            raise CommandError("El registro de skills tiene errores.")
        self.stdout.write(self.style.SUCCESS("Skills validas. No se detectaron conflictos."))

    def _list(self, registry, include_disabled=False):
        skills = registry.all(include_disabled=include_disabled)
        if not skills:
            self.stdout.write("No hay skills cargadas.")
            return
        for skill in skills:
            status = "activa" if skill.enabled else "inactiva"
            self.stdout.write(f"{skill.name} [{skill.priority}] v{skill.version} - {skill.domain} - {status}")

    def _search(self, registry, options):
        skills = registry.search(
            query=options["query"] or None,
            tags=options["tag"],
            domain=options["domain"] or None,
            limit=options["limit"],
        )
        if not skills:
            self.stdout.write("No se encontraron skills.")
            return
        for skill in skills:
            tags = ", ".join(skill.tags)
            self.stdout.write(f"{skill.name} [{skill.priority}] tags: {tags}")
            self.stdout.write(f"  {skill.description}")

    def _show(self, registry, name):
        skill = registry.get(name)
        if not skill:
            raise CommandError(f"No existe una skill activa llamada {name}.")

        self.stdout.write(f"{skill.name} v{skill.version}")
        self.stdout.write(f"Prioridad: {skill.priority}")
        self.stdout.write(f"Dominio: {skill.domain}")
        self.stdout.write(f"Tags: {', '.join(skill.tags)}")
        self.stdout.write(f"Descripcion: {skill.description}")
        self.stdout.write("Reglas:")
        for rule in skill.rules:
            self.stdout.write(f"  - {rule}")
        if skill.defaults:
            self.stdout.write("Defaults:")
            for key, value in skill.defaults.items():
                self.stdout.write(f"  - {key}: {value}")
