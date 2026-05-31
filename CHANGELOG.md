# Changelog

All notable changes to this project will be documented in this file.

## 0.5.0

- Add `--sort` with newest, oldest, title, price, views, sales, downloads, favorites, and rating options.
- Add richer JSON/CSV metadata: `created_iso`, `discount`, `views`, `sales`, `downloads`, `favorites`, `rating`, and `reviews`.
- Add `text-only` and `image-only` aliases for `--mode`.
- Show planned per-mode output counts during `--dry-run`.
- Add PyPI publish workflow scaffold.
- Add package build checks to CI.
- Modernize package license metadata for current setuptools builds.

## 0.4.0

- Add `--version`.
- Add `--dry-run`.
- Add `--list-domains` and `--list-types`.
- Add GitHub Actions package installation smoke checks.
- Add contributor and security documentation.

## 0.3.0

- Add metadata filters: `--domain`, `--type`, `--free-only`, `--paid-only`, `--min-price`, and `--max-price`.
- Add timestamped filenames with `--timestamp-filenames`.
- Add `--quiet` and `--verbose`.
- Include `price` in JSON and CSV exports.
- Add GitHub issue and pull request templates.

## 0.2.0

- Add Firestore pagination.
- Add retry/backoff for transient network and PromptBase errors.
- Add Markdown, JSON, and CSV export formats.
- Add `.gitattributes`.

## 0.1.0

- Initial CLI exporter.
- Export all, text-only, and image-only PromptBase prompt catalogs.
- Support TXT output.
