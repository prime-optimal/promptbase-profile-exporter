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
- Filters by PromptBase domain, model/type, free/paid status, or price range.
- Sorts by newest, oldest, title, price, views, sales, downloads, favorites, or rating.
- Exports richer JSON/CSV metadata such as views, sales, downloads, favorites, rating, and reviews.
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

For example, this writes only paid GPT prompts into JSON:

```bash
python -m promptbase_exporter @acb --mode all --format json --type gpt --paid-only
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

## Validation

Before writing files, the tool checks that:

- the profile exists
- approved prompts were found
- prompt details were matched by slug when available
- output records are sorted newest to oldest
- written files contain the expected number of records

If descriptions are missing for any prompt, the command finishes with a non-zero exit code unless `--allow-missing-descriptions` is used.

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

Build the package:

```bash
python -m pip install build twine
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
  formatting.py
  models.py
tests/
  test_cli.py
  test_client.py
  test_formatting.py
  test_profile_input.py
CHANGELOG.md
CONTRIBUTING.md
RELEASE.md
SECURITY.md
```

## License

MIT License. See [LICENSE](LICENSE).
