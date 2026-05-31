from __future__ import annotations

import argparse
import html
import sys
import urllib.parse
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import __version__
from .cli import parse_datetime_ms
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
from .models import Profile, PromptRecord

WEB_MODES = ("split", "all", "text", "image")
PRICE_FILTERS = ("all", "free", "paid")
DEFAULT_OUTPUT_DIR = "exports"
MAX_FORM_BYTES = 20_000


class WebInputError(ValueError):
    """Raised when a submitted web export request is invalid."""


@dataclass(frozen=True)
class ExportRequest:
    profile_input: str
    mode: str = "split"
    output_dir: Path = Path(DEFAULT_OUTPUT_DIR)
    export_format: str = "txt"
    sort: str = "newest"
    domain: str = ""
    prompt_type: str = ""
    price_filter: str = "all"
    min_price: float | None = None
    max_price: float | None = None
    limit: int | None = None
    since: str = ""
    until: str = ""
    timestamp_filenames: bool = False
    allow_missing_descriptions: bool = False


@dataclass(frozen=True)
class ExportedFile:
    mode: str
    path: Path
    count: int


@dataclass(frozen=True)
class WebExportResult:
    username: str
    total_records: int
    selected_records: int
    text_records: int
    image_records: int
    other_records: int
    files: tuple[ExportedFile, ...]


FetchPrompts = Callable[[str], tuple[Profile, list[PromptRecord]]]
WriteExport = Callable[[Path, str, str, list[PromptRecord], str, str | None], Path]
CountWrittenRecords = Callable[[Path, str], int]


def default_request() -> ExportRequest:
    return ExportRequest(profile_input="")


def build_request_config(
    form_data: Mapping[str, str | Sequence[str]],
) -> ExportRequest:
    """Build and validate an export request from web form data."""
    profile_input = _single_value(form_data, "profile").strip()
    if not profile_input:
        raise WebInputError("Profile is required.")

    mode = _single_value(form_data, "mode", "split")
    if mode not in WEB_MODES:
        raise WebInputError(f"Unsupported mode: {mode}.")

    export_format = _single_value(form_data, "format", "txt")
    if export_format not in EXPORT_FORMATS:
        raise WebInputError(f"Unsupported format: {export_format}.")

    sort = _single_value(form_data, "sort", "newest")
    if sort not in SORT_OPTIONS:
        raise WebInputError(f"Unsupported sort option: {sort}.")

    price_filter = _single_value(form_data, "price_filter", "all")
    if price_filter not in PRICE_FILTERS:
        raise WebInputError(f"Unsupported price filter: {price_filter}.")

    min_price = _parse_optional_price(form_data, "min_price")
    max_price = _parse_optional_price(form_data, "max_price")
    if min_price is not None and max_price is not None and min_price > max_price:
        raise WebInputError("Minimum price cannot be greater than maximum price.")
    limit = _parse_optional_int(form_data, "limit")
    since = _single_value(form_data, "since").strip()
    until = _single_value(form_data, "until").strip()
    since_created = parse_datetime_ms(since, end_of_day=False) if since else None
    until_created = parse_datetime_ms(until, end_of_day=True) if until else None
    if (
        since_created is not None
        and until_created is not None
        and since_created > until_created
    ):
        raise WebInputError("Since date cannot be later than until date.")

    output_dir = _single_value(form_data, "output_dir", DEFAULT_OUTPUT_DIR).strip()
    if not output_dir:
        output_dir = DEFAULT_OUTPUT_DIR

    return ExportRequest(
        profile_input=profile_input,
        mode=mode,
        output_dir=Path(output_dir).expanduser(),
        export_format=export_format,
        sort=sort,
        domain=_single_value(form_data, "domain").strip(),
        prompt_type=_single_value(form_data, "prompt_type").strip(),
        price_filter=price_filter,
        min_price=min_price,
        max_price=max_price,
        limit=limit,
        since=since,
        until=until,
        timestamp_filenames=_as_bool(_single_value(form_data, "timestamp_filenames")),
        allow_missing_descriptions=_as_bool(
            _single_value(form_data, "allow_missing_descriptions")
        ),
    )


def run_export(
    request: ExportRequest,
    *,
    fetcher: FetchPrompts = fetch_prompts,
    writer: WriteExport = write_export,
    counter: CountWrittenRecords = count_written_records,
) -> WebExportResult:
    """Fetch, filter, sort, write, and validate exports for one web request."""
    profile, records = fetcher(request.profile_input)
    if not records:
        raise WebInputError(f"No approved prompts found for @{profile.username}.")
    if not sorted_newest_to_oldest(records):
        raise WebInputError("Prompt records are not sorted newest to oldest.")

    free_only = request.price_filter == "free"
    paid_only = request.price_filter == "paid"
    selected_records = filter_records_by_metadata(
        records,
        domains=parse_csv_option(request.domain),
        prompt_types=parse_csv_option(request.prompt_type),
        free_only=free_only,
        paid_only=paid_only,
        min_price=request.min_price,
        max_price=request.max_price,
        since_created=parse_datetime_ms(request.since, end_of_day=False)
        if request.since
        else None,
        until_created=parse_datetime_ms(request.until, end_of_day=True)
        if request.until
        else None,
    )
    if not selected_records:
        raise WebInputError("No prompts matched the selected filters.")

    selected_records = sort_records(selected_records, request.sort)
    if request.limit is not None:
        selected_records = selected_records[: request.limit]
    missing_descriptions = [record for record in selected_records if not record.description]
    if missing_descriptions and not request.allow_missing_descriptions:
        raise WebInputError(
            "Missing descriptions for "
            f"{len(missing_descriptions)} prompt(s). "
            "Enable partial exports to write these records."
        )

    modes = ("all", "text", "image") if request.mode == "split" else (request.mode,)
    timestamp = (
        datetime.now().strftime("%Y%m%d_%H%M%S")
        if request.timestamp_filenames
        else None
    )

    exported_files: list[ExportedFile] = []
    for mode in modes:
        filtered = filter_records(selected_records, mode)
        output_path = writer(
            request.output_dir,
            profile.username,
            mode,
            filtered,
            request.export_format,
            timestamp,
        )
        written_count = counter(output_path, request.export_format)
        if written_count != len(filtered):
            raise WebInputError(
                f"Validation failed for {output_path}: "
                f"expected {len(filtered)}, wrote {written_count}."
            )
        exported_files.append(ExportedFile(mode=mode, path=output_path, count=written_count))

    image_count = len(filter_records(selected_records, "image"))
    text_count = len(filter_records(selected_records, "text"))
    return WebExportResult(
        username=profile.username,
        total_records=len(records),
        selected_records=len(selected_records),
        text_records=text_count,
        image_records=image_count,
        other_records=len(selected_records) - image_count - text_count,
        files=tuple(exported_files),
    )


def render_form(
    request: ExportRequest | None = None,
    *,
    result: WebExportResult | None = None,
    error: str | None = None,
) -> str:
    """Render the local web UI as a complete HTML document."""
    request = request or default_request()
    status_block = ""
    if error:
        status_block = f'<section class="notice error"><h2>Error</h2><p>{_h(error)}</p></section>'
    elif result:
        rows = "\n".join(
            "<tr>"
            f"<td>{_h(item.mode)}</td>"
            f"<td>{item.count}</td>"
            f"<td><code>{_h(str(item.path))}</code></td>"
            "</tr>"
            for item in result.files
        )
        status_block = f"""
        <section class="notice success">
          <h2>Export complete</h2>
          <p>
            @{_h(result.username)}: {result.selected_records} selected from
            {result.total_records} prompts. Text: {result.text_records},
            image: {result.image_records}, other: {result.other_records}.
          </p>
          <table>
            <thead><tr><th>Mode</th><th>Prompts</th><th>File</th></tr></thead>
            <tbody>{rows}</tbody>
          </table>
        </section>
        """

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>PromptBase Profile Exporter</title>
  <style>
    :root {{
      color-scheme: light dark;
      --bg: #f5f7f9;
      --panel: #ffffff;
      --text: #16202a;
      --muted: #5f6b77;
      --line: #d9e1e8;
      --accent: #1f7a5c;
      --danger: #a33d3d;
    }}
    @media (prefers-color-scheme: dark) {{
      :root {{
        --bg: #11171d;
        --panel: #19222b;
        --text: #f0f4f8;
        --muted: #adbac7;
        --line: #34414f;
      }}
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.5;
    }}
    main {{
      width: min(980px, calc(100% - 32px));
      margin: 32px auto;
    }}
    header {{
      margin-bottom: 20px;
    }}
    h1 {{
      margin: 0 0 6px;
      font-size: 32px;
    }}
    h2 {{
      margin: 0 0 12px;
      font-size: 20px;
    }}
    p {{
      margin: 0;
      color: var(--muted);
    }}
    form, .notice {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 20px;
      margin-bottom: 16px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 16px;
    }}
    .full {{
      grid-column: 1 / -1;
    }}
    label {{
      display: block;
      font-weight: 650;
      margin-bottom: 6px;
    }}
    input, select {{
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 10px 12px;
      background: transparent;
      color: var(--text);
      font: inherit;
    }}
    .checkline {{
      display: flex;
      align-items: center;
      gap: 10px;
      min-height: 42px;
    }}
    .checkline input {{
      width: auto;
    }}
    .actions {{
      display: flex;
      align-items: center;
      justify-content: flex-end;
      gap: 12px;
      margin-top: 18px;
    }}
    button {{
      border: 0;
      border-radius: 6px;
      padding: 10px 16px;
      background: var(--accent);
      color: white;
      font: inherit;
      font-weight: 700;
      cursor: pointer;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 14px;
    }}
    th, td {{
      border-top: 1px solid var(--line);
      padding: 10px 8px;
      text-align: left;
      vertical-align: top;
    }}
    code {{
      overflow-wrap: anywhere;
    }}
    .success {{
      border-color: color-mix(in srgb, var(--accent) 45%, var(--line));
    }}
    .error {{
      border-color: color-mix(in srgb, var(--danger) 55%, var(--line));
    }}
    .error h2 {{
      color: var(--danger);
    }}
    @media (max-width: 720px) {{
      main {{
        width: min(100% - 20px, 980px);
        margin: 18px auto;
      }}
      .grid {{
        grid-template-columns: 1fr;
      }}
      .actions {{
        justify-content: stretch;
      }}
      button {{
        width: 100%;
      }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>PromptBase Profile Exporter</h1>
      <p>Run local exports without leaving your browser.</p>
    </header>
    {status_block}
    <form method="post" action="/export">
      <div class="grid">
        <div class="full">
          <label for="profile">PromptBase profile</label>
          <input id="profile" name="profile" value="{_h(request.profile_input)}"
            placeholder="https://promptbase.com/profile/acb" required>
        </div>
        <div>
          <label for="mode">Mode</label>
          {render_select("mode", WEB_MODES, request.mode)}
        </div>
        <div>
          <label for="format">Format</label>
          {render_select("format", EXPORT_FORMATS, request.export_format)}
        </div>
        <div>
          <label for="sort">Sort</label>
          {render_select("sort", SORT_OPTIONS, request.sort)}
        </div>
        <div>
          <label for="price_filter">Price</label>
          {render_select("price_filter", PRICE_FILTERS, request.price_filter)}
        </div>
        <div>
          <label for="domain">Domain filter</label>
          <input id="domain" name="domain" value="{_h(request.domain)}"
            placeholder="text,image">
        </div>
        <div>
          <label for="prompt_type">Type filter</label>
          <input id="prompt_type" name="prompt_type" value="{_h(request.prompt_type)}"
            placeholder="gpt,claude,chatgpt-image">
        </div>
        <div>
          <label for="min_price">Minimum price</label>
          <input id="min_price" name="min_price" inputmode="decimal"
            value="{_h(_format_optional_float(request.min_price))}" placeholder="0">
        </div>
        <div>
          <label for="max_price">Maximum price</label>
          <input id="max_price" name="max_price" inputmode="decimal"
            value="{_h(_format_optional_float(request.max_price))}" placeholder="10">
        </div>
        <div>
          <label for="since">Since</label>
          <input id="since" name="since" value="{_h(request.since)}" placeholder="2026-01-01">
        </div>
        <div>
          <label for="until">Until</label>
          <input id="until" name="until" value="{_h(request.until)}" placeholder="2026-12-31">
        </div>
        <div>
          <label for="limit">Limit</label>
          <input id="limit" name="limit" inputmode="numeric"
            value="{_h(_format_optional_int(request.limit))}" placeholder="50">
        </div>
        <div class="full">
          <label for="output_dir">Output directory</label>
          <input id="output_dir" name="output_dir" value="{_h(str(request.output_dir))}">
        </div>
        <label class="checkline">
          <input type="checkbox" name="timestamp_filenames" value="1"
            {_checked(request.timestamp_filenames)}>
          Timestamp filenames
        </label>
        <label class="checkline">
          <input type="checkbox" name="allow_missing_descriptions" value="1"
            {_checked(request.allow_missing_descriptions)}>
          Allow partial exports
        </label>
      </div>
      <div class="actions">
        <button type="submit">Export prompts</button>
      </div>
    </form>
  </main>
</body>
</html>
"""


def render_select(name: str, options: Sequence[str], selected: str) -> str:
    items = []
    for option in options:
        selected_attr = " selected" if option == selected else ""
        items.append(
            f'<option value="{_h(option)}"{selected_attr}>{_h(option)}</option>'
        )
    return f'<select id="{_h(name)}" name="{_h(name)}">\n' + "\n".join(items) + "\n</select>"


class PromptBaseWebHandler(BaseHTTPRequestHandler):
    server_version = f"PromptBaseProfileExporter/{__version__}"

    def do_GET(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        if path == "/healthz":
            self._send_text("ok\n")
            return
        if path in {"", "/"}:
            self._send_html(render_form())
            return
        self._send_text("not found\n", status=404)

    def do_POST(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        if path != "/export":
            self._send_text("not found\n", status=404)
            return

        request: ExportRequest | None = None
        try:
            form = self._read_form()
            request = build_request_config(form)
            result = run_export(request)
            self._send_html(render_form(request, result=result))
        except WebInputError as exc:
            self._send_html(render_form(request, error=str(exc)), status=400)
        except PromptBaseError as exc:
            self._send_html(render_form(request, error=str(exc)), status=502)
        except Exception as exc:  # pragma: no cover - last-resort web boundary
            self._send_html(
                render_form(request, error=f"Unexpected error: {exc}"),
                status=500,
            )

    def _read_form(self) -> Mapping[str, list[str]]:
        content_length = int(self.headers.get("Content-Length") or "0")
        if content_length > MAX_FORM_BYTES:
            raise WebInputError("Submitted form is too large.")
        body = self.rfile.read(content_length).decode("utf-8", errors="replace")
        return urllib.parse.parse_qs(body, keep_blank_values=True)

    def _send_html(self, body: str, *, status: int = 200) -> None:
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def _send_text(self, body: str, *, status: int = 200) -> None:
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)


def serve(host: str = "127.0.0.1", port: int = 8765) -> None:
    with ThreadingHTTPServer((host, port), PromptBaseWebHandler) as server:
        print(f"Serving PromptBase Profile Exporter at http://{host}:{port}/")
        server.serve_forever()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="promptbase-export-web",
        description="Start the local PromptBase Profile Exporter web UI.",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args(argv)

    try:
        serve(args.host, args.port)
    except KeyboardInterrupt:
        print("\nServer stopped.", file=sys.stderr)
    return 0


def _single_value(
    data: Mapping[str, str | Sequence[str]],
    name: str,
    default: str = "",
) -> str:
    value = data.get(name, default)
    if isinstance(value, str):
        return value
    if not value:
        return default
    return str(value[0])


def _parse_optional_price(
    data: Mapping[str, str | Sequence[str]],
    name: str,
) -> float | None:
    raw = _single_value(data, name).strip()
    if not raw:
        return None
    try:
        value = float(raw)
    except ValueError as exc:
        raise WebInputError(f"{name.replace('_', ' ').title()} must be a number.") from exc
    if value < 0:
        raise WebInputError(f"{name.replace('_', ' ').title()} cannot be negative.")
    return value


def _parse_optional_int(
    data: Mapping[str, str | Sequence[str]],
    name: str,
) -> int | None:
    raw = _single_value(data, name).strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError as exc:
        raise WebInputError(f"{name.replace('_', ' ').title()} must be an integer.") from exc
    if value <= 0:
        raise WebInputError(f"{name.replace('_', ' ').title()} must be greater than zero.")
    return value


def _as_bool(value: str) -> bool:
    return value.lower() in {"1", "true", "yes", "on"}


def _format_optional_float(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:g}"


def _format_optional_int(value: int | None) -> str:
    if value is None:
        return ""
    return str(value)


def _checked(value: bool) -> str:
    return "checked" if value else ""


def _h(value: object) -> str:
    return html.escape(str(value), quote=True)


if __name__ == "__main__":
    raise SystemExit(main())
