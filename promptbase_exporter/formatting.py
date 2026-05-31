from __future__ import annotations

import csv
import io
import json
import re
from pathlib import Path

from .models import PromptRecord

EXPORT_FORMATS = ("txt", "markdown", "json", "csv")
FORMAT_EXTENSIONS = {
    "txt": "txt",
    "markdown": "md",
    "json": "json",
    "csv": "csv",
}


def filter_records(records: list[PromptRecord], mode: str) -> list[PromptRecord]:
    if mode == "all":
        return list(records)
    if mode == "text":
        return [record for record in records if record.is_text]
    if mode == "image":
        return [record for record in records if record.is_image]
    raise ValueError(f"Unsupported mode: {mode}")


def format_records_as_text(records: list[PromptRecord]) -> str:
    parts: list[str] = []
    for index, record in enumerate(records, 1):
        description = record.description.replace("\r\n", "\n").replace("\r", "\n")
        parts.append(
            f"{index}.\n"
            f"Title: {record.title}\n"
            f"Description:\n"
            f"{description.strip()}\n"
        )
    return "\n".join(parts)


def format_records_as_markdown(records: list[PromptRecord]) -> str:
    parts = ["# PromptBase Prompt Export", ""]
    for index, record in enumerate(records, 1):
        description = record.description.replace("\r\n", "\n").replace("\r", "\n")
        parts.extend(
            [
                f"## {index}. {record.title}",
                "",
                f"- URL: {record.url}",
                f"- Domain: {record.domain or 'unknown'}",
                f"- Type: {record.prompt_type or 'unknown'}",
                "",
                description.strip(),
                "",
            ]
        )
    return "\n".join(parts).rstrip() + "\n"


def record_to_dict(record: PromptRecord) -> dict[str, object]:
    return {
        "title": record.title,
        "description": record.description,
        "slug": record.slug,
        "url": record.url,
        "type": record.prompt_type,
        "domain": record.domain,
        "created": record.created,
    }


def format_records_as_json(records: list[PromptRecord]) -> str:
    data = [record_to_dict(record) for record in records]
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def format_records_as_csv(records: list[PromptRecord]) -> str:
    fieldnames = ["title", "description", "slug", "url", "type", "domain", "created"]
    rows = [record_to_dict(record) for record in records]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def format_records(records: list[PromptRecord], export_format: str) -> str:
    if export_format == "txt":
        return format_records_as_text(records)
    if export_format == "markdown":
        return format_records_as_markdown(records)
    if export_format == "json":
        return format_records_as_json(records)
    if export_format == "csv":
        return format_records_as_csv(records)
    raise ValueError(f"Unsupported export format: {export_format}")


def expected_filename(username: str, mode: str, export_format: str = "txt") -> str:
    safe_username = re.sub(r"[^A-Za-z0-9_.-]+", "_", username).strip("_")
    extension = FORMAT_EXTENSIONS[export_format]
    return f"{safe_username}_{mode}_prompts.{extension}"


def write_export(
    output_dir: Path,
    username: str,
    mode: str,
    records: list[PromptRecord],
    export_format: str,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / expected_filename(username, mode, export_format)
    output_path.write_text(format_records(records, export_format), encoding="utf-8", newline="\n")
    return output_path


def count_written_records(path: Path, export_format: str) -> int:
    text = path.read_text(encoding="utf-8")
    if export_format == "txt":
        return len(re.findall(r"^\d+\.$", text, flags=re.MULTILINE))
    if export_format == "markdown":
        return len(re.findall(r"^## \d+\. ", text, flags=re.MULTILINE))
    if export_format == "json":
        return len(json.loads(text))
    if export_format == "csv":
        return sum(1 for _ in csv.DictReader(io.StringIO(text)))
    raise ValueError(f"Unsupported export format: {export_format}")


def sorted_newest_to_oldest(records: list[PromptRecord]) -> bool:
    return all(records[i].created >= records[i + 1].created for i in range(len(records) - 1))
