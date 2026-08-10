## AI Платформа AIналитик
**Скачать:** https://github.com/chaussky/ainalyst.git

**LinkedIn:** https://www.linkedin.com/in/anatole-tchaoussky-82957a40b/

---

# Руководство разработчика

_Версия: v1 / Дата: апрель 2026_

Этот документ описывает архитектуру платформы AIналитик «под капотом»: как устроены компоненты, как они взаимодействуют, как добавить новый сервер или скилл. Для понимания того, **как пользоваться** платформой — смотрите пользовательскую инструкцию (`1-introduction.md` и `ch*` файлы).

---

## Содержание

1. [Архитектура платформы](#1-архитектура-платформы)
2. [Система фаз и `phase.py`](#2-система-фаз-и-phasepy)
3. [`common.py` — единый источник истины](#3-commonpy--единый-источник-истины)
4. [Архитектура MCP-серверов](#4-архитектура-mcp-серверов)
5. [Структура скиллов (SKILL.md)](#5-структура-скиллов-skillmd)
6. [Хранилище артефактов](#6-хранилище-артефактов)
7. [Интеграция с Confluence](#7-интеграция-с-confluence)
8. [Тестирование](#8-тестирование)
9. [Среда разработки](#9-среда-разработки)
10. [Добавление нового MCP-сервера](#10-добавление-нового-mcp-сервера)
11. [Технический долг и решения по дизайну](#11-технический-долг-и-решения-по-дизайну)

---

## 1. Архитектура платформы

### Три слоя

Платформа состоит из трёх слоёв, которые работают вместе при каждом запросе BA:

```
┌─────────────────────────────────────────────────────┐
│  Claude Code                                        │
│  Агент. Читает CLAUDE.md и SKILL.md, управляет      │
│  фазами, вызывает MCP-инструменты, ведёт BA         │
│  по процессу.                                       │
└──────────────────────┬──────────────────────────────┘
                       │ вызывает
┌──────────────────────▼──────────────────────────────┐
│  Skills (SKILL.md + references/)                    │
│  21 специализированный модуль знаний. Каждый        │
│  «знает» одну задачу BABOK: методологию, алгоритм,  │
│  шаблоны, ссылки на MCP-инструменты.                │
└──────────────────────┬──────────────────────────────┘
                       │ инструктирует вызывать
┌──────────────────────▼──────────────────────────────┐
│  MCP servers (22 x *_mcp.py)                         │
│  114 tools. Perform the analytical                   │
│  operations: build requirement graphs, analyze       │
│  transcripts, save artifacts.                        │
└──────────────────────┬──────────────────────────────┘
                       │ пишет
┌──────────────────────▼──────────────────────────────┐
│  governance_plans/data/    — JSON (машиночитаемые)  │
│  governance_plans/reports/ — Markdown (для людей)   │
└─────────────────────────────────────────────────────┘
```

### Поток одного запроса

Когда BA пишет что-то вроде «подготовь план выявления для интервью с финдиром», происходит следующее:

1. **Claude Code** читает `CLAUDE.md` — системный промпт, описывающий роль и принципы работы
2. По триггерам в `CLAUDE.md` определяет задачу: это **4.1 Подготовка к выявлению**
3. Читает `skills/elicitation_prep/SKILL.md` — методологию и алгоритм
4. Задаёт уточняющие вопросы (тип встречи, стейкхолдер, цель)
5. Вызывает MCP-инструмент `save_elicitation_plan` из `elicitation_mcp.py`
6. Инструмент через `common.py` сохраняет артефакт в `governance_plans/reports/`
7. Claude Code сообщает BA о результате и предлагает следующий шаг

### Ключевые файлы

| Файл / папка | Роль |
|---|---|
| `CLAUDE.md` | Системный промпт для Claude Code: роль, фазы, триггеры по задачам, принципы |
| `phase.py` | Генератор `.mcp.json`. Управляет активной фазой. |
| `skills/common.py` | Единый источник истины: константы, матрицы, `save_artifact`, пути к папкам |
| `skills/*_mcp.py` | 22 MCP-сервера, по одному на задачу BABOK |
| `skills/integrations/confluence_mcp.py` | BASE_SERVER — Confluence, включён во все фазы |
| `skills/*/SKILL.md` | Контекстные инструкции для Claude Code (методология + алгоритм) |
| `skills/*/references/*.md` | Детальные справочники — читаются только по алгоритму SKILL.md |
| `governance_plans/data/` | JSON-артефакты: граф требований, результаты приоритизации и т.д. |
| `governance_plans/reports/` | Markdown-артефакты: планы, протоколы, рекомендации |
| `inputs/` | Входные материалы BA: транскрипты, документы, регламенты |
| `.claude/` | Хуки, правила и настройки Claude Code |
| `.mcp.json` | Генерируется `phase.py`. В `.gitignore` — пути специфичны для машины |

---

## 2. Система фаз и `phase.py`

### Проблема и решение

У LLM есть ограниченное контекстное окно. Загрузка всех 22 MCP-серверов одновременно занимает значительную его часть и деградирует качество работы. Платформа решает это через **активную фазу**: в каждый момент загружены только серверы нужной главы BABOK.

`phase.py` управляет этим: читает нужный набор серверов → генерирует `.mcp.json` с абсолютными путями → записывает имя активной фазы в `.ainalyst_phase`.

### Фазы

| Имя фазы | Команда | Главы BABOK | MCP-серверы (кроме BASE) |
|---|---|---|---|
| `planning` | `python phase.py planning` | 3 | — только BASE |
| `elicitation` | `python phase.py elicitation` | 4.1–4.5 | 5 серверов |
| `lifecycle` | `python phase.py lifecycle` | 5.1–5.5 | 5 серверов |
| `analysis` | `python phase.py analysis` | 6.1–6.4 | 4 сервера |
| `design` | `python phase.py design` | 7.1–7.6 | 6 серверов |
| `full` | `python phase.py full` | Все главы | 20 серверов |

Без аргументов `python phase.py` показывает текущую активную фазу и подсказки по каждой.

### BASE_SERVER — базовый сервер

Два сервера присутствуют во **всех** фазах:

```python
BASE_SERVER = {
    "babok-ch3": _server("skills/planning_mcp.py"),
    "babok-confluence": _server("skills/integrations/confluence_mcp.py"),
}
```

- `planning_mcp.py` — лёгкий (7 инструментов), нужен всегда: `project_id`, реестр стейкхолдеров
- `confluence_mcp.py` — 5 инструментов, стартует без `.env`. Ошибка возникает только при вызове инструмента, если ключи не заполнены

### Как `phase.py` генерирует пути

```python
PROJECT_ROOT = Path(__file__).resolve().parent

def _server(script: str) -> dict:
    return {"command": "python", "args": [str(PROJECT_ROOT / script)]}
```

`Path(__file__).resolve().parent` — абсолютный путь к папке где лежит `phase.py`. Это делает `.mcp.json` переносимым на уровне скрипта: путь вычисляется в момент запуска `phase.py` на конкретной машине. Поэтому `.mcp.json` в `.gitignore` — файл специфичен для каждой машины разработчика.

### Жизненный цикл смены фазы

```bash
python phase.py design     # 1. Записывает .ainalyst_phase, генерирует .mcp.json
# Claude Code: /restart    # 2. Перезагружает MCP-серверы из нового .mcp.json
```

После `/restart` Claude Code загружает новый набор серверов — и работает с инструментами нужной главы.

### Чтение текущей фазы

`phase.py` без аргументов читает `.ainalyst_phase` и выводит что сейчас активно. Файл `.ainalyst_phase` тоже в `.gitignore` — он специфичен для текущей сессии разработчика.

---

## 3. `common.py` — единый источник истины

Файл `skills/common.py` — центральный служебный модуль. Все MCP-серверы импортируют из него константы и функции. Это гарантирует что бизнес-логика не дублируется.

### Пути к артефактам

```python
BASE_DIR    = "governance_plans"
DATA_DIR    = os.path.join(BASE_DIR, "data")     # JSON: машиночитаемые данные
REPORTS_DIR = os.path.join(BASE_DIR, "reports")  # Markdown: документы для людей
```

Пути относительные — MCP-серверы всегда запускаются из корня проекта через Claude Code.

### Раскладка по подкаталогам проекта (issue #1)

Артефакты раскладываются по подпапке проекта, чтобы несколько проектов/команд не
превращали `governance_plans/` в свалку:

```
governance_plans/
├── data/<project_id>/<project_id>_traceability_repo.json   # JSON
│   └── specs/                                               # спеки 7.1
└── reports/<project_id>/6_1_current_state_<project_id>_<ts>.md  # Markdown
```

Центральные хелперы в `common.py` (единственный источник пути):

```python
def normalize_project_id(project_id: str) -> str:
    """Безопасное имя проекта для каталога: lower/trim, разделители и '..' → '_',
    whitelist [a-z0-9_-]. Защита от path traversal."""

def data_dir_for(project_id) -> str:    # governance_plans/data/<safe_pid>/
def report_dir_for(project_id) -> str:  # governance_plans/reports/<safe_pid>/

def data_path(project_id, filename) -> str:
    """Single resolver for the JSON path (read and write): data/<project_id>/<filename>.
    ONE candidate — the artifact is written and looked for in the same place."""
```

Правила для разработчика:
- **JSON**: собирай путь через `data_path(project_id, f"{safe}_{FILENAME}")` и пиши его **`write_json_artifact(path, data)`** — никогда через `open(...,"w")` + `json.dump` (см. «Запись JSON-артефакта» ниже; писатель сам создаёт каталог). Имя файла сохраняет префикс `{safe}_`, поэтому файл представляется сам, даже если его читают вне контекста.
- **Markdown**: вызывай `save_artifact(content, prefix, project_id=...)`. С `project_id` отчёт пишется в `reports/<project_id>/`. Без `project_id` он ложится прямо в `reports/` — этот путь не принадлежит ни одному проекту, и обратно его никто не читает; передавай id.
- **Одна раскладка, никаких запасных вариантов** (решение владельца, 2026-08-03). `data_path` и `specs_dir` перебирали пять и четыре расположения соответственно, чтобы артефакты, созданные до перехода на папку-на-проект, продолжали находиться. Проектов старше платформы не бывает, поэтому эти кандидаты могли найти только файл, который положил ТЕСТ, — а платой был многовариантный поиск у каждого читателя, ответ которого зависел от того, что случайно лежит на диске. Вместе с ними ушёл и `migrate_artifacts.py`.

**The `project_id` contract: an id must be a FIXED POINT of `normalize_project_id`** — spelled exactly the way its folder will be. `^[a-z0-9][a-z0-9_-]*$`, plus `normalize_project_id(pid) == pid`, plus not reserved. That makes id → folder bijective, so a collision cannot be constructed: there is no second spelling that lands on the same folder. Refused, all for the same reason: `CRM Up`, `demo.v2`, `crm__up`, `_crm`, `црм_апгрейд`.

**Id, который нельзя представить, ОТКЛОНЯЕТСЯ, а не переписывается** (решение владельца, 2026-08-03). `normalize_project_id` — функция «многие в одного»: она вырезает всё за пределами `[a-z0-9_-]`, поэтому нелатинский id терял все символы до единого и попадал в одну общую папку-заглушку, где два разных проекта молча перемешивали артефакты друг друга. Страж, который это останавливает:

```python
def project_id_error(project_id) -> Optional[str]:   # BA-facing refusal, or None
def require_valid_project_id(project_id) -> None:    # raises InvalidProjectIdError
def project_id_suggestion(project_id) -> str:        # latin hint, for the TEXT only
```

- `require_valid_project_id` вызывается из `data_dir_for`, `report_dir_for`, `data_path` и `specs_dir` — любое чтение и любая запись проходят через одну из них.
- Проверка **не смотрит на состояние**: она никогда не спрашивает, существуют ли уже файлы. Вариант «проверять по существованию» пробовали и откатили: «папка уже есть» истинно ровно в опасном случае — когда id схлопывается на папку другого проекта.
- Транслитерация используется **только** для подсказки внутри текста отказа. До пути она не доходит, поэтому таблица не входит в контракт с диском и может меняться без потери проектов.
- Сама заглушка (`_unknown` / `unknown`) — **зарезервированный** id. Передавай в `data_path` СЫРОЙ `project_id`, а не заранее нормализованное значение, иначе страж обходится.

**Каждый инструмент, принимающий `project_id`/`project_name`, ОБЯЗАН нести `@guard_artifact_errors`** (под `@mcp.tool()`). Этот декоратор превращает `CorruptArtifactError` (включая его подкласс `ArtifactShapeError`) и `InvalidProjectIdError` в строку `❌`, которую инструмент обязан вернуть; без него отказ уходит наружу протокольной ошибкой. Это проверяется тестом `tests/test_project_id_validation.py::TestEveryToolTakingAProjectIdIsGuarded`, который сканирует каждый модуль: новый инструмент, забывший декоратор, роняет прогон.

### Запись JSON-артефакта: `write_json_artifact()`

**Каждая запись JSON-файла проекта идёт через одну функцию.** Запись через `open(path, "w")` + `json.dump` — это дефект, и `tests/test_json_writer.py::TestNoDirectWritesRemain` роняет прогон, если такая появится снова.

```python
from skills.common import write_json_artifact

write_json_artifact(data_path(project_id, f"{safe}_{FILENAME}"), repo)
```

Дело не в аккуратности. `open(path, "w")` **обрезает прежнюю версию раньше, чем существует хоть один байт замены**, поэтому каждое такое место было окном, в котором никем не управляемое прерывание — Ctrl+C, кончившееся место на диске, севшая батарея, антивирус, удерживающий дескриптор, — могло свести весь проект к наполовину записанному файлу. Таких мест было 32, и резервных копий не было нигде.

Три гарантии, и это намеренно не одна и та же гарантия трижды:

| Гарантия | От чего защищает | Механизм |
|---|---|---|
| **Атомарность** | запись оборвалась | замена собирается под временным именем в том же каталоге и встаёт на место через `os.replace` — имя указывает либо на один целый файл, либо на другой, но никогда на разорванный |
| **Поколения** | содержимое, записанное безупречно и **неверно**; правки руками | заменяемая версия копируется в `governance_plans/.history/`, хранятся последние `HISTORY_GENERATIONS` (5) |
| **Форма** | инструмент сохранил то, чего не прочитает ни одна другая глава | граф требований принимает `requirements` + `links` только списками; отказ происходит **до** того, как файл тронут |

Четыре следствия, которые сопровождающему надо знать:

1. **Копии снимаются ДО записи**, поэтому самое свежее поколение — это состояние на одно изменение назад, а не то, которое записывается. Поколения существуют ради случая, когда содержимое записано безупречно и неверно (`init_traceability_repo` однажды уничтожил тип узла атомарно, валидно и с `✅`), и там нужна ровно та версия, которую этот инструмент заменил. Копирование после записи сделало бы самое свежее поколение второй копией повреждения.
2. **Цена этого названа в тексте ошибки.** Файл, уничтоженный снаружи, восстанавливается на одно изменение назад, и `read_json_artifact` говорит это прямо, а не оставляет аналитику узнать самому уже после того, как он последовал совету.
3. **`ArtifactShapeError` наследует `CorruptArtifactError`**, поэтому существующая граница инструмента преобразует и его. Отдельный `except` для него добавлять не надо.
4. **`.history/` плоская**, и это безопасно только потому, что имена артефактов всегда несут префикс проекта; чистка считает по имени артефакта и только `*.json`, поэтому мусор `.part` от убитого процесса не вытеснит настоящее поколение.

Сериализация происходит **до** того, как файловая система тронута: содержимое, которое не кодируется, — дефект вызывающего кода, и оно не должно стоить аналитику сохранённой версии.

**Чего писатель НЕ даёт — одновременного запуска.** Каждый инструмент читает файл целиком, меняет его в памяти и целиком записывает обратно. Две команды подряд — норма, это обычный порядок работы. Две команды **одновременно** (скрипт, CI, два открытых терминала по одному проекту) кончаются правилом «кто последний, тот и прав»: второй запуск стартовал от состояния до сохранения первого, поэтому затирает его правку — и о потере никто не сообщит. Платформа рассчитана на одного аналитика в одной сессии; параллельный запуск инструментов по одному проекту не поддерживается.

Следствия для «экзотических» имён: id вне правила (`r&d_portal`, `CRM (v2)`, `demo.v2`, имя любой нелатинской письменностью) отклоняется, поэтому артефакты, сохранённые под таким именем, недостижимы, пока папку не переименуют. Ничего не удаляется — переименование делается руками, а текст отказа называет годный id, в который переименовывать.

### `_ensure_dirs()` и `save_artifact()`

```python
def save_artifact(content: str, prefix: str, project_id: Optional[str] = None) -> str:
    """Сохраняет Markdown-артефакт в reports/ (или reports/<project_id>/) и возвращает путь."""
    _ensure_dirs()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{prefix}_{timestamp}.md"
    out_dir = report_dir_for(project_id) if project_id else REPORTS_DIR
    if project_id:
        os.makedirs(out_dir, exist_ok=True)
    filepath = os.path.join(out_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    return f"\n\n✅ Артефакт сохранен: `{filepath}`"
```

Несколько важных следствий:
- `governance_plans/data/` и `governance_plans/reports/` **создаются автоматически**. Ручной `mkdir` не нужен — папки уже есть в репозитории с `.gitkeep`, а при их случайном отсутствии `_ensure_dirs()` создаст их сама.
- `save_artifact` пишет **только в `reports/`** (Markdown). JSON-файлы каждый сервер пишет напрямую в `DATA_DIR` через собственную логику, но **путь строит через `data_path`**.
- Временна́я метка в имени файла обеспечивает уникальность: `{prefix}_20260402_143022.md`

### Матрицы — единственный источник истины

Три словаря описывают ключевую бизнес-логику платформы и импортируются всеми серверами, которым они нужны:

**`APPROACH_MATRIX`** — выбор методологии (Predictive / Hybrid / Agile) по уровню изменений и неопределённости:

```python
APPROACH_MATRIX: dict[tuple[str, str], tuple[str, list[str]]] = {
    ("Low",    "Low"):    ("Predictive (Waterfall)", [...]),
    ("Low",    "Medium"): ("Predictive (Waterfall)", [...]),
    ("Low",    "High"):   ("Hybrid",                 [...]),
    ("Medium", "Low"):    ("Hybrid",                 [...]),
    ("Medium", "Medium"): ("Hybrid",                 [...]),
    ("Medium", "High"):   ("Adaptive (Agile)",        [...]),
    ("High",   "Low"):    ("Adaptive (Agile)",        [...]),
    ("High",   "Medium"): ("Adaptive (Agile)",        [...]),
    ("High",   "High"):   ("Adaptive (Agile)",        [...]),
}
```

**`REGULATORY_OVERRIDE`** — корректировка методологии при регуляторных требованиях:

```python
REGULATORY_OVERRIDE: dict[str, str] = {
    "Adaptive (Agile)": "Hybrid (Agile + compliance gates)",
    "Hybrid":           "Hybrid (с усиленным Governance)",
}
```

**`QUADRANT_STRATEGIES`** — стратегии вовлечения стейкхолдеров по матрице «влияние × интерес»:

```python
QUADRANT_STRATEGIES: dict[tuple[str, str], tuple[str, str, str]] = {
    ("High", "High"):     ("Key Players",     "Manage Closely — ...", "Еженедельно"),
    ("High", "Medium"):   ("Context Setters", "Keep Satisfied — ...", "При вехах"),
    # ...
}
```

> **Правило:** при необходимости изменить логику выбора методологии или стратегии вовлечения — менять только здесь, в `common.py`. Не в каждом `*_mcp.py` отдельно.

### Модель `Stakeholder`

```python
class Stakeholder(BaseModel):
    name: str
    influence: str = Field(..., pattern="^(Low|Medium|High)$")
    interest:  str = Field(..., pattern="^(Low|Medium|High)$")
    attitude:  Optional[str] = Field("Neutral")
```

Используется в `planning_mcp.py` для типизации входных данных реестра стейкхолдеров.

---

## 4. Архитектура MCP-серверов

### Паттерн сервера

Каждый `*_mcp.py` — самодостаточный MCP-сервер. Минимальная структура:

```python
# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst. Licensed under AGPL v3.
from fastmcp import FastMCP
from skills.common import save_artifact, DATA_DIR, REPORTS_DIR

mcp = FastMCP("babok-ch4-41")   # имя сервера — как в phase.py

@mcp.tool()
def save_elicitation_plan(
    project_id: str,
    stakeholder: str,
    # ...
) -> str:
    """Сохранить план выявления."""
    # бизнес-логика
    content = _build_markdown(...)
    return save_artifact(content, f"elicitation_plan_{project_id}_{stakeholder}")

if __name__ == "__main__":
    mcp.run()
```

Ключевые принципы:
- **Один файл — один сервер** с собственным экземпляром `FastMCP`
- **Запуск через `mcp.run()`** в `if __name__ == "__main__"` — стандартный паттерн для Claude Code
- **Все матрицы и константы — из `common.py`**, не дублировать в каждом файле
- **Copyright-строка** в первой строке каждого файла — не трогать при правках

### Почему `planning_mcp.py` — монолит

Глава 3 не разбита на отдельные серверы по задачам 3.1–3.5, в отличие от Глав 4–7. Причина: `planning_mcp.py` входит в `BASE_SERVER` и загружается во **всех** фазах. Разбивка на 5 отдельных серверов не дала бы экономии контекста — все они всё равно загружались бы в каждой фазе. При этом 7 инструментов — лёгкий монолит, и архитектурно это оправдано.

### Все 22 MCP-сервера

| Сервер (ключ в `.mcp.json`) | Файл | Гл. BABOK | Инструментов |
|---|---|---|---|
| `babok-ch3` | `planning_mcp.py` | 3 | 7 |
| `babok-confluence` | `integrations/confluence_mcp.py` | - | 5 |
| `babok-ch4-41` | `elicitation_mcp.py` | 4.1 | 3 |
| `babok-ch4-42` | `elicitation_conduct_mcp.py` | 4.2 | 4 |
| `babok-ch4-43` | `elicitation_confirm_mcp.py` | 4.3 | 2 |
| `babok-ch4-44` | `elicitation_communicate_mcp.py` | 4.4 | 3 |
| `babok-ch4-45` | `elicitation_collaborate_mcp.py` | 4.5 | 3 |
| `babok-ch5-51` | `requirements_traceability_mcp.py` | 5.1 | 5 |
| `babok-ch5-52` | `requirements_maintain_mcp.py` | 5.2 | 4 |
| `babok-ch5-53` | `requirements_prioritize_mcp.py` | 5.3 | 5 |
| `babok-ch5-54` | `requirements_assess_changes_mcp.py` | 5.4 | 4 |
| `babok-ch5-55` | `requirements_approve_mcp.py` | 5.5 | 5 |
| `babok-ch6-61` | `current_state_mcp.py` | 6.1 | 6 |
| `babok-ch6-62` | `future_state_mcp.py` | 6.2 | 8 |
| `babok-ch6-63` | `risk_assessment_mcp.py` | 6.3 | 7 |
| `babok-ch6-64` | `change_strategy_mcp.py` | 6.4 | 7 |
| `babok-ch7-71` | `requirements_spec_mcp.py` | 7.1 | 9 |
| `babok-ch7-72` | `requirements_verify_mcp.py` | 7.2 | 6 |
| `babok-ch7-73` | `requirements_validate_mcp.py` | 7.3 | 7 |
| `babok-ch7-74` | `requirements_architecture_mcp.py` | 7.4 | 5 |
| `babok-ch7-75` | `design_options_mcp.py` | 7.5 | 5 |
| `babok-ch7-76` | `value_recommend_mcp.py` | 7.6 | 4 |

**Итого: 22 сервера, 114 инструментов.**

### Технические ограничения FastMCP

**1. `Field(..., pattern=...)` не поддерживается.**

FastMCP не проходит валидацию pydantic-полей с `pattern`. Используй `Literal`:

```python
# ❌ Не работает в FastMCP
status: str = Field(..., pattern="^(Draft|Active|Approved)$")

# ✅ Работает
from typing import Literal
status: Literal["Draft", "Active", "Approved"]
```

**2. Сложные вложенные структуры — через JSON-строку.**

Если инструмент принимает список объектов или вложенный словарь, передавай их как JSON-строку с парсингом внутри функции:

```python
@mcp.tool()
def register_requirements(project_id: str, requirements_json: str) -> str:
    """
    requirements_json: JSON-строка вида
    [{"id": "REQ-001", "text": "...", "type": "functional"}]
    """
    requirements = json.loads(requirements_json)
    # дальше работаем с Python-объектом
```

### Центральный граф требований

Файл `{project_id}_traceability_repo.json` в `governance_plans/data/` — ключевой артефакт Главы 5. Формат edge list:

```json
{
  "requirements": [
    {"id": "REQ-001", "text": "...", "status": "Active", "owner": "BA"}
  ],
  "links": [
    {"source": "REQ-001", "target": "REQ-002", "relation": "derives"}
  ]
}
```

Типы связей (`relation`): `derives`, `depends`, `satisfies`, `verifies`, `modifies`.

> **Критично:** ключи именно `requirements` (узлы) и `links` (рёбра), поле типа связи — `relation`. Не `nodes`/`edges`, не `type`. Это формат который ожидают все инструменты Главы 5 при BFS-обходе и impact analysis.

---

---

## 5. Структура скиллов (SKILL.md)

### Зачем нужны скиллы

MCP-серверы выполняют операции, но не знают **методологию**: когда вызывать инструмент, в каком порядке, что спросить у BA перед вызовом. Эту роль выполняют скиллы — контекстные инструкции для Claude Code.

Скилл — это не код. Это Markdown-файл, который Claude Code читает перед началом задачи BABOK и следует его алгоритму.

### Принцип progressive disclosure

Каждый скилл реализует два уровня детализации:

```
skills/
└── elicitation_conduct/
    ├── SKILL.md            ← лёгкий контекст (4–12 КБ), всегда читается
    └── references/
        ├── single_interview.md    ← детальный справочник (~13 КБ)
        ├── multi_interview.md     ← читается только по алгоритму
        └── change_request_elicitation.md
```

- **`SKILL.md`** — методология, алгоритм работы, шаблоны, ссылки на инструменты. Читается Claude Code в начале каждой задачи.
- **`references/*.md`** — детальные справочники (гайды по RCA, методы приоритизации, критерии качества и т.д.). Читаются только когда алгоритм SKILL.md явно указывает «прочитай references/X.md».

Это снижает загрузку контекстного окна: детальный справочник по методу fishbone не нужен на каждом шаге, только когда BA реально делает RCA.

### Структура SKILL.md

Каждый `SKILL.md` начинается с YAML front-matter:

```yaml
---
name: elicitation_conduct
description: >
  Скилл BABOK 4.2 — Проведение выявления. Триггеры: "вот транскрипт интервью",
  "проанализируй интервью", "сравни два интервью" ...
project: "AI-powered Platform AInalyst (AI Платформа AIналитик)"
copyright: "Copyright (c) 2026 Anatoly Chaussky. Licensed under AGPL v3."
---
```

Поле `description` с триггерами — это то, по чему Claude Code определяет какой скилл нужен сейчас. Писать триггеры точно и полно — важно для правильного срабатывания.

После front-matter — содержимое в свободном Markdown:

- Роль Claude в этой задаче (одна фраза)
- Пошаговый алгоритм
- Таблицы / матрицы решений (если нужны)
- MCP-инструменты: какой вызывать, когда, с какими параметрами
- Ссылки на references с условием: «если BA выбрал метод fishbone — прочитай `references/rca_guide.md`»

### Все 21 скилл

| Задача BABOK | Путь к SKILL.md |
|---|---|
| Глава 3 (все задачи) | `skills/planning_prep/SKILL.md` |
| 4.1 Подготовка к выявлению | `skills/elicitation_prep/SKILL.md` |
| 4.2 Проведение выявления | `skills/elicitation_conduct/SKILL.md` |
| 4.3 Подтверждение результатов | `skills/elicitation_confirm/SKILL.md` |
| 4.4 Коммуникация результатов | `skills/elicitation_communicate/SKILL.md` |
| 4.5 Управление сотрудничеством | `skills/elicitation_collaborate/SKILL.md` |
| 5.1 Трассировка требований | `skills/requirements_traceability/SKILL.md` |
| 5.2 Поддержка требований | `skills/requirements_maintain/SKILL.md` |
| 5.3 Приоритизация | `skills/requirements_prioritize/SKILL.md` |
| 5.4 Оценка изменений (CR) | `skills/requirements_assess_changes/SKILL.md` |
| 5.5 Утверждение требований | `skills/requirements_approve/SKILL.md` |
| 6.1 Анализ текущего состояния | `skills/current_state/SKILL.md` |
| 6.2 Определение будущего состояния | `skills/future_state/SKILL.md` |
| 6.3 Оценка рисков | `skills/risk_assessment/SKILL.md` |
| 6.4 Стратегия изменения | `skills/change_strategy/SKILL.md` |
| 7.1 Спецификация требований | `skills/requirements_spec/SKILL.md` |
| 7.2 Верификация требований | `skills/requirements_verify/SKILL.md` |
| 7.3 Валидация требований | `skills/requirements_validate/SKILL.md` |
| 7.4 Архитектура требований | `skills/requirements_architecture/SKILL.md` |
| 7.5 Варианты дизайна | `skills/design_options/SKILL.md` |
| 7.6 Оценка ценности и рекомендация | `skills/value_recommend/SKILL.md` |

### Как добавить новый скилл

1. Создать папку `skills/{task_name}/`
2. Создать `SKILL.md` с YAML front-matter (name, description с триггерами, project, copyright)
3. Опционально — создать `skills/{task_name}/references/` с детальными справочниками
4. Добавить ссылку на скилл в `CLAUDE.md` (таблица «Скиллы — читай перед каждой задачей»)

---

## 6. Хранилище артефактов

### Структура папок

Одна папка на проект — резолвер и контракт `project_id` описаны в разделе 3, «Раскладка по подкаталогам проекта».

```
governance_plans/
├── data/                                          ← JSON, machine-readable data for the MCP
│   ├── .gitkeep
│   └── <project_id>/
│       ├── <project_id>_traceability_repo.json    ← requirements graph (5.1)
│       ├── <project_id>_prioritization.json       ← prioritization results (5.3)
│       ├── <project_id>_design_options.json       ← design options (7.5)
│       ├── <project_id>_change_strategy.json      ← change strategy (6.4)
│       └── specs/                                 ← 7.1 specifications
├── reports/                                       ← Markdown, documents for humans
│   ├── .gitkeep
│   └── <project_id>/
│       ├── 6_1_current_state_<project_id>_<ts>.md ← as-is analysis (6.1)
│       ├── 6_3_risk_assessment_<project_id>_<ts>.md
│       └── 7_6_recommendation_<project_id>_<ts>.md ← recommendation to the sponsor (7.6)
└── .history/                                      ← previous versions of the data/ files
    └── <project_id>_traceability_repo.json.20260809_004512_118430.json
```

**Правило разделения:** JSON → `data/`, Markdown → `reports/`. Это зафиксировано в `common.py` через константы `DATA_DIR` и `REPORTS_DIR` и отражено в `.gitignore`.

**В `.history/` пишет только `write_json_artifact`** (раздел 3). Папка плоская и хранит последние `HISTORY_GENERATIONS` (5) версий каждого артефакта с именем `<артефакт>.<YYYYmmdd_HHMMSS_ffffff>.json`. Автоматически её не читает ничто: восстановление — осознанное действие, потому что платформа не может знать, повреждён текущий файл или просто новый.

### `.gitignore` и `.gitkeep`

```gitignore
governance_plans/data/*
governance_plans/reports/*
governance_plans/.history/
!governance_plans/data/.gitkeep
!governance_plans/reports/.gitkeep
```

Содержимое папок Git игнорирует: артефакты принадлежат проекту конкретного BA и в репозиторий попадать не должны. В `.history/` лежит то же содержимое на версию назад, поэтому она игнорируется по той же причине. Сами папки сохраняются через `.gitkeep`.

`_ensure_dirs()` в `common.py` создаёт `data/` и `reports/` автоматически при первом вызове `save_artifact`. Папки уже присутствуют в репозитории с `.gitkeep` — ручной `mkdir` не нужен.

### `inputs/`

```
inputs/
├── README.md       ← инструкция для BA что сюда класть
├── interview_ivanov_21mar.txt
├── workshop_results.pdf
└── regulations_v3.docx
```

BA кладёт сюда входные материалы перед обработкой. Содержимое в `.gitignore`. Claude Code читает файлы напрямую по пути — BA достаточно назвать имя файла в разговоре.

Поддерживаемые форматы: `.txt`, `.md`, `.pdf`, `.docx`

### Три уровня хранения

| Уровень | Где | Статус |
|---|---|---|
| 1 (локальный) | `governance_plans/` на машине BA | ✅ Реализовано |
| 2 (командный) | Confluence (через `confluence_mcp.py`) | ✅ Реализовано |
| 3 (версионный) | `governance_plans/.history/` — последние 5 версий каждого JSON-артефакта | ✅ Реализовано |
| 4 (аудит) | Git или другое внешнее хранилище: полная история, диффы, авторство | 📋 Технический долг |

Уровень 3 отвечает на вопрос «верни то, что этот инструмент только что заменил», и ни на что больше: пять поколений, без диффов, без автора, без истории дальше этого. Уровень 4 остаётся открытым, и `.history/` его не заменяет.

---

## 7. Интеграция с Confluence

### Архитектура

`skills/integrations/confluence_mcp.py` — входит в `BASE_SERVER` и **загружается во всех фазах автоматически**. Это не опциональный плагин, а часть базовой конфигурации.

Сервер стартует без ошибок даже при незаполненном `.env` — graceful fallback. Ошибка подключения возникает только в момент вызова конкретного инструмента, когда сервер пытается обратиться к Confluence API.

### Пять инструментов

| Инструмент | Что делает |
|---|---|
| `publish_artifact_to_confluence` | Публикует артефакт, **уже сохранённый** в `reports/` — документ читается с диска, поэтому его текст передавать не нужно |
| `push_to_confluence` | Публикует Markdown, переданный текстом — для разового содержимого, которое не является сохранённым артефактом |
| `pull_from_confluence` | Загружает содержимое страницы в контекст |
| `sync_page` | Обновляет существующую страницу (или создаёт, если её нет) |
| `list_space_pages` | Перечисляет страницы пространства (поиск по заголовку) |

Пользуйся `publish_artifact_to_confluence` всякий раз, когда содержимое — это результат задачи BABOK: именно прогон сохранённого документа обратно через текст и приводит к тому, что опубликованная страница отличается от артефакта, которым себя называет.

### Настройка через `.env`

Скопировать `.env.example` → `.env` и заполнить один из двух вариантов:

**Confluence Cloud:**
```env
CONFLUENCE_URL=https://your-company.atlassian.net
CONFLUENCE_EMAIL=you@company.com
CONFLUENCE_API_TOKEN=your_api_token_here
CONFLUENCE_SPACE_KEY=BA
```

**Confluence Server / Data Center:**
```env
CONFLUENCE_URL=https://confluence.internal.company.com
CONFLUENCE_USERNAME=your_username
CONFLUENCE_PASSWORD=your_password
CONFLUENCE_SPACE_KEY=BA
```

`CONFLUENCE_SPACE_KEY` — пространство по умолчанию. Можно переопределить при каждом вызове инструмента через параметр `space_key`.

### Типичный сценарий использования

После создания артефакта в `governance_plans/reports/` BA может опубликовать его в Confluence одной командой Claude Code:

> «Опубликуй план стейкхолдеров в Confluence, пространство BA»

Claude Code вызывает `push_to_confluence` — Markdown конвертируется в Confluence Storage Format через `_markdown_to_confluence_storage()` и публикуется как страница.

---

## 8. Тестирование

### Запуск

```bash
python3 -m unittest discover
```

Без pip, без внешних зависимостей — все внешние пакеты замоканы в `conftest.py`. Тесты запускаются в чистом Python-окружении.

### `conftest.py` и моки

`conftest.py` мокает все внешние зависимости до импорта MCP-серверов:

```python
# Мокаются: fastmcp, pydantic, mcp, atlassian, markdown2
sys.modules["fastmcp"] = MagicMock()
sys.modules["pydantic"] = MagicMock()
# ...
```

Это позволяет запускать тесты без установки `mcp[cli]`, `fastmcp`, `atlassian-python-api` и других runtime-зависимостей.

### `BaseMCPTest`

Базовый класс для всех тестов платформы:

```python
class BaseMCPTest(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.original_dir = os.getcwd()
        os.chdir(self.test_dir)          # каждый тест изолирован в tmpdir

    def tearDown(self):
        os.chdir(self.original_dir)
        shutil.rmtree(self.test_dir)
```

Каждый тест работает в своём временном каталоге — артефакты не засоряют рабочую папку и не влияют друг на друга.

### `patch` вместо глобального мока

```python
# ✅ Правильно — патчим save_artifact в конкретном модуле
@patch("skills.elicitation_mcp.save_artifact")
def test_save_plan(self, mock_save):
    mock_save.return_value = "✅ Артефакт сохранен"
    result = save_elicitation_plan(project_id="test", ...)
    mock_save.assert_called_once()

# ❌ Неправильно — глобальный мок ломает другие тесты
@patch("skills.common.save_artifact")
```

Патчить нужно в пространстве имён того модуля, который использует функцию, а не там где она определена.

### Структура тестов

Каждая глава и задача BABOK имеет отдельный файл:

| Файл | Покрывает |
|---|---|
| `tests/test_ch3_ch4.py` | Глава 4 (Глава 3 проверяется через `planning_mcp.py`) |
| `tests/test_ch4_41.py` … `test_ch4_45.py` | Задачи 4.1–4.5 по отдельности |
| `tests/test_ch5_51.py` … `test_ch5_55.py` | Задачи 5.1–5.5 по отдельности |
| `tests/test_ch6_61.py` … `test_ch6_64.py` | Задачи 6.1–6.4 по отдельности |
| `tests/test_ch7_71.py` … `test_ch7_76.py` | Задачи 7.1–7.6 по отдельности |
| `tests/test_confluence.py` | Интеграция с Confluence |
| `tests/test_common_*.py` | Общие помощники из `common.py` |
| `tests/test_json_writer.py` | Надёжность хранения артефактов (`write_json_artifact`) |

У нескольких задач есть второй файл — под свойство, которое проходит поперёк задачи: например `test_ch7_72_preserves_approval.py` и `test_ch7_73_alignment_direction.py`.

**Покрытие:** запусти `python -m pytest -q` — счётчик печатается в конце. Здесь он намеренно не повторяется: число, записанное в прозу, становится неверным на следующий день после добавления теста, а этот гайд уже носил такое устаревшее число.

### Как добавить тест для нового инструмента

```python
from tests.conftest import BaseMCPTest
from unittest.mock import patch
from skills.my_new_mcp import my_new_tool   # импорт после моков в conftest

class TestMyNewTool(BaseMCPTest):

    def setUp(self):
        super().setUp()
        # дополнительная настройка если нужна

    @patch("skills.my_new_mcp.save_artifact")
    def test_basic_call(self, mock_save):
        mock_save.return_value = "✅ Артефакт сохранен"
        result = my_new_tool(project_id="test_proj", param="value")
        self.assertIn("test_proj", result)
        mock_save.assert_called_once()
```

---

## 9. Среда разработки

### Требования

- Python 3.10 или выше
- pip (входит в стандартную поставку Python)

### Установка зависимостей

```bash
pip install -r requirements.txt
```

`requirements.txt` фиксирует точные версии всех зависимостей:

```
mcp[cli]==1.28.1
pydantic==2.13.4
atlassian-python-api==4.0.7    # Confluence Cloud + Server/DC интеграция
markdown2==2.5.5               # Markdown → HTML для Confluence storage format
```

Версии зафиксированы намеренно — плавающие ограничения (`>=`) допускают breaking-изменения при обновлении. При изменении версий — проверять совместимость вручную.

### Первый запуск

```bash
git clone <url>
cd ainalyst
pip install -r requirements.txt
cp .env.example .env
# Заполнить .env — Confluence API-ключи (если нужна интеграция)
python phase.py planning
# Открыть проект в Claude Code
```

После этих шагов `.mcp.json` сгенерирован с правильными абсолютными путями для текущей машины. Claude Code при открытии проекта загрузит MCP-серверы фазы `planning`.

### Почему `.mcp.json` не в репозитории

`.mcp.json` содержит абсолютные пути, специфичные для машины разработчика. Захардкоженный путь `/home/claude/ainalyst/` сломает Claude Code у любого, кто клонирует репозиторий в другую директорию (DAMAGE_REPORT_v26, Проблема 2). Файл добавлен в `.gitignore` — он генерируется `phase.py` при первом запуске.

Аналогично в `.gitignore` попадает `.ainalyst_phase` — файл хранит имя текущей активной фазы и специфичен для сессии разработчика.

### Настройка `.env`

Скопировать `.env.example` → `.env`. Два варианта в зависимости от типа Confluence:

**Confluence Cloud:**
```env
CONFLUENCE_URL=https://your-company.atlassian.net
CONFLUENCE_EMAIL=you@company.com
CONFLUENCE_API_TOKEN=your_api_token_here
CONFLUENCE_SPACE_KEY=BA
```

**Confluence Server / Data Center:**
```env
CONFLUENCE_URL=https://confluence.internal.company.com
CONFLUENCE_USERNAME=your_username
CONFLUENCE_PASSWORD=your_password
CONFLUENCE_SPACE_KEY=BA
```

Если `.env` не заполнен — платформа работает в полном объёме кроме Confluence-инструментов. MCP-сервер `confluence_mcp.py` стартует без ошибок, ошибка подключения возникает только в момент вызова конкретного инструмента.

### `.claude/` — интеграция с Claude Code

```
.claude/
├── settings.json        ← разрешения и настройки Claude Code
├── hooks/
│   ├── session_start.sh ← запускается при старте сессии
│   └── post_tool_use.sh ← запускается после каждого вызова инструмента
└── rules/
    ├── artifacts.md     ← правила работы с артефактами
    └── babok_process.md ← правила соблюдения BABOK-процесса
```

**`settings.json`** объявляет хуки и привязывает их к событиям Claude Code (`SessionStart`, `PostToolUse`). При добавлении нового хука — регистрировать здесь.

**`session_start.sh`** — запускается в начале каждой сессии. Выводит в контекст Claude Code:
- список активных проектов (по JSON-файлам в `governance_plans/data/`)
- последние 5 артефактов из `governance_plans/reports/`
- список входных материалов в `inputs/`, готовых к обработке
- подсказки по командам (голосовой режим, плановый режим)

Используется `find` вместо `ls *.{ext}` — это починка: раньше раскрытие фигурных скобок в bash давало ошибку, если файлов одного из типов не было.

**`post_tool_use.sh`** — запускается после каждого вызова MCP-инструмента. Если инструмент сохранил `.md`-файл в `governance_plans/reports/` — выводит уведомление с именем файла и командой для просмотра.

**`rules/`** — правила поведения Claude Code, которые он учитывает при работе. `artifacts.md` описывает как именовать и сохранять артефакты; `babok_process.md` — правила следования BABOK-методологии в диалоге с BA.

### Смена фазы в процессе разработки

```bash
python phase.py design     # 1. Генерирует новый .mcp.json
# В Claude Code: /restart  # 2. Перезагружает MCP-серверы
```

Смена фазы без `/restart` не применяется — Claude Code держит серверы загруженными до явной перезагрузки.

---

## 10. Добавление нового MCP-сервера

### Чеклист (6 шагов)

**Шаг 1 — Создать MCP-сервер**

Файл `skills/{chapter}_{task}_mcp.py`. Минимальный шаблон:

```python
# Copyright (c) 2026 Anatoly Chaussky. All rights reserved.
# Licensed under the AInalyst Commercial License (see COMMERCIAL_LICENSE.md).
"""
AInalyst — BABOK Глава X.Y: [Название задачи]
MCP-сервер для Claude Code.
"""

from fastmcp import FastMCP
from skills.common import save_artifact, DATA_DIR, REPORTS_DIR

mcp = FastMCP("babok-chX-XY")


@mcp.tool()
def my_new_tool(
    project_id: str,
    param: str,
) -> str:
    """
    [Описание инструмента для Claude Code].

    Возвращает путь к сохранённому артефакту.
    """
    content = f"# Результат\n\nproject_id: {project_id}\n"
    return save_artifact(content, f"{project_id}_my_prefix")


if __name__ == "__main__":
    mcp.run()
```

Требования:
- **Copyright-строка** в начале файла — не трогать при правках
- `FastMCP` с уникальным именем сервера (`babok-chX-XY`)
- `save_artifact` из `common.py` — не писать файлы напрямую
- Все матрицы и константы — в `common.py`, не дублировать в сервере

**Шаг 2 — Создать скилл**

```
skills/{task}/
├── SKILL.md          ← всегда. Методология, алгоритм, ссылки на MCP
└── references/       ← опционально. Детальные справочники
    ├── guide.md
    └── templates.md
```

Структура `SKILL.md` (минимум):

```markdown
# [Название задачи BABOK]

## Что это
[Одна фраза — суть задачи]

## Когда применять
[Триггеры — когда BA запрашивает эту задачу]

## Алгоритм
1. [Шаг 1]
2. [Шаг 2]
3. Вызвать `my_new_tool(project_id=..., param=...)`

## MCP-инструменты
| Инструмент | Когда |
|---|---|
| `my_new_tool` | [условие] |

## Справочники
- `references/guide.md` — читать когда [условие]
```

**Шаг 3 — Зарегистрировать в `phase.py`**

Добавить сервер в нужную фазу:

```python
"analysis": {
    "servers": {
        **BASE_SERVER,
        "babok-ch6-61": _server("skills/current_state_mcp.py"),
        "babok-chX-XY": _server("skills/my_new_mcp.py"),   # ← добавить здесь
    }
},
```

Если сервер нужен во всех фазах — добавить в `BASE_SERVER`. Но это редкий случай: в `BASE_SERVER` сейчас только 2 сервера (`planning_mcp.py` и `confluence_mcp.py`).

**Шаг 4 — Обновить `CLAUDE.md`**

Добавить инструмент в таблицу серверов и прописать триггеры — когда Claude Code должен вызывать этот инструмент. `CLAUDE.md` — системный промпт агента, именно он определяет поведение Claude Code при запросах BA.

**Шаг 5 — Написать тесты**

Файл `tests/test_chX_XY.py`:

```python
# Copyright (c) 2026 Anatoly Chaussky. All rights reserved.
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.conftest import BaseMCPTest
from unittest.mock import patch
import skills.my_new_mcp as mod


class TestMyNewTool(BaseMCPTest):

    def _call(self, **overrides):
        # {**defaults, **overrides}, not dict(key=val, **overrides)
        defaults = {
            "project_id": "test_proj",
            "param": "value",
        }
        kwargs = {**defaults, **overrides}
        with patch("skills.my_new_mcp.save_artifact") as mock_save:
            mock_save.return_value = "✅ Артефакт сохранен"
            result = mod.my_new_tool(**kwargs)
            return result, mock_save

    def test_basic_call(self):
        result, mock_save = self._call()
        self.assertIn("test_proj", result)
        mock_save.assert_called_once()

    def test_project_id_in_result(self):
        result, _ = self._call(project_id="crm_bank")
        self.assertIn("crm_bank", result)
```

Паттерн `_call(**overrides)` — обязательный. `{**defaults, **overrides}` семантически корректен и не падает, если передан уже существующий ключ.

**Шаг 6 — Запустить тесты**

```bash
python3 -m unittest discover
```

Все 1636+ тестов должны быть зелёными после добавления нового сервера.

### Требования к именованию

| Сущность | Паттерн | Пример |
|---|---|---|
| MCP-файл | `skills/{chapter}_{task}_mcp.py` | `skills/risk_assessment_mcp.py` |
| FastMCP имя | `babok-chX-XY` | `babok-ch6-63` |
| Скилл-папка | `skills/{task}/` | `skills/risk_assessment/` |
| Тест-файл | `tests/test_chX_XY.py` | `tests/test_ch6_63.py` |
| JSON-артефакт | `{project_id}_{prefix}.json` | `crm_bank_risk_register.json` |
| MD-артефакт | `{X_Y}_{description}_{project}.md` | `6_3_risk_assessment_crm_bank.md` |

---

## 11. Технический долг и решения по дизайну

### Решения, которые стоит знать

Полный журнал решений — внутренний рабочий документ, и в этот репозиторий он не входит. **Ниже — опубликованное подмножество:** те решения, без которых код не прочитать, не выводя заново, почему он устроен именно так.

---

**Поколения копируются ДО записи** (9 августа 2026)

`write_json_artifact` (раздел 3) копирует в `governance_plans/.history/` ту версию, которую собирается заменить, а не ту, которую только что записал. Поколения существуют ради случая, когда содержимое записано безупречно и **неверно**: `init_traceability_repo` однажды уничтожил тип узла у каждого требования, которого коснулся, — атомарно, валидно и с `✅`, — и там нужна ровно та версия, которую этот инструмент заменил. Копирование после записи сделало бы самое свежее поколение второй копией повреждения.

Принятая цена: файл, уничтоженный снаружи, восстанавливается на одно изменение назад. Это сказано в сообщении `read_json_artifact`, а не оставлено аналитику на самостоятельное открытие уже после того, как он последовал совету, — платформа не вправе предлагать помощь, которую не может оказать.

`ArtifactShapeError` наследует `CorruptArtifactError` намеренно: `except CorruptArtifactError` встречается в кодовой базе ровно один раз (граница инструмента), поэтому наследование означает, что отказ записать испорченное содержимое доходит до аналитика той же читаемой строкой `❌` — и ни одного нового `except` заводить не нужно.

---

**Удаление `main.py`** (Сессия 45, 2 апреля 2026)

`main.py` был легаси-обёрткой, реэкспортировавшей функции из `planning_mcp.py`. Удалён: создавал путаницу по точке входа, «обратная совместимость» была бессмысленна (нет публичного API). Глава 3 обслуживается исключительно `skills/planning_mcp.py`.

---

**Удаление `planning.py`** (Сессия 46, 2 апреля 2026, REVIEW_v26)

`planning.py` был «чистым» утилитным модулем бизнес-логики Главы 3 без MCP-обёртки. Использовался только в `tests/test_ch3_ch4.py`. Дублировал `_classify_stakeholder` из `planning_mcp.py` с другой сигнатурой (принимала объект `Stakeholder` вместо двух строк). Удалён: `tests/test_ch3_ch4.py` переписан под прямое тестирование `planning_mcp.py` через `BaseMCPTest`. Архитектура Главы 3 приведена в соответствие с остальными главами.

---

**`planning_mcp.py` остаётся монолитом** (Сессия 46)

Решено не разбивать `planning_mcp.py` на 5 серверов по задачам 3.1–3.5, хотя Главы 4–7 устроены именно так. Обоснование: `planning_mcp.py` входит в `BASE_SERVER` и присутствует во всех фазах, поэтому разбивка не сэкономила бы контекстного окна. 7 инструментов — это лёгкий сервер, и монолит здесь оправдан. Симметрия ради симметрии была бы избыточной.

---

**Расхождения сигнатур при написании тестов Главы 5** (Сессия 38, 29 марта 2026)

При написании `test_ch5_51.py`–`test_ch5_53.py` обнаружены расхождения между ожидаемыми и фактическими сигнатурами инструментов. Зафиксировано как паттерн: тесты пишутся по реальным сигнатурам кода, не по документации. При рефакторинге инструментов — обновлять тесты одновременно с кодом.

---

**Паттерн `_call(**overrides)` в тестовых классах** (Сессия 39)

`dict(key=val, **overrides)` падает с `TypeError` при передаче ключа уже присутствующего в `dict()`. Обязательный паттерн для всех `_call(**overrides)`: `{**defaults, **overrides}`. `overrides` побеждает — конфликтов нет. Зафиксировано в `conftest.py` как комментарий.

---

**`patch` вместо глобального мока** (ранние сессии)

При тестировании MCP-серверов патчить нужно в пространстве имён того модуля, который использует функцию: `@patch("skills.my_mcp.save_artifact")`, а не `@patch("skills.common.save_artifact")`. Глобальный мок `common.save_artifact` ломает другие тесты, запущенные параллельно или в одном discover-проходе.

---

**Claude-in-Claude** (статус: 📋 Дизайн)

Серия решений по архитектуре функции Claude-in-Claude — вызов вложенного Claude-агента из MCP-инструмента для сложных аналитических операций. Единственный незакрытый функциональный блок платформы. Оставлен на последнюю очередь разработки.

---

### Открытый технический долг

| # | Проблема | Критичность | Статус |
|---|---|---|---|
| 1 | Claude-in-Claude | 🔴 Функционал | Последняя очередь |
| 2 | Уровень хранения 3 (Git-версионирование артефактов) | 🔵 Архитектура | Не реализовано |
| 3 | Запустить `pytest` на живой машине после публикации на GitHub | 📋 Процесс | После GitHub |
| 4 | Стратегия обновления платформы без потери данных проекта | 🔵 Архитектура | Нужен дизайн |
| 5 | `_classify_stakeholder` с двумя сигнатурами удалён, но общая сверка сигнатур после рефакторинга не проводилась | 📋 QA | После публикации |

**Уровень 3 хранилища (Git-версионирование)** — артефакты `governance_plans/` игнорируются Git по умолчанию (`.gitignore`). Планировалась возможность вести историю изменений и аудит через Git. Варианты реализации: отдельная ветка под данные проекта, отдельный репозиторий, `git add -f` для явного включения артефактов. Решение не принято, реализация отложена.

**Стратегия обновления платформы**: BA ведёт проект в копии `v23`, и выходит `v24`. Как забрать новые возможности, не потеряв артефакты в `governance_plans/` и входные материалы в `inputs/`? Рассматриваются варианты: `git pull` (требует от BA владения git), скрипт `update.py` или физическое разделение платформы и данных. Вопрос остаётся открытым.

---

### История по версиям

**v20 → v26** (март 2026)

Основные изменения:
- Написаны отдельные тесты для Глав 4 и 5 (раньше был монолитный `test_ch3_ch4.py`). Для задач 5.1–5.3 добавлено около 156 тестов
- В корень проекта добавлен `README.md`
- Починен баг глоба в `session_start.sh` (`find` вместо `ls *.{txt,md,pdf,docx}`)
- В `requirements.txt` зафиксированы точные версии (раньше были плавающие `>=`)
- `interviews/` переименована в `inputs/` (список типов входных материалов расширен)
- Добавлено руководство пользователя (`USER_GUIDE.md`) и 6 отдельных CH-файлов
- `.mcp.json` убран из репозитория и добавлен в `.gitignore`; его генерирует `phase.py`
- Созданы `governance_plans/data/.gitkeep` и `governance_plans/reports/.gitkeep`

**v26 → v27** (1–2 апреля 2026, финальная подготовка к GitHub)

- Починены все критические баги из `DAMAGE_REPORT_v26.md`
- Удалён `main.py` — Глава 3 идёт через `planning_mcp.py`
- Удалён `planning.py` — дублирование с `planning_mcp.py` устранено
- `tests/test_ch3_ch4.py` переписан под `BaseMCPTest` и прямое тестирование `planning_mcp.py`
- Починен `CLAUDE.md` — структура `governance_plans/` отражает реальные подпапки `data/` и `reports/`
- Проверен `phase.py` — все 22 сервера на диске, пути через `Path(__file__).resolve().parent`
- Итог: 1636 тестов, все зелёные; 22 MCP-сервера, 111 инструментов; 27 Python-файлов без синтаксических ошибок; хардкод-путей `/home/claude` не найдено
