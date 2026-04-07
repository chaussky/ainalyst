"""
tests/test_ch5_54.py — Тесты для задачи 5.4 Assess Requirements Changes

Покрытие:
  Unit-тесты утилит:
    - _repo_path, _find_node, _find_links
    - _bfs_impact: изолированный узел, цепочка, несколько типов связей
    - _calc_score: граничные значения, все комбинации
    - _score_verdict: все пороги
    - _get_version_minor: форматы версий

  Интеграционные тесты MCP:
    - open_cr: успешная регистрация, дубликат, отсутствующие требования
    - run_cr_impact: BFS-обход, modifies-связи, Impact/Schedule авто-расчёт,
                     волатильные требования, конфликты приоритетов, нет BR-трассировки
    - score_cr: все вердикты формулы, регуляторный CR, ba_notes
    - resolve_cr: Approved (under_change), Rejected (без изменений),
                  Deferred, Approved_with_Modification,
                  регуляторный CR нельзя Reject, Decision Record генерируется

  Интеграционный pipeline:
    - полный happy path: open → impact → score → resolve (Approved)
    - полный path: open → impact → score → resolve (Rejected)
    - повторный resolve невозможен без score
"""

import json
import os
import sys
import unittest
from datetime import date

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from tests.conftest import BaseMCPTest, make_test_repo, save_test_repo, load_test_repo

import skills.requirements_assess_changes_mcp as mod54


# ---------------------------------------------------------------------------
# Unit-тесты утилит (без файловой системы)
# ---------------------------------------------------------------------------

class TestUtils(unittest.TestCase):

    def test_repo_path_normalizes_spaces(self):
        path = mod54._repo_path("My Project")
        self.assertNotIn(" ", path)
        self.assertIn("my_project", path)
        self.assertIn("traceability_repo.json", path)

    def test_repo_path_lowercase(self):
        path = mod54._repo_path("CRM 2024")
        self.assertIn("crm_2024", path)

    def test_find_node_existing(self):
        repo = make_test_repo()
        node = mod54._find_node(repo, "FR-001")
        self.assertIsNotNone(node)
        self.assertEqual(node["id"], "FR-001")

    def test_find_node_missing(self):
        self.assertIsNone(mod54._find_node(make_test_repo(), "XX-999"))

    def test_find_links_both_directions(self):
        repo = make_test_repo()
        links = mod54._find_links(repo, "FR-001")
        self.assertEqual(len(links), 2)  # derives + verifies

    def test_find_links_isolated_node(self):
        repo = make_test_repo()
        links = mod54._find_links(repo, "FR-002")
        self.assertEqual(len(links), 0)

    def test_find_links_no_modifies_leakage(self):
        """modifies-связи должны корректно обнаруживаться через _find_links."""
        repo = make_test_repo()
        repo["links"].append({
            "from": "CR-001", "to": "FR-001", "relation": "modifies"
        })
        links = mod54._find_links(repo, "CR-001")
        self.assertTrue(any(l["relation"] == "modifies" for l in links))


class TestBfsImpact(unittest.TestCase):

    def _make_repo_with_chain(self):
        """BR-001 ← derives ← FR-001 ← verifies ← TC-001."""
        repo = make_test_repo()
        return repo

    def test_bfs_from_fr001_finds_br_and_tc(self):
        repo = self._make_repo_with_chain()
        affected = mod54._bfs_impact(repo, ["FR-001"])
        ids = [a["id"] for a in affected]
        self.assertIn("BR-001", ids)
        self.assertIn("TC-001", ids)

    def test_bfs_isolated_node_empty(self):
        repo = make_test_repo()
        affected = mod54._bfs_impact(repo, ["FR-002"])
        self.assertEqual(len(affected), 0)

    def test_bfs_does_not_follow_modifies(self):
        """BFS не должен рекурсивно обходить modifies-связи."""
        repo = make_test_repo()
        repo["requirements"].append({
            "id": "CR-001", "type": "change_request", "title": "CR",
            "version": "1.0", "status": "open"
        })
        repo["links"].append({"from": "CR-001", "to": "FR-001", "relation": "modifies"})
        affected = mod54._bfs_impact(repo, ["FR-001"])
        ids = [a["id"] for a in affected]
        self.assertNotIn("CR-001", ids)

    def test_bfs_no_duplicates(self):
        repo = make_test_repo()
        affected = mod54._bfs_impact(repo, ["FR-001"])
        ids = [a["id"] for a in affected]
        self.assertEqual(len(ids), len(set(ids)))

    def test_bfs_affected_has_relation_field(self):
        repo = make_test_repo()
        affected = mod54._bfs_impact(repo, ["FR-001"])
        for item in affected:
            self.assertIn("relation", item)
            self.assertIn("id", item)
            self.assertIn("title", item)


class TestCalcScore(unittest.TestCase):

    def test_high_benefit_low_cost_high_urgency_approves(self):
        # Benefit=High(3), Cost=Low(1 raw), Urgency=Critical(3), Impact=High(3), Schedule=Low(1 raw)
        # Formula: 3*2 + 3*1.5 + 3*1 - 1*1.5 - 1*1 = 11.0 >= 8.0
        score = mod54._calc_score(3, 1, 3, 3, 1)
        self.assertGreaterEqual(score, mod54.SCORE_APPROVE)

    def test_low_benefit_high_cost_rejects(self):
        # Benefit=Low(1), Cost=High(3 raw), Urgency=Normal(1), Impact=Low(1), Schedule=High(3 raw)
        # Formula: 1*2 + 1*1.5 + 1*1 - 3*1.5 - 3*1 = -3.0 < 1.0
        score = mod54._calc_score(1, 3, 1, 1, 3)
        self.assertLess(score, mod54.SCORE_DEFER)

    def test_medium_values_modify_range(self):
        # Benefit=Medium(2), Cost=Medium(2 raw), Urgency=High(2), Impact=Medium(2), Schedule=Medium(2 raw)
        # Formula: 2*2 + 2*1.5 + 2*1 - 2*1.5 - 2*1 = 4.0 in [4.0, 8.0)
        score = mod54._calc_score(2, 2, 2, 2, 2)
        self.assertGreaterEqual(score, mod54.SCORE_MODIFY)
        self.assertLess(score, mod54.SCORE_APPROVE)

    def test_score_is_float(self):
        score = mod54._calc_score(2, 2, 2, 2, 2)
        self.assertIsInstance(score, float)

    def test_formula_weights(self):
        """Benefit имеет наибольший вес (×2.0)."""
        score_high_benefit = mod54._calc_score(3, 2, 2, 2, 2)
        score_low_benefit = mod54._calc_score(1, 2, 2, 2, 2)
        self.assertGreater(score_high_benefit, score_low_benefit)


class TestScoreVerdict(unittest.TestCase):

    def test_approve_threshold(self):
        self.assertIn("Approve", mod54._score_verdict(8.0))
        self.assertIn("Approve", mod54._score_verdict(10.0))

    def test_modify_threshold(self):
        self.assertIn("Modify", mod54._score_verdict(4.0))
        self.assertIn("Modify", mod54._score_verdict(7.9))

    def test_defer_threshold(self):
        self.assertIn("Defer", mod54._score_verdict(1.0))
        self.assertIn("Defer", mod54._score_verdict(3.9))

    def test_reject_threshold(self):
        self.assertIn("Reject", mod54._score_verdict(0.9))
        self.assertIn("Reject", mod54._score_verdict(-5.0))


class TestGetVersionMinor(unittest.TestCase):

    def test_normal_version(self):
        self.assertEqual(mod54._get_version_minor("1.3"), 3)

    def test_major_only(self):
        self.assertEqual(mod54._get_version_minor("2"), 0)

    def test_invalid_string(self):
        self.assertEqual(mod54._get_version_minor("unknown"), 0)

    def test_zero_minor(self):
        self.assertEqual(mod54._get_version_minor("1.0"), 0)

    def test_high_minor(self):
        self.assertEqual(mod54._get_version_minor("1.4"), 4)


# ---------------------------------------------------------------------------
# Интеграционные тесты — open_cr
# ---------------------------------------------------------------------------

class TestOpenCR(BaseMCPTest):

    P = "proj_54_open"

    def _setup_repo(self):
        repo = make_test_repo(self.P)
        save_test_repo(repo)

    def test_open_cr_success(self):
        self._setup_repo()
        result = mod54.open_cr(
            project_name=self.P,
            cr_id="CR-001",
            title="Добавить экспорт в PDF",
            description="Пользователи хотят экспортировать отчёты в PDF",
            initiator="Product Owner",
            cr_type="new_requirement",
            formality="standard",
            target_req_ids_json='["FR-001"]',
        )
        self.assertIn("CR-001", result)
        self.assertIn("зарегистрирован", result.lower())

    def test_open_cr_creates_node_in_repo(self):
        self._setup_repo()
        mod54.open_cr(
            project_name=self.P,
            cr_id="CR-001",
            title="Test CR",
            description="desc",
            initiator="PO",
            cr_type="change_existing",
            formality="standard",
            target_req_ids_json='["FR-001"]',
        )
        repo = load_test_repo(self.P)
        cr = mod54._find_node(repo, "CR-001")
        self.assertIsNotNone(cr)
        self.assertEqual(cr["type"], "change_request")
        self.assertEqual(cr["status"], "open")

    def test_open_cr_duplicate_rejected(self):
        self._setup_repo()
        kwargs = dict(
            project_name=self.P, cr_id="CR-001", title="T",
            description="d", initiator="PO", cr_type="new_requirement",
            formality="standard", target_req_ids_json='["FR-001"]',
        )
        mod54.open_cr(**kwargs)
        result = mod54.open_cr(**kwargs)
        self.assertIn("уже существует", result)

    def test_open_cr_missing_target_req(self):
        self._setup_repo()
        result = mod54.open_cr(
            project_name=self.P,
            cr_id="CR-001",
            title="T",
            description="d",
            initiator="PO",
            cr_type="new_requirement",
            formality="standard",
            target_req_ids_json='["XX-999"]',
        )
        self.assertIn("не найден", result)

    def test_open_cr_regulatory_sets_urgency_critical(self):
        self._setup_repo()
        mod54.open_cr(
            project_name=self.P,
            cr_id="CR-REG",
            title="Соответствие GDPR",
            description="Регуляторное изменение",
            initiator="Legal",
            cr_type="change_existing",
            formality="high",
            target_req_ids_json='["FR-001"]',
            urgency="Normal",
            regulatory=True,
        )
        repo = load_test_repo(self.P)
        cr = mod54._find_node(repo, "CR-REG")
        self.assertEqual(cr["urgency"], "Critical")

    def test_open_cr_invalid_json_target(self):
        self._setup_repo()
        result = mod54.open_cr(
            project_name=self.P,
            cr_id="CR-001",
            title="T",
            description="d",
            initiator="PO",
            cr_type="new_requirement",
            formality="standard",
            target_req_ids_json="not_json",
        )
        self.assertIn("❌", result)

    def test_open_cr_pre_release_warning(self):
        self._setup_repo()
        result = mod54.open_cr(
            project_name=self.P,
            cr_id="CR-001",
            title="T",
            description="d",
            initiator="PO",
            cr_type="new_requirement",
            formality="high",
            target_req_ids_json='["FR-001"]',
            project_phase="pre_release",
        )
        self.assertIn("pre_release", result)

    def test_open_cr_history_recorded(self):
        self._setup_repo()
        mod54.open_cr(
            project_name=self.P,
            cr_id="CR-001",
            title="T",
            description="d",
            initiator="PO",
            cr_type="new_requirement",
            formality="standard",
            target_req_ids_json='["FR-001"]',
        )
        repo = load_test_repo(self.P)
        self.assertTrue(any(
            h.get("action") == "cr_opened" and h.get("cr_id") == "CR-001"
            for h in repo.get("history", [])
        ))


# ---------------------------------------------------------------------------
# Интеграционные тесты — run_cr_impact
# ---------------------------------------------------------------------------

class TestRunCRImpact(BaseMCPTest):

    P = "proj_54_impact"

    def _setup_and_open(self, cr_id="CR-001", target='["FR-001"]'):
        repo = make_test_repo(self.P)
        save_test_repo(repo)
        mod54.open_cr(
            project_name=self.P,
            cr_id=cr_id,
            title="Test CR",
            description="desc",
            initiator="PO",
            cr_type="change_existing",
            formality="standard",
            target_req_ids_json=target,
        )

    def test_run_cr_impact_success(self):
        self._setup_and_open()
        result = mod54.run_cr_impact(self.P, "CR-001")
        self.assertIn("Анализ влияния", result)

    def test_run_cr_impact_creates_modifies_links(self):
        self._setup_and_open()
        mod54.run_cr_impact(self.P, "CR-001")
        repo = load_test_repo(self.P)
        modifies = [l for l in repo["links"]
                    if l["from"] == "CR-001" and l["relation"] == "modifies"]
        self.assertEqual(len(modifies), 1)
        self.assertEqual(modifies[0]["to"], "FR-001")

    def test_run_cr_impact_no_duplicate_modifies(self):
        """Повторный вызов не создаёт дублирующих modifies-связей."""
        self._setup_and_open()
        mod54.run_cr_impact(self.P, "CR-001")
        mod54.run_cr_impact(self.P, "CR-001")
        repo = load_test_repo(self.P)
        modifies = [l for l in repo["links"]
                    if l["from"] == "CR-001" and l["relation"] == "modifies"]
        self.assertEqual(len(modifies), 1)

    def test_run_cr_impact_stores_impact_data(self):
        self._setup_and_open()
        mod54.run_cr_impact(self.P, "CR-001")
        repo = load_test_repo(self.P)
        cr = mod54._find_node(repo, "CR-001")
        self.assertIsNotNone(cr.get("impact_analysis"))
        self.assertIn("impact_auto", cr["impact_analysis"])
        self.assertIn("schedule_auto", cr["impact_analysis"])

    def test_run_cr_impact_bfs_finds_downstream(self):
        """FR-001 → derives → BR-001 и verifies → TC-001 должны быть найдены."""
        self._setup_and_open()
        mod54.run_cr_impact(self.P, "CR-001")
        repo = load_test_repo(self.P)
        cr = mod54._find_node(repo, "CR-001")
        affected_ids = cr["impact_analysis"]["affected_ids"]
        self.assertIn("BR-001", affected_ids)
        self.assertIn("TC-001", affected_ids)

    def test_run_cr_impact_isolated_req_low_impact(self):
        """FR-002 изолирован — Impact должен быть Low."""
        repo = make_test_repo(self.P)
        save_test_repo(repo)
        mod54.open_cr(
            project_name=self.P,
            cr_id="CR-ISO",
            title="Isolated CR",
            description="d",
            initiator="PO",
            cr_type="change_existing",
            formality="standard",
            target_req_ids_json='["FR-002"]',
        )
        mod54.run_cr_impact(self.P, "CR-ISO")
        repo = load_test_repo(self.P)
        cr = mod54._find_node(repo, "CR-ISO")
        self.assertEqual(cr["impact_analysis"]["impact_auto"], "Low")

    def test_run_cr_impact_pre_release_high_schedule(self):
        repo = make_test_repo(self.P)
        save_test_repo(repo)
        mod54.open_cr(
            project_name=self.P,
            cr_id="CR-PRE",
            title="Pre-release CR",
            description="d",
            initiator="PO",
            cr_type="change_existing",
            formality="high",
            target_req_ids_json='["FR-002"]',
            project_phase="pre_release",
        )
        mod54.run_cr_impact(self.P, "CR-PRE")
        repo = load_test_repo(self.P)
        cr = mod54._find_node(repo, "CR-PRE")
        self.assertEqual(cr["impact_analysis"]["schedule_auto"], "High")

    def test_run_cr_impact_volatile_req_warning(self):
        """Требование с версией 1.3+ должно попасть в volatile_req_ids."""
        repo = make_test_repo(self.P)
        # Делаем FR-002 волатильным
        for r in repo["requirements"]:
            if r["id"] == "FR-002":
                r["version"] = "1.3"
        save_test_repo(repo)
        mod54.open_cr(
            project_name=self.P,
            cr_id="CR-VOL",
            title="Volatile CR",
            description="d",
            initiator="PO",
            cr_type="change_existing",
            formality="standard",
            target_req_ids_json='["FR-002"]',
        )
        mod54.run_cr_impact(self.P, "CR-VOL")
        repo = load_test_repo(self.P)
        cr = mod54._find_node(repo, "CR-VOL")
        self.assertIn("FR-002", cr["impact_analysis"]["volatile_req_ids"])

    def test_run_cr_impact_priority_conflict_wont(self):
        """Требование с приоритетом Won't должно попасть в priority_conflicts."""
        repo = make_test_repo(self.P)
        for r in repo["requirements"]:
            if r["id"] == "FR-002":
                r["priority"] = "Won't"
        save_test_repo(repo)
        mod54.open_cr(
            project_name=self.P,
            cr_id="CR-CONF",
            title="Conflict CR",
            description="d",
            initiator="PO",
            cr_type="change_existing",
            formality="standard",
            target_req_ids_json='["FR-002"]',
        )
        mod54.run_cr_impact(self.P, "CR-CONF")
        repo = load_test_repo(self.P)
        cr = mod54._find_node(repo, "CR-CONF")
        self.assertIn("FR-002", cr["impact_analysis"]["priority_conflicts"])

    def test_run_cr_impact_no_br_trace_detected(self):
        """FR-002 не связан с BR через derives — должен попасть в no_br_trace."""
        repo = make_test_repo(self.P)
        save_test_repo(repo)
        mod54.open_cr(
            project_name=self.P,
            cr_id="CR-NBR",
            title="No BR CR",
            description="d",
            initiator="PO",
            cr_type="change_existing",
            formality="standard",
            target_req_ids_json='["FR-002"]',
        )
        mod54.run_cr_impact(self.P, "CR-NBR")
        repo = load_test_repo(self.P)
        cr = mod54._find_node(repo, "CR-NBR")
        self.assertIn("FR-002", cr["impact_analysis"]["no_br_trace"])

    def test_run_cr_impact_br_traced_not_in_no_br(self):
        """FR-001 связан с BR-001 через derives — не должен попасть в no_br_trace."""
        repo = make_test_repo(self.P)
        save_test_repo(repo)
        mod54.open_cr(
            project_name=self.P,
            cr_id="CR-HBR",
            title="Has BR CR",
            description="d",
            initiator="PO",
            cr_type="change_existing",
            formality="standard",
            target_req_ids_json='["FR-001"]',
        )
        mod54.run_cr_impact(self.P, "CR-HBR")
        repo = load_test_repo(self.P)
        cr = mod54._find_node(repo, "CR-HBR")
        self.assertNotIn("FR-001", cr["impact_analysis"]["no_br_trace"])

    def test_run_cr_impact_without_open_fails(self):
        repo = make_test_repo(self.P)
        save_test_repo(repo)
        result = mod54.run_cr_impact(self.P, "CR-GHOST")
        self.assertIn("❌", result)

    def test_run_cr_impact_wrong_type_fails(self):
        """_find_node существует, но это не CR."""
        repo = make_test_repo(self.P)
        save_test_repo(repo)
        result = mod54.run_cr_impact(self.P, "FR-001")
        self.assertIn("❌", result)


# ---------------------------------------------------------------------------
# Интеграционные тесты — score_cr
# ---------------------------------------------------------------------------

class TestScoreCR(BaseMCPTest):

    P = "proj_54_score"

    def _setup_open_impact(self, cr_id="CR-001", target='["FR-001"]', regulatory=False):
        repo = make_test_repo(self.P)
        save_test_repo(repo)
        mod54.open_cr(
            project_name=self.P,
            cr_id=cr_id,
            title="Test CR",
            description="desc",
            initiator="PO",
            cr_type="change_existing",
            formality="standard",
            target_req_ids_json=target,
            regulatory=regulatory,
        )
        mod54.run_cr_impact(self.P, cr_id)

    def test_score_cr_success(self):
        self._setup_open_impact()
        result = mod54.score_cr(self.P, "CR-001", "High", "Low", "High")
        self.assertIn("CR Score", result)

    def test_score_cr_stores_score_data(self):
        self._setup_open_impact()
        mod54.score_cr(self.P, "CR-001", "High", "Low", "Critical")
        repo = load_test_repo(self.P)
        cr = mod54._find_node(repo, "CR-001")
        self.assertIsNotNone(cr.get("score"))
        self.assertIn("total_score", cr["score"])
        self.assertIn("formula_verdict", cr["score"])

    def test_score_cr_approve_verdict(self):
        self._setup_open_impact()
        result = mod54.score_cr(self.P, "CR-001", "High", "Low", "Critical")
        self.assertIn("Approve", result)

    def test_score_cr_reject_verdict(self):
        self._setup_open_impact(target='["FR-002"]')  # изолированный → Impact Low
        result = mod54.score_cr(self.P, "CR-001", "Low", "High", "Normal")
        self.assertIn("Reject", result)

    def test_score_cr_regulatory_cant_reject(self):
        """Регуляторный CR с низким скором должен стать Defer, не Reject."""
        self._setup_open_impact(target='["FR-002"]', regulatory=True)
        result = mod54.score_cr(self.P, "CR-001", "Low", "High", "Normal")
        self.assertNotIn("❌ Reject", result)
        self.assertIn("Defer", result)

    def test_score_cr_ba_notes_included(self):
        self._setup_open_impact()
        result = mod54.score_cr(self.P, "CR-001", "Medium", "Medium", "High",
                                ba_notes="Стратегически важно для Q3")
        self.assertIn("Стратегически важно для Q3", result)

    def test_score_cr_without_impact_fails(self):
        repo = make_test_repo(self.P)
        save_test_repo(repo)
        mod54.open_cr(
            project_name=self.P,
            cr_id="CR-NOIMPA",
            title="T",
            description="d",
            initiator="PO",
            cr_type="new_requirement",
            formality="standard",
            target_req_ids_json='["FR-001"]',
        )
        # Намеренно не вызываем run_cr_impact
        result = mod54.score_cr(self.P, "CR-NOIMPA", "High", "Low", "High")
        self.assertIn("❌", result)

    def test_score_cr_urgency_override(self):
        """urgency можно переопределить в score_cr."""
        self._setup_open_impact()
        mod54.score_cr(self.P, "CR-001", "High", "Low", "Critical")
        repo = load_test_repo(self.P)
        cr = mod54._find_node(repo, "CR-001")
        self.assertEqual(cr["urgency"], "Critical")


# ---------------------------------------------------------------------------
# Интеграционные тесты — resolve_cr
# ---------------------------------------------------------------------------

class TestResolveCR(BaseMCPTest):

    P = "proj_54_resolve"

    def _setup_full_pipeline(self, cr_id="CR-001", target='["FR-001"]',
                              benefit="High", cost="Low", urgency="High",
                              regulatory=False):
        repo = make_test_repo(self.P)
        save_test_repo(repo)
        mod54.open_cr(
            project_name=self.P,
            cr_id=cr_id,
            title="Test CR",
            description="desc",
            initiator="PO",
            cr_type="change_existing",
            formality="standard",
            target_req_ids_json=target,
            regulatory=regulatory,
        )
        mod54.run_cr_impact(self.P, cr_id)
        mod54.score_cr(self.P, cr_id, benefit, cost, urgency)

    def test_resolve_approved_changes_status(self):
        self._setup_full_pipeline()
        mod54.resolve_cr(
            self.P, "CR-001", "Approved",
            decided_by="Sponsor", rationale="Высокая ценность"
        )
        repo = load_test_repo(self.P)
        # FR-001 и затронутые должны быть under_change
        fr = mod54._find_node(repo, "FR-001")
        self.assertEqual(fr["status"], "under_change")

    def test_resolve_approved_cr_status_updated(self):
        self._setup_full_pipeline()
        mod54.resolve_cr(
            self.P, "CR-001", "Approved",
            decided_by="Sponsor", rationale="OK"
        )
        repo = load_test_repo(self.P)
        cr = mod54._find_node(repo, "CR-001")
        self.assertIn("approved", cr["status"])

    def test_resolve_rejected_no_req_changes(self):
        self._setup_full_pipeline()
        mod54.resolve_cr(
            self.P, "CR-001", "Rejected",
            decided_by="Sponsor", rationale="Не обосновано"
        )
        repo = load_test_repo(self.P)
        fr = mod54._find_node(repo, "FR-001")
        self.assertNotEqual(fr["status"], "under_change")

    def test_resolve_deferred_no_req_changes(self):
        self._setup_full_pipeline()
        mod54.resolve_cr(
            self.P, "CR-001", "Deferred",
            decided_by="PO", rationale="Следующий спринт"
        )
        repo = load_test_repo(self.P)
        fr = mod54._find_node(repo, "FR-001")
        self.assertNotEqual(fr["status"], "under_change")

    def test_resolve_approved_with_modification(self):
        self._setup_full_pipeline()
        result = mod54.resolve_cr(
            self.P, "CR-001", "Approved_with_Modification",
            decided_by="Sponsor", rationale="Частично",
            modification_notes="Только экспорт в PDF, без Excel"
        )
        self.assertIn("Modification", result)
        repo = load_test_repo(self.P)
        cr = mod54._find_node(repo, "CR-001")
        self.assertIn("approved", cr["status"])

    def test_resolve_regulatory_cr_cannot_reject(self):
        self._setup_full_pipeline(benefit="Low", cost="High", urgency="Normal",
                                  regulatory=True)
        result = mod54.resolve_cr(
            self.P, "CR-001", "Rejected",
            decided_by="Sponsor", rationale="Дорого"
        )
        self.assertIn("❌", result)
        self.assertIn("регуляторный", result.lower())

    def test_resolve_without_score_fails(self):
        repo = make_test_repo(self.P)
        save_test_repo(repo)
        mod54.open_cr(
            project_name=self.P,
            cr_id="CR-NOSCORE",
            title="T",
            description="d",
            initiator="PO",
            cr_type="new_requirement",
            formality="standard",
            target_req_ids_json='["FR-001"]',
        )
        mod54.run_cr_impact(self.P, "CR-NOSCORE")
        # Намеренно пропускаем score_cr
        result = mod54.resolve_cr(
            self.P, "CR-NOSCORE", "Approved",
            decided_by="Sponsor", rationale="OK"
        )
        self.assertIn("❌", result)

    def test_resolve_saves_decision_data(self):
        self._setup_full_pipeline()
        mod54.resolve_cr(
            self.P, "CR-001", "Approved",
            decided_by="Sponsor", rationale="Ценность высокая"
        )
        repo = load_test_repo(self.P)
        cr = mod54._find_node(repo, "CR-001")
        decision = cr.get("decision", {})
        self.assertEqual(decision.get("verdict"), "Approved")
        self.assertEqual(decision.get("decided_by"), "Sponsor")
        self.assertIn("Ценность", decision.get("rationale", ""))

    def test_resolve_history_recorded(self):
        self._setup_full_pipeline()
        mod54.resolve_cr(
            self.P, "CR-001", "Approved",
            decided_by="Sponsor", rationale="OK"
        )
        repo = load_test_repo(self.P)
        self.assertTrue(any(
            h.get("action") == "cr_resolved" and h.get("cr_id") == "CR-001"
            for h in repo.get("history", [])
        ))

    def test_resolve_generates_artifact(self):
        self._setup_full_pipeline()
        result = mod54.resolve_cr(
            self.P, "CR-001", "Approved",
            decided_by="Sponsor", rationale="OK"
        )
        # save_artifact мокирован в conftest — проверяем что он вызван (результат присутствует)
        self.assertIn("Сохранено", result)

    def test_resolve_unknown_cr_fails(self):
        repo = make_test_repo(self.P)
        save_test_repo(repo)
        result = mod54.resolve_cr(
            self.P, "CR-GHOST", "Approved",
            decided_by="Sponsor", rationale="OK"
        )
        self.assertIn("❌", result)


# ---------------------------------------------------------------------------
# Интеграционный pipeline — полный happy path
# ---------------------------------------------------------------------------

class TestFullPipeline(BaseMCPTest):

    P = "proj_54_pipeline"

    def _init_repo(self):
        repo = make_test_repo(self.P)
        save_test_repo(repo)

    def test_full_pipeline_approved(self):
        """open → impact → score → resolve(Approved): полный цикл без ошибок."""
        self._init_repo()

        r1 = mod54.open_cr(
            project_name=self.P,
            cr_id="CR-001",
            title="Экспорт в PDF",
            description="Пользователи запрашивают PDF-экспорт отчётов",
            initiator="Product Owner",
            cr_type="new_requirement",
            formality="standard",
            target_req_ids_json='["FR-001"]',
            urgency="High",
        )
        self.assertNotIn("❌", r1)

        r2 = mod54.run_cr_impact(self.P, "CR-001")
        self.assertNotIn("❌", r2)

        r3 = mod54.score_cr(self.P, "CR-001", "High", "Low", "High")
        self.assertNotIn("❌", r3)

        r4 = mod54.resolve_cr(
            self.P, "CR-001", "Approved",
            decided_by="Sponsor",
            rationale="CR полностью обоснован, ценность подтверждена"
        )
        self.assertNotIn("❌", r4)

        # Финальная проверка состояния репозитория
        repo = load_test_repo(self.P)
        cr = mod54._find_node(repo, "CR-001")
        self.assertIn("approved", cr["status"])

        # modifies-связь создана
        modifies = [l for l in repo["links"]
                    if l["from"] == "CR-001" and l["relation"] == "modifies"]
        self.assertEqual(len(modifies), 1)

        # Затронутые требования под_изменением
        fr = mod54._find_node(repo, "FR-001")
        self.assertEqual(fr["status"], "under_change")

    def test_full_pipeline_rejected(self):
        """open → impact → score → resolve(Rejected): требования не трогаются."""
        self._init_repo()

        mod54.open_cr(
            project_name=self.P,
            cr_id="CR-REJ",
            title="Низкоприоритетный CR",
            description="Косметическое изменение",
            initiator="User",
            cr_type="change_existing",
            formality="standard",
            target_req_ids_json='["FR-002"]',
            urgency="Normal",
        )
        mod54.run_cr_impact(self.P, "CR-REJ")
        mod54.score_cr(self.P, "CR-REJ", "Low", "High", "Normal")
        mod54.resolve_cr(
            self.P, "CR-REJ", "Rejected",
            decided_by="PO",
            rationale="Не обосновано бизнес-ценностью"
        )

        repo = load_test_repo(self.P)
        cr = mod54._find_node(repo, "CR-REJ")
        self.assertIn("rejected", cr["status"])

        fr2 = mod54._find_node(repo, "FR-002")
        self.assertNotEqual(fr2["status"], "under_change")

    def test_multiple_cr_independent(self):
        """Два CR в одном проекте не мешают друг другу."""
        self._init_repo()

        for cr_id, target in [("CR-A", '["FR-001"]'), ("CR-B", '["FR-002"]')]:
            mod54.open_cr(
                project_name=self.P,
                cr_id=cr_id,
                title=f"CR {cr_id}",
                description="d",
                initiator="PO",
                cr_type="change_existing",
                formality="standard",
                target_req_ids_json=target,
            )
            mod54.run_cr_impact(self.P, cr_id)
            mod54.score_cr(self.P, cr_id, "Medium", "Medium", "Normal")

        repo = load_test_repo(self.P)
        cr_a = mod54._find_node(repo, "CR-A")
        cr_b = mod54._find_node(repo, "CR-B")
        self.assertIsNotNone(cr_a)
        self.assertIsNotNone(cr_b)
        self.assertIsNotNone(cr_a.get("score"))
        self.assertIsNotNone(cr_b.get("score"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
