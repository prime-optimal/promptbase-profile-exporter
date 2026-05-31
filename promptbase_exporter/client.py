from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any

from .models import Profile, PromptRecord

FIRESTORE_RUN_QUERY = (
    "https://firestore.googleapis.com/v1/projects/"
    "promptbase/databases/(default)/documents:runQuery"
)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


class PromptBaseError(RuntimeError):
    """Raised when PromptBase public data cannot be resolved."""


def parse_profile_input(profile_input: str) -> str:
    """Return a PromptBase username from a URL, path, username, or @username."""
    raw = profile_input.strip()
    if not raw:
        raise PromptBaseError("Profile input is empty.")

    raw = raw.rstrip("/")
    parsed = urllib.parse.urlparse(raw)

    if parsed.scheme and parsed.netloc:
        path_parts = [part for part in parsed.path.split("/") if part]
        if len(path_parts) >= 2 and path_parts[0].lower() == "profile":
            return path_parts[1].lstrip("@")
        raise PromptBaseError(
            "Expected a PromptBase profile URL like "
            "https://promptbase.com/profile/username."
        )

    if raw.lower().startswith("profile/"):
        return raw.split("/", 1)[1].strip("/").lstrip("@")

    return raw.lstrip("@")


def firestore_value(value: dict[str, Any]) -> Any:
    if "stringValue" in value:
        return value["stringValue"]
    if "integerValue" in value:
        return int(value["integerValue"])
    if "doubleValue" in value:
        return float(value["doubleValue"])
    if "booleanValue" in value:
        return bool(value["booleanValue"])
    if "nullValue" in value:
        return None
    if "arrayValue" in value:
        values = value.get("arrayValue", {}).get("values", [])
        return [firestore_value(item) for item in values]
    if "mapValue" in value:
        fields = value.get("mapValue", {}).get("fields", {})
        return {key: firestore_value(item) for key, item in fields.items()}
    return value


def field_filter(field_path: str, op: str, value: dict[str, Any]) -> dict[str, Any]:
    return {"field": {"fieldPath": field_path}, "op": op, "value": value}


def _run_query(
    collection: str,
    filters: list[dict[str, Any]],
    *,
    order_by: list[dict[str, Any]] | None = None,
    limit: int = 500,
    start_after: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    if not filters:
        raise ValueError("At least one filter is required.")

    if len(filters) == 1:
        where: dict[str, Any] = {"fieldFilter": filters[0]}
    else:
        where = {
            "compositeFilter": {
                "op": "AND",
                "filters": [{"fieldFilter": item} for item in filters],
            }
        }

    structured_query: dict[str, Any] = {
        "from": [{"collectionId": collection}],
        "where": where,
        "limit": limit,
    }
    if order_by:
        structured_query["orderBy"] = order_by
    if start_after:
        structured_query["startAt"] = {"values": start_after, "before": False}

    request = urllib.request.Request(
        FIRESTORE_RUN_QUERY,
        data=json.dumps({"structuredQuery": structured_query}).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
    )

    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            rows = json.load(response)
    except Exception as exc:  # pragma: no cover - exercised in real network runs.
        raise PromptBaseError(f"PromptBase query failed: {exc}") from exc

    docs: list[dict[str, Any]] = []
    for row in rows:
        document = row.get("document")
        if not document:
            continue
        fields = {
            key: firestore_value(item)
            for key, item in document.get("fields", {}).items()
        }
        fields["_doc_name"] = document["name"]
        docs.append(fields)
    return docs


def _order_by(field_path: str, direction: str) -> dict[str, Any]:
    return {"field": {"fieldPath": field_path}, "direction": direction}


def resolve_profile(profile_input: str) -> Profile:
    username = parse_profile_input(profile_input)
    docs = _run_query(
        "Items",
        [
            field_filter("username", "EQUAL", {"stringValue": username}),
            field_filter("itemType", "EQUAL", {"stringValue": "profile"}),
        ],
        limit=5,
    )
    if not docs:
        raise PromptBaseError(f"Profile not found: {username}")

    profile_doc = docs[0]
    uid = profile_doc.get("uid") or profile_doc.get("id") or profile_doc.get("itemId")
    if not uid:
        raise PromptBaseError(f"Profile UID could not be resolved: {username}")
    return Profile(username=username, uid=str(uid))


def fetch_prompt_items(profile: Profile) -> list[dict[str, Any]]:
    docs = _run_query(
        "Items",
        [
            field_filter("status", "EQUAL", {"stringValue": "approved"}),
            field_filter("uid", "EQUAL", {"stringValue": profile.uid}),
            field_filter("itemType", "EQUAL", {"stringValue": "prompt"}),
        ],
        order_by=[
            _order_by("created", "DESCENDING"),
            _order_by("__name__", "DESCENDING"),
        ],
        limit=1000,
    )

    seen_slugs: set[str] = set()
    prompts: list[dict[str, Any]] = []
    for doc in docs:
        slug = str(doc.get("slug") or "").strip()
        title = str(doc.get("title") or "").strip()
        if not slug or not title or slug in seen_slugs:
            continue
        seen_slugs.add(slug)
        prompts.append(doc)
    return prompts


def fetch_prompt_details(profile: Profile) -> dict[str, dict[str, Any]]:
    docs = _run_query(
        "PromptDetails",
        [field_filter("uid", "EQUAL", {"stringValue": profile.uid})],
        order_by=[_order_by("__name__", "ASCENDING")],
        limit=1000,
    )

    by_slug: dict[str, dict[str, Any]] = {}
    for doc in docs:
        slug = str(doc.get("slug") or "").strip()
        if not slug:
            continue
        if slug not in by_slug or int(doc.get("created") or 0) >= int(
            by_slug[slug].get("created") or 0
        ):
            by_slug[slug] = doc
    return by_slug


def fetch_prompts(profile_input: str) -> tuple[Profile, list[PromptRecord]]:
    profile = resolve_profile(profile_input)
    items = fetch_prompt_items(profile)
    details_by_slug = fetch_prompt_details(profile)

    records: list[PromptRecord] = []
    for item in items:
        slug = str(item.get("slug") or "").strip()
        details = details_by_slug.get(slug, {})
        records.append(
            PromptRecord(
                title=str(item.get("title") or "").strip(),
                description=str(details.get("description") or "").strip(),
                slug=slug,
                prompt_type=str(item.get("type") or "").strip(),
                domain=str(item.get("domain") or "").strip(),
                created=int(item.get("created") or 0),
            )
        )

    records.sort(key=lambda record: (record.created, record.slug), reverse=True)
    return profile, records
