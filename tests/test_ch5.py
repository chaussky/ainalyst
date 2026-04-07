"""
tests/test_ch5.py — Тесты для Главы 5 (5.1 Трассировка и 5.2 Поддержание)
"""

import json
import os
import sys
import unittest
from datetime import date, timedelta

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Моки применяются через conftest при импорте
from tests.conftest import BaseMCPTest, make_test_repo, save_test_repo, load_test_repo
from skills.common import DATA_DIR

import skills.requirements_traceability_mcp as mod51
import skills.requirements_maintain_mcp as mod52


# ---------------------------------------------------------------------------
# 5.1 — Утилиты (чистые функции, без файловой системы)
# ---------------------------------------------------------------------------

class TestTraceabilityUtils(unittest.TestCase):

    def test_repo_path_normalizes_spaces(self):
        path = mod51._repo_path("My Project")
        self.assertNotIn(" ", path)
        self.assertIn("my_project", path)
        self.assertIn("traceability_repo.json", path)

    def test_repo_path_consistency_51_52(self):
        for name in ["Test Project", "CRM 2024", "банк онлайн"]:
            self.assertEqual(
                mod51._repo_path(name), mod52._repo_path(name),
                f"Пути различаются для: {name}"
            )

    def test_find_req_existing(self):
        repo = make_test_repo()
        req = mod51._find_req(repo, "FR-001")
        self.assertIsNotNone(req)
        self.assertEqual(req["id"], "FR-001")

    def test_find_req_missing(self):
        self.assertIsNone(mod51._find_req(make_test_repo(), "XX-999"))

    def test_find_links_both_directions(self):
        repo = make_test_repo()
        links = mod51._find_links(repo, "FR-001")
        self.assertEqual(len(links), 2)  # derives + verifies

    def test_find_links_isolated_node(self):
        repo = make_test_repo()
        self.assertEqual(len(mod51._find_links(repo, "FR-002")), 0)


# ---------------------------------------------------------------------------
# 5.1 — MCP-инструменты (с файловой системой)
# ---------------------------------------------------------------------------

class TestTraceabilityMCP(BaseMCPTest):

    P = "proj_51"

    def _init(self):
        return mod51.init_traceability_repo(self.P, "Standard", json.dumps([
            {"id": "BR-001", "type": "business", "title": "БТ", "version": "1.0", "status": "confirmed"},
            {"id": "FR-001", "type": "solution", "title": "ФТ", "version": "1.0", "status": "confirmed"},
            {"id": "FR-DEP", "type": "solution", "title": "Устар.", "version": "1.0", "status": "deprecated"},
        ]))

    def test_init_creates_json_file(self):
        self._init()
        files = [f for f in os.listdir(DATA_DIR) if f.endswith(".json")]
        self.assertEqual(len(files), 1)

    def test_init_correct_structure(self):
        self._init()
        repo = load_test_repo(self.P)
        self.assertEqual(repo["project"], self.P)
        self.assertIn("requirements", repo)
        self.assertIn("links", repo)
        self.assertIn("history", repo)

    def test_init_deduplication(self):
        self._init()
        mod51.init_traceability_repo(self.P, "Standard", json.dumps([
            {"id": "BR-001", "type": "business", "title": "Новое название", "version": "1.1", "status": "confirmed"}
        ]))
        repo = load_test_repo(self.P)
        count = sum(1 for r in repo["requirements"] if r["id"] == "BR-001")
        self.assertEqual(count, 1)

    def test_add_link_creates_entry(self):
        self._init()
        mod51.add_trace_link(self.P, "FR-001", "BR-001", "derives", "тест")
        repo = load_test_repo(self.P)
        self.assertTrue(any(
            l["from"] == "FR-001" and l["to"] == "BR-001" and l["relation"] == "derives"
            for l in repo["links"]
        ))

    def test_add_link_no_duplicate(self):
        self._init()
        mod51.add_trace_link(self.P, "FR-001", "BR-001", "derives", "")
        mod51.add_trace_link(self.P, "FR-001", "BR-001", "derives", "")
        repo = load_test_repo(self.P)
        count = sum(1 for l in repo["links"]
                    if l["from"] == "FR-001" and l["to"] == "BR-001")
        self.assertEqual(count, 1)

    def test_add_link_remove(self):
        self._init()
        mod51.add_trace_link(self.P, "FR-001", "BR-001", "derives", "")
        result = mod51.add_trace_link(self.P, "FR-001", "BR-001", "derives", "", remove=True)
        self.assertIn("✅", result)
        repo = load_test_repo(self.P)
        self.assertEqual(
            len([l for l in repo["links"] if l["from"] == "FR-001" and l["to"] == "BR-001"]), 0
        )

    def test_add_link_remove_nonexistent(self):
        self._init()
        result = mod51.add_trace_link(self.P, "XX-001", "YY-001", "derives", "", remove=True)
        self.assertIn("не найдена", result)

    def test_impact_finds_affected(self):
        self._init()
        mod51.add_trace_link(self.P, "FR-001", "BR-001", "derives", "")
        result = mod51.run_impact_analysis(self.P, "BR-001", "Изменение")
        self.assertIn("FR-001", result)

    def test_impact_unknown_req(self):
        self._init()
        result = mod51.run_impact_analysis(self.P, "XX-999", "Тест")
        self.assertIn("не найдено", result)

    def test_coverage_excludes_deprecated(self):
        self._init()
        result = mod51.check_coverage(self.P)
        if "Нет источника" in result:
            idx = result.find("Нет источника")
            section = result[idx:idx + 600]
            self.assertNotIn("FR-DEP", section)

    def test_coverage_fr001_orphan_without_link(self):
        self._init()
        result = mod51.check_coverage(self.P)
        self.assertIn("FR-001", result)  # orphan — нет derives вверх

    def test_export_contains_active_requirements(self):
        self._init()
        result = mod51.export_traceability_matrix(self.P)
        self.assertIn("BR-001", result)
        self.assertIn("FR-001", result)

    def test_export_filter_by_type(self):
        self._init()
        result = mod51.export_traceability_matrix(self.P, filter_type="business")
        self.assertIn("BR-001", result)
        self.assertNotIn("FR-001", result)


# ---------------------------------------------------------------------------
# 5.2 — Утилиты
# ---------------------------------------------------------------------------

class TestMaintainUtils(unittest.TestCase):

    def test_minor_version(self):
        self.assertEqual(mod52._minor_version("1.0"), 0)
        self.assertEqual(mod52._minor_version("1.3"), 3)
        self.assertEqual(mod52._minor_version("invalid"), 0)
        self.assertEqual(mod52._minor_version(""), 0)

    def test_days_since_today(self):
        self.assertEqual(mod52._days_since(str(date.today())), 0)

    def test_days_since_past(self):
        self.assertEqual(mod52._days_since(str(date.today() - timedelta(days=10))), 10)

    def test_days_since_invalid(self):
        self.assertEqual(mod52._days_since("bad-date"), 0)


# ---------------------------------------------------------------------------
# 5.2 — MCP-инструменты
# ---------------------------------------------------------------------------

class TestMaintainMCP(BaseMCPTest):

    P = "proj_52"

    def _prepare(self):
        save_test_repo(make_test_repo(self.P))

    def test_update_status(self):
        self._prepare()
        mod52.update_requirement(self.P, "FR-001", "После 5.5", new_status="approved")
        repo = load_test_repo(self.P)
        fr001 = next(r for r in repo["requirements"] if r["id"] == "FR-001")
        self.assertEqual(fr001["status"], "approved")

    def test_update_writes_history(self):
        self._prepare()
        mod52.update_requirement(self.P, "FR-001", "Тест", new_status="approved")
        repo = load_test_repo(self.P)
        self.assertTrue(any(h["action"] == "requirement_updated" for h in repo["history"]))

    def test_update_auto_volatility(self):
        self._prepare()
        mod52.update_requirement(self.P, "FR-001", "Много изменений", new_version="1.4")
        repo = load_test_repo(self.P)
        fr001 = next(r for r in repo["requirements"] if r["id"] == "FR-001")
        self.assertEqual(fr001.get("stability"), "Volatile")

    def test_update_unknown_id(self):
        self._prepare()
        result = mod52.update_requirement(self.P, "XX-999", "Тест", new_status="approved")
        self.assertIn("не найдено", result)

    def test_update_no_changes(self):
        self._prepare()
        result = mod52.update_requirement(self.P, "FR-001", "Проверка")
        self.assertIn("Нет изменений", result)

    def test_deprecate_sets_status(self):
        self._prepare()
        mod52.deprecate_requirements(self.P, json.dumps(["FR-002"]), "deprecated", "Устарело")
        repo = load_test_repo(self.P)
        fr002 = next(r for r in repo["requirements"] if r["id"] == "FR-002")
        self.assertEqual(fr002["status"], "deprecated")

    def test_deprecate_preserves_record(self):
        self._prepare()
        mod52.deprecate_requirements(self.P, json.dumps(["FR-002"]), "deprecated", "Тест")
        repo = load_test_repo(self.P)
        self.assertIn("FR-002", [r["id"] for r in repo["requirements"]])

    def test_deprecate_superseded_requires_superseded_by(self):
        self._prepare()
        result = mod52.deprecate_requirements(
            self.P, json.dumps(["FR-001"]), "superseded", "Заменено", superseded_by=""
        )
        self.assertIn("❌", result)

    def test_deprecate_superseded_ok_with_superseded_by(self):
        self._prepare()
        mod52.deprecate_requirements(
            self.P, json.dumps(["FR-002"]), "superseded", "Заменено", superseded_by="FR-010"
        )
        repo = load_test_repo(self.P)
        fr002 = next(r for r in repo["requirements"] if r["id"] == "FR-002")
        self.assertEqual(fr002["superseded_by"], "FR-010")

    def test_health_detects_volatile(self):
        self._prepare()
        repo = load_test_repo(self.P)
        for r in repo["requirements"]:
            if r["id"] == "FR-001":
                r["version"] = "1.4"
        save_test_repo(repo)
        result = mod52.check_requirements_health(self.P)
        self.assertIn("FR-001", result)

    def test_health_excludes_deprecated(self):
        self._prepare()
        mod52.deprecate_requirements(self.P, json.dumps(["FR-002"]), "deprecated", "Тест")
        result = mod52.check_requirements_health(self.P)
        self.assertNotIn("FR-002", result)

    def test_find_reusable_approved_candidate(self):
        self._prepare()
        mod52.update_requirement(self.P, "FR-001", "Для reuse",
                                 new_status="approved", reuse_candidate="true")
        result = mod52.find_reusable_requirements(self.P)
        self.assertIn("FR-001", result)


# ---------------------------------------------------------------------------
# Интеграция 5.1 + 5.2
# ---------------------------------------------------------------------------

class TestIntegration51_52(BaseMCPTest):

    P = "integ"

    def test_one_file_two_modules(self):
        mod51.init_traceability_repo(self.P, "Standard", json.dumps([
            {"id": "FR-001", "type": "solution", "title": "Тест",
             "version": "1.0", "status": "confirmed"}
        ]))
        mod52.update_requirement(self.P, "FR-001", "Интеграция", new_status="approved")
        files = [f for f in os.listdir(DATA_DIR) if f.endswith(".json")]
        self.assertEqual(len(files), 1)
        repo = load_test_repo(self.P)
        fr001 = next(r for r in repo["requirements"] if r["id"] == "FR-001")
        self.assertEqual(fr001["status"], "approved")

    def test_history_from_both_modules(self):
        mod51.init_traceability_repo(self.P, "Standard", json.dumps([
            {"id": "FR-001", "type": "solution", "title": "Тест",
             "version": "1.0", "status": "draft"}
        ]))
        mod51.add_trace_link(self.P, "FR-001", "BR-001", "derives", "")
        mod52.update_requirement(self.P, "FR-001", "Тест", new_status="confirmed")
        repo = load_test_repo(self.P)
        actions = [h["action"] for h in repo["history"]]
        self.assertIn("link_added", actions)
        self.assertIn("requirement_updated", actions)

    def test_deprecated_by_52_excluded_from_51_coverage(self):
        mod51.init_traceability_repo(self.P, "Standard", json.dumps([
            {"id": "BR-001", "type": "business", "title": "БТ", "version": "1.0", "status": "confirmed"},
            {"id": "FR-001", "type": "solution", "title": "ФТ", "version": "1.0", "status": "confirmed"},
            {"id": "FR-OLD", "type": "solution", "title": "Старое", "version": "1.0", "status": "confirmed"},
        ]))
        mod51.add_trace_link(self.P, "FR-001", "BR-001", "derives", "")
        mod52.deprecate_requirements(self.P, json.dumps(["FR-OLD"]), "deprecated", "Устарело")
        result = mod51.check_coverage(self.P)
        if "Нет источника" in result:
            idx = result.find("Нет источника")
            section = result[idx:idx + 800]
            self.assertNotIn("FR-OLD", section)


if __name__ == "__main__":
    unittest.main(verbosity=2)


# ---------------------------------------------------------------------------
# 5.3 — Prioritize Requirements
# ---------------------------------------------------------------------------

import skills.requirements_prioritize_mcp as mod53


def make_prio_repo(project_name: str = "prio_test") -> dict:
    """Тестовый репозиторий совместимый с 5.1/5.2 форматом."""
    return {
        "project": project_name,
        "formality_level": "Standard",
        "created": str(date.today()),
        "updated": str(date.today()),
        "requirements": [
            {"id": "FR-001", "type": "solution", "title": "Авторизация",
             "version": "1.0", "status": "confirmed", "priority": None},
            {"id": "FR-002", "type": "solution", "title": "Личный кабинет",
             "version": "1.0", "status": "confirmed", "priority": None},
            {"id": "FR-003", "type": "solution", "title": "Отчёты",
             "version": "1.4", "status": "confirmed", "priority": None},  # volatile
            {"id": "BR-001", "type": "business", "title": "Снизить время обработки",
             "version": "1.0", "status": "confirmed", "priority": None},
        ],
        "links": [
            {"from": "FR-002", "to": "FR-001", "relation": "depends",
             "rationale": "ЛК требует авторизацию", "added": str(date.today())},
        ],
        "history": [],
    }


def save_prio_repo(repo: dict) -> None:
    safe = repo["project"].lower().replace(" ", "_")
    path = os.path.join(DATA_DIR, f"{safe}_traceability_repo.json")
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(repo, f, ensure_ascii=False, indent=2)


def load_prio_file(project_name: str) -> dict:
    safe = project_name.lower().replace(" ", "_")
    path = os.path.join(DATA_DIR, f"{safe}_prioritization.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


class TestPrioritizeUtils(unittest.TestCase):
    """Тесты чистых утилит 5.3."""

    def test_minor_version_normal(self):
        self.assertEqual(mod53._minor_version("1.3"), 3)

    def test_minor_version_zero(self):
        self.assertEqual(mod53._minor_version("1.0"), 0)

    def test_minor_version_invalid(self):
        self.assertEqual(mod53._minor_version("bad"), 0)

    def test_stability_flag_critical(self):
        node = {"version": "1.4", "stability": "Volatile"}
        self.assertEqual(mod53._stability_flag(node), "critical")

    def test_stability_flag_warning(self):
        node = {"version": "1.3", "stability": "Volatile"}
        self.assertEqual(mod53._stability_flag(node), "warning")

    def test_stability_flag_ok(self):
        node = {"version": "1.0", "stability": "Stable"}
        self.assertIsNone(mod53._stability_flag(node))

    def test_stability_flag_unknown(self):
        node = {"version": "1.0", "stability": "Unknown"}
        self.assertEqual(mod53._stability_flag(node), "unknown")

    def test_aggregate_moscow_consensus_must(self):
        scores = {
            "SH-001": {"FR-001": "Must"},
            "SH-002": {"FR-001": "Must"},
        }
        influence = {"SH-001": "High", "SH-002": "Medium"}
        result = mod53._aggregate_moscow(scores, influence)
        self.assertEqual(result["FR-001"]["priority"], "Must")

    def test_aggregate_moscow_conflict_resolves_by_weight(self):
        # High influence говорит Must, Low — Won't → Must должен победить
        scores = {
            "SH-001": {"FR-001": "Must"},   # High weight=3
            "SH-002": {"FR-001": "Won't"},  # Low weight=1
        }
        influence = {"SH-001": "High", "SH-002": "Low"}
        result = mod53._aggregate_moscow(scores, influence)
        # Взвешенный: (4*3 + 1*1) / 4 = 13/4 = 3.25 → Should (≥2.5)
        self.assertIn(result["FR-001"]["priority"], ["Must", "Should"])

    def test_aggregate_wsjf_calculates_score(self):
        scores = {
            "SH-001": {"FR-001": {"bv": 8, "tc": 5, "rr": 3, "js": 4}},
        }
        influence = {"SH-001": "High"}
        result = mod53._aggregate_wsjf(scores, influence)
        self.assertIn("FR-001", result)
        self.assertGreater(result["FR-001"]["wsjf"], 0)
        self.assertIn("priority", result["FR-001"])

    def test_aggregate_impact_effort_quick_win(self):
        scores = {"SH-001": {"FR-001": {"impact": "High", "effort": "Low"}}}
        influence = {"SH-001": "Medium"}
        qmap = {"QuickWins": "Must", "BigBets": "Should",
                "FillIns": "Could", "ThanklessTasks": "Won't"}
        result = mod53._aggregate_impact_effort(scores, influence, qmap)
        self.assertEqual(result["FR-001"]["priority"], "Must")
        self.assertEqual(result["FR-001"]["quadrant"], "QuickWins")

    def test_aggregate_impact_effort_thankless(self):
        scores = {"SH-001": {"FR-001": {"impact": "Low", "effort": "High"}}}
        influence = {"SH-001": "Medium"}
        qmap = {"QuickWins": "Must", "BigBets": "Should",
                "FillIns": "Could", "ThanklessTasks": "Won't"}
        result = mod53._aggregate_impact_effort(scores, influence, qmap)
        self.assertEqual(result["FR-001"]["priority"], "Won't")

    def test_find_dependency_violation_detected(self):
        repo = {
            "links": [
                {"from": "FR-002", "to": "FR-001", "relation": "depends"}
            ]
        }
        priorities = {
            "FR-002": {"priority": "Must"},
            "FR-001": {"priority": "Won't"},
        }
        violations = mod53._find_dependency_violations(repo, priorities)
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0]["req_id"], "FR-002")

    def test_find_dependency_no_violation_when_ok(self):
        repo = {
            "links": [{"from": "FR-002", "to": "FR-001", "relation": "depends"}]
        }
        priorities = {
            "FR-002": {"priority": "Must"},
            "FR-001": {"priority": "Must"},
        }
        self.assertEqual(len(mod53._find_dependency_violations(repo, priorities)), 0)

    def test_find_dependency_ignores_non_depends(self):
        repo = {
            "links": [{"from": "TC-001", "to": "FR-001", "relation": "verifies"}]
        }
        priorities = {
            "TC-001": {"priority": "Must"},
            "FR-001": {"priority": "Won't"},
        }
        # verifies не является dependency — violation не должен возникать
        self.assertEqual(len(mod53._find_dependency_violations(repo, priorities)), 0)

    def test_detect_stakeholder_conflicts_critical(self):
        scores = {
            "SH-001": {"FR-001": "Must"},
            "SH-002": {"FR-001": "Won't"},
        }
        conflicts = mod53._detect_stakeholder_conflicts(scores, "MoSCoW")
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["spread"], 3)

    def test_detect_no_conflict_same_scores(self):
        scores = {
            "SH-001": {"FR-001": "Must"},
            "SH-002": {"FR-001": "Must"},
        }
        self.assertEqual(len(mod53._detect_stakeholder_conflicts(scores, "MoSCoW")), 0)

    def test_must_inflation_detected(self):
        priorities = {
            "FR-001": {"priority": "Must"},
            "FR-002": {"priority": "Must"},
            "FR-003": {"priority": "Must"},
            "FR-004": {"priority": "Should"},
        }
        result = mod53._check_must_inflation(priorities)
        self.assertTrue(result["inflated"])  # 75% > 60%

    def test_must_inflation_not_triggered(self):
        priorities = {
            "FR-001": {"priority": "Must"},
            "FR-002": {"priority": "Should"},
            "FR-003": {"priority": "Could"},
        }
        result = mod53._check_must_inflation(priorities)
        self.assertFalse(result["inflated"])  # 33% < 60%


class TestPrioritizeTools(BaseMCPTest):
    """Интеграционные тесты MCP-инструментов 5.3."""

    P = "prio_test"

    def _prepare_repo(self):
        save_prio_repo(make_prio_repo(self.P))

    def test_start_session_creates_file(self):
        self._prepare_repo()
        result = mod53.start_prioritization_session(
            self.P, "MVP scope", "MoSCoW")
        self.assertIn("MVP scope", result)
        prio = load_prio_file(self.P)
        self.assertEqual(len(prio["sessions"]), 1)
        self.assertEqual(prio["sessions"][0]["label"], "MVP scope")

    def test_start_session_no_repo_warns(self):
        result = mod53.start_prioritization_session(
            "nonexistent_project", "Test", "MoSCoW")
        self.assertIn("не содержит требований", result)

    def test_start_session_duplicate_label(self):
        self._prepare_repo()
        mod53.start_prioritization_session(self.P, "Sprint 1", "MoSCoW")
        result = mod53.start_prioritization_session(self.P, "Sprint 1", "MoSCoW")
        self.assertIn("уже существует", result)

    def test_start_session_flags_volatile_requirement(self):
        self._prepare_repo()
        result = mod53.start_prioritization_session(
            self.P, "Vol Test", "MoSCoW")
        # FR-003 имеет версию 1.4 — должен быть отмечен
        self.assertIn("FR-003", result)

    def test_start_session_wsjf_shows_scale(self):
        self._prepare_repo()
        result = mod53.start_prioritization_session(
            self.P, "WSJF test", "WSJF", wsjf_scale="Fibonacci")
        self.assertIn("Fibonacci", result)
        self.assertIn("1, 2, 3, 5, 8, 13", result)

    def test_start_session_impact_effort_custom_mapping(self):
        self._prepare_repo()
        custom = json.dumps({"BigBets": "Must"})
        result = mod53.start_prioritization_session(
            self.P, "IE test", "ImpactEffort",
            quadrant_mapping_json=custom)
        self.assertIn("Must", result)

    def test_add_scores_moscow_saved(self):
        self._prepare_repo()
        mod53.start_prioritization_session(self.P, "S1", "MoSCoW")
        scores = json.dumps([
            {"req_id": "FR-001", "score": "Must"},
            {"req_id": "FR-002", "score": "Should"},
        ])
        result = mod53.add_stakeholder_scores(
            self.P, "S1", "SH-001", "High", scores)
        self.assertIn("SH-001", result)
        prio = load_prio_file(self.P)
        session = prio["sessions"][0]
        self.assertIn("SH-001", session["stakeholder_scores"])
        self.assertEqual(session["stakeholder_scores"]["SH-001"]["FR-001"], "Must")

    def test_add_scores_invalid_moscow_value(self):
        self._prepare_repo()
        mod53.start_prioritization_session(self.P, "S1", "MoSCoW")
        bad = json.dumps([{"req_id": "FR-001", "score": "High"}])
        result = mod53.add_stakeholder_scores(self.P, "S1", "SH-001", "High", bad)
        self.assertIn("Недопустимое значение", result)

    def test_add_scores_two_stakeholders_both_saved(self):
        self._prepare_repo()
        mod53.start_prioritization_session(self.P, "S2", "MoSCoW")
        s1 = json.dumps([{"req_id": "FR-001", "score": "Must"}])
        s2 = json.dumps([{"req_id": "FR-001", "score": "Could"}])
        mod53.add_stakeholder_scores(self.P, "S2", "SH-001", "High", s1)
        mod53.add_stakeholder_scores(self.P, "S2", "SH-002", "Low", s2)
        prio = load_prio_file(self.P)
        session = prio["sessions"][0]
        self.assertIn("SH-001", session["stakeholder_scores"])
        self.assertIn("SH-002", session["stakeholder_scores"])

    def test_add_scores_update_existing(self):
        self._prepare_repo()
        mod53.start_prioritization_session(self.P, "S3", "MoSCoW")
        s1 = json.dumps([{"req_id": "FR-001", "score": "Must"}])
        s2 = json.dumps([{"req_id": "FR-001", "score": "Should"}])
        mod53.add_stakeholder_scores(self.P, "S3", "SH-001", "High", s1)
        mod53.add_stakeholder_scores(self.P, "S3", "SH-001", "High", s2)
        prio = load_prio_file(self.P)
        session = prio["sessions"][0]
        # Второй вызов должен перезаписать
        self.assertEqual(session["stakeholder_scores"]["SH-001"]["FR-001"], "Should")

    def test_add_scores_wsjf_format(self):
        self._prepare_repo()
        mod53.start_prioritization_session(self.P, "WSJF1", "WSJF")
        scores = json.dumps([
            {"req_id": "FR-001", "bv": 8, "tc": 5, "rr": 3, "js": 4},
        ])
        result = mod53.add_stakeholder_scores(
            self.P, "WSJF1", "SH-001", "High", scores)
        self.assertNotIn("Ошибка", result)
        prio = load_prio_file(self.P)
        saved = prio["sessions"][0]["stakeholder_scores"]["SH-001"]["FR-001"]
        self.assertEqual(saved["bv"], 8.0)

    def test_run_aggregation_moscow_produces_priorities(self):
        self._prepare_repo()
        mod53.start_prioritization_session(self.P, "AGG1", "MoSCoW")
        scores = json.dumps([
            {"req_id": "FR-001", "score": "Must"},
            {"req_id": "FR-002", "score": "Should"},
            {"req_id": "BR-001", "score": "Must"},
        ])
        mod53.add_stakeholder_scores(self.P, "AGG1", "SH-001", "High", scores)
        result = mod53.run_aggregation(self.P, "AGG1")
        self.assertIn("Must", result)
        self.assertIn("FR-001", result)

    def test_run_aggregation_detects_conflict(self):
        self._prepare_repo()
        mod53.start_prioritization_session(self.P, "CONF1", "MoSCoW")
        s1 = json.dumps([{"req_id": "FR-001", "score": "Must"}])
        s2 = json.dumps([{"req_id": "FR-001", "score": "Won't"}])
        mod53.add_stakeholder_scores(self.P, "CONF1", "SH-001", "High", s1)
        mod53.add_stakeholder_scores(self.P, "CONF1", "SH-002", "Low", s2)
        result = mod53.run_aggregation(self.P, "CONF1")
        self.assertIn("Конфликт", result)
        self.assertIn("FR-001", result)

    def test_run_aggregation_detects_dependency_violation(self):
        self._prepare_repo()
        # FR-002 depends on FR-001 (из make_prio_repo)
        mod53.start_prioritization_session(self.P, "DEP1", "MoSCoW")
        # FR-002 = Must, FR-001 = Won't → violation
        scores = json.dumps([
            {"req_id": "FR-001", "score": "Won't"},
            {"req_id": "FR-002", "score": "Must"},
            {"req_id": "BR-001", "score": "Should"},
        ])
        mod53.add_stakeholder_scores(self.P, "DEP1", "SH-001", "High", scores)
        result = mod53.run_aggregation(self.P, "DEP1")
        self.assertIn("Violation", result)

    def test_run_aggregation_must_inflation(self):
        self._prepare_repo()
        mod53.start_prioritization_session(self.P, "INF1", "MoSCoW")
        scores = json.dumps([
            {"req_id": "FR-001", "score": "Must"},
            {"req_id": "FR-002", "score": "Must"},
            {"req_id": "FR-003", "score": "Must"},
            {"req_id": "BR-001", "score": "Must"},
        ])
        mod53.add_stakeholder_scores(self.P, "INF1", "SH-001", "High", scores)
        result = mod53.run_aggregation(self.P, "INF1")
        self.assertIn("Inflation", result)

    def test_run_aggregation_wsjf(self):
        self._prepare_repo()
        mod53.start_prioritization_session(self.P, "WSJF2", "WSJF")
        scores = json.dumps([
            {"req_id": "FR-001", "bv": 13, "tc": 8, "rr": 5, "js": 3},
            {"req_id": "FR-002", "bv": 3, "tc": 1, "rr": 1, "js": 8},
        ])
        mod53.add_stakeholder_scores(self.P, "WSJF2", "SH-001", "High", scores)
        result = mod53.run_aggregation(self.P, "WSJF2")
        self.assertIn("WSJF", result)
        self.assertIn("FR-001", result)

    def test_run_aggregation_no_scores_warns(self):
        self._prepare_repo()
        mod53.start_prioritization_session(self.P, "EMPTY", "MoSCoW")
        result = mod53.run_aggregation(self.P, "EMPTY")
        self.assertIn("Нет оценок", result)

    def test_resolve_conflict_marks_resolved(self):
        self._prepare_repo()
        mod53.start_prioritization_session(self.P, "RES1", "MoSCoW")
        s1 = json.dumps([{"req_id": "FR-001", "score": "Must"}])
        s2 = json.dumps([{"req_id": "FR-001", "score": "Won't"}])
        mod53.add_stakeholder_scores(self.P, "RES1", "SH-001", "High", s1)
        mod53.add_stakeholder_scores(self.P, "RES1", "SH-002", "Low", s2)
        mod53.run_aggregation(self.P, "RES1")
        result = mod53.resolve_conflict(
            self.P, "RES1", "FR-001", "stakeholder_conflict",
            "Must", "Согласовано со спонсором", "Sponsor")
        self.assertIn("разрешён", result)
        prio = load_prio_file(self.P)
        session = prio["sessions"][0]
        conflict = next((c for c in session["conflicts"]
                         if c["req_id"] == "FR-001"), None)
        self.assertIsNotNone(conflict)
        self.assertTrue(conflict["resolved"])

    def test_resolve_conflict_updates_priority(self):
        self._prepare_repo()
        mod53.start_prioritization_session(self.P, "RES2", "MoSCoW")
        s1 = json.dumps([{"req_id": "FR-001", "score": "Should"}])
        mod53.add_stakeholder_scores(self.P, "RES2", "SH-001", "High", s1)
        mod53.run_aggregation(self.P, "RES2")
        mod53.resolve_conflict(
            self.P, "RES2", "FR-001", "stakeholder_conflict",
            "Must", "Решение PM", "PM")
        prio = load_prio_file(self.P)
        session = prio["sessions"][0]
        self.assertEqual(
            session["aggregated"]["FR-001"]["priority"], "Must")

    def test_save_result_updates_repo(self):
        self._prepare_repo()
        mod53.start_prioritization_session(self.P, "SAVE1", "MoSCoW")
        scores = json.dumps([
            {"req_id": "FR-001", "score": "Must"},
            {"req_id": "FR-002", "score": "Should"},
            {"req_id": "BR-001", "score": "Must"},
            {"req_id": "FR-003", "score": "Could"},
        ])
        mod53.add_stakeholder_scores(self.P, "SAVE1", "SH-001", "High", scores)
        mod53.run_aggregation(self.P, "SAVE1")
        mod53.save_prioritization_result(self.P, "SAVE1")
        # Читаем репозиторий 5.1 напрямую
        safe = self.P.lower().replace(" ", "_")
        repo_path = os.path.join(DATA_DIR,
                                  f"{safe}_traceability_repo.json")
        with open(repo_path) as f:
            repo = json.load(f)
        fr001 = next(r for r in repo["requirements"] if r["id"] == "FR-001")
        self.assertEqual(fr001["priority"], "Must")

    def test_save_result_history_written(self):
        self._prepare_repo()
        mod53.start_prioritization_session(self.P, "HIST1", "MoSCoW")
        scores = json.dumps([{"req_id": "FR-001", "score": "Must"}])
        mod53.add_stakeholder_scores(self.P, "HIST1", "SH-001", "High", scores)
        mod53.run_aggregation(self.P, "HIST1")
        mod53.save_prioritization_result(self.P, "HIST1")
        safe = self.P.lower().replace(" ", "_")
        with open(os.path.join(DATA_DIR,
                                f"{safe}_traceability_repo.json")) as f:
            repo = json.load(f)
        actions = [h["action"] for h in repo.get("history", [])]
        self.assertIn("priority_updated", actions)

    def test_save_result_closes_session(self):
        self._prepare_repo()
        mod53.start_prioritization_session(self.P, "CLOSE1", "MoSCoW")
        scores = json.dumps([{"req_id": "FR-001", "score": "Must"}])
        mod53.add_stakeholder_scores(self.P, "CLOSE1", "SH-001", "High", scores)
        mod53.run_aggregation(self.P, "CLOSE1")
        mod53.save_prioritization_result(self.P, "CLOSE1")
        prio = load_prio_file(self.P)
        session = prio["sessions"][0]
        self.assertEqual(session["status"], "closed")

    def test_snapshot_appended_second_session(self):
        self._prepare_repo()
        # Первая сессия
        mod53.start_prioritization_session(self.P, "S-A", "MoSCoW")
        s = json.dumps([{"req_id": "FR-001", "score": "Must"}])
        mod53.add_stakeholder_scores(self.P, "S-A", "SH-001", "High", s)
        mod53.run_aggregation(self.P, "S-A")
        mod53.save_prioritization_result(self.P, "S-A")
        # Вторая сессия
        mod53.start_prioritization_session(self.P, "S-B", "MoSCoW")
        mod53.add_stakeholder_scores(self.P, "S-B", "SH-001", "High", s)
        mod53.run_aggregation(self.P, "S-B")
        mod53.save_prioritization_result(self.P, "S-B")
        # Обе сессии должны существовать
        prio = load_prio_file(self.P)
        labels = [sess["label"] for sess in prio["sessions"]]
        self.assertIn("S-A", labels)
        self.assertIn("S-B", labels)
        self.assertEqual(len(prio["sessions"]), 2)

    def test_add_scores_to_closed_session(self):
        self._prepare_repo()
        mod53.start_prioritization_session(self.P, "CLOSED", "MoSCoW")
        s = json.dumps([{"req_id": "FR-001", "score": "Must"}])
        mod53.add_stakeholder_scores(self.P, "CLOSED", "SH-001", "High", s)
        mod53.run_aggregation(self.P, "CLOSED")
        mod53.save_prioritization_result(self.P, "CLOSED")
        result = mod53.add_stakeholder_scores(self.P, "CLOSED", "SH-002", "Low", s)
        self.assertIn("закрыта", result)

    def test_impact_effort_custom_mapping_applied(self):
        self._prepare_repo()
        # Big Bets → Must (нестандартный маппинг)
        custom = json.dumps({"BigBets": "Must"})
        mod53.start_prioritization_session(
            self.P, "IE2", "ImpactEffort", quadrant_mapping_json=custom)
        scores = json.dumps([
            {"req_id": "FR-001", "impact": "High", "effort": "High"},  # Big Bet
        ])
        mod53.add_stakeholder_scores(self.P, "IE2", "SH-001", "High", scores)
        result = mod53.run_aggregation(self.P, "IE2")
        prio = load_prio_file(self.P)
        session = prio["sessions"][0]
        self.assertEqual(
            session["aggregated"].get("FR-001", {}).get("priority"), "Must")

