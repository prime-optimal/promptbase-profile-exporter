# Release Checklist

Use this checklist when publishing a new version.

## 1. Update Versioned Files

- `promptbase_exporter/__init__.py`
- `pyproject.toml`
- `CHANGELOG.md`

## 2. Run Local Validation

```bash
python -m unittest discover -s tests
python -m promptbase_exporter --version
python -m promptbase_exporter https://promptbase.com/profile/acb --dry-run
python -m promptbase_exporter https://promptbase.com/profile/acb --list-domains
```

## 3. Build Package

```bash
python -m pip install build twine
python -m build
python -m twine check dist/*
```

## 4. Commit And Push

```bash
git add .
git commit -m "Release vX.Y.Z"
git push
```

## 5. Create GitHub Release

```bash
git tag vX.Y.Z
git push origin vX.Y.Z
```

Then create a GitHub Release from the tag and copy the relevant `CHANGELOG.md` section into the release notes.

## 6. PyPI Publishing

The `publish` GitHub Actions workflow is configured for PyPI trusted publishing.

Before the first release:

1. Create or claim the PyPI project name.
2. Configure PyPI trusted publishing for this GitHub repository.
3. Set the GitHub environment name to `pypi`.
4. Publish a GitHub Release.

No PyPI API token is required when trusted publishing is configured correctly.
