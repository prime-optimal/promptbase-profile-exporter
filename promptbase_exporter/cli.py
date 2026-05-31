from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

from . import __version__
from .client import PromptBaseError, fetch_prompts
from .formatting import (
    EXPORT_FORMATS,
    SORT_OPTIONS,
    count_written_records,
    filter_records,
    filter_records_by_metadata,
    parse_csv_option,
    sort_records,
    sorted_newest_to_oldest,
    write_export,
)

MODE_ALIASES = {
    "text-only": "text",
    "image-only": "image",
}
MODES = ("split", "all", "text", "image", *MODE_ALIASES)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="promptbase-export",
        description="Export public PromptBase profile prompts to catalog files.",
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
        help=(
            "Which export to write. 'split' writes all, text, and image files. "
            "Aliases: text-only, image-only."
        ),
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        default="exports",
        help="Directory where export files will be written.",
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=EXPORT_FORMATS,
        default="txt",
        help="Output file format.",
    )
    parser.add_argument(
        "--sort",
        choices=SORT_OPTIONS,
        default="newest",
        help="Sort selected prompts before writing.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--allow-missing-descriptions",
        action="store_true",
        help="Write files even if one or more prompt descriptions are missing.",
    )
    parser.add_argument(
        "--domain",
        help="Comma-separated domain filter, for example: text,image,video.",
    )
    parser.add_argument(
        "--type",
        dest="prompt_type",
        help="Comma-separated PromptBase type filter, for example: gpt,claude.",
    )
    price_group = parser.add_mutually_exclusive_group()
    price_group.add_argument(
        "--free-only",
        action="store_true",
        help="Export only free prompts.",
    )
    price_group.add_argument(
        "--paid-only",
        action="store_true",
        help="Export only paid prompts.",
    )
    parser.add_argument(
        "--min-price",
        type=float,
        help="Export prompts priced at or above this amount.",
    )
    parser.add_argument(
        "--max-price",
        type=float,
        help="Export prompts priced at or below this amount.",
    )
    parser.add_argument(
        "--timestamp-filenames",
        action="store_true",
        help="Append a YYYYMMDD_HHMMSS timestamp to generated filenames.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch, filter, and validate records without writing files.",
    )
    parser.add_argument(
        "--list-domains",
        action="store_true",
        help="Print domain counts after filters and exit without writing files.",
    )
    parser.add_argument(
        "--list-types",
        action="store_true",
        help="Print PromptBase type counts after filters and exit without writing files.",
    )
    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress normal command output.",
    )
    output_group.add_argument(
        "--verbose",
        action="store_true",
        help="Print extra filtering details.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.mode = MODE_ALIASES.get(args.mode, args.mode)

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

    if args.min_price is not None and args.min_price < 0:
        print("error: --min-price cannot be negative", file=sys.stderr)
        return 1
    if args.max_price is not None and args.max_price < 0:
        print("error: --max-price cannot be negative", file=sys.stderr)
        return 1
    if (
        args.min_price is not None
        and args.max_price is not None
        and args.min_price > args.max_price
    ):
        print("error: --min-price cannot be greater than --max-price", file=sys.stderr)
        return 1

    selected_records = filter_records_by_metadata(
        records,
        domains=parse_csv_option(args.domain),
        prompt_types=parse_csv_option(args.prompt_type),
        free_only=args.free_only,
        paid_only=args.paid_only,
        min_price=args.min_price,
        max_price=args.max_price,
    )
    if not selected_records:
        print("error: no prompts matched the selected filters", file=sys.stderr)
        return 1
    selected_records = sort_records(selected_records, args.sort)

    missing_descriptions = [record for record in selected_records if not record.description]
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
    timestamp = (
        datetime.now().strftime("%Y%m%d_%H%M%S")
        if args.timestamp_filenames
        else None
    )

    if not args.quiet:
        print(f"Profile: @{profile.username}")
        print(f"Approved prompts found: {len(records)}")
        print(f"Selected after filters: {len(selected_records)}")
        if args.verbose:
            print(f"Format: {args.format}")
            print(f"Sort: {args.sort}")
            print(f"Output directory: {output_dir}")
            if args.domain:
                print(f"Domain filter: {args.domain}")
            if args.prompt_type:
                print(f"Type filter: {args.prompt_type}")
            if args.free_only:
                print("Price filter: free only")
            if args.paid_only:
                print("Price filter: paid only")
            if args.min_price is not None or args.max_price is not None:
                print(f"Price range: {args.min_price}..{args.max_price}")

    if args.list_domains:
        print_counts("Domains", count_by(selected_records, "domain"))
    if args.list_types:
        print_counts("Types", count_by(selected_records, "prompt_type"))
    if args.dry_run and not args.quiet:
        print_planned_outputs(selected_records, modes)

    if args.dry_run or args.list_domains or args.list_types:
        if not args.quiet:
            print("Dry run: no files written.")
        return 0

    for mode in modes:
        filtered = filter_records(selected_records, mode)
        output_path = write_export(
            output_dir,
            profile.username,
            mode,
            filtered,
            args.format,
            timestamp=timestamp,
        )
        written_count = count_written_records(output_path, args.format)
        if written_count != len(filtered):
            print(
                f"error: validation failed for {output_path}: "
                f"expected {len(filtered)}, wrote {written_count}",
                file=sys.stderr,
            )
            return 1
        if not args.quiet:
            print(f"Wrote {mode:>5}: {written_count:>4} prompts -> {output_path}")

    image_count = len(filter_records(selected_records, "image"))
    text_count = len(filter_records(selected_records, "text"))
    other_count = len(selected_records) - image_count - text_count
    if not args.quiet:
        print(
            "Summary: "
            f"text={text_count}, image={image_count}, "
            f"other={other_count}, selected={len(selected_records)}, all={len(records)}"
        )
    return 0


def count_by(records, attribute: str) -> dict[str, int]:
    counts = Counter((getattr(record, attribute) or "unknown") for record in records)
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def print_counts(title: str, counts: dict[str, int]) -> None:
    print(f"{title}:")
    for key, value in counts.items():
        print(f"  {key}: {value}")


def print_planned_outputs(records, modes: list[str]) -> None:
    print("Planned outputs:")
    for mode in modes:
        print(f"  {mode}: {len(filter_records(records, mode))}")
