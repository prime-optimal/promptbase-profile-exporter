from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .client import PromptBaseError, fetch_prompts
from .formatting import (
    count_written_records,
    filter_records,
    sorted_newest_to_oldest,
    write_text_export,
)

MODES = ("split", "all", "text", "image")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="promptbase-export",
        description="Export public PromptBase profile prompts to text files.",
    )
    parser.add_argument(
        "profile",
        help="PromptBase profile URL, path, username, or @username.",
    )
    parser.add_argument(
        "-m",
        "--mode",
        choices=MODES,
        default="split",
        help="Which export to write. 'split' writes all, text, and image files.",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        default="exports",
        help="Directory where export files will be written.",
    )
    parser.add_argument(
        "--allow-missing-descriptions",
        action="store_true",
        help="Write files even if one or more prompt descriptions are missing.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        profile, records = fetch_prompts(args.profile)
    except PromptBaseError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if not records:
        print(f"error: no approved prompts found for @{profile.username}", file=sys.stderr)
        return 1

    if not sorted_newest_to_oldest(records):
        print("error: prompt records are not sorted newest to oldest", file=sys.stderr)
        return 1

    missing_descriptions = [record for record in records if not record.description]
    if missing_descriptions and not args.allow_missing_descriptions:
        print(
            "error: missing descriptions for "
            f"{len(missing_descriptions)} prompt(s). "
            "Use --allow-missing-descriptions to write partial exports.",
            file=sys.stderr,
        )
        for record in missing_descriptions[:10]:
            print(f"  - {record.title} ({record.slug})", file=sys.stderr)
        return 1

    modes = ["all", "text", "image"] if args.mode == "split" else [args.mode]
    output_dir = Path(args.output_dir)

    print(f"Profile: @{profile.username}")
    print(f"Approved prompts found: {len(records)}")

    for mode in modes:
        filtered = filter_records(records, mode)
        output_path = write_text_export(output_dir, profile.username, mode, filtered)
        written_count = count_written_records(output_path)
        if written_count != len(filtered):
            print(
                f"error: validation failed for {output_path}: "
                f"expected {len(filtered)}, wrote {written_count}",
                file=sys.stderr,
            )
            return 1
        print(f"Wrote {mode:>5}: {written_count:>4} prompts -> {output_path}")

    image_count = len(filter_records(records, "image"))
    text_count = len(filter_records(records, "text"))
    other_count = len(records) - image_count - text_count
    print(
        "Summary: "
        f"text={text_count}, image={image_count}, other={other_count}, all={len(records)}"
    )
    return 0
