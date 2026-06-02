from __future__ import annotations

import json
import logging
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from django.conf import settings


logger = logging.getLogger(__name__)

PRIORITY_WEIGHTS = {
    "critical": 400,
    "high": 300,
    "medium": 200,
    "low": 100,
}

TOKEN_RE = re.compile(r"[a-zA-Z0-9_áéíóúÁÉÍÓÚñÑ°/.+-]+")


class SkillError(RuntimeError):
    """Base exception for skill registry problems."""


class SkillValidationError(SkillError):
    """Raised when a skill file has an invalid structure."""


@dataclass(frozen=True)
class Skill:
    name: str
    version: str
    enabled: bool
    priority: str
    domain: str
    tags: tuple[str, ...] = field(default_factory=tuple)
    description: str = ""
    rules: tuple[str, ...] = field(default_factory=tuple)
    defaults: dict[str, Any] = field(default_factory=dict)
    tools: tuple[str, ...] = field(default_factory=tuple)
    examples: tuple[str, ...] = field(default_factory=tuple)
    extends: tuple[str, ...] = field(default_factory=tuple)
    conflicts_with: tuple[str, ...] = field(default_factory=tuple)
    source: str = ""

    @property
    def priority_weight(self) -> int:
        return PRIORITY_WEIGHTS.get(self.priority, 0)

    @property
    def version_key(self) -> tuple[int, ...]:
        parts = []
        for part in self.version.split("."):
            try:
                parts.append(int(part))
            except ValueError:
                parts.append(0)
        return tuple(parts)

    def searchable_text(self) -> str:
        payload = [
            self.name,
            self.version,
            self.priority,
            self.domain,
            self.description,
            " ".join(self.tags),
            " ".join(self.rules),
            json.dumps(self.defaults, ensure_ascii=False, sort_keys=True),
            " ".join(self.tools),
            " ".join(self.examples),
        ]
        return " ".join(payload).lower()


class SkillRegistry:
    def __init__(self, skills_dir: str | Path | None = None):
        default_dir = Path(settings.BASE_DIR) / "system" / "skills"
        self.skills_dir = Path(skills_dir or getattr(settings, "SKILLS_DIR", default_dir))
        self._skills: dict[str, Skill] = {}
        self._all_skills: dict[str, Skill] = {}
        self._defaults: dict[str, Any] = {}
        self._schema_version = ""
        self._loaded = False
        self._fingerprint: tuple[tuple[str, float], ...] = ()
        self._lock = threading.RLock()

    @property
    def loaded(self) -> bool:
        return self._loaded

    @property
    def defaults(self) -> dict[str, Any]:
        self.load()
        return dict(self._defaults)

    @property
    def schema_version(self) -> str:
        self.load()
        return self._schema_version

    def load(self, force: bool = False) -> None:
        with self._lock:
            fingerprint = self._build_fingerprint()
            if self._loaded and not force and fingerprint == self._fingerprint:
                return

            raw_skills: dict[str, dict[str, Any]] = {}
            defaults: dict[str, Any] = {}
            schema_version = ""

            for path in self._skill_files():
                payload = self._read_json(path)
                schema_version = str(payload.get("schema_version") or schema_version or "1.0")
                defaults.update(payload.get("defaults", {}))
                for raw_skill in payload.get("skills", []):
                    name = raw_skill.get("name")
                    if not name:
                        raise SkillValidationError(f"Skill sin nombre en {path}")
                    if name in raw_skills:
                        existing_version = raw_skills[name].get("version", "0")
                        incoming_version = raw_skill.get("version", "0")
                        if self._version_tuple(incoming_version) <= self._version_tuple(existing_version):
                            continue
                    raw_skill["_source"] = str(path)
                    raw_skills[name] = raw_skill

            resolved: dict[str, Skill] = {}
            for name in raw_skills:
                self._resolve_skill(name, raw_skills, resolved, stack=())

            ordered = dict(
                sorted(
                    resolved.items(),
                    key=lambda item: (
                        -item[1].priority_weight,
                        tuple(-part for part in item[1].version_key),
                        item[0],
                    ),
                )
            )
            self._all_skills = ordered
            self._skills = {name: skill for name, skill in ordered.items() if skill.enabled}
            self._defaults = defaults
            self._schema_version = schema_version
            self._fingerprint = fingerprint
            self._loaded = True

            conflicts = self.detect_conflicts()
            if conflicts:
                logger.warning("Conflictos de skills detectados: %s", conflicts)

    def all(self, include_disabled: bool = False) -> list[Skill]:
        self.load()
        if include_disabled:
            return list(self._all_skills.values())
        return [skill for skill in self._skills.values() if skill.enabled]

    def get(self, name: str) -> Skill | None:
        self.load()
        return self._skills.get(name)

    def search(
        self,
        query: str | None = None,
        tags: list[str] | tuple[str, ...] | None = None,
        domain: str | None = None,
        limit: int | None = None,
    ) -> list[Skill]:
        self.load()
        wanted_tags = {tag.lower() for tag in (tags or [])}
        query_tokens = self._tokens(query or "")
        domain_text = domain.lower() if domain else None
        scored: list[tuple[int, Skill]] = []

        for skill in self._skills.values():
            if domain_text and skill.domain.lower() != domain_text:
                continue

            skill_tags = {tag.lower() for tag in skill.tags}
            if wanted_tags and not wanted_tags.issubset(skill_tags):
                continue

            score = skill.priority_weight
            score += len(wanted_tags & skill_tags) * 75

            if query_tokens:
                haystack = skill.searchable_text()
                score += sum(35 for token in query_tokens if token in haystack)
                score += sum(80 for token in query_tokens if token in skill_tags)

            scored.append((score, skill))

        scored.sort(key=lambda item: (-item[0], -item[1].priority_weight, item[1].name))
        skills = [skill for _score, skill in scored]
        return skills[:limit] if limit else skills

    def best_match(
        self,
        query: str | None = None,
        tags: list[str] | tuple[str, ...] | None = None,
        domain: str | None = None,
    ) -> Skill | None:
        matches = self.search(query=query, tags=tags, domain=domain, limit=1)
        return matches[0] if matches else None

    def resolve_context(
        self,
        query: str | None = None,
        tags: list[str] | tuple[str, ...] | None = None,
        domain: str | None = None,
        limit: int = 5,
    ) -> dict[str, Any]:
        skills = self.search(query=query, tags=tags, domain=domain, limit=limit)
        defaults = dict(self.defaults)
        for skill in reversed(skills):
            defaults.update(skill.defaults)
        return {
            "schema_version": self.schema_version,
            "defaults": defaults,
            "skills": skills,
            "conflicts": self.detect_conflicts(),
        }

    def detect_conflicts(self) -> list[dict[str, str]]:
        self.load()
        conflicts = []
        enabled_names = set(self._skills)
        for skill in self._skills.values():
            for conflict_name in skill.conflicts_with:
                if conflict_name in enabled_names:
                    conflicts.append(
                        {
                            "skill": skill.name,
                            "conflicts_with": conflict_name,
                            "source": skill.source,
                        }
                    )
        return conflicts

    def validate(self) -> list[str]:
        self.load(force=True)
        errors = []
        for skill in self._skills.values():
            if skill.priority not in PRIORITY_WEIGHTS:
                errors.append(f"{skill.name}: prioridad invalida {skill.priority}")
            if not skill.tags:
                errors.append(f"{skill.name}: no tiene tags")
            if not skill.rules:
                errors.append(f"{skill.name}: no tiene reglas")
        for conflict in self.detect_conflicts():
            errors.append(f"{conflict['skill']} entra en conflicto con {conflict['conflicts_with']}")
        return errors

    def _skill_files(self) -> list[Path]:
        if not self.skills_dir.exists():
            return []
        return sorted(self.skills_dir.glob("*.json"))

    def _build_fingerprint(self) -> tuple[tuple[str, float], ...]:
        return tuple((str(path), path.stat().st_mtime) for path in self._skill_files())

    def _read_json(self, path: Path) -> dict[str, Any]:
        try:
            with path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except json.JSONDecodeError as exc:
            raise SkillValidationError(f"JSON invalido en {path}: {exc}") from exc

        if not isinstance(payload, dict):
            raise SkillValidationError(f"El archivo {path} debe contener un objeto JSON")
        if "skills" not in payload or not isinstance(payload["skills"], list):
            raise SkillValidationError(f"El archivo {path} debe contener una lista 'skills'")
        return payload

    def _resolve_skill(
        self,
        name: str,
        raw_skills: dict[str, dict[str, Any]],
        resolved: dict[str, Skill],
        stack: tuple[str, ...],
    ) -> Skill:
        if name in resolved:
            return resolved[name]
        if name in stack:
            raise SkillValidationError(f"Herencia circular en skills: {' -> '.join(stack + (name,))}")
        if name not in raw_skills:
            raise SkillValidationError(f"Skill base no encontrada: {name}")

        raw_skill = dict(raw_skills[name])
        base_payload: dict[str, Any] = {}
        for parent_name in raw_skill.get("extends", []):
            parent = self._resolve_skill(parent_name, raw_skills, resolved, stack + (name,))
            base_payload = self._merge_payloads(base_payload, self._skill_to_payload(parent))

        merged = self._merge_payloads(base_payload, raw_skill)
        skill = self._parse_skill(merged)
        resolved[name] = skill
        return skill

    def _parse_skill(self, payload: dict[str, Any]) -> Skill:
        name = str(payload.get("name", "")).strip()
        if not name:
            raise SkillValidationError("Skill sin nombre")
        priority = str(payload.get("priority", "medium")).lower()
        if priority not in PRIORITY_WEIGHTS:
            raise SkillValidationError(f"{name}: prioridad invalida {priority}")

        return Skill(
            name=name,
            version=str(payload.get("version", "1.0.0")),
            enabled=bool(payload.get("enabled", True)),
            priority=priority,
            domain=str(payload.get("domain", "general")),
            tags=tuple(payload.get("tags", [])),
            description=str(payload.get("description", "")),
            rules=tuple(payload.get("rules", [])),
            defaults=dict(payload.get("defaults", {})),
            tools=tuple(payload.get("tools", [])),
            examples=tuple(payload.get("examples", [])),
            extends=tuple(payload.get("extends", [])),
            conflicts_with=tuple(payload.get("conflicts_with", [])),
            source=str(payload.get("_source", "")),
        )

    def _merge_payloads(self, base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        merged = dict(base)
        for key, value in override.items():
            if key == "defaults":
                nested = dict(merged.get("defaults", {}))
                nested.update(value or {})
                merged[key] = nested
            elif key in {"tags", "rules", "tools", "examples", "conflicts_with"}:
                current = list(merged.get(key, []))
                for item in value or []:
                    if item not in current:
                        current.append(item)
                merged[key] = current
            else:
                merged[key] = value
        return merged

    def _skill_to_payload(self, skill: Skill) -> dict[str, Any]:
        return {
            "name": skill.name,
            "version": skill.version,
            "enabled": skill.enabled,
            "priority": skill.priority,
            "domain": skill.domain,
            "tags": list(skill.tags),
            "description": skill.description,
            "rules": list(skill.rules),
            "defaults": dict(skill.defaults),
            "tools": list(skill.tools),
            "examples": list(skill.examples),
            "extends": list(skill.extends),
            "conflicts_with": list(skill.conflicts_with),
            "_source": skill.source,
        }

    def _tokens(self, text: str) -> set[str]:
        return {token.lower() for token in TOKEN_RE.findall(text)}

    def _version_tuple(self, version: str) -> tuple[int, ...]:
        return Skill(
            name="_",
            version=version,
            enabled=True,
            priority="low",
            domain="_",
        ).version_key


_registry: SkillRegistry | None = None


def get_skill_registry() -> SkillRegistry:
    global _registry
    if _registry is None:
        _registry = SkillRegistry()
    return _registry


def load_skills(force: bool = False) -> SkillRegistry:
    registry = get_skill_registry()
    registry.load(force=force)
    return registry


def find_skills(
    query: str | None = None,
    tags: list[str] | tuple[str, ...] | None = None,
    domain: str | None = None,
    limit: int | None = None,
) -> list[Skill]:
    return get_skill_registry().search(query=query, tags=tags, domain=domain, limit=limit)


def get_skill(name: str) -> Skill | None:
    return get_skill_registry().get(name)


def resolve_operational_context(
    query: str | None = None,
    tags: list[str] | tuple[str, ...] | None = None,
    domain: str | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    return get_skill_registry().resolve_context(query=query, tags=tags, domain=domain, limit=limit)
