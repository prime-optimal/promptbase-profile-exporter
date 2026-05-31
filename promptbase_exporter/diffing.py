from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .formatting import record_to_dict
from .models import PromptRecord

COMPARE_FIELDS = ("title", "description", "type", "domain", "price")


@dataclass(frozen=True)
class ChangedRecord:
    previous: dict[str, Any]
    current: dict[str, Any]
    fields: tuple[str, ...]


@dataclass(frozen=True)
class CatalogDiff:
    added: tuple[dict[str, Any], ...]
    removed: tuple[dict[str, Any], ...]
    changed: tuple[ChangedRecord, ...]
    unchanged: int

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.removed or self.changed)


def load_catalog(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    if suffix == ".json":
        data = json.loads(text)
        if not isinstance(data, list):
            raise ValueError("JSON catalog must contain a list of records.")
        return [_normalize_record(item) for item in data if isinstance(item, dict)]
    if suffix == ".csv":
        return [_normalize_record(row) for row in csv.DictReader(io.StringIO(text))]
    if suffix == ".txt":
        return [_normalize_record(item) for item in _parse_text_catalog(text)]
    if suffix in {".md", ".markdown"}:
        return [_normalize_record(item) for item in _parse_markdown_catalog(text)]
    raise ValueError(f"Unsupported catalog file extension: {path.suffix}")


def compare_catalogs(
    previous: list[dict[str, Any]],
    current_records: list[PromptRecord],
) -> CatalogDiff:
    current = [record_to_dict(record) for record in current_records]
    previous_by_slug = {
        _slug_key(record): index
        for index, record in enumerate(previous)
        if _slug_key(record)
    }
    previous_by_title = {
        _title_key(record): index
        for index, record in enumerate(previous)
        if _title_key(record)
    }

    used_previous: set[int] = set()
    added: list[dict[str, Any]] = []
    changed: list[ChangedRecord] = []
    unchanged = 0

    for record in current:
        previous_index = _match_previous(record, previous_by_slug, previous_by_title)
        if previous_index is None or previous_index in used_previous:
            added.append(record)
            continue

        used_previous.add(previous_index)
        previous_record = previous[previous_index]
        changed_fields = _changed_fields(previous_record, record)
        if changed_fields:
            changed.append(
                ChangedRecord(
                    previous=previous_record,
                    current=record,
                    fields=tuple(changed_fields),
                )
            )
        else:
            unchanged += 1

    removed = [
        record
        for index, record in enumerate(previous)
        if index not in used_previous
    ]
    return CatalogDiff(
        added=tuple(added),
        removed=tuple(removed),
        changed=tuple(changed),
        unchanged=unchanged,
    )


def format_diff_report(diff: CatalogDiff) -> str:
    lines = [
        "# PromptBase Catalog Diff",
        "",
        "Summary:",
        f"- Added: {len(diff.added)}",
        f"- Removed: {len(diff.removed)}",
        f"- Changed: {len(diff.changed)}",
        f"- Unchanged: {diff.unchanged}",
        "",
    ]

    _append_record_section(lines, "Added", diff.added)
    _append_changed_section(lines, diff.changed)
    _append_record_section(lines, "Removed", diff.removed)
    return "\n".join(lines).rstrip() + "\n"


def write_diff_report(path: Path, diff: CatalogDiff) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(format_diff_report(diff), encoding="utf-8", newline="\n")
    return path


def _parse_text_catalog(text: str) -> list[dict[str, str]]:
    pattern = re.compile(
        r"(?ms)^\d+\.\s*\nTitle:\s*(?P<title>.*?)\nDescription:\n(?P<description>.*?)(?=^\d+\.\s*$|\Z)"
    )
    return [
        {
            "title": match.group("title").strip(),
            "description": match.group("description").strip(),
        }
        for match in pattern.finditer(text)
    ]


def _parse_markdown_catalog(text: str) -> list[dict[str, str]]:
    sections = re.split(r"(?m)^## \d+\. ", text)
    records: list[dict[str, str]] = []
    for section in sections[1:]:
        lines = section.splitlines()
        if not lines:
            continue
        title = lines[0].strip()
        metadata: dict[str, str] = {}
        body_lines: list[str] = []
        in_metadata = True
        for line in lines[1:]:
            if in_metadata and line.startswith("- "):
                key, _, value = line[2:].partition(":")
                metadata[key.strip().lower()] = value.strip()
                continue
            if in_metadata and not line.strip():
                continue
            in_metadata = False
            body_lines.append(line)
        records.append(
            {
                "title": title,
                "description": "\n".join(body_lines).strip(),
                "slug": _slug_from_url(metadata.get("url", "")),
                "type": metadata.get("type", ""),
                "domain": metadata.get("domain", ""),
                "price": metadata.get("price", ""),
            }
        )
    return records


def _normalize_record(record: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(record)
    if "prompt_type" in normalized and "type" not in normalized:
        normalized["type"] = normalized["prompt_type"]
    for key in ("title", "description", "slug", "type", "domain", "url"):
        normalized[key] = str(normalized.get(key) or "").strip()
    return normalized


def _match_previous(
    record: dict[str, Any],
    previous_by_slug: dict[str, int],
    previous_by_title: dict[str, int],
) -> int | None:
    slug = _slug_key(record)
    if slug and slug in previous_by_slug:
        return previous_by_slug[slug]
    title = _title_key(record)
    if title and title in previous_by_title:
        return previous_by_title[title]
    return None


def _changed_fields(previous: dict[str, Any], current: dict[str, Any]) -> list[str]:
    changed: list[str] = []
    for field in COMPARE_FIELDS:
        if field not in previous and field not in {"title", "description"}:
            continue
        if field not in {"title", "description"} and _metadata_missing(previous.get(field)):
            continue
        previous_value = _comparable_value(previous.get(field))
        current_value = _comparable_value(current.get(field))
        if previous_value != current_value:
            changed.append(field)
    return changed


def _comparable_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:g}"
    return re.sub(r"\s+", " ", str(value).replace("\r\n", "\n").replace("\r", "\n")).strip()


def _metadata_missing(value: Any) -> bool:
    return value is None or str(value).strip() == ""


def _slug_key(record: dict[str, Any]) -> str:
    return str(record.get("slug") or "").strip().casefold()


def _title_key(record: dict[str, Any]) -> str:
    return _comparable_value(record.get("title")).casefold()


def _slug_from_url(url: str) -> str:
    match = re.search(r"/prompt/([^/?#]+)", url)
    return match.group(1) if match else ""


def _append_record_section(
    lines: list[str],
    title: str,
    records: tuple[dict[str, Any], ...],
) -> None:
    if not records:
        return
    lines.extend([f"## {title}", ""])
    for record in records:
        lines.append(f"- {_record_label(record)}")
    lines.append("")


def _append_changed_section(lines: list[str], records: tuple[ChangedRecord, ...]) -> None:
    if not records:
        return
    lines.extend(["## Changed", ""])
    for record in records:
        lines.append(f"- {_record_label(record.current)}")
        lines.append(f"  Changed fields: {', '.join(record.fields)}")
    lines.append("")


def _record_label(record: dict[str, Any]) -> str:
    title = str(record.get("title") or "Untitled").strip()
    slug = str(record.get("slug") or "").strip()
    if slug:
        return f"{title} ({slug})"
    return title
