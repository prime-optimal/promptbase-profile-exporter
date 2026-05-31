# Release Checklist

Use this checklist when publishing a new version.

## 1. Update Versioned Files

- `promptbase_exporter/__init__.py`
- `pyproject.toml`
- `CHANGELOG.md` (promote the `Unreleased` section to the new version)
- `@vX.Y.Z` pin examples in `README.md` and `docs/github-action.md`

## 2. Run Local Validation

```bash
python -m unittest discover -s tests
python -m ruff check .
python -m promptbase_exporter --version
python -m promptbase_exporter.web --version
python -m promptbase_exporter https://promptbase.com/profile/acb --dry-run
python -m promptbase_exporter https://promptbase.com/profile/acb --list-domains
```

## 3. Build Package

```bash
python -m pip install -e ".[dev]"
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

The tag is what users pin the GitHub Action to (`@vX.Y.Z`), so publishing the release completes the process.

## Optional: PyPI Publishing

This project is not published to PyPI; users install it by cloning the
repository or by pinning the GitHub Action to a release tag, neither of which
needs PyPI.

To add PyPI distribution later, configure [trusted publishing](https://docs.pypi.org/trusted-publishers/)
for the repository, add a `pypi` GitHub environment, and restore a publish
workflow that runs `python -m build` and `pypa/gh-action-pypi-publish` on
`release: published`.
