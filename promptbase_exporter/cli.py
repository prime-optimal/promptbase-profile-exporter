from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import date, datetime, time, timezone
from pathlib import Path

from . import __version__
from .client import PromptBaseError, fetch_prompts
from .diffing import compare_catalogs, format_diff_report, load_catalog, write_diff_report
from .formatting import (
    EXPORT_FORMATS,
    SORT_OPTIONS,
    count_written_records,
    filter_records,
    filter_records_by_metadata,
    infer_format_from_path,
    parse_csv_option,
    sort_records,
    sorted_newest_to_oldest,
    write_export,
    write_export_to_path,
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
        help="Output file format. Defaults to txt, or inferred from --output-file/--update-file.",
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
        "--output-file",
        type=Path,
        help="Write a single export to this exact file path. Requires --mode all, text, or image.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow --output-file to replace an existing file.",
    )
    parser.add_argument(
        "--compare",
        type=Path,
        help="Compare the selected prompts against an existing JSON, CSV, TXT, or Markdown export.",
    )
    parser.add_argument(
        "--diff-output",
        type=Path,
        help="Write the comparison report to this path. Requires --compare or --update-file.",
    )
    parser.add_argument(
        "--fail-on-diff",
        action="store_true",
        help="Exit with code 2 when --compare finds added, removed, or changed records.",
    )
    parser.add_argument(
        "--update-file",
        type=Path,
        help=(
            "Compare against this existing export and rewrite it with current selected prompts. "
            "Requires --mode all, text, or image."
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Export only the first N prompts after filtering and sorting.",
    )
    parser.add_argument(
        "--since",
        help="Export prompts created on or after this date or datetime, for example 2026-01-01.",
    )
    parser.add_argument(
        "--until",
        help="Export prompts created on or before this date or datetime, for example 2026-12-31.",
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
        options = normalize_options(parser, args)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

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
        since_created=options["since_created"],
        until_created=options["until_created"],
    )
    if not selected_records:
        print("error: no prompts matched the selected filters", file=sys.stderr)
        return 1
    selected_records = sort_records(selected_records, args.sort)
    if args.limit is not None:
        selected_records = selected_records[: args.limit]

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
            print(f"Format: {options['export_format']}")
            print(f"Sort: {args.sort}")
            print(f"Output directory: {output_dir}")
            if options["output_file"]:
                print(f"Output file: {options['output_file']}")
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
            if args.since or args.until:
                print(f"Created range: {args.since or '*'}..{args.until or '*'}")
            if args.limit is not None:
                print(f"Limit: {args.limit}")

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

    diff_exit_code = 0
    if options["compare_path"]:
        diff_exit_code = handle_compare(
            selected_records,
            modes,
            options["compare_path"],
            args.diff_output,
            args.fail_on_diff,
            quiet=args.quiet,
        )
        if diff_exit_code and not args.update_file:
            return diff_exit_code

    if options["output_file"]:
        mode = modes[0]
        filtered = filter_records(selected_records, mode)
        try:
            output_path = write_export_to_path(
                options["output_file"],
                filtered,
                options["export_format"],
                overwrite=options["overwrite_output"],
            )
        except FileExistsError as exc:
            print(f"error: {exc}. Use --overwrite to replace it.", file=sys.stderr)
            return 1
        written_count = count_written_records(output_path, options["export_format"])
        if written_count != len(filtered):
            print(
                f"error: validation failed for {output_path}: "
                f"expected {len(filtered)}, wrote {written_count}",
                file=sys.stderr,
            )
            return 1
        if not args.quiet:
            print(f"Wrote {mode:>5}: {written_count:>4} prompts -> {output_path}")
            print_summary(selected_records, all_count=len(records))
        return diff_exit_code

    for mode in modes:
        filtered = filter_records(selected_records, mode)
        output_path = write_export(
            output_dir,
            profile.username,
            mode,
            filtered,
            options["export_format"],
            timestamp=timestamp,
        )
        written_count = count_written_records(output_path, options["export_format"])
        if written_count != len(filtered):
            print(
                f"error: validation failed for {output_path}: "
                f"expected {len(filtered)}, wrote {written_count}",
                file=sys.stderr,
            )
            return 1
        if not args.quiet:
            print(f"Wrote {mode:>5}: {written_count:>4} prompts -> {output_path}")

    if not args.quiet:
        print_summary(selected_records, all_count=len(records))
    return 0


def normalize_options(_parser: argparse.ArgumentParser, args: argparse.Namespace) -> dict:
    if args.limit is not None and args.limit <= 0:
        raise ValueError("--limit must be greater than zero")
    if args.output_file and args.update_file:
        raise ValueError("--output-file and --update-file cannot be used together")
    if args.timestamp_filenames and (args.output_file or args.update_file):
        raise ValueError("--timestamp-filenames cannot be used with --output-file or --update-file")
    if args.diff_output and not (args.compare or args.update_file):
        raise ValueError("--diff-output requires --compare or --update-file")
    if args.fail_on_diff and not (args.compare or args.update_file):
        raise ValueError("--fail-on-diff requires --compare or --update-file")
    if (args.output_file or args.compare or args.update_file) and args.mode == "split":
        raise ValueError(
            "--output-file, --compare, and --update-file require --mode all, text, or image"
        )

    output_file = args.output_file
    compare_path = args.compare
    overwrite_output = args.overwrite
    if args.update_file:
        if not args.update_file.exists():
            raise ValueError(f"--update-file does not exist: {args.update_file}")
        output_file = args.update_file
        compare_path = args.update_file
        overwrite_output = True

    if output_file and not args.format:
        export_format = infer_format_from_path(output_file)
    else:
        export_format = args.format or "txt"

    since_created = parse_datetime_ms(args.since, end_of_day=False) if args.since else None
    until_created = parse_datetime_ms(args.until, end_of_day=True) if args.until else None
    if (
        since_created is not None
        and until_created is not None
        and since_created > until_created
    ):
        raise ValueError("--since cannot be later than --until")

    return {
        "compare_path": compare_path,
        "export_format": export_format,
        "output_file": output_file,
        "overwrite_output": overwrite_output,
        "since_created": since_created,
        "until_created": until_created,
    }


def parse_datetime_ms(value: str, *, end_of_day: bool) -> int:
    raw = value.strip()
    if not raw:
        raise ValueError("date value cannot be empty")
    try:
        if re_full_date(raw):
            parsed_date = date.fromisoformat(raw)
            parsed_datetime = datetime.combine(
                parsed_date,
                time.max if end_of_day else time.min,
                tzinfo=timezone.utc,
            )
        else:
            parsed_datetime = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if parsed_datetime.tzinfo is None:
                parsed_datetime = parsed_datetime.replace(tzinfo=timezone.utc)
            else:
                parsed_datetime = parsed_datetime.astimezone(timezone.utc)
    except ValueError as exc:
        raise ValueError(
            f"invalid date/datetime '{value}'. Use YYYY-MM-DD or ISO datetime."
        ) from exc
    return int(parsed_datetime.timestamp() * 1000)


def re_full_date(value: str) -> bool:
    return len(value) == 10 and value[4] == "-" and value[7] == "-"


def handle_compare(
    selected_records,
    modes: list[str],
    compare_path: Path,
    diff_output: Path | None,
    fail_on_diff: bool,
    *,
    quiet: bool,
) -> int:
    try:
        previous_records = load_catalog(compare_path)
    except (OSError, ValueError) as exc:
        print(f"error: could not load comparison catalog: {exc}", file=sys.stderr)
        return 1
    filtered = filter_records(selected_records, modes[0])
    diff = compare_catalogs(previous_records, filtered)
    report = format_diff_report(diff)
    if not quiet:
        print(report.rstrip())
    if diff_output:
        write_diff_report(diff_output, diff)
        if not quiet:
            print(f"Wrote diff report -> {diff_output}")
    if fail_on_diff and diff.has_changes:
        return 2
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


def print_summary(records, all_count: int | None = None) -> None:
    image_count = len(filter_records(records, "image"))
    text_count = len(filter_records(records, "text"))
    other_count = len(records) - image_count - text_count
    total = all_count if all_count is not None else len(records)
    print(
        "Summary: "
        f"text={text_count}, image={image_count}, "
        f"other={other_count}, selected={len(records)}, all={total}"
    )
