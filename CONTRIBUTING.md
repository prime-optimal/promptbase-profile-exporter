# Contributing

Thanks for helping improve PromptBase Profile Exporter.

## Development Setup

```bash
git clone https://github.com/IACBI/promptbase-profile-exporter.git
cd promptbase-profile-exporter
python -m pip install -e .
python -m unittest discover -s tests
```

## Pull Request Checklist

- Keep the project dependency-free unless a dependency is clearly justified.
- Add or update tests for behavior changes.
- Update `README.md` when user-facing commands change.
- Update `CHANGELOG.md` for notable changes.
- Run:

```bash
python -m unittest discover -s tests
python -m promptbase_exporter --version
```

## Manual Network Check

When changing PromptBase fetching behavior, run at least one real export:

```bash
python -m promptbase_exporter https://promptbase.com/profile/acb --dry-run
```

Avoid committing generated `exports/` files.
