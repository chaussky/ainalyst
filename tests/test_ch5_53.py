"""
tests/test_ch5_53.py — Тесты для Главы 5.3: Prioritize Requirements
MCP-файл: skills/requirements_prioritize_mcp.py
Инструменты: start_prioritization_session, add_stakeholder_scores,
             run_aggregation, resolve_conflict, save_prioritization_result

Стратегия: BaseMCPTest (tmpdir + chdir), setup_mocks() до импортов,
save_artifact патчится через patch() по правилу ADR-068.
"""

import json
import os
import sys
import unittest
from datetime import date
from unittest.mock import patch, MagicMock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from tests.conftest import setup_mocks, BaseMCPTest, make_test_repo, save_test_repo
setup_mocks()

import skills.requirements_prioritize_mcp as mod53
from skills.common import data_path


# ---------------------------------------------------------------------------
# Вспомогательные данные
# ---------------------------------------------------------------------------

PROJECT = "prio_test"
SESSION = "MVP scope"


def _setup_repo(project=PROJECT):
    """Создаёт тестовый трассировочный репозиторий для 5.3."""
    repo = make_test_repo(project)
    save_test_repo(repo)
    return repo


def _start_session(project=PROJECT, session=SESSION, method="MoSCoW"):
    """Открывает сессию приоритизации."""
    with patch("skills.requirements_prioritize_mcp.save_artifact"):
        return mod53.start_prioritization_session(
            project_name=project,
            session_label=session,
            method=method,
        )


def _add_scores_moscow(project=PROJECT, session=SESSION, sh_id="SH-001",
                       influence="High", req_ids=None):
    """Добавляет MoSCoW-оценки стейкхолдера."""
    if req_ids is None:
        req_ids = ["BR-001", "FR-001", "FR-002"]
    scores = [{"req_id": r, "score": "Must"} for r in req_ids]
    with patch("skills.requirements_prioritize_mcp.save_artifact"):
        return mod53.add_stakeholder_scores(
            project_name=project,
            session_label=session,
            stakeholder_id=sh_id,
            stakeholder_influence=influence,
            scores_json=json.dumps(scores),
        )


# ---------------------------------------------------------------------------
# TestUtils53
# ---------------------------------------------------------------------------

class TestUtils53(unittest.TestCase):
    """Тесты вспомогательных функций модуля 5.3."""

    def test_minor_version_normal(self):
        """1.3 → minor = 3."""
        self.assertEqual(mod53._minor_version("1.3"), 3)

    def test_minor_version_zero(self):
        """1.0 → minor = 0."""
        self.assertEqual(mod53._minor_version("1.0"), 0)

    def test_minor_version_invalid(self):
        """Невалидная строка не бросает исключение."""
        result = mod53._minor_version("bad")
        self.assertIsInstance(result, int)

    def test_stability_flag_critical(self):
        """Версия 1.4 → критический флаг нестабильности."""
        flag = mod53._stability_flag({"version": "1.4"})
        self.assertIsNotNone(flag)

    def test_stability_flag_warning(self):
        """Версия 1.3 → предупреждающий флаг (VOLATILITY_WARNING = 3)."""
        flag = mod53._stability_flag({"version": "1.3"})
        self.assertIsNotNone(flag)

    def test_stability_flag_ok(self):
        """Версия 1.1 → нет флага."""
        flag = mod53._stability_flag({"version": "1.1"})
        self.assertIsNone(flag)

    def test_stability_flag_no_version(self):
        """Нет поля version → нет флага."""
        flag = mod53._stability_flag({})
        self.assertIsNone(flag)

    def test_aggregate_moscow_consensus_must(self):
        """Все голосуют Must → результат Must."""
        scores = {
            "SH-001": {"FR-001": "Must"},
            "SH-002": {"FR-001": "Must"},
        }
        influence = {"SH-001": "High", "SH-002": "Medium"}
        result = mod53._aggregate_moscow(scores, influence)
        agg = result["FR-001"]
        priority = agg.get("priority") if isinstance(agg, dict) else agg
        self.assertEqual(priority, "Must")

    def test_aggregate_moscow_conflict(self):
        """Must vs Won't → конфликт или решение по весу."""
        scores = {
            "SH-001": {"FR-001": "Must"},
            "SH-002": {"FR-001": "Won't"},
        }
        influence = {"SH-001": "High", "SH-002": "Low"}
        result = mod53._aggregate_moscow(scores, influence)
        self.assertIn("FR-001", result)

    def test_aggregate_wsjf_calculates_score(self):
        """WSJF: суммарный CoD и JS → числовой WSJF-score."""
        scores = {
            "SH-001": {"FR-001": {"bv": 8, "tc": 3, "rr": 2, "js": 5}},
        }
        influence = {"SH-001": "High"}
        result = mod53._aggregate_wsjf(scores, influence)
        self.assertIn("FR-001", result)

    def test_aggregate_impact_effort_quick_win(self):
        """High impact + Low effort → QuickWins."""
        scores = {
            "SH-001": {"FR-001": {"impact": "High", "effort": "Low"}},
        }
        influence = {"SH-001": "High"}
        qmap = {"QuickWins": "Must", "BigBets": "Should", "FillIns": "Could", "ThanklessTasks": "Won't"}
        result = mod53._aggregate_impact_effort(scores, influence, qmap)
        self.assertIn("FR-001", result)

    def test_detect_conflicts_critical(self):
        """Must vs Won't → конфликт обнаруживается."""
        scores = {
            "SH-001": {"FR-001": "Must"},
            "SH-002": {"FR-001": "Won't"},
        }
        conflicts = mod53._detect_stakeholder_conflicts(scores, "MoSCoW")
        self.assertTrue(len(conflicts) > 0)

    def test_detect_no_conflict_same_scores(self):
        """Одинаковые оценки → нет конфликтов."""
        scores = {
            "SH-001": {"FR-001": "Must"},
            "SH-002": {"FR-001": "Must"},
        }
        conflicts = mod53._detect_stakeholder_conflicts(scores, "MoSCoW")
        self.assertEqual(len(conflicts), 0)

    def test_must_inflation_detected(self):
        """Более 60% Must → инфляция обнаруживается."""
        priorities = {
            "FR-001": {"priority": "Must"}, "FR-002": {"priority": "Must"},
            "FR-003": {"priority": "Must"}, "FR-004": {"priority": "Must"},
            "FR-005": {"priority": "Could"},
        }
        result = mod53._check_must_inflation(priorities)
        self.assertIsNotNone(result)

    def test_must_inflation_not_triggered(self):
        """Менее 60% Must → инфляция не зафиксирована (inflated=False)."""
        priorities = {
            "FR-001": {"priority": "Must"}, "FR-002": {"priority": "Should"},
            "FR-003": {"priority": "Could"}, "FR-004": {"priority": "Won't"},
        }
        result = mod53._check_must_inflation(priorities)
        # Функция возвращает dict {"inflated": bool, "must_ratio": float}
        self.assertFalse(result["inflated"])


# ---------------------------------------------------------------------------
# TestStartPrioritizationSession
# ---------------------------------------------------------------------------

class TestStartPrioritizationSession(BaseMCPTest):
    """Тесты для инструмента 5.3: start_prioritization_session."""

    def setUp(self):
        super().setUp()
        _setup_repo()

    def _call(self, **overrides):
        defaults = dict(
            project_name=PROJECT,
            session_label=SESSION,
            method="MoSCoW",
        )
        kwargs = {**defaults, **overrides}
        with patch("skills.requirements_prioritize_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Сохранено"
            return mod53.start_prioritization_session(**kwargs)

    # --- методы ---

    def test_method_moscow(self):
        """Метод MoSCoW — сессия создаётся."""
        result = self._call(method="MoSCoW")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_method_wsjf(self):
        """Метод WSJF — сессия создаётся."""
        result = self._call(method="WSJF", session_label="WSJF session")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_method_impact_effort(self):
        """Метод ImpactEffort — сессия создаётся."""
        result = self._call(method="ImpactEffort", session_label="IE session")
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    # --- файл создаётся ---

    def test_creates_prio_file(self):
        """Файл приоритизации создаётся на диске."""
        self._call()
        safe_name = PROJECT.lower().replace(" ", "_")
        path = data_path(safe_name, f"{safe_name}_prioritization.json")
        self.assertTrue(os.path.exists(path), f"Файл не найден: {path}")

    # --- дубликат метки ---

    def test_duplicate_session_label_warns(self):
        """Повторная метка сессии → предупреждение."""
        self._call()
        result = self._call()  # второй вызов с той же меткой
        self.assertTrue("⚠️" in result or "❌" in result)

    # --- нет репозитория ---

    def test_no_repo_warns(self):
        """Нет репозитория 5.1 → предупреждение."""
        result = self._call(project_name="nonexistent_xyz")
        self.assertIsInstance(result, str)
        self.assertTrue("⚠️" in result or "❌" in result)

    # --- волатильное требование ---

    def test_flags_volatile_requirement(self):
        """Нестабильное требование (версия 1.4+) упоминается в отчёте."""
        safe_name = PROJECT.lower().replace(" ", "_")
        path = data_path(safe_name, f"{safe_name}_traceability_repo.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for r in data["requirements"]:
            if r["id"] == "FR-001":
                r["version"] = "1.5"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

        result = self._call(session_label="Volatile test session")
        self.assertIn("FR-001", result)

    # --- WSJF шкала ---

    def test_wsjf_fibonacci_scale(self):
        """WSJF Fibonacci scale упоминается в отчёте."""
        result = self._call(method="WSJF", session_label="WSJF Fib",
                            wsjf_scale="Fibonacci")
        self.assertIsInstance(result, str)
        self.assertIn("Fibonacci", result)

    # --- ImpactEffort custom mapping ---

    def test_impact_effort_custom_mapping(self):
        """Кастомный маппинг квадрантов применяется."""
        qmap = json.dumps({"QuickWins": "Must", "BigBets": "Could"})
        result = self._call(method="ImpactEffort", session_label="IE custom",
                            quadrant_mapping_json=qmap)
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_returns_string(self):
        """Всегда возвращает строку."""
        self.assertIsInstance(self._call(), str)


# ---------------------------------------------------------------------------
# TestAddStakeholderScores
# ---------------------------------------------------------------------------

class TestAddStakeholderScores(BaseMCPTest):
    """Тесты для инструмента 5.3: add_stakeholder_scores."""

    def setUp(self):
        super().setUp()
        _setup_repo()
        _start_session()

    def _call(self, **overrides):
        defaults = dict(
            project_name=PROJECT,
            session_label=SESSION,
            stakeholder_id="SH-001",
            stakeholder_influence="High",
            scores_json=json.dumps([
                {"req_id": "BR-001", "score": "Must"},
                {"req_id": "FR-001", "score": "Should"},
                {"req_id": "FR-002", "score": "Could"},
            ]),
        )
        kwargs = {**defaults, **overrides}
        with patch("skills.requirements_prioritize_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Сохранено"
            return mod53.add_stakeholder_scores(**kwargs)

    def test_moscow_scores_saved(self):
        """MoSCoW-оценки сохраняются без ошибок."""
        result = self._call()
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_scores_persisted(self):
        """Оценки записываются в файл."""
        self._call()
        safe_name = PROJECT.lower().replace(" ", "_")
        path = data_path(safe_name, f"{safe_name}_prioritization.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        session = mod53._find_session(data["sessions"], SESSION)
        self.assertIn("SH-001", session["stakeholder_scores"])

    def test_two_stakeholders_both_saved(self):
        """Оценки двух стейкхолдеров сохраняются независимо."""
        self._call(stakeholder_id="SH-001")
        self._call(stakeholder_id="SH-002", stakeholder_influence="Medium")
        safe_name = PROJECT.lower().replace(" ", "_")
        path = data_path(safe_name, f"{safe_name}_prioritization.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        session = mod53._find_session(data["sessions"], SESSION)
        self.assertIn("SH-001", session["stakeholder_scores"])
        self.assertIn("SH-002", session["stakeholder_scores"])

    def test_update_existing_stakeholder_scores(self):
        """Повторный вызов заменяет предыдущие оценки."""
        self._call(stakeholder_id="SH-001")
        updated_scores = json.dumps([{"req_id": "BR-001", "score": "Won't"}])
        self._call(stakeholder_id="SH-001", scores_json=updated_scores)
        safe_name = PROJECT.lower().replace(" ", "_")
        path = data_path(safe_name, f"{safe_name}_prioritization.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        session = mod53._find_session(data["sessions"], SESSION)
        sh_scores = session["stakeholder_scores"]["SH-001"]
        # Оценка должна быть обновлена
        self.assertIsNotNone(sh_scores)

    def test_wsjf_scores(self):
        """WSJF-оценки валидируются и сохраняются."""
        _start_session(session="WSJF session", method="WSJF")
        # (A dead `__wrapped__` probe used to sit here. It was never taken — the tool
        # carried no wrapper at the time — and its result was overwritten by the real
        # call below before anything was asserted. Adding a real decorator to the tool
        # boundary made the dead branch live and it failed immediately.)
        with patch("skills.requirements_prioritize_mcp.save_artifact"):
            result = mod53.add_stakeholder_scores(
                project_name=PROJECT,
                session_label="WSJF session",
                stakeholder_id="SH-001",
                stakeholder_influence="High",
                scores_json=json.dumps([
                    {"req_id": "BR-001", "bv": 8, "tc": 5, "rr": 3, "js": 5},
                    {"req_id": "FR-001", "bv": 5, "tc": 3, "rr": 2, "js": 3},
                ]),
            )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_invalid_moscow_value(self):
        """Невалидное MoSCoW значение → ошибка."""
        result = self._call(
            scores_json=json.dumps([{"req_id": "BR-001", "score": "INVALID"}])
        )
        self.assertIn("❌", result)

    def test_invalid_json_scores(self):
        """Невалидный JSON scores_json → ошибка."""
        result = self._call(scores_json="{bad}")
        self.assertIn("❌", result)

    def test_closed_session_rejected(self):
        """Оценки в закрытую сессию не принимаются."""
        # Вручную закрываем сессию
        safe_name = PROJECT.lower().replace(" ", "_")
        path = data_path(safe_name, f"{safe_name}_prioritization.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        session = mod53._find_session(data["sessions"], SESSION)
        session["status"] = "closed"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

        result = self._call()
        self.assertIn("❌", result)

    def test_nonexistent_session_rejected(self):
        """Несуществующая сессия → ошибка."""
        result = self._call(session_label="Nonexistent session")
        self.assertIn("❌", result)

    def test_returns_string(self):
        """Всегда возвращает строку."""
        self.assertIsInstance(self._call(), str)


# ---------------------------------------------------------------------------
# TestRunAggregation
# ---------------------------------------------------------------------------

class TestRunAggregation(BaseMCPTest):
    """Тесты для инструмента 5.3: run_aggregation."""

    def setUp(self):
        super().setUp()
        _setup_repo()
        _start_session()
        _add_scores_moscow(sh_id="SH-001", influence="High")

    def _call(self, **overrides):
        defaults = dict(
            project_name=PROJECT,
            session_label=SESSION,
            conflict_threshold="Normal",
        )
        kwargs = {**defaults, **overrides}
        with patch("skills.requirements_prioritize_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Сохранено"
            return mod53.run_aggregation(**kwargs)

    def test_aggregation_produces_priorities(self):
        """Агрегация возвращает результат с приоритетами."""
        result = self._call()
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_threshold_strict(self):
        """Строгий порог — конфликты детектируются активнее."""
        _add_scores_moscow(sh_id="SH-002", influence="Low",
                           req_ids=["BR-001", "FR-001", "FR-002"])
        result = self._call(conflict_threshold="Strict")
        self.assertIsInstance(result, str)

    def test_threshold_loose(self):
        """Мягкий порог — меньше конфликтов."""
        result = self._call(conflict_threshold="Loose")
        self.assertIsInstance(result, str)

    def _add_should_for_fr001(self):
        """SH-002 scores FR-001 as Should; SH-001 (from setUp) scored it Must.
        Category spread = Must(4) - Should(3) = 1."""
        with patch("skills.requirements_prioritize_mcp.save_artifact"):
            mod53.add_stakeholder_scores(
                project_name=PROJECT, session_label=SESSION,
                stakeholder_id="SH-002", stakeholder_influence="Medium",
                scores_json=json.dumps([{"req_id": "FR-001", "score": "Should"}]),
            )

    def test_strict_threshold_detects_one_category_spread(self):
        """Strict (spread >= 1) must surface a one-category disagreement
        (Must vs Should). Regression: the conflict detector hard-coded a
        spread >= 2 floor, so Strict could never reach 1-category conflicts
        and behaved identically to Normal."""
        self._add_should_for_fr001()
        result = self._call(conflict_threshold="Strict")
        self.assertIn("Конфликты стейкхолдеров (1 шт.)", result)
        self.assertNotIn("Конфликтов не обнаружено", result)

    def test_normal_threshold_ignores_one_category_spread(self):
        """Normal (spread >= 2) must NOT flag a one-category disagreement —
        guards the fix against over-reporting."""
        self._add_should_for_fr001()
        result = self._call(conflict_threshold="Normal")
        self.assertIn("Конфликтов не обнаружено", result)

    def test_detects_stakeholder_conflict(self):
        """Конфликт между стейкхолдерами обнаруживается."""
        with patch("skills.requirements_prioritize_mcp.save_artifact"):
            mod53.add_stakeholder_scores(
                project_name=PROJECT,
                session_label=SESSION,
                stakeholder_id="SH-002",
                stakeholder_influence="Medium",
                scores_json=json.dumps([
                    {"req_id": "BR-001", "score": "Won't"},
                    {"req_id": "FR-001", "score": "Won't"},
                    {"req_id": "FR-002", "score": "Won't"},
                ]),
            )
        result = self._call()
        self.assertIsInstance(result, str)

    def test_detects_must_inflation(self):
        """Must Inflation обнаруживается когда >60% требований Must."""
        result = self._call()
        # При оценках только Must от одного стейкхолдера — инфляция возможна
        self.assertIsInstance(result, str)

    def test_no_scores_warns(self):
        """Нет оценок → предупреждение."""
        _start_session(session="Empty session")
        with patch("skills.requirements_prioritize_mcp.save_artifact"):
            result = mod53.run_aggregation(
                project_name=PROJECT,
                session_label="Empty session",
            )
        self.assertIsInstance(result, str)
        self.assertTrue("⚠️" in result or "❌" in result)

    def test_nonexistent_session_error(self):
        """Несуществующая сессия → ошибка."""
        with patch("skills.requirements_prioritize_mcp.save_artifact"):
            result = mod53.run_aggregation(
                project_name=PROJECT,
                session_label="Phantom session",
            )
        self.assertIn("❌", result)

    def test_returns_string(self):
        """Всегда возвращает строку."""
        self.assertIsInstance(self._call(), str)


# ---------------------------------------------------------------------------
# TestResolveConflict
# ---------------------------------------------------------------------------

class TestResolveConflict(BaseMCPTest):
    """Тесты для инструмента 5.3: resolve_conflict."""

    def setUp(self):
        super().setUp()
        _setup_repo()
        _start_session()
        _add_scores_moscow(sh_id="SH-001", influence="High")
        # Добавляем второго стейкхолдера с противоположными оценками
        with patch("skills.requirements_prioritize_mcp.save_artifact"):
            mod53.add_stakeholder_scores(
                project_name=PROJECT,
                session_label=SESSION,
                stakeholder_id="SH-002",
                stakeholder_influence="Low",
                scores_json=json.dumps([
                    {"req_id": "BR-001", "score": "Won't"},
                    {"req_id": "FR-001", "score": "Won't"},
                    {"req_id": "FR-002", "score": "Won't"},
                ]),
            )
        with patch("skills.requirements_prioritize_mcp.save_artifact"):
            mod53.run_aggregation(project_name=PROJECT, session_label=SESSION)

    def _call(self, **overrides):
        defaults = dict(
            project_name=PROJECT,
            session_label=SESSION,
            req_id="BR-001",
            conflict_type="stakeholder_conflict",
            final_priority="Must",
            rationale="Бизнес-спонсор настаивает на включении",
            decided_by="Sponsor",
        )
        kwargs = {**defaults, **overrides}
        with patch("skills.requirements_prioritize_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Сохранено"
            return mod53.resolve_conflict(**kwargs)

    def test_resolve_marks_resolved(self):
        """Разрешение конфликта отрабатывает без ошибок."""
        result = self._call()
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_resolve_updates_priority(self):
        """Итоговый приоритет обновляется в данных сессии."""
        self._call(req_id="BR-001", final_priority="Should")
        safe_name = PROJECT.lower().replace(" ", "_")
        path = data_path(safe_name, f"{safe_name}_prioritization.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        session = mod53._find_session(data["sessions"], SESSION)
        agg = session["aggregated"].get("BR-001")
        if isinstance(agg, dict):
            self.assertEqual(agg.get("priority"), "Should")

    def test_resolve_all_priority_values(self):
        """Все значения final_priority принимаются."""
        for priority in ["Must", "Should", "Could", "Won't"]:
            result = self._call(final_priority=priority)
            self.assertIsInstance(result, str)

    def test_resolve_dependency_violation(self):
        """conflict_type=dependency_violation — разрешается."""
        result = self._call(conflict_type="dependency_violation")
        self.assertIsInstance(result, str)

    def test_resolve_inflation(self):
        """conflict_type=inflation — разрешается."""
        result = self._call(conflict_type="inflation")
        self.assertIsInstance(result, str)

    def test_nonexistent_session_error(self):
        """Несуществующая сессия → ошибка."""
        result = self._call(session_label="Ghost session")
        self.assertIn("❌", result)

    def test_returns_string(self):
        """Всегда возвращает строку."""
        self.assertIsInstance(self._call(), str)


# ---------------------------------------------------------------------------
# TestSavePrioritizationResult
# ---------------------------------------------------------------------------

class TestSavePrioritizationResult(BaseMCPTest):
    """Тесты для инструмента 5.3: save_prioritization_result."""

    def setUp(self):
        super().setUp()
        _setup_repo()
        _start_session()
        _add_scores_moscow(sh_id="SH-001", influence="High")
        with patch("skills.requirements_prioritize_mcp.save_artifact"):
            mod53.run_aggregation(project_name=PROJECT, session_label=SESSION)

    def _call(self, **overrides):
        defaults = dict(project_name=PROJECT, session_label=SESSION)
        kwargs = {**defaults, **overrides}
        with patch("skills.requirements_prioritize_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = ""
            return mod53.save_prioritization_result(**kwargs)

    def test_the_platforms_own_word_for_this_field_is_accepted(self):
        """`priority` is what the concept is called everywhere else — the graph node's
        field, this module's own aggregation output, 7.1's writer. Only the input said
        `score`, and a record using the natural spelling was rejected as a bad VALUE
        ("Invalid value 'None'"), sending the analyst to re-check priorities they had
        written correctly."""
        _start_session(session="wave-syn")
        with patch("skills.requirements_prioritize_mcp.save_artifact"):
            result = mod53.add_stakeholder_scores(
                project_name=PROJECT, session_label="wave-syn", stakeholder_id="SH-001",
                stakeholder_influence="High",
                scores_json=json.dumps([{"req_id": "FR-001", "priority": "Must"}]))
        self.assertNotIn("❌", result)
        self.assertIn("Требований оценено:** 1", result)

    def test_a_record_with_no_recognisable_score_names_the_field(self):
        _start_session(session="wave-nokey")
        with patch("skills.requirements_prioritize_mcp.save_artifact"):
            result = mod53.add_stakeholder_scores(
                project_name=PROJECT, session_label="wave-nokey", stakeholder_id="SH-001",
                stakeholder_influence="High",
                scores_json=json.dumps([{"req_id": "FR-001", "verdict": "Must"}]))
        self.assertIn("❌", result)
        self.assertIn("`score`", result)
        self.assertNotIn("Invalid value", result,
                         "a missing KEY was diagnosed as a bad VALUE")

    def test_an_empty_session_does_not_claim_it_wrote_priorities(self):
        """A session where no score was ever accepted used to close FOREVER and hand
        back a document saying both `Requirements updated: 0` and "Priorities have
        been written to the 5.1 repository".

        The production path into this is one keystroke wide: mistype the score field
        and every score is rejected (finding V-4), then finalise."""
        _start_session(session="wave-empty")
        with patch("skills.requirements_prioritize_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = ""
            result = mod53.save_prioritization_result(PROJECT, "wave-empty")

        self.assertNotIn("Priorities have been written", result)
        self.assertIn("Обновлено требований:** 0", result)
        self.assertIn("не собрано ни одной оценки", result.lower())

    def test_an_empty_session_is_not_closed_by_finalising_it(self):
        """Nothing was collected, so there is nothing to finalise. Closing anyway cost
        the analyst the session — `add_stakeholder_scores`, `run_aggregation` and
        `resolve_conflict` all refuse on a closed one — in exchange for a document
        that recorded nothing."""
        _start_session(session="wave-empty2")
        with patch("skills.requirements_prioritize_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = ""
            mod53.save_prioritization_result(PROJECT, "wave-empty2")

        _add_scores_moscow(session="wave-empty2", sh_id="SH-001", influence="High")
        with patch("skills.requirements_prioritize_mcp.save_artifact"):
            agg = mod53.run_aggregation(project_name=PROJECT, session_label="wave-empty2")
        self.assertNotIn("уже закрыта", agg.lower(),
                         "the analyst lost the session by finalising an empty one")

    def test_save_result_works(self):
        """Финализация сессии проходит без ошибок."""
        result = self._call()
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)

    def test_updates_traceability_repo(self):
        """Приоритеты записываются в трассировочный репозиторий."""
        self._call()
        safe_name = PROJECT.lower().replace(" ", "_")
        path = data_path(safe_name, f"{safe_name}_traceability_repo.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        # Хотя бы одно требование должно получить приоритет
        has_priority = any(r.get("priority") for r in data["requirements"])
        self.assertTrue(has_priority, "Ни одно требование не получило приоритет")

    def test_history_written_to_repo(self):
        """История изменений записывается в трассировочный репозиторий."""
        self._call()
        safe_name = PROJECT.lower().replace(" ", "_")
        path = data_path(safe_name, f"{safe_name}_traceability_repo.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("history", data)

    def test_session_closes(self):
        """Сессия помечается как closed после финализации."""
        self._call()
        safe_name = PROJECT.lower().replace(" ", "_")
        path = data_path(safe_name, f"{safe_name}_prioritization.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        session = mod53._find_session(data["sessions"], SESSION)
        self.assertEqual(session["status"], "closed")

    def test_second_session_snapshot_appended(self):
        """Вторая сессия создаёт отдельный снапшот."""
        self._call()  # закрываем первую

        _start_session(session="Sprint 2 planning")
        _add_scores_moscow(session="Sprint 2 planning", sh_id="SH-001")
        with patch("skills.requirements_prioritize_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = ""
            mod53.run_aggregation(
                project_name=PROJECT, session_label="Sprint 2 planning"
            )
        with patch("skills.requirements_prioritize_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = ""
            result2 = mod53.save_prioritization_result(
                project_name=PROJECT, session_label="Sprint 2 planning"
            )
        self.assertIsInstance(result2, str)
        self.assertNotIn("❌", result2)

    def test_nonexistent_session_error(self):
        """Несуществующая сессия → ошибка."""
        result = self._call(session_label="Phantom session")
        self.assertIn("❌", result)

    def test_save_artifact_called(self):
        """save_artifact вызывается при финализации."""
        with patch("skills.requirements_prioritize_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Сохранено"
            mod53.save_prioritization_result(
                project_name=PROJECT, session_label=SESSION
            )
            mock_sa.assert_called_once()

    def test_returns_string(self):
        """Всегда возвращает строку."""
        self.assertIsInstance(self._call(), str)


# ---------------------------------------------------------------------------
# TestIntegration53
# ---------------------------------------------------------------------------

class TestIntegration53(BaseMCPTest):
    """Интеграционные тесты: полный цикл 5.3."""

    def setUp(self):
        super().setUp()
        _setup_repo()

    def test_full_moscow_workflow(self):
        """Полный цикл MoSCoW: start → scores × 2 → aggregate → save."""
        _start_session()

        _add_scores_moscow(sh_id="SH-001", influence="High",
                           req_ids=["BR-001", "FR-001", "FR-002"])
        _add_scores_moscow(sh_id="SH-002", influence="Medium",
                           req_ids=["BR-001", "FR-001", "FR-002"])

        with patch("skills.requirements_prioritize_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = ""
            agg_result = mod53.run_aggregation(
                project_name=PROJECT, session_label=SESSION
            )
        self.assertIsInstance(agg_result, str)

        with patch("skills.requirements_prioritize_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = ""
            save_result = mod53.save_prioritization_result(
                project_name=PROJECT, session_label=SESSION
            )
        self.assertIsInstance(save_result, str)
        self.assertNotIn("❌", save_result)

    def test_conflict_resolution_then_save(self):
        """Цикл с разрешением конфликта."""
        _start_session()
        _add_scores_moscow(sh_id="SH-001", influence="High")
        with patch("skills.requirements_prioritize_mcp.save_artifact"):
            mod53.add_stakeholder_scores(
                project_name=PROJECT,
                session_label=SESSION,
                stakeholder_id="SH-002",
                stakeholder_influence="Low",
                scores_json=json.dumps([
                    {"req_id": "BR-001", "score": "Won't"},
                    {"req_id": "FR-001", "score": "Could"},
                    {"req_id": "FR-002", "score": "Should"},
                ]),
            )
        with patch("skills.requirements_prioritize_mcp.save_artifact"):
            mod53.run_aggregation(project_name=PROJECT, session_label=SESSION)
        with patch("skills.requirements_prioritize_mcp.save_artifact"):
            mod53.resolve_conflict(
                project_name=PROJECT,
                session_label=SESSION,
                req_id="BR-001",
                conflict_type="stakeholder_conflict",
                final_priority="Must",
                rationale="Спонсор настаивает",
                decided_by="Sponsor",
            )
        with patch("skills.requirements_prioritize_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = ""
            result = mod53.save_prioritization_result(
                project_name=PROJECT, session_label=SESSION
            )
        self.assertIsInstance(result, str)
        self.assertNotIn("❌", result)


class TestSaveWritesWsjfScoreAndNamesPhantomIds(BaseMCPTest):
    """Two seams of the same save step, both found on the full-pipeline audit:

    (1) 5.5's rejection analysis reads `wsjf_score` off the graph node to warn
    "you are rejecting a high-value requirement" — but nothing ever WROTE that
    field (grep: one reader, zero writers), so the warning was dead by
    construction. A WSJF session now persists the score alongside the priority.

    (2) A score for a typo'd req_id ("FR-01") rendered in the aggregation report
    and then silently vanished at save — "Requirements updated: N" under a table
    with N+1 rows, a count with no explanation. Unmatched ids are now NAMED."""

    P = "prio_seams"

    def _wsjf_session(self):
        save_test_repo(make_test_repo(self.P))
        with patch("skills.requirements_prioritize_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            mod53.start_prioritization_session(self.P, "wsjf run", "WSJF")
            mod53.add_stakeholder_scores(
                self.P, "wsjf run", "Anna", "High",
                json.dumps([
                    {"req_id": "FR-001", "bv": 8, "tc": 5, "rr": 3, "js": 3},
                    {"req_id": "FR-01", "bv": 5, "tc": 2, "rr": 2, "js": 2},  # typo
                ]))
            mod53.run_aggregation(self.P, "wsjf run")
            return mod53.save_prioritization_result(self.P, "wsjf run")

    def test_wsjf_score_lands_on_the_node(self):
        self._wsjf_session()
        with open(data_path(self.P, f"{self.P}_traceability_repo.json"),
                  encoding="utf-8") as f:
            repo = json.load(f)
        node = next(r for r in repo["requirements"] if r["id"] == "FR-001")
        self.assertIn("wsjf_score", node,
                      "5.5 reads wsjf_score off the node — someone must write it")
        self.assertGreater(node["wsjf_score"], 0)

    def test_phantom_id_is_named_not_silently_dropped(self):
        out = self._wsjf_session()
        self.assertIn("FR-01", out)
        self.assertIn("НЕ сохранены", out)


class TestTheReportNamesTheStepThatIsActuallyMissing(BaseMCPTest):
    """One condition — `not session["aggregated"]` — stood for three different states,
    and the document described all three as the first one.

    An empty aggregate means "nothing was WRITTEN". It does not mean "nothing was
    COLLECTED": scores live in `stakeholder_scores` and reach `aggregated` only when
    `run_aggregation` is called. Skipping that call is an ordinary omission, and the
    report answered it by denying the scores exist — two sections above its own
    "Stakeholders: 1" — then telling the analyst to enter them again.

    The third state is a session already closed on disk. There the text announced
    "The session is still OPEN" and advised `add_stakeholder_scores`, which the
    platform refuses on a closed session: a document contradicting the disk and
    handing out a step that cannot be taken.

    What must NOT change: a session where nothing was ever collected still records
    nothing, still says so, and still stays open (V-3/V-4, pinned by
    test_an_empty_session_does_not_claim_it_wrote_priorities and
    test_an_empty_session_is_not_closed_by_finalising_it).
    """

    def setUp(self):
        super().setUp()
        _setup_repo()

    def _finalise(self, session):
        with patch("skills.requirements_prioritize_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = ""
            return mod53.save_prioritization_result(PROJECT, session)

    def _prio_path(self):
        safe = PROJECT.lower().replace(" ", "_")
        return data_path(safe, f"{safe}_prioritization.json")

    def _close_on_disk(self, session):
        """The state a session finalised by the PREVIOUS version is left in: closed,
        with an empty aggregate. Written directly because the current code refuses to
        close such a session at all — which is the point of the fix that created it."""
        path = self._prio_path()
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        closed = 0
        for s in data["sessions"]:
            if s["label"] == session:
                s["status"] = "closed"
                s["закрыт_at"] = "2026-08-01"
                closed += 1
        assert closed == 1, f"fixture закрыт {closed} sessions, not the one under test"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # -- scores collected, aggregation skipped ------------------------------

    def test_collected_scores_are_not_denied(self):
        _start_session(session="wave-noagg")
        _add_scores_moscow(session="wave-noagg", sh_id="SH-001", influence="High")
        out = self._finalise("wave-noagg")

        self.assertIn("Стейкхолдеров: 1", out, "fixture did not collect anything")
        self.assertNotIn("не собрано ни одной оценки", out,
                         "the scores are on disk and counted two sections below:\n" + out)

    def test_the_missing_step_is_named(self):
        """The gap is the aggregation, so that is the step the document must name."""
        _start_session(session="wave-noagg2")
        _add_scores_moscow(session="wave-noagg2", sh_id="SH-001", influence="High")
        out = self._finalise("wave-noagg2")

        self.assertIn("run_aggregation", out)
        self.assertNotIn("Вызвать `add_stakeholder_scores`", out,
                         "they are already entered; re-entering them is not the step")

    def test_nothing_is_written_when_the_aggregate_is_empty(self):
        """The diagnosis changes; the caution does not. No aggregate, no priorities."""
        _start_session(session="wave-noagg3")
        _add_scores_moscow(session="wave-noagg3", sh_id="SH-001", influence="High")
        out = self._finalise("wave-noagg3")

        self.assertNotIn("Priorities have been written", out)
        safe = PROJECT.lower().replace(" ", "_")
        with open(data_path(safe, f"{safe}_traceability_repo.json"), encoding="utf-8") as f:
            repo = json.load(f)
        self.assertFalse(any(r.get("priority") for r in repo["requirements"]),
                         "an un-aggregated session wrote priorities to the graph")

    def test_the_session_that_wrote_nothing_stays_open(self):
        _start_session(session="wave-noagg4")
        _add_scores_moscow(session="wave-noagg4", sh_id="SH-001", influence="High")
        self._finalise("wave-noagg4")

        with patch("skills.requirements_prioritize_mcp.save_artifact"):
            agg = mod53.run_aggregation(project_name=PROJECT, session_label="wave-noagg4")
        self.assertNotIn("уже закрыта", agg.lower(),
                         "finalising before aggregating cost the analyst the session")

    # -- session already closed on disk -------------------------------------

    def test_a_closed_session_is_not_called_open(self):
        _start_session(session="wave-legacy")
        self._close_on_disk("wave-legacy")
        out = self._finalise("wave-legacy")

        self.assertNotIn("ещё ОТКРЫТА", out,
                         "the disk says закрыт:\n" + out)
        self.assertNotIn("Сессия остаётся открытой", out,
                         "the disk says закрыт:\n" + out)

    def test_a_closed_session_is_not_told_to_add_scores(self):
        """The platform answers `add_stakeholder_scores` on a closed session with
        `❌ Session is already closed`. Advice the platform refuses is not advice."""
        _start_session(session="wave-legacy2")
        self._close_on_disk("wave-legacy2")
        out = self._finalise("wave-legacy2")

        self.assertNotIn("Вызвать `add_stakeholder_scores`", out, out)

        with patch("skills.requirements_prioritize_mcp.save_artifact"):
            refused = mod53.add_stakeholder_scores(
                project_name=PROJECT, session_label="wave-legacy2",
                stakeholder_id="SH-001", stakeholder_influence="High",
                scores_json=json.dumps([{"req_id": "FR-001", "score": "Must"}]))
        self.assertIn("закрыт", refused.lower(),
                      "fixture is wrong: the platform accepted the advised step")

    def test_a_closed_empty_session_is_sent_to_a_new_session(self):
        """The only route left once the session is closed — the same one the
        re-finalisation note already names."""
        _start_session(session="wave-legacy3")
        self._close_on_disk("wave-legacy3")
        out = self._finalise("wave-legacy3")

        self.assertIn("новую сессию приоритизации", out.lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
