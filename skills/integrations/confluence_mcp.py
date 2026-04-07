"""
integrations/confluence_mcp.py — Интеграция с Confluence
Статус: РЕАЛИЗОВАНО (Cloud + Server/DC)

Поддерживаемые варианты подключения:
  Cloud:     CONFLUENCE_URL + CONFLUENCE_USERNAME + CONFLUENCE_API_TOKEN + CONFLUENCE_CLOUD=true
  Server/DC: CONFLUENCE_URL + CONFLUENCE_API_TOKEN (PAT, Confluence 7.9+) + CONFLUENCE_CLOUD=false

Конфигурация через переменные окружения:
  CONFLUENCE_URL        — базовый URL (https://your-domain.atlassian.net или https://wiki.company.com)
  CONFLUENCE_USERNAME   — email (Cloud) или логин (Server). Для Server/DC PAT не нужен.
  CONFLUENCE_API_TOKEN  — API token (Cloud) или Personal Access Token (Server)
  CONFLUENCE_CLOUD      — "true" для Cloud, "false" для Server (по умолчанию "true")
  CONFLUENCE_SPACE_KEY  — ключ пространства по умолчанию (например "BA", "PROJ")

Инструменты MCP:
  - push_to_confluence   — экспорт Markdown-артефакта → страница Confluence
  - pull_from_confluence — импорт страницы Confluence → JSON для init_traceability_repo (5.1)
  - sync_page            — обновить существующую страницу (синхронизация)
  - list_space_pages     — список страниц пространства (для выбора перед импортом)

Дополнительно:
  - export_artifact_to_confluence() — вспомогательная функция для хука _export_hook() в 5.2

Зависимости (добавлены в requirements.txt):
  atlassian-python-api>=3.41.0
  markdown2>=2.4.0

# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst (AI Платформа AIналитик). Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
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
# Утилиты: подключение и конвертация форматов
# ---------------------------------------------------------------------------

def _get_confluence_client():
    """
    Создаёт клиент Confluence из переменных окружения.
    Возвращает: (confluence_client, error_message_or_None)
    """
    try:
        from atlassian import Confluence
    except ImportError:
        return None, (
            "❌ Библиотека `atlassian-python-api` не установлена.\n"
            "Установите: `pip install atlassian-python-api`"
        )

    url = os.environ.get("CONFLUENCE_URL", "").rstrip("/")
    username = os.environ.get("CONFLUENCE_USERNAME", "")
    api_token = os.environ.get("CONFLUENCE_API_TOKEN", "")
    is_cloud = os.environ.get("CONFLUENCE_CLOUD", "true").lower() == "true"

    if not url:
        return None, (
            "❌ Не задана переменная окружения `CONFLUENCE_URL`.\n"
            "Cloud:  export CONFLUENCE_URL=https://your-domain.atlassian.net\n"
            "Server: export CONFLUENCE_URL=https://wiki.company.com"
        )
    if not api_token:
        return None, (
            "❌ Не задан `CONFLUENCE_API_TOKEN`.\n"
            "Cloud:  получи на https://id.atlassian.com/manage-profile/security/api-tokens\n"
            "Server: Settings → Personal Access Tokens (Confluence 7.9+)"
        )

    try:
        if is_cloud:
            if not username:
                return None, "❌ Для Cloud нужен CONFLUENCE_USERNAME (email аккаунта Atlassian)."
            confluence = Confluence(
                url=url,
                username=username,
                password=api_token,
                cloud=True,
            )
        else:
            # Server/DC с Personal Access Token
            confluence = Confluence(
                url=url,
                token=api_token,
            )
        return confluence, None
    except Exception as e:
        return None, f"❌ Ошибка инициализации клиента Confluence: {e}"


def _markdown_to_confluence_storage(markdown_text: str) -> str:
    """
    Конвертирует Markdown → Confluence Storage Format (XHTML-подобный).
    Использует markdown2 если доступен, иначе базовую регекс-конвертацию.
    """
    # Убираем HTML-комментарии (наши метаданные <!-- BABOK ... -->)
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
    Конвертирует Confluence Storage Format → читаемый текст.
    Сохраняет структуру для последующего парсинга требований.
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
    Эвристически извлекает требования из текста страницы.
    Ищет паттерны ID: BR-001, FR-007, NFR-003, US-012 и т.д.
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
            title = title[:120] if title else f"Требование {req_id}"

            requirements.append({
                "id": req_id,
                "type": type_map.get(prefix, "solution"),
                "title": title or f"Требование {req_id}",
                "version": "1.0",
                "status": "draft",
                "source_artifact": source_url,
            })

    return requirements


def _default_space_key() -> str:
    return os.environ.get("CONFLUENCE_SPACE_KEY", "")


# ---------------------------------------------------------------------------
# MCP 1 — Экспорт артефакта в Confluence
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
    Экспортирует Markdown-артефакт в Confluence как страницу.
    Если страница существует и update_if_exists=True — обновляет. Иначе создаёт новую.

    Args:
        content_markdown:   Markdown-содержимое (артефакт из любой задачи BABOK).
        page_title:         Заголовок страницы в Confluence.
        space_key:          Ключ пространства (BA, PROJ...). Если пусто — из CONFLUENCE_SPACE_KEY.
        parent_page_title:  Заголовок родительской страницы (опционально).
        update_if_exists:   True — обновить если существует. False — ошибка если существует.

    Returns:
        Результат с URL страницы.
    """
    logger.info(f"push_to_confluence: '{page_title}' → space='{space_key}'")

    confluence, error = _get_confluence_client()
    if error:
        return error

    space = space_key or _default_space_key()
    if not space:
        return "❌ Не указан space_key. Задай параметр или переменную CONFLUENCE_SPACE_KEY."

    html_content = _markdown_to_confluence_storage(content_markdown)

    parent_id = None
    if parent_page_title:
        try:
            parent_page = confluence.get_page_by_title(space=space, title=parent_page_title)
            if parent_page:
                parent_id = parent_page.get("id")
            else:
                return f"❌ Родительская страница '{parent_page_title}' не найдена в '{space}'."
        except Exception as e:
            return f"❌ Ошибка при поиске родительской страницы: {e}"

    try:
        existing = confluence.get_page_by_title(space=space, title=page_title)

        if existing:
            if not update_if_exists:
                url_path = existing.get("_links", {}).get("webui", "")
                base_url = os.environ.get("CONFLUENCE_URL", "").rstrip("/")
                return (
                    f"⚠️ Страница '{page_title}' уже существует.\n"
                    f"URL: {base_url}/wiki{url_path}\n"
                    f"Используй update_if_exists=True для обновления."
                )
            result = confluence.update_page(
                page_id=existing["id"],
                title=page_title,
                body=html_content,
                parent_id=parent_id,
            )
            operation = "обновлена"
        else:
            result = confluence.create_page(
                space=space,
                title=page_title,
                body=html_content,
                parent_id=parent_id,
            )
            operation = "создана"

        if not result:
            return f"❌ Confluence вернул пустой ответ. Проверьте права в пространстве '{space}'."

        url_path = result.get("_links", {}).get("webui", "")
        base_url = os.environ.get("CONFLUENCE_URL", "").rstrip("/")
        full_url = f"{base_url}/wiki{url_path}" if url_path else base_url

        return (
            f"✅ Страница {operation}: **{page_title}**\n\n"
            f"**Пространство:** {space}  \n"
            f"**ID:** {result.get('id', '—')}  \n"
            f"**URL:** {full_url}  \n"
            f"**Дата:** {date.today()}"
        )

    except Exception as e:
        return f"❌ Ошибка при работе с Confluence: {e}"


# ---------------------------------------------------------------------------
# MCP 2 — Импорт страницы Confluence → формат репозитория 5.1
# ---------------------------------------------------------------------------

@mcp.tool()
def pull_from_confluence(
    page_title: str,
    space_key: str = "",
    project_name: str = "",
) -> str:
    """
    Импортирует страницу Confluence с требованиями → JSON для init_traceability_repo (5.1).

    Сценарий: BA уже ведёт проект в Confluence → подключает нашу платформу.
    Инструмент извлекает требования эвристически (по ID-паттернам: FR-001, BR-003 и т.д.)
    и возвращает готовый JSON для передачи в init_traceability_repo.

    Args:
        page_title:    Заголовок страницы в Confluence с требованиями.
        space_key:     Ключ пространства. Если пусто — из CONFLUENCE_SPACE_KEY.
        project_name:  Название проекта (если пусто — берётся из заголовка страницы).

    Returns:
        JSON с требованиями + инструкции по следующему шагу (init_traceability_repo).
    """
    logger.info(f"pull_from_confluence: '{page_title}', space='{space_key}'")

    confluence, error = _get_confluence_client()
    if error:
        return error

    space = space_key or _default_space_key()
    if not space:
        return "❌ Не указан space_key."

    try:
        page = confluence.get_page_by_title(
            space=space,
            title=page_title,
            expand="body.storage,version",
        )
        if not page:
            return (
                f"❌ Страница '{page_title}' не найдена в пространстве '{space}'.\n"
                f"Используй `list_space_pages` для просмотра доступных страниц."
            )
    except Exception as e:
        return f"❌ Ошибка при получении страницы: {e}"

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
        f"<!-- Импорт из Confluence | {page_title} | {date.today()} -->",
        "",
        f"# 📥 Импорт из Confluence",
        "",
        f"**Страница:** {page_title}  ",
        f"**Пространство:** {space}  ",
        f"**Версия:** {page_version}, изменено {last_modified}  ",
        f"**URL:** {full_url}",
        "",
        f"## Извлечено требований: {len(requirements)}",
        "",
    ]

    if requirements:
        lines += [
            "| ID | Тип | Название |",
            "|----|-----|----------|",
        ]
        for r in requirements:
            lines.append(f"| `{r['id']}` | {r['type']} | {r['title']} |")
        lines.append("")

    lines += [
        "## Следующий шаг — передать в init_traceability_repo (5.1)",
        "",
        "```json",
        requirements_json,
        "```",
        "",
        "> ⚠️ Автоматическое извлечение эвристическое — работает по ID-паттернам (FR-001, BR-003 и т.д.).",
        "> Если на странице нет явных ID — требования нужно добавить вручную.",
        "> Проверь список перед передачей в init_traceability_repo.",
        "",
        "## Фрагмент содержимого страницы",
        "",
        "```",
        plain_text[:2000] + ("…" if len(plain_text) > 2000 else ""),
        "```",
    ]

    content = "\n".join(lines)
    save_artifact(content, prefix="confluence_pull")
    return content


# ---------------------------------------------------------------------------
# MCP 3 — Синхронизация существующей страницы
# ---------------------------------------------------------------------------

@mcp.tool()
def sync_page(
    page_title: str,
    new_content_markdown: str,
    space_key: str = "",
    create_if_missing: bool = False,
) -> str:
    """
    Обновляет существующую страницу Confluence новым содержимым.
    Используется для регулярной синхронизации живых артефактов.

    Args:
        page_title:            Заголовок страницы для обновления.
        new_content_markdown:  Новое содержимое в Markdown.
        space_key:             Ключ пространства. Если пусто — из CONFLUENCE_SPACE_KEY.
        create_if_missing:     True — создать если не существует.

    Returns:
        Результат с версией до/после.
    """
    logger.info(f"sync_page: '{page_title}'")

    confluence, error = _get_confluence_client()
    if error:
        return error

    space = space_key or _default_space_key()
    if not space:
        return "❌ Не указан space_key."

    try:
        existing = confluence.get_page_by_title(space=space, title=page_title, expand="version")
    except Exception as e:
        return f"❌ Ошибка при поиске страницы: {e}"

    if not existing:
        if create_if_missing:
            return push_to_confluence(
                content_markdown=new_content_markdown,
                page_title=page_title,
                space_key=space,
            )
        return (
            f"❌ Страница '{page_title}' не найдена в '{space}'.\n"
            f"Используй create_if_missing=True или push_to_confluence для создания."
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
            f"✅ Страница синхронизирована: **{page_title}**\n\n"
            f"**Версия:** {old_version} → {new_version}  \n"
            f"**URL:** {full_url}  \n"
            f"**Дата:** {date.today()}"
        )
    except Exception as e:
        return f"❌ Ошибка при обновлении: {e}"


# ---------------------------------------------------------------------------
# MCP 4 — Список страниц пространства
# ---------------------------------------------------------------------------

@mcp.tool()
def list_space_pages(
    space_key: str = "",
    search_title: str = "",
    limit: int = 25,
) -> str:
    """
    Возвращает список страниц пространства Confluence.
    Используй перед pull_from_confluence для выбора нужной страницы.

    Args:
        space_key:    Ключ пространства. Если пусто — из CONFLUENCE_SPACE_KEY.
        search_title: Фильтр по части заголовка (опционально).
        limit:        Максимум страниц (по умолчанию 25).
    """
    logger.info(f"list_space_pages: space='{space_key}', search='{search_title}'")

    confluence, error = _get_confluence_client()
    if error:
        return error

    space = space_key or _default_space_key()
    if not space:
        return "❌ Не указан space_key."

    try:
        pages = confluence.get_all_pages_from_space(
            space=space, start=0, limit=limit, expand="version",
        )
    except Exception as e:
        return f"❌ Ошибка при получении страниц: {e}"

    if not pages:
        return f"ℹ️ Страниц в пространстве '{space}' не найдено или нет доступа."

    if search_title:
        pages = [p for p in pages if search_title.lower() in p.get("title", "").lower()]

    lines = [
        f"# 📋 Страницы пространства '{space}'",
        "",
        f"Найдено: **{len(pages)}**{f' (фильтр: «{search_title}»)' if search_title else ''}",
        "",
        "| Заголовок | ID | Изменено |",
        "|-----------|-----|----------|",
    ]
    for page in pages:
        modified = page.get("version", {}).get("when", "—")[:10]
        lines.append(f"| {page.get('title', '—')} | `{page.get('id', '—')}` | {modified} |")

    lines += ["", "---", "Для импорта: `pull_from_confluence(page_title='<заголовок>')`"]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Вспомогательная функция для хука _export_hook() в 5.2
# ---------------------------------------------------------------------------

def export_artifact_to_confluence(
    content_markdown: str,
    page_title: str,
    space_key: str = "",
    parent_page_title: str = "",
) -> dict:
    """
    Программный вызов (не MCP-инструмент) — для _export_hook() в requirements_maintain_mcp.py.

    Замени в _export_hook():
        from skills.integrations.confluence_mcp import export_artifact_to_confluence
        return export_artifact_to_confluence(content, page_title, space_key)

    Returns:
        {"status": "synced", "url": "..."} или {"status": "error", "message": "..."}
    """
    confluence, error = _get_confluence_client()
    if error:
        return {"status": "error", "message": error}

    space = space_key or _default_space_key()
    if not space:
        return {"status": "error", "message": "Не задан CONFLUENCE_SPACE_KEY"}

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
