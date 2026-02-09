from __future__ import annotations

import re
from functools import lru_cache
from string import Formatter

from django.core.management.base import CommandError

ALLOWED_TEMPLATE_FIELDS = {"database", "datetime", "ext"}

DATE_DIRECTIVE_PATTERNS = {
    "%a": r"[A-Za-z]{3}",
    "%A": r"[A-Za-z]+",
    "%w": r"\d",
    "%d": r"\d{2}",
    "%b": r"[A-Za-z]{3}",
    "%B": r"[A-Za-z]+",
    "%m": r"\d{2}",
    "%y": r"\d{2}",
    "%Y": r"\d{4}",
    "%H": r"\d{2}",
    "%I": r"\d{2}",
    "%M": r"\d{2}",
    "%S": r"\d{2}",
    "%f": r"\d{6}",
    "%z": r"(?:[+-]\d{4}|[+-]\d{2}:\d{2})",
    "%j": r"\d{3}",
    "%U": r"\d{2}",
    "%W": r"\d{2}",
    "%%": r"%",
}


def validate_db_filename_template(template: str) -> None:
    _compile_db_filename_pattern(template)


def database_from_backup_name(filename: str, template: str, date_format: str | None = None) -> str | None:
    pattern = _compile_db_filename_pattern(template, date_format)
    match = pattern.fullmatch(filename)
    if not match:
        return None
    return match.group("database")


@lru_cache(maxsize=16)
def _compile_db_filename_pattern(template: str, date_format: str | None = None) -> re.Pattern[str]:
    parsed = list(Formatter().parse(template))
    if not parsed:
        raise CommandError("DB_FILENAME_TEMPLATE cannot be empty.")
    first_literal, first_field, _first_spec, _first_conv = parsed[0]
    if first_literal or first_field != "database":
        raise CommandError(
            "DB_FILENAME_TEMPLATE must start with {database} so backup ownership is "
            "deterministic for cleanup/list/restore operations."
        )
    if len(parsed) > 1 and parsed[1][0] == "":
        raise CommandError(
            "DB_FILENAME_TEMPLATE must include a separator immediately after {database} "
            "(for example: {database}-{datetime}.{ext})."
        )

    parts: list[str] = []
    saw_database = False
    seen_fields: set[str] = set()

    for literal, field_name, format_spec, conversion in parsed:
        parts.append(re.escape(literal))
        if field_name is None:
            continue

        if conversion is not None or format_spec:
            raise CommandError(
                "DB_FILENAME_TEMPLATE does not support format conversions/specifiers. "
                "Use only plain placeholders: {database}, {datetime}, {ext}."
            )

        if field_name not in ALLOWED_TEMPLATE_FIELDS:
            allowed = ", ".join(sorted(ALLOWED_TEMPLATE_FIELDS))
            raise CommandError(
                f"Unsupported placeholder {{{field_name}}} in DB_FILENAME_TEMPLATE. Supported placeholders: {allowed}."
            )

        if field_name in seen_fields:
            raise CommandError(
                f"Placeholder {{{field_name}}} appears more than once in DB_FILENAME_TEMPLATE. "
                "Each placeholder may only appear once."
            )
        seen_fields.add(field_name)

        if field_name == "database":
            saw_database = True
        datetime_pattern = _date_format_to_regex(date_format) if date_format else r"[^/]+?"
        field_patterns = {
            "database": r"(?P<database>[^/]+?)",
            "datetime": f"(?P<datetime>{datetime_pattern})",
            "ext": r"(?P<ext>[^/]+)",
        }
        parts.append(field_patterns[field_name])

    if not saw_database:  # pragma: no cover - guarded by the first_field check above
        raise CommandError(
            "DB_FILENAME_TEMPLATE must include {database} so backups can be associated "
            "with the correct Django database alias."
        )

    return re.compile("".join(parts))


def _date_format_to_regex(date_format: str) -> str:
    parts: list[str] = []
    i = 0
    while i < len(date_format):
        if date_format[i] == "%" and i + 1 < len(date_format):
            token = date_format[i : i + 2]
            parts.append(DATE_DIRECTIVE_PATTERNS.get(token, re.escape(token)))
            i += 2
            continue
        parts.append(re.escape(date_format[i]))
        i += 1
    return "".join(parts)
