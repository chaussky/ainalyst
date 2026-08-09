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
import re
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

    def test_repo_path_is_under_the_project_folder(self):
        path = mod54._repo_path("my_project")
        self.assertIn(os.path.join("my_project", "my_project_traceability_repo.json"), path)

    def test_a_spelling_that_would_be_rewritten_gets_no_path(self):
        import skills.common as common_mod
        with self.assertRaises(common_mod.InvalidProjectIdError):
            mod54._repo_path("CRM 2024")

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

    def test_the_headline_count_matches_the_list_below_it(self):
        """V-2 — a direct hit on "a number that does not match the list under it".
        The count included the CR's own targets, while the breakdown grouped by link
        type, and a target has no link to itself, so it appeared in neither group."""
        self._setup_and_open()
        result = mod54.run_cr_impact(self.P, "CR-001")

        headline = int(re.search(r"\*\*Total nodes affected:\*\* (\d+)", result).group(1))
        breakdown = result.split("### Affected nodes by link type")[1].split("\n---")[0]
        listed = len([ln for ln in breakdown.split("\n") if ln.strip().startswith("- `")])
        self.assertEqual(headline, listed,
                         f"headline says {headline}, the breakdown lists {listed}")

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


class TestScheduleRiskDirection(BaseMCPTest):
    """Regression: a HIGH schedule risk must LOWER a CR's score, not raise it.

    run_cr_impact stored schedule_score inverted (High risk -> 1, Low risk -> 3)
    while _calc_score subtracts schedule_risk as a penalty proportional to risk.
    The net effect ranked risky CRs above safe ones."""

    P = "proj_54_sched"

    def _score_with_phase(self, cr_id, phase):
        # Both CRs target the isolated FR-002 (no links) so Impact is identical;
        # only the project phase changes the schedule risk.
        mod54.open_cr(
            project_name=self.P, cr_id=cr_id, title="T", description="d",
            initiator="PO", cr_type="change_existing", formality="standard",
            target_req_ids_json='["FR-002"]', project_phase=phase,
        )
        mod54.run_cr_impact(self.P, cr_id)
        mod54.score_cr(self.P, cr_id, "Medium", "Medium", "Normal")
        repo = load_test_repo(self.P)
        return mod54._find_node(repo, cr_id)["score"]["total_score"]

    def test_high_schedule_risk_scores_lower_than_low(self):
        save_test_repo(make_test_repo(self.P))
        score_high = self._score_with_phase("CR-HIGH", "pre_release")   # High schedule risk
        score_low = self._score_with_phase("CR-LOW", "development")     # Low schedule risk
        self.assertLess(
            score_high, score_low,
            "A CR with HIGH schedule risk must score lower than an identical CR with LOW risk",
        )


class TestBrPathKnowsRealGoalTypes(BaseMCPTest):
    """The upward walk answering 'does this requirement trace to business?' was wrong
    on TWO axes: it terminated only on the legacy node type `business`, and it followed
    only `derives`. Real roots are `business_goal` (6.2) and `business_need` (6.1), and
    7.1 links requirements to objectives with `satisfies` (ADR-082).

    Same class as findings 7.3-A and 7.4-B; missed here because that audit pass checked
    the DIRECTION of derives (correct) and never the type set.
    """

    P = "br_path_types"

    def _save(self, nodes, links):
        repo = make_test_repo(self.P)
        repo["requirements"] = nodes
        repo["links"] = links
        save_test_repo(repo)

    def _fr(self):
        return {"id": "FR-500", "type": "functional", "title": "Auto-assign",
                "version": "1.0", "status": "draft", "added": str(date.today()),
                "source_artifact": ""}

    def _goal(self, node_type):
        return {"id": "BG-001", "type": node_type, "title": "Cut handling time",
                "version": "1.0", "status": "confirmed", "added": str(date.today()),
                "source_artifact": ""}

    def _run_impact(self):
        mod54.open_cr(
            project_name=self.P, cr_id="CR-900",
            title="Change the assignment rule",
            description="Operations asked for a different routing rule",
            initiator="Ops Lead", cr_type="change_existing", formality="standard",
            target_req_ids_json='["FR-500"]',
        )
        return mod54.run_cr_impact(project_name=self.P, cr_id="CR-900")

    def _untraced_line(self, result):
        """The rendered 'no traceability' line only — the id list is interpolated
        straight into it."""
        marker = "no traceability to a business requirement"
        low = result.lower()
        if marker not in low:
            return ""
        return low.split(marker, 1)[1].split("\n", 1)[0]

    def test_satisfies_to_business_goal_counts_as_traced(self):
        self._save(
            [self._goal("business_goal"), self._fr()],
            [{"from": "FR-500", "to": "BG-001", "relation": "satisfies",
              "created": str(date.today())}],
        )
        self.assertNotIn("fr-500", self._untraced_line(self._run_impact()))

    def test_derives_to_business_need_counts_as_traced(self):
        self._save(
            [self._goal("business_need"), self._fr()],
            [{"from": "FR-500", "to": "BG-001", "relation": "derives",
              "created": str(date.today())}],
        )
        self.assertNotIn("fr-500", self._untraced_line(self._run_impact()))

    def test_legacy_business_type_still_works(self):
        """The pre-existing behaviour must survive the widening."""
        self._save(
            [self._goal("business"), self._fr()],
            [{"from": "FR-500", "to": "BG-001", "relation": "derives",
              "created": str(date.today())}],
        )
        self.assertNotIn("fr-500", self._untraced_line(self._run_impact()))

    def test_unlinked_requirement_is_still_reported(self):
        """The walk must not degenerate into 'everything is traced'."""
        self._save([self._fr()], [])
        self.assertIn("fr-500", self._untraced_line(self._run_impact()))

    def test_link_to_a_plain_requirement_is_not_a_business_trace(self):
        """Reaching another requirement is not reaching business."""
        self._save(
            [self._fr(),
             {"id": "FR-501", "type": "functional", "title": "Queue view",
              "version": "1.0", "status": "draft", "added": str(date.today()),
              "source_artifact": ""}],
            [{"from": "FR-500", "to": "FR-501", "relation": "derives",
              "created": str(date.today())}],
        )
        self.assertIn("fr-500", self._untraced_line(self._run_impact()))


# ---------------------------------------------------------------------------
# The objective-hub inflation and the status clobber (full-pipeline audit,
# claimflow run: a CR targeting ONE requirement reported "20 affected" and
# Approved flattened every node in the graph to `under_change`)
# ---------------------------------------------------------------------------

def _hub_repo(project: str) -> dict:
    """BG-001 is a hub: three requirements satisfy it, a risk threatens it, and it
    derives from BN-001 — the shape 7.1 + 6.x produce on every real project."""
    today = str(date.today())
    return {
        "project": project,
        "formality_level": "Standard",
        "created": today,
        "updated": today,
        "requirements": [
            {"id": "FR-A", "type": "functional", "title": "Auto-triage",
             "version": "1.0", "status": "draft", "added": today},
            {"id": "FR-B", "type": "functional", "title": "Fraud scoring",
             "version": "1.0", "status": "draft", "added": today},
            {"id": "FR-C", "type": "functional", "title": "Doc extraction",
             "version": "1.0", "status": "draft", "added": today},
            {"id": "BG-001", "type": "business_goal", "title": "Settle in 10 days",
             "version": "1.0", "status": "confirmed", "added": today},
            {"id": "BN-001", "type": "business_need", "title": "Meet the deadline",
             "version": "1.0", "status": "confirmed", "added": today},
            {"id": "RK-001", "type": "risk", "title": "Model bias",
             "version": "1.0", "status": "identified", "added": today},
        ],
        "links": [
            {"from": "FR-A", "to": "BG-001", "relation": "satisfies", "added": today},
            {"from": "FR-B", "to": "BG-001", "relation": "satisfies", "added": today},
            {"from": "FR-C", "to": "BG-001", "relation": "satisfies", "added": today},
            {"from": "BG-001", "to": "BN-001", "relation": "derives", "added": today},
            {"from": "RK-001", "to": "BG-001", "relation": "threatens", "added": today},
        ],
        "history": [],
    }


class TestBfsImpactStopsAtBusinessNodes(unittest.TestCase):
    """5.1's hub fix (Part 2d) explicitly says the inflation 'fed 5.4's Impact and
    Schedule Risk scores' — but 5.4 has its own `_bfs_impact`, which kept expanding
    THROUGH the objective back down to every sibling. The better the analyst's
    traceability, the higher the artificial CR impact."""

    def test_siblings_via_objective_hub_are_not_affected(self):
        affected = mod54._bfs_impact(_hub_repo("hub"), ["FR-A"])
        ids = {a["id"] for a in affected}
        self.assertIn("BG-001", ids, "the objective itself IS affected")
        self.assertNotIn("FR-B", ids, "a sibling sharing the objective is not")
        self.assertNotIn("FR-C", ids)
        self.assertNotIn("RK-001", ids, "a risk hanging off the objective is not")
        self.assertNotIn("BN-001", ids, "nothing beyond the first business node")


class TestResolveCrLeavesOtherChaptersStatuses(BaseMCPTest):
    """`resolve_cr` (Approved) stamped `under_change` on every affected node —
    `status` is one field written by four chapters, so 5.4 erased 6.2's `confirmed`
    on goals, 6.3's `identified` on risks and 6.4's `defined` on the scope node.
    Only requirement-role nodes take the requirements-lifecycle status."""

    P = "cr_roles"

    def _setup(self, extra_links=None):
        repo = make_test_repo(self.P)
        today = str(date.today())
        repo["requirements"] += [
            {"id": "BG-001", "type": "business_goal", "title": "Settle in 10 days",
             "version": "1.0", "status": "confirmed", "added": today},
            {"id": "BN-001", "type": "business_need", "title": "Meet the deadline",
             "version": "1.0", "status": "confirmed", "added": today},
            {"id": "RK-001", "type": "risk", "title": "Model bias",
             "version": "1.0", "status": "identified", "added": today},
            {"id": "SOL-001", "type": "solution_scope", "title": "Solution Scope — cr_roles",
             "version": "1.0", "status": "defined", "added": today},
        ]
        repo["links"] += [
            {"from": "FR-001", "to": "BG-001", "relation": "satisfies", "added": today},
            {"from": "BG-001", "to": "BN-001", "relation": "derives", "added": today},
            {"from": "RK-001", "to": "BG-001", "relation": "threatens", "added": today},
            # a mitigation dependency pulls the risk into the BFS directly
            {"from": "FR-001", "to": "RK-001", "relation": "depends", "added": today},
        ] + (extra_links or [])
        save_test_repo(repo)

    def _open_impact_score(self, cr_id="CR-900", targets='["FR-001"]'):
        mod54.open_cr(
            self.P, cr_id=cr_id, title="Probe CR",
            description="Probe", initiator="BA",
            cr_type="change_existing", formality="standard",
            target_req_ids_json=targets,
        )
        mod54.run_cr_impact(self.P, cr_id=cr_id)
        mod54.score_cr(self.P, cr_id=cr_id, benefit="High", cost="Low")

    def test_approved_cr_does_not_clobber_other_chapters_statuses(self):
        self._setup()
        self._open_impact_score()
        mod54.resolve_cr(self.P, cr_id="CR-900", decision="Approved",
                         decided_by="Sponsor", rationale="probe")
        by_id = {r["id"]: r for r in load_test_repo(self.P)["requirements"]}
        self.assertEqual(by_id["FR-001"]["status"], "under_change",
                         "the target requirement itself IS under change")
        self.assertEqual(by_id["BG-001"]["status"], "confirmed",
                         "6.2 owns the goal's status")
        self.assertEqual(by_id["BN-001"]["status"], "confirmed")
        self.assertEqual(by_id["RK-001"]["status"], "identified",
                         "6.3 owns the risk's status")
        self.assertEqual(by_id["SOL-001"]["status"], "defined",
                         "6.4 owns the scope node's status")
        self.assertEqual(by_id["TC-001"]["status"], "draft",
                         "a test node does not enter the requirements lifecycle")
        self.assertEqual(by_id["BR-001"]["status"], "confirmed",
                         "a business node reached as BFS collateral is not clobbered")

    def test_explicit_business_class_target_still_marked(self):
        """A legacy business-CLASS requirement the analyst NAMED as the CR target is
        their intent — the role filter must not silence it (the `business` literal
        is both the legacy root type and the BABOK requirement class)."""
        self._setup()
        self._open_impact_score(cr_id="CR-901", targets='["BR-001"]')
        mod54.resolve_cr(self.P, cr_id="CR-901", decision="Approved",
                         decided_by="Sponsor", rationale="probe")
        by_id = {r["id"]: r for r in load_test_repo(self.P)["requirements"]}
        self.assertEqual(by_id["BR-001"]["status"], "under_change")


if __name__ == "__main__":
    unittest.main(verbosity=2)
