"""
integrations/confluence_mcp.py — Confluence integration
Status: IMPLEMENTED (Cloud + Server/DC)

Supported connection modes:
  Cloud:     CONFLUENCE_URL + CONFLUENCE_USERNAME + CONFLUENCE_API_TOKEN + CONFLUENCE_CLOUD=true
  Server/DC: CONFLUENCE_URL + CONFLUENCE_API_TOKEN (PAT, Confluence 7.9+) + CONFLUENCE_CLOUD=false

Configuration via environment variables:
  CONFLUENCE_URL        — base URL (https://your-domain.atlassian.net or https://wiki.company.com)
  CONFLUENCE_USERNAME   — email (Cloud) or login (Server). Not needed for Server/DC PAT.
  CONFLUENCE_API_TOKEN  — API token (Cloud) or Personal Access Token (Server)
  CONFLUENCE_CLOUD      — "true" for Cloud, "false" for Server (default "true")
  CONFLUENCE_SPACE_KEY  — default space key (for example "BA", "PROJ")

MCP tools:
  - push_to_confluence   — export a Markdown artifact → Confluence page
  - pull_from_confluence — import a Confluence page → JSON for init_traceability_repo (5.1)
  - sync_page            — update an existing page (synchronization)
  - list_space_pages     — list the pages of a space (to choose before import)
  - publish_artifact_to_confluence — publish a SAVED artifact by project + selector

Additionally:
  - export_artifact_to_confluence() — helper function for the _export_hook() hook in 5.2

Dependencies (added to requirements.txt):
  atlassian-python-api>=3.41.0
  markdown2>=2.4.0

# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""

import json
import os
import re
from html import unescape as _html_unescape
from datetime import date, datetime
from typing import Optional
from mcp.server.fastmcp import FastMCP
from skills.common import (
    save_artifact, logger, normalize_project_id, report_dir_for, specs_dir,
)

mcp = FastMCP("BABOK_Confluence_Integration")


# ---------------------------------------------------------------------------
# Utilities: connection and format conversion
# ---------------------------------------------------------------------------

def _get_confluence_client():
    """
    Creates a Confluence client from environment variables.
    Returns: (confluence_client, error_message_or_None)
    """
    try:
        from atlassian import Confluence
    except ImportError:
        return None, (
            "❌ The `atlassian-python-api` library is not installed.\n"
            "Install it: `pip install atlassian-python-api`"
        )

    url = os.environ.get("CONFLUENCE_URL", "").rstrip("/")
    username = os.environ.get("CONFLUENCE_USERNAME", "")
    api_token = os.environ.get("CONFLUENCE_API_TOKEN", "")
    is_cloud = os.environ.get("CONFLUENCE_CLOUD", "true").lower() == "true"

    if not url:
        return None, (
            "❌ The `CONFLUENCE_URL` environment variable is not set.\n"
            "Cloud:  export CONFLUENCE_URL=https://your-domain.atlassian.net\n"
            "Server: export CONFLUENCE_URL=https://wiki.company.com"
        )
    if not api_token:
        return None, (
            "❌ `CONFLUENCE_API_TOKEN` is not set.\n"
            "Cloud:  get one at https://id.atlassian.com/manage-profile/security/api-tokens\n"
            "Server: Settings → Personal Access Tokens (Confluence 7.9+)"
        )

    try:
        if is_cloud:
            if not username:
                return None, "❌ Cloud requires CONFLUENCE_USERNAME (the Atlassian account email)."
            confluence = Confluence(
                url=url,
                username=username,
                password=api_token,
                cloud=True,
            )
        else:
            # Server/DC with a Personal Access Token
            confluence = Confluence(
                url=url,
                token=api_token,
            )
        return confluence, None
    except Exception as e:
        return None, f"❌ Failed to initialize the Confluence client: {e}"


def _markdown_tables_to_html(text: str) -> str:
    """Converts pipe tables to XHTML for the no-markdown2 fallback.

    Every BABOK artifact this integration publishes is table-heavy, so leaving raw
    pipes would ship an unreadable page. Runs on already-escaped text.
    """
    out = []
    rows = []

    def flush():
        if not rows:
            return
        body = []
        for i, cells in enumerate(rows):
            tag = "th" if i == 0 else "td"
            body.append("<tr>" + "".join(f"<{tag}>{c}</{tag}>" for c in cells) + "</tr>")
        out.append("<table><tbody>" + "".join(body) + "</tbody></table>")
        rows.clear()

    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|") and len(stripped) > 1:
            cells = [c.strip() for c in stripped[1:-1].split("|")]
            # the |---|---| separator row carries no data
            if all(re.fullmatch(r':?-{2,}:?', c or "") for c in cells):
                continue
            rows.append(cells)
        else:
            flush()
            out.append(line)
    flush()
    return "\n".join(out)


def _markdown_to_confluence_storage(markdown_text: str) -> str:
    """
    Converts Markdown → Confluence Storage Format (XHTML-like).
    Uses markdown2 if available, otherwise a basic regex conversion.
    """
    # Strip HTML comments (our metadata <!-- BABOK ... -->)
    text = re.sub(r'<!--.*?-->', '', markdown_text, flags=re.DOTALL)

    try:
        import markdown2
        html = markdown2.markdown(
            text,
            extras=["tables", "fenced-code-blocks", "header-ids"]
        )
    except ImportError:
        # Fallback when markdown2 is missing. Confluence storage format is strict
        # XHTML, so '&' and '<' MUST be escaped first — an NFR like "response < 2s"
        # or any '&' in the text otherwise makes the body invalid XML and Confluence
        # rejects the whole request with a 400. markdown2 does this itself.
        html = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
        html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
        html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
        html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
        html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)
        html = re.sub(r'`([^`]+)`', r'<code>\1</code>', html)
        html = _markdown_tables_to_html(html)
        paragraphs = html.split('\n\n')
        html = ''.join(
            f'<p>{p.strip()}</p>' if not p.strip().startswith('<') else p
            for p in paragraphs if p.strip()
        )

    html = re.sub(r'<p>\s*</p>', '', html)
    return html.strip()


def _confluence_storage_to_text(storage_content: str) -> str:
    """
    Converts Confluence Storage Format → readable text.
    Preserves the structure for subsequent requirements parsing.
    """
    text = storage_content
    text = re.sub(r'<h1[^>]*>(.*?)</h1>', r'\n# \1\n', text, flags=re.DOTALL)
    text = re.sub(r'<h2[^>]*>(.*?)</h2>', r'\n## \1\n', text, flags=re.DOTALL)
    text = re.sub(r'<h3[^>]*>(.*?)</h3>', r'\n### \1\n', text, flags=re.DOTALL)
    text = re.sub(r'<tr[^>]*>', '\n| ', text)
    text = re.sub(r'<t[hd][^>]*>(.*?)</t[hd]>', r'\1 | ', text, flags=re.DOTALL)
    text = re.sub(r'<li[^>]*>(.*?)</li>', r'\n- \1', text, flags=re.DOTALL)
    text = re.sub(r'<br\s*/?>', '\n', text)
    # Block-level elements END A LINE. Without this, "<p>FR-001 …</p><p>BR-002 …</p>"
    # collapses into a single line, the next ID gets glued to the previous text
    # ("routingBR-002"), the \b in the ID pattern stops matching — and that
    # requirement is silently dropped from the import.
    text = re.sub(r'</(p|div|h[1-6]|blockquote|pre|tr|table|ul|ol)\s*>', '\n', text,
                  flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    # Confluence storage format is XHTML: '&', '<' and typographic characters are
    # always entity-encoded. Without decoding, requirement titles carry literal
    # '&mdash;' / '&amp;' / '&lt;' into the 5.1 repository and every report downstream.
    text = _html_unescape(text)
    text = text.replace('\xa0', ' ')
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _extract_requirements_heuristic(text: str, source_url: str) -> list:
    """
    Heuristically extracts requirements from the page text.
    Looks for ID patterns: BR-001, FR-007, NFR-003, US-012, etc.
    """
    requirements = []
    seen_ids = set()

    id_pattern = re.compile(
        r'\b(BR|SR|FR|NFR|TR|UC|US|REQ|FUNC|NFUNC)[-_](\d+)\b',
        re.IGNORECASE
    )
    type_map = {
        "BR": "business", "SR": "stakeholder",
        "FR": "solution", "NFR": "solution",
        "TR": "transition", "UC": "solution",
        "US": "solution", "REQ": "solution",
        "FUNC": "solution", "NFUNC": "solution",
    }

    for line in text.split('\n'):
        for match in id_pattern.finditer(line):
            req_id = match.group(0).upper().replace("_", "-")
            if req_id in seen_ids:
                continue
            seen_ids.add(req_id)

            prefix = match.group(1).upper()
            title = id_pattern.sub("", line).strip()
            # Trim separators left over from the source markup: leading bullets and
            # dashes (incl. the en/em dashes Confluence encodes as entities) and the
            # trailing table-cell pipe produced by the storage→text conversion.
            title = re.sub(r'^[\s|\-–—:.]+', '', title)
            title = re.sub(r'[\s|]+$', '', title).strip()
            title = title[:120] if title else f"Requirement {req_id}"

            requirements.append({
                "id": req_id,
                "type": type_map.get(prefix, "solution"),
                "title": title or f"Requirement {req_id}",
                "version": "1.0",
                "status": "draft",
                "source_artifact": source_url,
            })

    return requirements


def _default_space_key() -> str:
    return os.environ.get("CONFLUENCE_SPACE_KEY", "")


def _cql_escape(value: str) -> str:
    """Escapes a value for embedding in a quoted CQL string literal."""
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _normalize_search_hit(item: dict) -> dict:
    """Normalizes one CQL search hit to a page object.

    `rest/api/search` wraps the page under a `content` key, while the plain content
    endpoints return the page object directly. Accept BOTH shapes rather than betting
    on one. The modification timestamp also lives in different places: `lastModified`
    on the search hit, `version.when` on the content object.
    """
    if not isinstance(item, dict):
        return {}
    inner = item.get("content")
    page = dict(inner) if isinstance(inner, dict) else dict(item)

    version = page.get("version")
    version = dict(version) if isinstance(version, dict) else {}
    if not version.get("when") and item.get("lastModified"):
        version["when"] = item["lastModified"]
    if version:
        page["version"] = version
    if not page.get("title") and item.get("title"):
        page["title"] = item["title"]
    return page


def _base_web_url() -> str:
    """Base URL of the Confluence web UI, without a trailing slash.

    Cloud serves the web UI under the /wiki context path; Server/DC serves it at the
    site root. Used only as a fallback when the API response carries no `_links.base`.
    """
    env_url = os.environ.get("CONFLUENCE_URL", "").rstrip("/")
    is_cloud = os.environ.get("CONFLUENCE_CLOUD", "true").lower() == "true"
    return f"{env_url}/wiki" if is_cloud else env_url


def _page_url(page: dict) -> str:
    """Builds the full page URL from a Confluence API response object.

    Prefers the `_links.base` the API itself returns — it already carries the right
    context path for both deployments (Cloud ends with /wiki, Server/DC does not).
    Falls back to _base_web_url() for responses that omit it (get_page_by_title
    returns a search hit whose _links has no `base`).
    """
    links = page.get("_links", {}) if isinstance(page, dict) else {}
    url_path = links.get("webui", "")
    base = (links.get("base") or "").rstrip("/") or _base_web_url()
    return f"{base}{url_path}" if url_path else base


# ---------------------------------------------------------------------------
# Artifact publishing: filename -> stable page identity
# ---------------------------------------------------------------------------

# save_artifact writes "{prefix}_{YYYYmmdd_HHMMSS}.md", so stripping the suffix
# leaves the prefix — which is the artifact's stable identity, because the
# producing tool chose it and put its own discriminator in it.
_TIMESTAMP_RE = re.compile(r"_\d{8}_\d{6}\.md$", re.IGNORECASE)

# A small CLOSED vocabulary, cosmetic only. This is deliberately NOT a per-artifact
# label map: such a map would need an entry for every new artifact type and would
# render a wrong title for anything not yet added. An unlisted acronym here renders
# as "Cr" — still stable, still a correct identity.
_TITLE_ACRONYMS = {"cr", "uc"}


def _strip_timestamp(filename: str) -> str:
    """'5_5_approval_record_v1.0_20260720_151747.md' -> '5_5_approval_record_v1.0'."""
    base = os.path.basename(filename)
    stripped = _TIMESTAMP_RE.sub("", base)
    if stripped != base:
        return stripped
    return base[:-3] if base.lower().endswith(".md") else base


def _humanize_stem(stem: str) -> str:
    """Turns an artifact prefix into a readable page title fragment.

    Tokens containing a digit or an uppercase letter are emitted verbatim — that is
    what protects version and id discriminators like 'v1.0' and 'CR-003'.
    """
    stem = re.sub(r"^(\d)_(\d)_", r"\1.\2 ", stem)
    words = []
    for word in stem.replace("_", " ").split():
        if any(ch.isdigit() for ch in word) or any(ch.isupper() for ch in word):
            words.append(word)
        elif word.lower() in _TITLE_ACRONYMS:
            words.append(word.upper())
        else:
            words.append(word[:1].upper() + word[1:])
    return " ".join(words)


def _derive_page_title(project_id: str, path: str) -> str:
    """Builds the Confluence page title for a stored artifact.

    Several producers already embed the project in the prefix (6_1_current_state_{pid},
    6_2_future_state_{pid}, 5_3_prioritization_{project}); prepending the project again
    would title those "crm — 6.1 Current State crm". The trailing project id is stripped
    instead of skipping the prefix, so every page of a project shares one title shape and
    sorts together in the wiki.

    `endswith` rather than a substring test: a project literally named "state" would
    match "6_1_current_state_..." by accident and silently lose its prefix. Every real
    producer puts the project id last, so this covers all actual cases.
    """
    stem = _strip_timestamp(path)
    norm = normalize_project_id(project_id)
    if norm and stem.lower().endswith("_" + norm):
        stem = stem[: -(len(norm) + 1)]
    return f"{project_id} — {_humanize_stem(stem)}"


def _artifact_roots(project_id: str) -> list:
    """The two directories a project's publishable documents live in.

    `specs/` is included because 7.1 specifications are a real deliverable for a
    developer and do NOT live under reports/ — a consumer has tripped over exactly
    that before (finding 7.1-A).
    """
    roots = []
    for root in (report_dir_for(project_id), specs_dir(project_id)):
        if os.path.isdir(root) and root not in roots:
            roots.append(root)
    return roots


def _artifact_sort_key(path: str) -> float:
    """Sorts by the timestamp in the NAME, so a copied or restored file keeps its
    identity. A legacy artifact without one falls back to mtime, so it stays
    reachable rather than becoming invisible."""
    match = _TIMESTAMP_RE.search(os.path.basename(path))
    if match:
        try:
            return datetime.strptime(match.group(0)[1:-3], "%Y%m%d_%H%M%S").timestamp()
        except ValueError:
            pass
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0.0


def _list_artifacts(project_id: str) -> list:
    """Every .md in the project's roots, newest first. Both roots are ONE pool."""
    found = []
    for root in _artifact_roots(project_id):
        for name in os.listdir(root):
            if name.lower().endswith(".md"):
                found.append(os.path.join(root, name))
    return sorted(found, key=_artifact_sort_key, reverse=True)


def _artifact_listing(project_id: str) -> str:
    """Human-readable inventory + the search scope.

    The scope is printed in EVERY outcome: INT-H taught that a bare 'found nothing'
    is ambiguous between 'the thing is absent' and 'we looked in the wrong place'.
    """
    roots = _artifact_roots(project_id)
    scope = ", ".join(f"`{r}`" for r in roots) if roots else "(no project directories exist yet)"
    lines = [f"**Searched in:** {scope}", ""]
    artifacts = _list_artifacts(project_id)
    if not artifacts:
        lines.append(f"No .md artifacts found for project `{project_id}`.")
        return "\n".join(lines)
    lines += ["**Available artifacts (newest first):**", ""]
    for path in artifacts:
        lines.append(f"- `{os.path.basename(path)}`")
    lines += ["", "Pass one of these, or its prefix, as `artifact`."]
    return "\n".join(lines)


def _resolve_artifact(project_id: str, selector: str):
    """Finds the artifact to publish.

    Returns (path, note) on success — note explains the choice — or (None, message)
    on failure, where message is ready to be returned to the caller as-is.
    """
    roots = _artifact_roots(project_id)

    if not selector:
        return None, (
            f"ℹ️ Specify which artifact to publish (`artifact`).\n\n"
            + _artifact_listing(project_id)
        )

    # An explicit path: accept it only inside the project's own directories.
    # Publishing is outward-facing and effectively irreversible — a mistyped path
    # pushes an unintended local file into a shared wiki, where it may be read or
    # indexed before anyone notices. Refusing costs a retry; publishing does not undo.
    if os.path.isfile(selector):
        real = os.path.realpath(selector)
        inside = False
        for root in roots:
            real_root = os.path.realpath(root)
            try:
                if os.path.commonpath([real, real_root]) == real_root:
                    inside = True
                    break
            except ValueError:
                continue  # different drives on Windows
        if not inside:
            allowed = ", ".join(f"`{r}`" for r in roots) if roots else "(none exist yet)"
            return None, (
                f"❌ `{selector}` is outside project `{project_id}`.\n"
                f"Publishing is irreversible, so only the project's own directories "
                f"are allowed: {allowed}"
            )
        return real, f"Publishing `{os.path.basename(real)}` (explicit path)."

    # Otherwise a filename prefix, case-insensitive.
    needle = selector.lower()
    matches = [p for p in _list_artifacts(project_id)
               if os.path.basename(p).lower().startswith(needle)]

    if not matches:
        return None, (
            f"❌ Nothing matches `{selector}` in project `{project_id}`.\n\n"
            + _artifact_listing(project_id)
        )

    chosen = matches[0]
    if len(matches) > 1:
        note = (f"Publishing `{os.path.basename(chosen)}` — newest of "
                f"{len(matches)} matching `{selector}`.")
    else:
        note = f"Publishing `{os.path.basename(chosen)}`."
    return chosen, note


# ---------------------------------------------------------------------------
# MCP 1 — Export an artifact to Confluence
# ---------------------------------------------------------------------------

@mcp.tool()
def push_to_confluence(
    content_markdown: str,
    page_title: str,
    space_key: str = "",
    parent_page_title: str = "",
    update_if_exists: bool = True,
) -> str:
    """
    Exports a Markdown artifact to Confluence as a page.
    If the page exists and update_if_exists=True — updates it. Otherwise creates a new one.

    Args:
        content_markdown:   Markdown content (an artifact from any BABOK task).
        page_title:         Page title in Confluence.
        space_key:          Space key (BA, PROJ...). If empty — from CONFLUENCE_SPACE_KEY.
        parent_page_title:  Parent page title (optional).
        update_if_exists:   True — update if it exists. False — error if it exists.

    Returns:
        The result with the page URL.
    """
    logger.info(f"push_to_confluence: '{page_title}' → space='{space_key}'")

    confluence, error = _get_confluence_client()
    if error:
        return error

    space = space_key or _default_space_key()
    if not space:
        return "❌ space_key not provided. Set the parameter or the CONFLUENCE_SPACE_KEY variable."

    html_content = _markdown_to_confluence_storage(content_markdown)

    parent_id = None
    if parent_page_title:
        try:
            parent_page = confluence.get_page_by_title(space=space, title=parent_page_title)
            if parent_page:
                parent_id = parent_page.get("id")
            else:
                return f"❌ Parent page '{parent_page_title}' not found in '{space}'."
        except Exception as e:
            return f"❌ Error while searching for the parent page: {e}"

    try:
        existing = confluence.get_page_by_title(space=space, title=page_title)

        if existing:
            if not update_if_exists:
                return (
                    f"⚠️ Page '{page_title}' already exists.\n"
                    f"URL: {_page_url(existing)}\n"
                    f"Use update_if_exists=True to update it."
                )
            result = confluence.update_page(
                page_id=existing["id"],
                title=page_title,
                body=html_content,
                parent_id=parent_id,
            )
            operation = "updated"
        else:
            result = confluence.create_page(
                space=space,
                title=page_title,
                body=html_content,
                parent_id=parent_id,
            )
            operation = "created"

        if not result:
            return f"❌ Confluence returned an empty response. Check permissions in space '{space}'."

        full_url = _page_url(result)

        return (
            f"✅ Page {operation}: **{page_title}**\n\n"
            f"**Space:** {space}  \n"
            f"**ID:** {result.get('id', '—')}  \n"
            f"**URL:** {full_url}  \n"
            f"**Date:** {date.today()}"
        )

    except Exception as e:
        return f"❌ Error while working with Confluence: {e}"


# ---------------------------------------------------------------------------
# MCP 2 — Import a Confluence page → 5.1 repository format
# ---------------------------------------------------------------------------

@mcp.tool()
def pull_from_confluence(
    page_title: str,
    space_key: str = "",
    project_name: str = "",
) -> str:
    """
    Imports a Confluence page with requirements → JSON for init_traceability_repo (5.1).

    Scenario: the BA already runs the project in Confluence → connects our platform.
    The tool extracts requirements heuristically (by ID patterns: FR-001, BR-003, etc.)
    and returns ready JSON to pass to init_traceability_repo.

    Args:
        page_title:    Title of the Confluence page with requirements.
        space_key:     Space key. If empty — from CONFLUENCE_SPACE_KEY.
        project_name:  Project name (if empty — taken from the page title).

    Returns:
        JSON with requirements + instructions for the next step (init_traceability_repo).
    """
    logger.info(f"pull_from_confluence: '{page_title}', space='{space_key}'")

    confluence, error = _get_confluence_client()
    if error:
        return error

    space = space_key or _default_space_key()
    if not space:
        return "❌ space_key not provided."

    try:
        page = confluence.get_page_by_title(
            space=space,
            title=page_title,
            expand="body.storage,version",
        )
        if not page:
            return (
                f"❌ Page '{page_title}' not found in space '{space}'.\n"
                f"Use `list_space_pages` to view available pages."
            )
    except Exception as e:
        return f"❌ Error while fetching the page: {e}"

    storage_content = page.get("body", {}).get("storage", {}).get("value", "")
    plain_text = _confluence_storage_to_text(storage_content)

    page_version = page.get("version", {}).get("number", 1)
    last_modified = page.get("version", {}).get("when", str(date.today()))[:10]
    full_url = _page_url(page)

    proj_name = project_name or page_title
    requirements = _extract_requirements_heuristic(plain_text, full_url)
    requirements_json = json.dumps(requirements, ensure_ascii=False, indent=2)

    lines = [
        f"<!-- Import from Confluence | {page_title} | {date.today()} -->",
        "",
        f"# 📥 Import from Confluence",
        "",
        f"**Page:** {page_title}  ",
        f"**Space:** {space}  ",
        f"**Project:** {proj_name}  ",
        f"**Version:** {page_version}, modified {last_modified}  ",
        f"**URL:** {full_url}",
        "",
        f"## Requirements extracted: {len(requirements)}",
        "",
    ]

    if requirements:
        lines += [
            "| ID | Type | Title |",
            "|----|------|-------|",
        ]
        for r in requirements:
            lines.append(f"| `{r['id']}` | {r['type']} | {r['title']} |")
        lines.append("")

    lines += [
        "## Next step — pass to init_traceability_repo (5.1)",
        "",
        f"Call it with `project_name=\"{proj_name}\"` and the list below:",
        "",
        "```json",
        requirements_json,
        "```",
        "",
        "> ⚠️ Automatic extraction is heuristic — it works by ID patterns (FR-001, BR-003, etc.).",
        "> If the page has no explicit IDs, requirements must be added manually.",
        "> Review the list before passing it to init_traceability_repo.",
        "",
        "## Page content excerpt",
        "",
        "```",
        plain_text[:2000] + ("…" if len(plain_text) > 2000 else ""),
        "```",
    ]

    content = "\n".join(lines)
    save_artifact(content, prefix="confluence_pull", project_id=proj_name)
    return content


# ---------------------------------------------------------------------------
# MCP 3 — Sync an existing page
# ---------------------------------------------------------------------------

@mcp.tool()
def sync_page(
    page_title: str,
    new_content_markdown: str,
    space_key: str = "",
    create_if_missing: bool = False,
) -> str:
    """
    Updates an existing Confluence page with new content.
    Used for regular synchronization of living artifacts.

    Args:
        page_title:            Title of the page to update.
        new_content_markdown:  New content in Markdown.
        space_key:             Space key. If empty — from CONFLUENCE_SPACE_KEY.
        create_if_missing:     True — create it if it doesn't exist.

    Returns:
        The result with the before/after version.
    """
    logger.info(f"sync_page: '{page_title}'")

    confluence, error = _get_confluence_client()
    if error:
        return error

    space = space_key or _default_space_key()
    if not space:
        return "❌ space_key not provided."

    try:
        existing = confluence.get_page_by_title(space=space, title=page_title, expand="version")
    except Exception as e:
        return f"❌ Error while searching for the page: {e}"

    if not existing:
        if create_if_missing:
            return push_to_confluence(
                content_markdown=new_content_markdown,
                page_title=page_title,
                space_key=space,
            )
        return (
            f"❌ Page '{page_title}' not found in '{space}'.\n"
            f"Use create_if_missing=True or push_to_confluence to create it."
        )

    old_version = existing.get("version", {}).get("number", 1)
    html_content = _markdown_to_confluence_storage(new_content_markdown)

    try:
        result = confluence.update_page(
            page_id=existing["id"],
            title=page_title,
            body=html_content,
        )
        new_version = result.get("version", {}).get("number", old_version + 1)
        full_url = _page_url(result)

        return (
            f"✅ Page synced: **{page_title}**\n\n"
            f"**Version:** {old_version} → {new_version}  \n"
            f"**URL:** {full_url}  \n"
            f"**Date:** {date.today()}"
        )
    except Exception as e:
        return f"❌ Error while updating: {e}"


# ---------------------------------------------------------------------------
# MCP 4 — List pages of a space
# ---------------------------------------------------------------------------

@mcp.tool()
def list_space_pages(
    space_key: str = "",
    search_title: str = "",
    limit: int = 25,
) -> str:
    """
    Returns a list of pages in a Confluence space.
    Use it before pull_from_confluence to choose the right page.

    Args:
        space_key:    Space key. If empty — from CONFLUENCE_SPACE_KEY.
        search_title: Filter by part of the title (optional).
        limit:        Maximum number of pages (default 25).
    """
    logger.info(f"list_space_pages: space='{space_key}', search='{search_title}'")

    confluence, error = _get_confluence_client()
    if error:
        return error

    space = space_key or _default_space_key()
    if not space:
        return "❌ space_key not provided."

    def _fetch_all():
        return confluence.get_all_pages_from_space(
            space=space, start=0, limit=limit, expand="version",
        ) or []

    def _filter_locally(all_pages):
        return [p for p in all_pages if search_title.lower() in p.get("title", "").lower()]

    scope_note = ""
    try:
        if search_title:
            # Search SERVER-SIDE. Filtering client-side would only ever see the first
            # `limit` pages of the space, so a page that exists beyond that window
            # reads as "not found" — the BA concludes it isn't there.
            try:
                cql_query = (
                    f'space = "{_cql_escape(space)}" and type = page '
                    f'and title ~ "{_cql_escape(search_title)}"'
                )
                response = confluence.cql(cql_query, limit=limit, expand="version")
                hits = response.get("results", []) if isinstance(response, dict) else (response or [])
                pages = [_normalize_search_hit(h) for h in hits]
                scope_note = "searched the whole space"
            except Exception as cql_error:
                # Some deployments restrict CQL — degrade instead of failing outright.
                logger.warning(f"list_space_pages: CQL search failed ({cql_error}); "
                               f"falling back to a client-side filter")
                pages = _filter_locally(_fetch_all())
                scope_note = f"CQL unavailable — filtered the first {limit} pages only"
        else:
            pages = _fetch_all()
    except Exception as e:
        return f"❌ Error while fetching pages: {e}"

    # NB: keep the quoting out of the f-string expression — a backslash inside an
    # f-string replacement field is a SyntaxError before Python 3.12 (PEP 701),
    # and this project supports Python 3.10+.
    filter_note = f' (filter: "{search_title}"; {scope_note})' if search_title else ""

    if not pages:
        if search_title:
            return (f"ℹ️ No pages matching '{search_title}' in space '{space}' "
                    f"({scope_note}).")
        return f"ℹ️ No pages found in space '{space}', or no access."

    lines = [
        f"# 📋 Pages of space '{space}'",
        "",
        f"Found: **{len(pages)}**{filter_note}",
        "",
        "| Title | ID | Modified |",
        "|-------|-----|----------|",
    ]
    for page in pages:
        modified = page.get("version", {}).get("when", "—")[:10]
        lines.append(f"| {page.get('title', '—')} | `{page.get('id', '—')}` | {modified} |")

    lines += ["", "---", "To import: `pull_from_confluence(page_title='<title>')`"]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# MCP 5 — Publish a stored artifact (by project + selector)
# ---------------------------------------------------------------------------

@mcp.tool()
def publish_artifact_to_confluence(
    project_id: str,
    artifact: str = "",
    space_key: str = "",
    parent_page_title: str = "",
    page_title: str = "",
) -> str:
    """
    Publishes an ALREADY SAVED artifact to Confluence — the document is read from
    disk, so it never has to be passed in as text.

    Use this instead of `push_to_confluence` whenever the content is already an
    artifact of some BABOK task. `push_to_confluence` remains for ad-hoc text.

    Args:
        project_id:         Project identifier (the artifact folder name).
        artifact:           Filename prefix (e.g. "7_6_recommendation") or a path to
                            the file. Several matches -> the newest is used.
                            Empty -> returns the list of available artifacts.
        space_key:          Space key. If empty — from CONFLUENCE_SPACE_KEY.
        parent_page_title:  Parent page title (optional).
        page_title:         Overrides the title derived from the filename.

    Returns:
        The publication result with the page URL, or the list of available artifacts.
    """
    logger.info(f"publish_artifact_to_confluence: project='{project_id}', artifact='{artifact}'")

    path, note = _resolve_artifact(project_id, artifact)
    if not path:
        return note

    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError as e:
        return f"❌ Could not read `{path}`: {e}"

    title = page_title or _derive_page_title(project_id, path)

    result = export_artifact_to_confluence(
        content_markdown=content,
        page_title=title,
        space_key=space_key,
        parent_page_title=parent_page_title,
    )

    if result.get("status") != "synced":
        # INT-D: the reason lives in `message` — surface it, never a bare failure.
        reason = result.get("message") or "unknown error"
        return f"❌ Publication failed: {reason}\n\n{note}"

    return (
        f"✅ Page {result.get('operation', 'published')}: **{title}**\n\n"
        f"{note}  \n"
        f"**Source:** `{path}`  \n"
        f"**URL:** {result.get('url', '—')}  \n"
        f"**Date:** {date.today()}"
    )


# ---------------------------------------------------------------------------
# Helper function for the _export_hook() hook in 5.2
# ---------------------------------------------------------------------------

def export_artifact_to_confluence(
    content_markdown: str,
    page_title: str,
    space_key: str = "",
    parent_page_title: str = "",
) -> dict:
    """
    Programmatic call (not an MCP tool) — for _export_hook() in requirements_maintain_mcp.py.

    Replace in _export_hook():
        from skills.integrations.confluence_mcp import export_artifact_to_confluence
        return export_artifact_to_confluence(content, page_title, space_key)

    Returns:
        {"status": "synced", "url": "..."} or {"status": "error", "message": "..."}
    """
    confluence, error = _get_confluence_client()
    if error:
        return {"status": "error", "message": error}

    space = space_key or _default_space_key()
    if not space:
        return {"status": "error", "message": "CONFLUENCE_SPACE_KEY is not set"}

    try:
        html_content = _markdown_to_confluence_storage(content_markdown)

        parent_id = None
        if parent_page_title:
            parent = confluence.get_page_by_title(space=space, title=parent_page_title)
            if parent:
                parent_id = parent.get("id")

        existing = confluence.get_page_by_title(space=space, title=page_title)
        if existing:
            result = confluence.update_page(
                page_id=existing["id"], title=page_title,
                body=html_content, parent_id=parent_id,
            )
            operation = "updated"
        else:
            result = confluence.create_page(
                space=space, title=page_title,
                body=html_content, parent_id=parent_id,
            )
            operation = "created"

        # `operation` tells the caller whether a living page was overwritten.
        # Additive and inert for existing consumers: _export_hook and its four call
        # sites in 5.2 all read named keys via .get().
        return {"status": "synced", "url": _page_url(result), "operation": operation}

    except Exception as e:
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    mcp.run()
