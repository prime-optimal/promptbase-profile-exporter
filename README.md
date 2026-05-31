# PromptBase Profile Exporter

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
- Splits output into `all`, `text`, and `image` views.
- Sorts every export from newest prompt to oldest prompt.
- Writes `txt`, `markdown`, `json`, or `csv` output.
- Paginates large profiles instead of stopping at the first page.
- Retries transient PromptBase/network failures with backoff.
- Performs basic validation before writing files.
- Uses only the Python standard library.

## Quick Start

```bash
git clone https://github.com/your-username/promptbase-profile-exporter.git
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
python -m promptbase_exporter https://promptbase.com/profile/acb --mode text
```

Export only image prompts:

```bash
python -m promptbase_exporter https://promptbase.com/profile/acb --mode image
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

Show help:

```bash
python -m promptbase_exporter --help
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
title, description, slug, url, type, domain, created
```

## Prompt Groups

The exporter uses PromptBase's public prompt metadata:

- `text`: prompts where `domain` is `text`
- `image`: prompts where `domain` is `image`
- `all`: every approved prompt returned for the profile, including text, image, video, or other domains if present

Every group is sorted by the prompt creation timestamp from newest to oldest.

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
6. Write clean exports in the requested format.

No login, API key, browser automation, or paid account is required.

## Responsible Use

Only export profiles and data you are allowed to use. This project is intended for public PromptBase listing metadata and personal backup/catalog workflows. PromptBase can change its public data model at any time, which may require updates to this tool.

## Development

Run tests:

```bash
python -m unittest discover -s tests
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
promptbase_exporter/
  __main__.py
  cli.py
  client.py
  formatting.py
  models.py
tests/
  test_formatting.py
  test_profile_input.py
```

## License

MIT License. See [LICENSE](LICENSE).
