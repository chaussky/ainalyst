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
from datetime import date
from typing import Optional
from mcp.server.fastmcp import FastMCP
from skills.common import save_artifact, logger

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
        html = text
        html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
        html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
        html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
        html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
        html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)
        html = re.sub(r'`([^`]+)`', r'<code>\1</code>', html)
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
    text = re.sub(r'<[^>]+>', '', text)
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
            title = re.sub(r'^[\s|\-:]+', '', title).strip()
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
                url_path = existing.get("_links", {}).get("webui", "")
                base_url = os.environ.get("CONFLUENCE_URL", "").rstrip("/")
                return (
                    f"⚠️ Page '{page_title}' already exists.\n"
                    f"URL: {base_url}/wiki{url_path}\n"
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

        url_path = result.get("_links", {}).get("webui", "")
        base_url = os.environ.get("CONFLUENCE_URL", "").rstrip("/")
        full_url = f"{base_url}/wiki{url_path}" if url_path else base_url

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
    url_path = page.get("_links", {}).get("webui", "")
    base_url = os.environ.get("CONFLUENCE_URL", "").rstrip("/")
    full_url = f"{base_url}/wiki{url_path}" if url_path else ""

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
    save_artifact(content, prefix="confluence_pull")
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
        url_path = result.get("_links", {}).get("webui", "")
        base_url = os.environ.get("CONFLUENCE_URL", "").rstrip("/")
        full_url = f"{base_url}/wiki{url_path}" if url_path else base_url

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

    try:
        pages = confluence.get_all_pages_from_space(
            space=space, start=0, limit=limit, expand="version",
        )
    except Exception as e:
        return f"❌ Error while fetching pages: {e}"

    if not pages:
        return f"ℹ️ No pages found in space '{space}', or no access."

    if search_title:
        pages = [p for p in pages if search_title.lower() in p.get("title", "").lower()]

    lines = [
        f"# 📋 Pages of space '{space}'",
        "",
        f"Found: **{len(pages)}**{f' (filter: \"{search_title}\")' if search_title else ''}",
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
        else:
            result = confluence.create_page(
                space=space, title=page_title,
                body=html_content, parent_id=parent_id,
            )

        url_path = result.get("_links", {}).get("webui", "")
        base_url = os.environ.get("CONFLUENCE_URL", "").rstrip("/")
        return {"status": "synced", "url": f"{base_url}/wiki{url_path}" if url_path else base_url}

    except Exception as e:
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    mcp.run()
