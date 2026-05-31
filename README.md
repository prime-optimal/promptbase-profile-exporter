# PromptBase Profile Exporter

[![tests](https://github.com/IACBI/promptbase-profile-exporter/actions/workflows/tests.yml/badge.svg)](https://github.com/IACBI/promptbase-profile-exporter/actions/workflows/tests.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Export public PromptBase profile prompts into clean, readable catalog files.

This small command-line tool takes a PromptBase profile URL, finds the public prompts on that profile, pulls each prompt title and description, and writes curated exports:

- all approved prompts
- text prompts only
- image prompts only

It is designed for prompt creators who want to back up, audit, share, or publish a clear catalog of their PromptBase listings.

## Features

- Accepts a full profile URL, profile path, username, or `@username`.
- Resolves the profile automatically through public PromptBase data.
- Exports title and description for every approved prompt.
- Splits output into `all`, `text`, and `image` views, with `text-only` and `image-only` aliases.
- Sorts every export from newest prompt to oldest prompt.
- Writes `txt`, `markdown`, `json`, or `csv` output.
- Filters by PromptBase domain, model/type, free/paid status, price range, date, or result limit.
- Sorts by newest, oldest, title, price, views, sales, downloads, favorites, or rating.
- Exports richer JSON/CSV metadata such as views, sales, downloads, favorites, rating, and reviews.
- Compares current exports against previous catalog files.
- Updates an existing catalog file in place when requested.
- Includes a local no-framework web UI.
- Includes a reusable GitHub Action for scheduled catalog exports.
- Can append timestamps to filenames for repeatable backups.
- Supports dry runs and quick domain/type inventory summaries.
- Paginates large profiles instead of stopping at the first page.
- Retries transient PromptBase/network failures with backoff.
- Performs basic validation before writing files.
- Uses only the Python standard library.

## Quick Start

```bash
git clone https://github.com/IACBI/promptbase-profile-exporter.git
cd promptbase-profile-exporter
python -m promptbase_exporter https://promptbase.com/profile/acb
```

The command creates an `exports/` folder with files like:

```text
exports/acb_all_prompts.txt
exports/acb_text_prompts.txt
exports/acb_image_prompts.txt
```

## Installation

No third-party packages are required.

Recommended:

```bash
python --version
```

Use Python 3.10 or newer.

Optional editable install:

```bash
python -m pip install -e .
promptbase-export https://promptbase.com/profile/acb
```

## Usage

Export all three files:

```bash
python -m promptbase_exporter https://promptbase.com/profile/acb
```

Export only text prompts:

```bash
python -m promptbase_exporter https://promptbase.com/profile/acb --mode text-only
```

Export only image prompts:

```bash
python -m promptbase_exporter https://promptbase.com/profile/acb --mode image-only
```

Short aliases are also supported:

```bash
python -m promptbase_exporter @acb --mode text
python -m promptbase_exporter @acb --mode image
```

Export all prompts into a custom folder:

```bash
python -m promptbase_exporter @acb --mode all --output-dir my_exports
```

Export Markdown files:

```bash
python -m promptbase_exporter @acb --format markdown
```

Export JSON for another tool:

```bash
python -m promptbase_exporter @acb --mode all --format json
```

Export CSV for spreadsheets:

```bash
python -m promptbase_exporter @acb --mode text --format csv
```

Export only Claude text prompts:

```bash
python -m promptbase_exporter @acb --mode text --type claude
```

Export paid prompts between two prices:

```bash
python -m promptbase_exporter @acb --paid-only --min-price 2 --max-price 6
```

Sort by price, views, or title:

```bash
python -m promptbase_exporter @acb --sort price
python -m promptbase_exporter @acb --sort views
python -m promptbase_exporter @acb --sort title
```

Preview what would be exported without writing files:

```bash
python -m promptbase_exporter @acb --dry-run
```

List domains and PromptBase types:

```bash
python -m promptbase_exporter @acb --list-domains
python -m promptbase_exporter @acb --list-types
```

Create timestamped backup files:

```bash
python -m promptbase_exporter @acb --timestamp-filenames
```

Show help:

```bash
python -m promptbase_exporter --help
```

Show the installed version:

```bash
promptbase-export --version
```

Portable module form:

```bash
python -m promptbase_exporter --version
```

Start the local web UI:

```bash
python -m promptbase_exporter.web
```

Then open `http://127.0.0.1:8765/`.

If installed with the project script:

```bash
promptbase-export-web
```

### Web UI security model

The web UI is intended for **local, single-user** use:

- It binds to `127.0.0.1` (loopback) by default and is unauthenticated.
  The `/export` endpoint fetches remote data and writes files, so do not
  expose it to untrusted networks. Passing `--host 0.0.0.0` prints a
  warning because it makes that endpoint reachable by other hosts.
- Requests to `/export` are checked for a matching `Host` header and a
  same-origin `Origin`/`Sec-Fetch-Site`, mitigating CSRF and DNS-rebinding
  from pages opened in your browser.
- Exports are confined to the directory the server was started in. Absolute
  paths and `..` traversal in the "Output directory" field are rejected.
  (The CLI, which you run yourself, still accepts arbitrary paths.)

## Output Formats

The default `.txt` file uses a simple numbered format:

```text
1.
Title: Example Prompt Title
Description:
The public PromptBase description appears here.

2.
Title: Another Prompt
Description:
Another public description appears here.
```

Markdown output is designed for GitHub-readable catalogs. JSON and CSV output include these fields:

```text
title, description, slug, url, type, domain, created, created_iso, price,
discount, views, sales, downloads, favorites, rating, reviews
```

## Prompt Groups

The exporter uses PromptBase's public prompt metadata:

- `text`: prompts where `domain` is `text`
- `image`: prompts where `domain` is `image`
- `all`: every approved prompt returned for the profile, including text, image, video, or other domains if present

Every group is sorted by the prompt creation timestamp from newest to oldest.

## Filters

Filters are applied before `--mode` output splitting:

- `--domain text,image,video`
- `--type gpt,claude,chatgpt-image`
- `--free-only`
- `--paid-only`
- `--min-price 2`
- `--max-price 10`
- `--since 2026-01-01`
- `--until 2026-12-31`
- `--limit 25`

For example, this writes only paid GPT prompts into JSON:

```bash
python -m promptbase_exporter @acb --mode all --format json --type gpt --paid-only
```

Date and count filters are also available:

```bash
python -m promptbase_exporter @acb --since 2026-01-01 --until 2026-12-31
python -m promptbase_exporter @acb --sort views --limit 25
```

Sorting is applied after filters and before writing:

- `--sort newest`
- `--sort oldest`
- `--sort title`
- `--sort price`
- `--sort views`
- `--sort sales`
- `--sort downloads`
- `--sort favorites`
- `--sort rating`

## Compare And Update

Compare the current profile catalog against an existing export:

```bash
python -m promptbase_exporter @acb --mode all --format json --compare exports/acb_all_prompts.json
```

Write a comparison report:

```bash
python -m promptbase_exporter @acb --mode all --compare exports/acb_all_prompts.json --diff-output exports/catalog-diff.md
```

Refresh an existing catalog file in place:

```bash
python -m promptbase_exporter @acb --mode all --update-file exports/acb_all_prompts.json
```

Write one exact file path instead of using the generated filename:

```bash
python -m promptbase_exporter @acb --mode text --output-file exports/text-prompts.csv --format csv
```

Existing `--output-file` targets are protected by default. Add `--overwrite` when replacing that file is intentional.

For CI workflows, make catalog changes fail the command with exit code `2`:

```bash
python -m promptbase_exporter @acb --mode all --compare exports/acb_all_prompts.json --fail-on-diff
```

## GitHub Action

This repository can be used as a composite GitHub Action:

```yaml
- uses: IACBI/promptbase-profile-exporter@v0.6.0
  with:
    profile-url: https://promptbase.com/profile/acb
    mode: split
    format: markdown
    output-dir: exports
```

See [docs/github-action.md](docs/github-action.md) for scheduled exports, artifact uploads, and workflows that commit updated catalogs back to a repository.

## Validation

Before writing files, the tool checks that:

- the profile exists
- approved prompts were found
- prompt details were matched by slug when available
- output records are sorted newest to oldest
- written files contain the expected number of records

If descriptions are missing for any prompt, the command finishes with a non-zero exit code unless `--allow-missing-descriptions` is used.

The exporter also checks for expected public data fields. If PromptBase changes its public data model, the command reports a schema-change error instead of silently producing a misleading catalog.

## Exit Codes

The `promptbase-export` command uses these exit codes so it can be scripted in CI:

| Code | Meaning |
| ---- | ------- |
| `0` | Success (including a clean `--compare` with no differences). |
| `1` | Error: invalid arguments, profile not found, no matching prompts, missing descriptions without `--allow-missing-descriptions`, or a write/validation failure. |
| `2` | `--fail-on-diff` was set and `--compare`/`--update-file` found added, removed, or changed records. |

Use code `2` to gate a pipeline on catalog drift; the GitHub Action exposes this through its `fail-on-diff` input.

## How It Works

PromptBase is a dynamic site backed by public Firebase/Firestore data. This tool reads the same public data used by the profile and prompt pages:

1. Extract the username from the profile URL.
2. Resolve the profile document and user id.
3. Fetch approved prompt items for that user id.
4. Fetch matching prompt detail documents.
5. Merge title, slug, type, domain, creation time, and description.
6. Apply user-selected filters.
7. Write clean exports in the requested format.

No login, API key, browser automation, or paid account is required.

## Responsible Use

Only export profiles and data you are allowed to use. This project is intended for public PromptBase listing metadata and personal backup/catalog workflows. PromptBase can change its public data model at any time, which may require updates to this tool.

## Development

Run tests:

```bash
python -m unittest discover -s tests
```

Run lint:

```bash
python -m pip install -e ".[dev]"
python -m ruff check .
```

Build the package:

```bash
python -m pip install -e ".[dev]"
python -m build
python -m twine check dist/*
```

Run the module locally:

```bash
python -m promptbase_exporter https://promptbase.com/profile/acb --mode split
```

## Publish To GitHub

From inside the project folder:

```bash
git init
git add .
git commit -m "Initial PromptBase profile exporter"
git branch -M main
git remote add origin https://github.com/your-username/promptbase-profile-exporter.git
git push -u origin main
```

Replace `your-username` with your GitHub username and create the empty repository on GitHub before pushing.

## Repository Structure

```text
.github/
  workflows/
    tests.yml
    publish.yml
promptbase_exporter/
  __main__.py
  cli.py
  client.py
  diffing.py
  formatting.py
  models.py
  web.py
tests/
  test_cli.py
  test_client.py
  test_diffing.py
  test_formatting.py
  test_profile_input.py
  test_web.py
CHANGELOG.md
CONTRIBUTING.md
docs/
  github-action.md
RELEASE.md
SECURITY.md
action.yml
```

## License

MIT License. See [LICENSE](LICENSE).
