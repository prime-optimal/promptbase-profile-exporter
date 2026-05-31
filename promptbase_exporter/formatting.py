from __future__ import annotations

import re
from pathlib import Path

from .models import PromptRecord


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


def expected_filename(username: str, mode: str) -> str:
    safe_username = re.sub(r"[^A-Za-z0-9_.-]+", "_", username).strip("_")
    return f"{safe_username}_{mode}_prompts.txt"


def write_text_export(
    output_dir: Path,
    username: str,
    mode: str,
    records: list[PromptRecord],
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / expected_filename(username, mode)
    output_path.write_text(format_records_as_text(records), encoding="utf-8", newline="\n")
    return output_path


def count_written_records(path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    return len(re.findall(r"^\d+\.$", text, flags=re.MULTILINE))


def sorted_newest_to_oldest(records: list[PromptRecord]) -> bool:
    return all(records[i].created >= records[i + 1].created for i in range(len(records) - 1))
