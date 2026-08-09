"""
tests/test_ch5_55.py — Тесты для BABOK 5.5 Approve Requirements.

Структура:
  - Unit (14): утилиты, _compute_req_status, _get_cr_context
  - prepare_approval_package (8): успех, дубликат, missing req, agile, audiences
  - record_approval_decision (14): approved, conditional, rejected, RACI-анализ, конфликты
  - close_approval_condition (7): успех, уже закрыто, не найдено, статус обновлён
  - check_approval_status (10): дашборд, блокеры, open conditions, вердикты
  - create_requirements_baseline (11): успех, блокеры, force, snapshot, история
  - Pipeline (6): полный predictive, полный agile, конфликт + разрешение, два пакета независимы
"""

import json
import os
import sys
import unittest
from datetime import date, timedelta
from unittest.mock import patch

# conftest регистрирует моки и предоставляет базовый класс
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests.conftest import (
    setup_mocks, BaseMCPTest, make_test_repo, save_test_repo, load_test_repo,
)

setup_mocks()

from skills.requirements_approve_mcp import (
    prepare_approval_package,
    record_approval_decision,
    close_approval_condition,
    check_approval_status,
    create_requirements_baseline,
    _compute_req_status,
    _verification_state,
    _get_cr_context,
    _load_approval_history,
    _save_approval_history,
    STATUS_APPROVED,
    STATUS_CONDITIONAL,
    STATUS_REJECTED,
    STATUS_PENDING,
)


# ---------------------------------------------------------------------------
# Вспомогательные утилиты для тестов
# ---------------------------------------------------------------------------

PROJECT = "test_project"


def _make_repo_with_verified(tmp_dir):
    """Репозиторий с verified требованиями (готовы к 5.5)."""
    repo = make_test_repo(PROJECT)
    for req in repo["requirements"]:
        if req["type"] != "test":
            req["status"] = "verified"
            req["priority"] = "Must"
    save_test_repo(repo)
    return repo


def _make_repo_with_cr(tmp_dir):
    """Репозиторий с CR, затрагивающим FR-001."""
    repo = _make_repo_with_verified(tmp_dir)
    repo["requirements"].append({
        "id": "CR-001",
        "type": "change_request",
        "title": "Изменить логику распределения",
        "status": "open",
        "target_req_ids": ["FR-001"],
    })
    repo["links"].append({
        "from": "CR-001",
        "to": "FR-001",
        "relation": "modifies",
        "added_date": str(date.today()),
    })
    save_test_repo(repo)
    return repo


def _open_package(project=PROJECT, package_id="APKG-001", req_ids=None, approach="predictive"):
    """Создаёт пакет и возвращает результат prepare_approval_package."""
    if req_ids is None:
        req_ids = ["FR-001", "FR-002"]
    return prepare_approval_package(
        project_name=project,
        package_id=package_id,
        package_title="Тестовый пакет",
        req_ids_json=json.dumps(req_ids),
        approach=approach,
    )


def _record(project=PROJECT, package_id="APKG-001", stakeholder="Иванов",
            raci="accountable", decision="approved", req_decisions=None,
            rejection_reason=""):
    """Вспомогательная обёртка для record_approval_decision."""
    rdj = json.dumps(req_decisions) if req_decisions else "[]"
    return record_approval_decision(
        project_name=project,
        package_id=package_id,
        stakeholder_name=stakeholder,
        stakeholder_raci=raci,
        decision=decision,
        req_decisions_json=rdj,
        rejection_reason=rejection_reason,
    )


# ---------------------------------------------------------------------------
# Unit — утилиты
# ---------------------------------------------------------------------------

class TestComputeReqStatus(BaseMCPTest):

    def _make_pkg(self, req_ids=None):
        return {
            "req_ids": req_ids or ["FR-001"],
            "stakeholder_decisions": {},
        }

    def test_no_decisions_returns_pending(self):
        pkg = self._make_pkg()
        self.assertEqual(_compute_req_status("FR-001", pkg), STATUS_PENDING)

    def test_approved_by_accountable(self):
        pkg = self._make_pkg()
        pkg["stakeholder_decisions"]["Иванов"] = {
            "raci": "accountable",
            "req_decisions": [{"req_id": "FR-001", "decision": "approved"}],
        }
        self.assertEqual(_compute_req_status("FR-001", pkg), STATUS_APPROVED)

    def test_rejected_by_accountable_blocks(self):
        pkg = self._make_pkg()
        pkg["stakeholder_decisions"]["Иванов"] = {
            "raci": "accountable",
            "req_decisions": [{"req_id": "FR-001", "decision": "rejected"}],
        }
        self.assertEqual(_compute_req_status("FR-001", pkg), STATUS_REJECTED)

    def test_rejected_by_consulted_does_not_block(self):
        pkg = self._make_pkg()
        pkg["stakeholder_decisions"]["Петров"] = {
            "raci": "accountable",
            "req_decisions": [{"req_id": "FR-001", "decision": "approved"}],
        }
        pkg["stakeholder_decisions"]["Сидоров"] = {
            "raci": "consulted",
            "req_decisions": [{"req_id": "FR-001", "decision": "rejected"}],
        }
        # Consulted rejected, но Accountable approved → approved
        self.assertEqual(_compute_req_status("FR-001", pkg), STATUS_APPROVED)

    def test_open_conditional_by_accountable_gives_conditional_approved(self):
        pkg = self._make_pkg()
        pkg["stakeholder_decisions"]["Иванов"] = {
            "raci": "accountable",
            "req_decisions": [{
                "req_id": "FR-001",
                "decision": "conditional",
                "condition_text": "Уточнить формулировку",
                "condition_closed": False,
            }],
        }
        self.assertEqual(_compute_req_status("FR-001", pkg), STATUS_CONDITIONAL)

    def test_closed_conditional_gives_approved(self):
        pkg = self._make_pkg()
        pkg["stakeholder_decisions"]["Иванов"] = {
            "raci": "accountable",
            "req_decisions": [{
                "req_id": "FR-001",
                "decision": "conditional",
                "condition_text": "Уточнить формулировку",
                "condition_closed": True,
            }],
        }
        self.assertEqual(_compute_req_status("FR-001", pkg), STATUS_APPROVED)

    def test_all_abstained_is_not_approval(self):
        """Audit finding: this test previously asserted the opposite — a lone
        accountable stakeholder abstaining produced `approved`, so a package where
        EVERY accountable party declined to take a position reached 100% approved
        and baselined cleanly: an official approval record with no approver.
        Abstention is a first-class decision meaning "no position"; it must not
        carry the requirement on its own."""
        pkg = self._make_pkg()
        pkg["stakeholder_decisions"]["Иванов"] = {
            "raci": "accountable",
            "req_decisions": [{"req_id": "FR-001", "decision": "abstained"}],
        }
        self.assertEqual(_compute_req_status("FR-001", pkg), STATUS_PENDING)

    def test_abstention_alongside_an_approval_still_approves(self):
        """Abstention does not BLOCK — it just does not count as a yes."""
        pkg = self._make_pkg()
        pkg["stakeholder_decisions"]["Иванов"] = {
            "raci": "accountable",
            "req_decisions": [{"req_id": "FR-001", "decision": "approved"}],
        }
        pkg["stakeholder_decisions"]["Petrov"] = {
            "raci": "responsible",
            "req_decisions": [{"req_id": "FR-001", "decision": "abstained"}],
        }
        self.assertEqual(_compute_req_status("FR-001", pkg), STATUS_APPROVED)

    def test_all_abstained_blocks_the_baseline_gate(self):
        """The consequence that matters: no approver → not ready for baseline."""
        from skills.requirements_approve_mcp import _baseline_gate
        pkg = self._make_pkg()
        pkg["stakeholder_decisions"]["Иванов"] = {
            "raci": "accountable",
            "req_decisions": [{"req_id": "FR-001", "decision": "abstained"}],
        }
        gate = _baseline_gate(pkg)
        self.assertFalse(gate["can_baseline"])
        self.assertEqual(gate["approved_pct"], 0)

    def test_req_not_in_decisions_gives_pending(self):
        pkg = self._make_pkg(["FR-001", "FR-002"])
        pkg["stakeholder_decisions"]["Иванов"] = {
            "raci": "accountable",
            "req_decisions": [{"req_id": "FR-001", "decision": "approved"}],
        }
        # FR-002 не упомянуто → pending
        self.assertEqual(_compute_req_status("FR-002", pkg), STATUS_PENDING)


class TestGetCrContext(BaseMCPTest):

    def test_returns_cr_refs(self):
        repo = make_test_repo(PROJECT)
        repo["requirements"].append({
            "id": "CR-001", "type": "change_request",
            "title": "CR Title", "status": "open",
        })
        repo["links"].append({
            "from": "CR-001", "to": "FR-001",
            "relation": "modifies",
        })
        save_test_repo(repo)
        from skills.requirements_approve_mcp import _load_repo
        loaded = _load_repo(PROJECT)
        refs = _get_cr_context(loaded, "FR-001")
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0]["cr_id"], "CR-001")

    def test_returns_empty_when_no_cr(self):
        repo = make_test_repo(PROJECT)
        save_test_repo(repo)
        from skills.requirements_approve_mcp import _load_repo
        loaded = _load_repo(PROJECT)
        refs = _get_cr_context(loaded, "FR-001")
        self.assertEqual(refs, [])

    def test_ignores_non_modifies_links(self):
        repo = make_test_repo(PROJECT)
        save_test_repo(repo)
        from skills.requirements_approve_mcp import _load_repo
        loaded = _load_repo(PROJECT)
        # verifies-связь не должна возвращаться как CR
        refs = _get_cr_context(loaded, "FR-001")
        self.assertFalse(any(r for r in refs if r.get("cr_id") == "TC-001"))


# ---------------------------------------------------------------------------
# prepare_approval_package
# ---------------------------------------------------------------------------

class TestPrepareApprovalPackage(BaseMCPTest):

    def setUp(self):
        super().setUp()
        _make_repo_with_verified(self.tmp_dir)

    def test_success_creates_package(self):
        result = _open_package()
        self.assertIn("APKG-001", result)
        self.assertIn("Тестовый пакет", result)
        history = _load_approval_history(PROJECT)
        self.assertIn("APKG-001", history["packages"])

    def test_sets_requirements_to_pending(self):
        _open_package()
        from skills.requirements_approve_mcp import _load_repo
        repo = _load_repo(PROJECT)
        fr001 = next(r for r in repo["requirements"] if r["id"] == "FR-001")
        self.assertEqual(fr001["status"], STATUS_PENDING)

    def test_duplicate_package_id_заблокирован(self):
        _open_package()
        result = _open_package()
        self.assertIn("уже существует", result)

    def test_missing_requirements_error(self):
        result = prepare_approval_package(
            project_name=PROJECT,
            package_id="APKG-X",
            package_title="Тест",
            req_ids_json='["FR-999"]',
            approach="predictive",
        )
        self.assertIn("не найдены", result)

    def test_invalid_json_error(self):
        result = prepare_approval_package(
            project_name=PROJECT,
            package_id="APKG-X",
            package_title="Тест",
            req_ids_json="not-json",
            approach="predictive",
        )
        self.assertIn("❌", result)

    def test_empty_req_ids_error(self):
        result = prepare_approval_package(
            project_name=PROJECT,
            package_id="APKG-X",
            package_title="Тест",
            req_ids_json="[]",
            approach="predictive",
        )
        self.assertIn("❌", result)

    def test_agile_includes_sprint_info(self):
        result = prepare_approval_package(
            project_name=PROJECT,
            package_id="APKG-AGILE",
            package_title="Sprint 5",
            req_ids_json='["FR-001"]',
            approach="agile",
            sprint_number="5",
        )
        self.assertIn("5", result)
        self.assertIn("Agile", result)

    def test_cr_warning_shown_when_open_cr(self):
        _make_repo_with_cr(self.tmp_dir)
        result = prepare_approval_package(
            project_name=PROJECT,
            package_id="APKG-CR",
            package_title="Пакет с CR",
            req_ids_json='["FR-001"]',
            approach="predictive",
        )
        self.assertIn("CR-001", result)


# ---------------------------------------------------------------------------
# record_approval_decision
# ---------------------------------------------------------------------------

class TestRecordApprovalDecision(BaseMCPTest):

    def setUp(self):
        super().setUp()
        _make_repo_with_verified(self.tmp_dir)
        _open_package()

    def test_approved_all_requirements(self):
        result = _record(decision="approved")
        self.assertIn("✅", result)
        self.assertIn("Иванов", result)

    def test_approved_updates_repo_status(self):
        _record(decision="approved")
        from skills.requirements_approve_mcp import _load_repo
        repo = _load_repo(PROJECT)
        fr001 = next(r for r in repo["requirements"] if r["id"] == "FR-001")
        self.assertEqual(fr001["status"], STATUS_APPROVED)

    def test_conditional_requires_condition_text(self):
        result = record_approval_decision(
            project_name=PROJECT,
            package_id="APKG-001",
            stakeholder_name="Иванов",
            stakeholder_raci="accountable",
            decision="conditional",
            req_decisions_json=json.dumps([
                {"req_id": "FR-001", "decision": "conditional"}
                # нет condition_text
            ]),
        )
        self.assertIn("❌", result)

    def test_conditional_with_condition_text_ok(self):
        result = record_approval_decision(
            project_name=PROJECT,
            package_id="APKG-001",
            stakeholder_name="Иванов",
            stakeholder_raci="accountable",
            decision="conditional",
            req_decisions_json=json.dumps([
                {
                    "req_id": "FR-001",
                    "decision": "conditional",
                    "condition_text": "Уточнить критерий",
                    "condition_deadline": "2026-05-01",
                    "condition_owner": "Петров",
                }
            ]),
        )
        self.assertIn("Уточнить критерий", result)

    def test_rejected_requires_reason_when_no_req_decisions(self):
        result = _record(decision="rejected", rejection_reason="")
        self.assertIn("❌", result)

    def test_rejected_with_reason_ok(self):
        result = _record(decision="rejected", rejection_reason="За пределами скоупа")
        self.assertIn("❌", result)
        self.assertIn("За пределами скоупа", result)

    def test_abstained_is_recorded(self):
        result = _record(decision="abstained")
        self.assertIn("abstained", result)

    def test_consulted_rejected_shows_info(self):
        result = _record(
            decision="rejected",
            raci="consulted",
            rejection_reason="Не согласен с формулировкой",
        )
        self.assertIn("Consulted", result)

    def test_conflict_flagged_for_must_priority(self):
        # Требование с Must приоритетом отклонено — должен быть флаг
        result = _record(decision="rejected", rejection_reason="Не нужно")
        self.assertIn("Must", result)

    def test_conflict_flagged_for_open_cr(self):
        _make_repo_with_cr(self.tmp_dir)
        _open_package(package_id="APKG-CR", req_ids=["FR-001"])
        result = record_approval_decision(
            project_name=PROJECT,
            package_id="APKG-CR",
            stakeholder_name="Иванов",
            stakeholder_raci="accountable",
            decision="rejected",
            rejection_reason="Требование изменяется",
        )
        self.assertIn("CR-001", result)

    def test_partial_req_decisions_with_mixed_decisions(self):
        result = record_approval_decision(
            project_name=PROJECT,
            package_id="APKG-001",
            stakeholder_name="Иванов",
            stakeholder_raci="accountable",
            decision="approved",
            req_decisions_json=json.dumps([
                {"req_id": "FR-001", "decision": "approved"},
                {"req_id": "FR-002", "decision": "rejected", "rejection_reason": "Неясная формулировка"},
            ]),
        )
        self.assertIn("FR-001", result)
        self.assertIn("FR-002", result)

    def test_unknown_req_id_in_decisions_заблокирован(self):
        result = record_approval_decision(
            project_name=PROJECT,
            package_id="APKG-001",
            stakeholder_name="Иванов",
            stakeholder_raci="accountable",
            decision="approved",
            req_decisions_json=json.dumps([
                {"req_id": "FR-999", "decision": "approved"},
            ]),
        )
        self.assertIn("не входят", result)

    def test_package_not_found_error(self):
        result = _record(package_id="APKG-MISSING")
        self.assertIn("❌", result)

    def test_multiple_stakeholders_recorded(self):
        _record(stakeholder="Иванов", decision="approved")
        _record(stakeholder="Петров", raci="responsible", decision="approved")
        history = _load_approval_history(PROJECT)
        pkg = history["packages"]["APKG-001"]
        self.assertIn("Иванов", pkg["stakeholder_decisions"])
        self.assertIn("Петров", pkg["stakeholder_decisions"])


# ---------------------------------------------------------------------------
# close_approval_condition
# ---------------------------------------------------------------------------

class TestCloseApprovalCondition(BaseMCPTest):

    def setUp(self):
        super().setUp()
        _make_repo_with_verified(self.tmp_dir)
        _open_package()
        # Создаём conditional от Иванова на FR-001
        record_approval_decision(
            project_name=PROJECT,
            package_id="APKG-001",
            stakeholder_name="Иванов",
            stakeholder_raci="accountable",
            decision="conditional",
            req_decisions_json=json.dumps([
                {
                    "req_id": "FR-001",
                    "decision": "conditional",
                    "condition_text": "Уточнить критерий приёмки",
                    "condition_deadline": "2026-05-01",
                    "condition_owner": "Петров",
                },
                {"req_id": "FR-002", "decision": "approved"},
            ]),
        )

    def test_close_condition_success(self):
        result = close_approval_condition(
            project_name=PROJECT,
            package_id="APKG-001",
            req_id="FR-001",
            stakeholder_name="Иванов",
            resolution_notes="Критерий уточнён, добавлен acceptance test",
        )
        self.assertIn("✅", result)
        self.assertIn("FR-001", result)

    def test_condition_closed_updates_requirement_status(self):
        close_approval_condition(
            project_name=PROJECT,
            package_id="APKG-001",
            req_id="FR-001",
            stakeholder_name="Иванов",
            resolution_notes="Критерий уточнён",
        )
        from skills.requirements_approve_mcp import _load_repo
        repo = _load_repo(PROJECT)
        fr001 = next(r for r in repo["requirements"] if r["id"] == "FR-001")
        self.assertEqual(fr001["status"], STATUS_APPROVED)

    def test_close_already_closed_condition(self):
        close_approval_condition(
            project_name=PROJECT,
            package_id="APKG-001",
            req_id="FR-001",
            stakeholder_name="Иванов",
            resolution_notes="Первое закрытие",
        )
        result = close_approval_condition(
            project_name=PROJECT,
            package_id="APKG-001",
            req_id="FR-001",
            stakeholder_name="Иванов",
            resolution_notes="Второе закрытие",
        )
        self.assertIn("уже закрыто", result)

    def test_wrong_stakeholder_error(self):
        result = close_approval_condition(
            project_name=PROJECT,
            package_id="APKG-001",
            req_id="FR-001",
            stakeholder_name="НеСуществующий",
            resolution_notes="Закрываю",
        )
        self.assertIn("❌", result)

    def test_wrong_req_id_error(self):
        result = close_approval_condition(
            project_name=PROJECT,
            package_id="APKG-001",
            req_id="FR-999",
            stakeholder_name="Иванов",
            resolution_notes="Закрываю",
        )
        self.assertIn("❌", result)

    def test_package_not_found_error(self):
        result = close_approval_condition(
            project_name=PROJECT,
            package_id="APKG-MISSING",
            req_id="FR-001",
            stakeholder_name="Иванов",
            resolution_notes="Закрываю",
        )
        self.assertIn("❌", result)

    def test_condition_closed_flag_persisted(self):
        close_approval_condition(
            project_name=PROJECT,
            package_id="APKG-001",
            req_id="FR-001",
            stakeholder_name="Иванов",
            resolution_notes="Критерий уточнён",
        )
        history = _load_approval_history(PROJECT)
        pkg = history["packages"]["APKG-001"]
        sh_data = pkg["stakeholder_decisions"]["Иванов"]
        fr001_decision = next(
            rd for rd in sh_data["req_decisions"] if rd["req_id"] == "FR-001"
        )
        self.assertTrue(fr001_decision.get("condition_closed"))


# ---------------------------------------------------------------------------
# check_approval_status
# ---------------------------------------------------------------------------

class TestASupersededRoundSaysSoItself(BaseMCPTest):
    """V-5, in the corrected reading. Packages ARE rounds: where a requirement appears
    in several, the latest governs — a settled decision (`approval_outcome`, pinned by
    test_the_latest_package_decides), so a requirement can be re-submitted after
    rework. The BASELINE GATE is not the defect and is not touched here.

    What was wrong is the DISPLAY. An overtaken round went on rendering as live: it
    printed `🔴 Verdict: Not ready for baseline` over a rejection the newer round had
    already overturned, and the newer round's Approval Record carried no trace of the
    reversal. Two live documents of one project contradicting each other, and the
    reversal in no audit trail."""

    def setUp(self):
        super().setUp()
        _make_repo_with_verified(self.tmp_dir)
        _open_package(package_id="PKG-A", req_ids=["FR-001"])
        _record(package_id="PKG-A", stakeholder="Иванов", raci="accountable",
                decision="rejected", rejection_reason="the flow is wrong",
                req_decisions=[{"req_id": "FR-001", "decision": "rejected",
                                "rejection_reason": "the flow is wrong"}])
        _open_package(package_id="PKG-B", req_ids=["FR-001"])
        _record(package_id="PKG-B", stakeholder="Иванов", raci="accountable",
                decision="approved",
                req_decisions=[{"req_id": "FR-001", "decision": "approved"}])

    def test_the_overtaken_round_names_the_round_that_overtook_it(self):
        result = check_approval_status(PROJECT, "PKG-A")
        self.assertIn("PKG-B", result,
                      "the older round still reads as the project's current position")
        self.assertIn("вытеснен", result.lower())

    def test_the_new_record_names_the_decision_it_overrides(self):
        with patch("skills.requirements_approve_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            create_requirements_baseline(PROJECT, "PKG-B", "2.0", decided_by="Иванов")
            record = mock_sa.call_args[0][0]
        self.assertIn("PKG-A", record, "the reversal is in no audit trail")
        self.assertIn("Иванов", record)
        self.assertIn("the flow is wrong", record)

    def test_a_round_nobody_overtook_is_left_alone(self):
        _open_package(package_id="PKG-C", req_ids=["FR-002"])
        _record(package_id="PKG-C", req_decisions=[{"req_id": "FR-002", "decision": "approved"}])
        result = check_approval_status(PROJECT, "PKG-C")
        self.assertNotIn("вытеснен", result.lower())


class TestADeadRoundCannotSignOffWhatALaterRoundRejected(BaseMCPTest):
    """The other direction of the same rule, and the one that reaches the graph.

    The display fix taught `check_approval_status` to say "Superseded — this round no
    longer decides anything". The very next paragraph of that same document still read
    "All mandatory conditions are satisfied. You can create the Requirements Baseline",
    and following it produced a signed Approval Record listing FR-001 as approved, over
    Ivanov's name, while the round that governs has him rejecting it — and wrote
    `status: approved` into the 5.1 graph.

    The BASELINE GATE stays open on purpose: refusing here on decisions taken in OTHER
    packages is precisely the regression that would make a legitimate re-submission
    after rework impossible (pinned by test_the_latest_round_still_baselines_below).
    What changes is that the record states the outcome the platform actually computes —
    `approval_outcome` — instead of re-deriving a different one from a dead round.
    """

    def setUp(self):
        super().setUp()
        _make_repo_with_verified(self.tmp_dir)
        _open_package(package_id="PKG-A", req_ids=["FR-001"])
        _record(package_id="PKG-A", stakeholder="Иванов", raci="accountable",
                decision="approved",
                req_decisions=[{"req_id": "FR-001", "decision": "approved"}])
        _open_package(package_id="PKG-B", req_ids=["FR-001"])
        _record(package_id="PKG-B", stakeholder="Иванов", raci="accountable",
                decision="rejected", rejection_reason="security review failed",
                req_decisions=[{"req_id": "FR-001", "decision": "rejected",
                                "rejection_reason": "security review failed"}])

    def _baseline_the_dead_round(self):
        with patch("skills.requirements_approve_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            returned = create_requirements_baseline(PROJECT, "PKG-A", "1.0",
                                                    decided_by="Иванов")
            record = mock_sa.call_args[0][0]
        return returned, record

    @staticmethod
    def _approved_section(record):
        return record.split("## Одобренные требования", 1)[1].split("\n---", 1)[0]

    def test_the_record_does_not_list_it_as_approved(self):
        _returned, record = self._baseline_the_dead_round()
        self.assertNotIn("`FR-001`", self._approved_section(record),
                         "the governing round rejected it:\n" + record)

    def test_the_record_names_the_round_that_governs(self):
        _returned, record = self._baseline_the_dead_round()
        self.assertIn("PKG-B", record,
                      "the record must say which round decided instead")

    def test_the_graph_does_not_record_it_as_approved(self):
        self._baseline_the_dead_round()
        node = [r for r in load_test_repo(PROJECT)["requirements"]
                if r["id"] == "FR-001"][0]
        self.assertNotEqual(node.get("status"), STATUS_APPROVED)

    def test_the_dashboard_does_not_invite_a_baseline_it_would_disown(self):
        out = check_approval_status(PROJECT, "PKG-A")
        verdict = out.split("## 📦 Вердикт", 1)[1]
        self.assertNotIn("All mandatory conditions are satisfied", verdict,
                         "the paragraph above says this round decides nothing:\n" + out)

    def test_the_latest_round_still_baselines_what_it_approved(self):
        """The closed decision, asserted from the baseline side: re-submission after
        rework must keep working. If this test ever fails, the fix above has grown
        into the regression it was written to avoid."""
        _open_package(package_id="PKG-C", req_ids=["FR-001"])
        _record(package_id="PKG-C", stakeholder="Иванов", raci="accountable",
                decision="approved",
                req_decisions=[{"req_id": "FR-001", "decision": "approved"}])
        with patch("skills.requirements_approve_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            create_requirements_baseline(PROJECT, "PKG-C", "2.0", decided_by="Иванов")
            record = mock_sa.call_args[0][0]
        self.assertIn("`FR-001`", self._approved_section(record))
        node = [r for r in load_test_repo(PROJECT)["requirements"]
                if r["id"] == "FR-001"][0]
        self.assertEqual(node.get("status"), STATUS_APPROVED)


class TestAnEmptyBaselineSaysTheSameThingInBothPlaces(BaseMCPTest):
    """The Approval Record learned to warn that a baseline holding no approved
    requirement is not a statement that the scope was agreed. The string the tool
    RETURNS — the one the analyst reads in the chat, without opening the file — kept
    the fixed three-step epilogue, whose step 2 is "hand off the list of approved
    requirements to development" over a list of none."""

    def setUp(self):
        super().setUp()
        _make_repo_with_verified(self.tmp_dir)
        _open_package(package_id="APKG-009", req_ids=["FR-001"])

    def test_the_returned_summary_does_not_send_an_empty_list_to_разработку(self):
        with patch("skills.requirements_approve_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            returned = create_requirements_baseline(
                PROJECT, "APKG-009", "0.1", decided_by="BA", force=True)
        self.assertIn("**Одобрено требований:** 0 из 1", returned)
        self.assertNotIn("Hand off the list of approved requirements to разработку",
                         returned)
        self.assertIn("нет ни одного согласованного требования", returned.lower())

    def test_a_baseline_that_did_approve_something_still_says_so(self):
        _record(package_id="APKG-009", stakeholder="Иванов", raci="accountable",
                decision="approved",
                req_decisions=[{"req_id": "FR-001", "decision": "approved"}])
        with patch("skills.requirements_approve_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            returned = create_requirements_baseline(
                PROJECT, "APKG-009", "1.0", decided_by="Иванов")
        self.assertIn("разработку", returned)


class TestCheckApprovalStatus(BaseMCPTest):

    def setUp(self):
        super().setUp()
        _make_repo_with_verified(self.tmp_dir)
        _open_package()

    def test_all_approved_ready_for_baseline(self):
        _record(decision="approved")
        result = check_approval_status(PROJECT, "APKG-001")
        self.assertIn("Готов к baseline", result)
        self.assertIn("✅", result)

    def test_rejected_accountable_blocks_baseline(self):
        _record(decision="rejected", rejection_reason="Не согласен")
        result = check_approval_status(PROJECT, "APKG-001")
        self.assertIn("Не готов", result)
        self.assertIn("🔴", result)

    def test_rejected_consulted_does_not_block(self):
        _record(stakeholder="Иванов", decision="approved")
        _record(stakeholder="Консалт", raci="consulted",
                decision="rejected", rejection_reason="Сомнения")
        result = check_approval_status(PROJECT, "APKG-001")
        # Consulted rejected — предупреждение, не блокировщик
        self.assertIn("Consulted", result)
        self.assertIn("Готов к baseline", result)

    def test_open_conditions_reported(self):
        record_approval_decision(
            project_name=PROJECT,
            package_id="APKG-001",
            stakeholder_name="Иванов",
            stakeholder_raci="accountable",
            decision="conditional",
            req_decisions_json=json.dumps([
                {
                    "req_id": "FR-001",
                    "decision": "conditional",
                    "condition_text": "Уточнить",
                    "condition_deadline": "2026-12-01",
                    "condition_owner": "Иванов",
                },
                {"req_id": "FR-002", "decision": "approved"},
            ]),
        )
        result = check_approval_status(PROJECT, "APKG-001")
        self.assertIn("Уточнить", result)

    def test_overdue_conditions_block_baseline(self):
        yesterday = str(date.today() - timedelta(days=1))
        record_approval_decision(
            project_name=PROJECT,
            package_id="APKG-001",
            stakeholder_name="Иванов",
            stakeholder_raci="accountable",
            decision="conditional",
            req_decisions_json=json.dumps([
                {
                    "req_id": "FR-001",
                    "decision": "conditional",
                    "condition_text": "Уточнить",
                    "condition_deadline": yesterday,
                    "condition_owner": "Иванов",
                },
                {"req_id": "FR-002", "decision": "approved"},
            ]),
        )
        result = check_approval_status(PROJECT, "APKG-001")
        self.assertIn("ПРОСРОЧЕНО", result)
        self.assertIn("Не готов", result)

    def _conditional_with_deadline(self, deadline):
        record_approval_decision(
            project_name=PROJECT,
            package_id="APKG-001",
            stakeholder_name="Иванов",
            stakeholder_raci="accountable",
            decision="conditional",
            req_decisions_json=json.dumps([
                {"req_id": "FR-001", "decision": "conditional",
                 "condition_text": "Clarify access", "condition_deadline": deadline,
                 "condition_owner": "Иванов"},
                {"req_id": "FR-002", "decision": "approved"},
            ]),
        )
        return check_approval_status(PROJECT, "APKG-001")

    def test_a_deadline_in_the_platforms_other_format_is_still_a_deadline(self):
        """`date.fromisoformat` inside `except ValueError: pass` treated every
        `dd.mm.yyyy` deadline — the format the whole of chapter 4 writes — as no
        deadline at all. A condition sixteen months past printed unmarked, the verdict
        said "not overdue", and `overdue_conditions`, one of the four baseline gates,
        could not fire on such data."""
        long_past = (date.today() - timedelta(days=480)).strftime("%d.%m.%Y")
        result = self._conditional_with_deadline(long_past)
        self.assertIn("ПРОСРОЧЕНО", result)
        self.assertNotIn("(not overdue)", result)

    def test_an_unreadable_deadline_is_not_reported_as_not_overdue(self):
        result = self._conditional_with_deadline("whenever")
        self.assertIn("НЕЧИТАЕМ", result.upper())
        self.assertNotIn("(not overdue)", result,
                         "a claim was made about a deadline nobody could read")

    def test_pending_requirements_block_baseline(self):
        # Не записываем ни одного решения — все pending
        result = check_approval_status(PROJECT, "APKG-001")
        self.assertIn("Не готов", result)
        self.assertIn("pending", result)

    def test_statistics_shown(self):
        _record(decision="approved")
        result = check_approval_status(PROJECT, "APKG-001")
        self.assertIn("Approved", result)
        self.assertIn("100%", result)

    def test_package_not_found(self):
        result = check_approval_status(PROJECT, "APKG-MISSING")
        self.assertIn("❌", result)

    def test_low_approval_pct_blocks_baseline(self):
        # Открываем большой пакет, одобряем только 1 из 4
        repo = make_test_repo(PROJECT)
        for req in repo["requirements"]:
            req["status"] = "verified"
        repo["requirements"].append({
            "id": "NFR-001", "type": "non_functional",
            "title": "Производительность", "status": "verified",
            "version": "1.0",
        })
        save_test_repo(repo)

        prepare_approval_package(
            project_name=PROJECT,
            package_id="APKG-BIG",
            package_title="Большой пакет",
            req_ids_json=json.dumps(["BR-001", "FR-001", "FR-002", "NFR-001"]),
            approach="predictive",
        )
        record_approval_decision(
            project_name=PROJECT,
            package_id="APKG-BIG",
            stakeholder_name="Иванов",
            stakeholder_raci="accountable",
            decision="approved",
            req_decisions_json=json.dumps([
                {"req_id": "BR-001", "decision": "approved"},
                {"req_id": "FR-001", "decision": "rejected", "rejection_reason": "Нет"},
                {"req_id": "FR-002", "decision": "rejected", "rejection_reason": "Нет"},
                {"req_id": "NFR-001", "decision": "rejected", "rejection_reason": "Нет"},
            ]),
        )
        result = check_approval_status(PROJECT, "APKG-BIG")
        self.assertIn("Не готов", result)

    def test_multiple_stakeholders_mixed(self):
        _record(stakeholder="Иванов", decision="approved")
        _record(stakeholder="Петров", raci="responsible", decision="approved")
        result = check_approval_status(PROJECT, "APKG-001")
        self.assertIn("Иванов", result)
        self.assertIn("Петров", result)
        self.assertIn("Готов к baseline", result)


# ---------------------------------------------------------------------------
# create_requirements_baseline
# ---------------------------------------------------------------------------

class TestCreateRequirementsBaseline(BaseMCPTest):

    def setUp(self):
        super().setUp()
        _make_repo_with_verified(self.tmp_dir)
        _open_package()

    def _approve_all(self, stakeholder="Иванов"):
        _record(stakeholder=stakeholder, decision="approved")

    def test_baseline_success(self):
        self._approve_all()
        result = create_requirements_baseline(
            project_name=PROJECT,
            package_id="APKG-001",
            baseline_version="v1.0",
            decided_by="Иванов",
        )
        self.assertIn("v1.0", result)
        self.assertIn("✅", result)

    def test_baseline_updates_repo_status(self):
        self._approve_all()
        create_requirements_baseline(
            project_name=PROJECT,
            package_id="APKG-001",
            baseline_version="v1.0",
            decided_by="Иванов",
        )
        from skills.requirements_approve_mcp import _load_repo
        repo = _load_repo(PROJECT)
        fr001 = next(r for r in repo["requirements"] if r["id"] == "FR-001")
        self.assertEqual(fr001["status"], STATUS_APPROVED)

    def test_baseline_saves_to_history(self):
        self._approve_all()
        create_requirements_baseline(
            project_name=PROJECT,
            package_id="APKG-001",
            baseline_version="v1.0",
            decided_by="Иванов",
        )
        history = _load_approval_history(PROJECT)
        self.assertEqual(len(history["baselines"]), 1)
        self.assertEqual(history["baselines"][0]["baseline_version"], "v1.0")

    def test_baseline_заблокирован_by_rejected_accountable(self):
        _record(decision="rejected", rejection_reason="Не согласен")
        result = create_requirements_baseline(
            project_name=PROJECT,
            package_id="APKG-001",
            baseline_version="v1.0",
            decided_by="Иванов",
        )
        self.assertIn("❌", result)
        self.assertIn("заблокирован", result)

    def test_force_overrides_blocker(self):
        _record(decision="rejected", rejection_reason="Не согласен")
        result = create_requirements_baseline(
            project_name=PROJECT,
            package_id="APKG-001",
            baseline_version="v1.0",
            decided_by="Иванов",
            force=True,
        )
        # With force=True the baseline should be created despite the A/R rejection.
        self.assertIsNotNone(result)

    def test_low_approval_pct_blocks_baseline_without_force(self):
        """Baseline creation must enforce the same readiness gate as
        check_approval_status: below 70% approved (here 50%: one open conditional,
        one approved) it must block unless force=True, instead of silently
        baselining only the approved subset."""
        record_approval_decision(
            project_name=PROJECT,
            package_id="APKG-001",
            stakeholder_name="Иванов",
            stakeholder_raci="accountable",
            decision="conditional",
            req_decisions_json=json.dumps([
                {"req_id": "FR-001", "decision": "conditional",
                 "condition_text": "Clarify", "condition_deadline": "2026-12-01",
                 "condition_owner": "Petrov"},   # open, NOT overdue
                {"req_id": "FR-002", "decision": "approved"},
            ]),
        )
        result = create_requirements_baseline(
            project_name=PROJECT,
            package_id="APKG-001",
            baseline_version="v1.0",
            decided_by="Иванов",
        )  # no force
        self.assertIn("❌", result)
        self.assertIn("заблокирован", result)
        history = _load_approval_history(PROJECT)
        self.assertEqual(len(history["baselines"]), 0, "no baseline may be created when not ready")

    def test_package_already_baselined_error(self):
        self._approve_all()
        create_requirements_baseline(
            project_name=PROJECT,
            package_id="APKG-001",
            baseline_version="v1.0",
            decided_by="Иванов",
        )
        result = create_requirements_baseline(
            project_name=PROJECT,
            package_id="APKG-001",
            baseline_version="v1.1",
            decided_by="Иванов",
        )
        self.assertIn("уже имеет baseline", result)

    def test_package_not_found_error(self):
        result = create_requirements_baseline(
            project_name=PROJECT,
            package_id="APKG-MISSING",
            baseline_version="v1.0",
            decided_by="Иванов",
        )
        self.assertIn("❌", result)

    def test_baseline_contains_stakeholder_summary(self):
        self._approve_all()
        create_requirements_baseline(
            project_name=PROJECT,
            package_id="APKG-001",
            baseline_version="v1.0",
            decided_by="Иванов",
        )
        history = _load_approval_history(PROJECT)
        bl = history["baselines"][0]
        self.assertIn("Иванов", bl["stakeholder_summary"])

    def test_baseline_with_open_conditions_and_force(self):
        record_approval_decision(
            project_name=PROJECT,
            package_id="APKG-001",
            stakeholder_name="Иванов",
            stakeholder_raci="accountable",
            decision="conditional",
            req_decisions_json=json.dumps([
                {
                    "req_id": "FR-001",
                    "decision": "conditional",
                    "condition_text": "Уточнить",
                    "condition_deadline": "2026-12-01",
                    "condition_owner": "Петров",
                },
                {"req_id": "FR-002", "decision": "approved"},
            ]),
        )
        result = create_requirements_baseline(
            project_name=PROJECT,
            package_id="APKG-001",
            baseline_version="v1.0",
            decided_by="Иванов",
            force=True,
        )
        self.assertIn("v1.0", result)
        history = _load_approval_history(PROJECT)
        bl = history["baselines"][0]
        self.assertEqual(len(bl["open_conditions"]), 1)

    def test_multiple_baselines_in_history(self):
        self._approve_all()
        create_requirements_baseline(
            project_name=PROJECT,
            package_id="APKG-001",
            baseline_version="v1.0",
            decided_by="Иванов",
        )
        # Второй пакет
        _make_repo_with_verified(self.tmp_dir)
        prepare_approval_package(
            project_name=PROJECT,
            package_id="APKG-002",
            package_title="Второй пакет",
            req_ids_json='["BR-001"]',
            approach="agile",
        )
        _record(package_id="APKG-002", decision="approved")
        create_requirements_baseline(
            project_name=PROJECT,
            package_id="APKG-002",
            baseline_version="sprint-1",
            decided_by="Иванов",
        )
        history = _load_approval_history(PROJECT)
        self.assertEqual(len(history["baselines"]), 2)

    def test_agile_sprint_baseline(self):
        prepare_approval_package(
            project_name=PROJECT,
            package_id="APKG-SPRINT",
            package_title="Sprint 3",
            req_ids_json='["BR-001"]',
            approach="agile",
            sprint_number="3",
        )
        _record(package_id="APKG-SPRINT", decision="approved")
        result = create_requirements_baseline(
            project_name=PROJECT,
            package_id="APKG-SPRINT",
            baseline_version="sprint-3",
            decided_by="Product Owner",
        )
        self.assertIn("sprint-3", result)


# ---------------------------------------------------------------------------
# Pipeline интеграционные тесты
# ---------------------------------------------------------------------------

class TestApprovalPipeline(BaseMCPTest):

    def setUp(self):
        super().setUp()
        _make_repo_with_verified(self.tmp_dir)

    def test_full_predictive_pipeline(self):
        """Полный Predictive pipeline: prepare → record × 2 → check → baseline."""
        # 1. prepare
        result = _open_package()
        self.assertIn("APKG-001", result)

        # 2. record — Спонсор одобряет
        r1 = _record(stakeholder="Спонсор", raci="accountable", decision="approved")
        self.assertIn("✅", r1)

        # 3. record — Бизнес-эксперт одобряет
        r2 = _record(stakeholder="Эксперт", raci="responsible", decision="approved")
        self.assertIn("✅", r2)

        # 4. check
        status = check_approval_status(PROJECT, "APKG-001")
        self.assertIn("Готов к baseline", status)

        # 5. baseline
        bl = create_requirements_baseline(
            project_name=PROJECT,
            package_id="APKG-001",
            baseline_version="v1.0",
            decided_by="Спонсор",
        )
        self.assertIn("v1.0", bl)

        # Проверяем историю
        history = _load_approval_history(PROJECT)
        self.assertEqual(len(history["baselines"]), 1)

    def test_full_agile_pipeline(self):
        """Agile pipeline: prepare sprint → PO одобряет → sprint baseline."""
        prepare_approval_package(
            project_name=PROJECT,
            package_id="SPRINT-1",
            package_title="Sprint 1 Backlog",
            req_ids_json='["FR-001"]',
            approach="agile",
            sprint_number="1",
        )
        record_approval_decision(
            project_name=PROJECT,
            package_id="SPRINT-1",
            stakeholder_name="Product Owner",
            stakeholder_raci="accountable",
            decision="approved",
        )
        status = check_approval_status(PROJECT, "SPRINT-1")
        self.assertIn("Готов к baseline", status)

        bl = create_requirements_baseline(
            project_name=PROJECT,
            package_id="SPRINT-1",
            baseline_version="sprint-1",
            decided_by="Product Owner",
        )
        self.assertIn("sprint-1", bl)

    def test_conditional_then_close_then_baseline(self):
        """Conditional → close_condition → baseline."""
        _open_package(req_ids=["FR-001"])
        record_approval_decision(
            project_name=PROJECT,
            package_id="APKG-001",
            stakeholder_name="Иванов",
            stakeholder_raci="accountable",
            decision="conditional",
            req_decisions_json=json.dumps([
                {
                    "req_id": "FR-001",
                    "decision": "conditional",
                    "condition_text": "Добавить acceptance criteria",
                    "condition_deadline": "2026-12-01",
                    "condition_owner": "BA",
                }
            ]),
        )

        # Статус ещё не ready
        status = check_approval_status(PROJECT, "APKG-001")
        self.assertIn("условия", status)

        # Закрываем условие
        close_approval_condition(
            project_name=PROJECT,
            package_id="APKG-001",
            req_id="FR-001",
            stakeholder_name="Иванов",
            resolution_notes="Acceptance criteria добавлены в документ",
        )

        # Теперь готов
        status2 = check_approval_status(PROJECT, "APKG-001")
        self.assertIn("Готов к baseline", status2)

        # Baseline
        bl = create_requirements_baseline(
            project_name=PROJECT,
            package_id="APKG-001",
            baseline_version="v1.0",
            decided_by="Иванов",
        )
        self.assertIn("v1.0", bl)

    def test_conflict_consulted_rejected_does_not_block(self):
        """Rejected от Consulted не блокирует baseline."""
        _open_package()
        _record(stakeholder="Спонсор", raci="accountable", decision="approved")
        _record(stakeholder="Пользователь", raci="consulted",
                decision="rejected", rejection_reason="Не удобно")

        status = check_approval_status(PROJECT, "APKG-001")
        self.assertIn("Готов к baseline", status)
        self.assertIn("Consulted", status)

    def test_two_packages_independent(self):
        """Два пакета не влияют друг на друга."""
        _open_package(package_id="APKG-A", req_ids=["FR-001"])
        _open_package(package_id="APKG-B", req_ids=["FR-002"])

        _record(package_id="APKG-A", decision="approved")
        # APKG-B остаётся без решений

        status_a = check_approval_status(PROJECT, "APKG-A")
        status_b = check_approval_status(PROJECT, "APKG-B")

        self.assertIn("Готов к baseline", status_a)
        self.assertIn("Не готов", status_b)

    def test_baseline_version_history_grows(self):
        """История baseline-ов растёт при каждом новом пакете."""
        # v1.0
        _open_package(package_id="V1", req_ids=["FR-001"])
        _record(package_id="V1", decision="approved")
        create_requirements_baseline(PROJECT, "V1", "v1.0", "Спонсор")

        # v1.1 — новый пакет
        prepare_approval_package(
            project_name=PROJECT,
            package_id="V11",
            package_title="Патч",
            req_ids_json='["FR-002"]',
            approach="predictive",
        )
        _record(package_id="V11", decision="approved")
        create_requirements_baseline(PROJECT, "V11", "v1.1", "Спонсор")

        history = _load_approval_history(PROJECT)
        versions = [bl["baseline_version"] for bl in history["baselines"]]
        self.assertIn("v1.0", versions)
        self.assertIn("v1.1", versions)


# ---------------------------------------------------------------------------
# B2-bis — 7.2 verification is visible in 5.5
# ---------------------------------------------------------------------------

def _make_repo_unverified(tmp_dir):
    """A repository whose requirements never passed 7.2 (status draft, no history)."""
    repo = make_test_repo(PROJECT)
    for req in repo["requirements"]:
        if req["type"] != "test":
            req["status"] = "draft"
            req["priority"] = "Must"
    repo["history"] = []
    save_test_repo(repo)
    return repo


class TestVerificationSnapshot(BaseMCPTest):
    """prepare_approval_package must capture verification BEFORE it overwrites status."""

    def test_snapshot_records_verified_reqs(self):
        _make_repo_with_verified(self.tmp_dir)
        prepare_approval_package(
            project_name=PROJECT, package_id="APKG-001", package_title="Pkg",
            req_ids_json='["FR-001"]', approach="predictive",
        )
        history = _load_approval_history(PROJECT)
        snapshot = history["packages"]["APKG-001"]["verification_snapshot"]
        self.assertEqual(snapshot, {"FR-001": True})

    def test_snapshot_survives_the_status_overwrite(self):
        """The legacy case: evidence lives only in the status, which prepare erases."""
        _make_repo_with_verified(self.tmp_dir)
        prepare_approval_package(
            project_name=PROJECT, package_id="APKG-001", package_title="Pkg",
            req_ids_json='["FR-001"]', approach="predictive",
        )
        repo = load_test_repo(PROJECT)
        node = next(r for r in repo["requirements"] if r["id"] == "FR-001")
        self.assertEqual(node["status"], STATUS_PENDING)  # status is gone
        history = _load_approval_history(PROJECT)
        self.assertTrue(history["packages"]["APKG-001"]["verification_snapshot"]["FR-001"])

    def test_snapshot_records_unverified_reqs(self):
        _make_repo_unverified(self.tmp_dir)
        prepare_approval_package(
            project_name=PROJECT, package_id="APKG-001", package_title="Pkg",
            req_ids_json='["FR-001"]', approach="predictive",
        )
        history = _load_approval_history(PROJECT)
        self.assertEqual(
            history["packages"]["APKG-001"]["verification_snapshot"], {"FR-001": False}
        )

    def test_unverified_reqs_are_warned_about_with_the_phase_hint(self):
        """7.2 lives in the `design` phase — a hint naming only the tool is unfollowable."""
        _make_repo_unverified(self.tmp_dir)
        out = prepare_approval_package(
            project_name=PROJECT, package_id="APKG-001", package_title="Pkg",
            req_ids_json='["FR-001"]', approach="predictive",
        )
        self.assertIn("FR-001", out)
        self.assertIn("7.2", out)
        self.assertIn("phase.py design", out)

    def test_verified_package_has_no_warning(self):
        _make_repo_with_verified(self.tmp_dir)
        out = prepare_approval_package(
            project_name=PROJECT, package_id="APKG-001", package_title="Pkg",
            req_ids_json='["FR-001"]', approach="predictive",
        )
        self.assertNotIn("Not verified via 7.2", out)


class TestVerificationState(BaseMCPTest):
    """_verification_state merges the live history with the stored snapshot."""

    def test_live_history_beats_a_stale_snapshot(self):
        """The BA may go to 7.2 AFTER preparing the package."""
        repo = _make_repo_unverified(self.tmp_dir)
        repo["history"].append({"action": "req_verified", "req_id": "FR-001"})
        package = {"req_ids": ["FR-001"], "verification_snapshot": {"FR-001": False}}
        state = _verification_state(repo, package)
        self.assertEqual(state["verified"], ["FR-001"])
        self.assertEqual(state["unverified"], [])

    def test_snapshot_fills_in_for_erased_status(self):
        repo = _make_repo_unverified(self.tmp_dir)
        package = {"req_ids": ["FR-001"], "verification_snapshot": {"FR-001": True}}
        state = _verification_state(repo, package)
        self.assertEqual(state["verified"], ["FR-001"])

    def test_missing_snapshot_key_is_unknown_not_unverified(self):
        """Packages already in flight when this shipped must not be called liars."""
        repo = _make_repo_unverified(self.tmp_dir)
        package = {"req_ids": ["FR-001"]}
        state = _verification_state(repo, package)
        self.assertFalse(state["known"])

    def test_forced_verification_is_listed_separately(self):
        repo = _make_repo_unverified(self.tmp_dir)
        repo["history"].append(
            {"action": "req_verified", "req_id": "FR-001", "forced": True}
        )
        package = {"req_ids": ["FR-001"], "verification_snapshot": {"FR-001": False}}
        state = _verification_state(repo, package)
        self.assertEqual(state["verified"], ["FR-001"])
        self.assertEqual(state["forced"], ["FR-001"])


class TestDashboardVerificationLine(BaseMCPTest):

    def _prepare(self, repo_factory):
        repo_factory(self.tmp_dir)
        prepare_approval_package(
            project_name=PROJECT, package_id="APKG-001", package_title="Pkg",
            req_ids_json='["FR-001", "FR-002"]', approach="predictive",
        )

    def test_all_verified_shows_a_green_line(self):
        self._prepare(_make_repo_with_verified)
        out = check_approval_status(project_name=PROJECT, package_id="APKG-001")
        self.assertIn("Верифицировано (7.2): 2 из 2", out)
        self.assertIn("✅ **Верифицировано (7.2)", out)

    def test_partially_verified_shows_the_ids(self):
        self._prepare(_make_repo_unverified)
        out = check_approval_status(project_name=PROJECT, package_id="APKG-001")
        self.assertIn("Верифицировано (7.2): 0 из 2", out)
        self.assertIn("🟡 **Верифицировано (7.2)", out)
        self.assertIn("FR-001", out)

    def test_unknown_package_says_so(self):
        self._prepare(_make_repo_with_verified)
        history = _load_approval_history(PROJECT)
        del history["packages"]["APKG-001"]["verification_snapshot"]
        _save_approval_history(PROJECT, history)
        # Also strip the live evidence, so only the missing snapshot remains.
        repo = load_test_repo(PROJECT)
        repo["history"] = []
        save_test_repo(repo)
        out = check_approval_status(project_name=PROJECT, package_id="APKG-001")
        self.assertIn("неизвестно", out.lower())

    def test_verification_does_not_change_the_verdict(self):
        """GLOBAL CONSTRAINT: the gate keeps its four conditions."""
        self._prepare(_make_repo_unverified)
        # req_decisions_json defaults to "[]" — the overall decision applies to every req.
        record_approval_decision(
            project_name=PROJECT, package_id="APKG-001", stakeholder_name="Sponsor",
            stakeholder_raci="accountable", decision="approved",
        )
        out = check_approval_status(project_name=PROJECT, package_id="APKG-001")
        self.assertIn("Готов к baseline", out)


class TestApprovalRecordVerificationSection(BaseMCPTest):

    def _approve_and_baseline(self, repo_factory, force=False):
        repo_factory(self.tmp_dir)
        prepare_approval_package(
            project_name=PROJECT, package_id="APKG-001", package_title="Pkg",
            req_ids_json='["FR-001", "FR-002"]', approach="predictive",
        )
        record_approval_decision(
            project_name=PROJECT, package_id="APKG-001", stakeholder_name="Sponsor",
            stakeholder_raci="accountable", decision="approved",
        )
        return create_requirements_baseline(
            project_name=PROJECT, package_id="APKG-001",
            baseline_version="v1.0", decided_by="Sponsor", force=force,
        )

    def _record_content(self):
        """conftest mocks save_artifact — the artifact text is in call_args, not on disk."""
        from skills.requirements_approve_mcp import save_artifact
        return save_artifact.call_args[0][0]

    def test_unverified_reqs_land_in_the_approval_record(self):
        self._approve_and_baseline(_make_repo_unverified)
        content = self._record_content()
        self.assertIn("Вошло в baseline без верификации 7.2", content)
        self.assertIn("FR-001", content)
        self.assertIn("FR-002", content)

    def test_fully_verified_record_has_no_such_section(self):
        self._approve_and_baseline(_make_repo_with_verified)
        content = self._record_content()
        self.assertNotIn("Вошло в baseline без верификации 7.2", content)

    def test_baseline_is_not_заблокирован_by_missing_verification(self):
        """GLOBAL CONSTRAINT: report-only. force must NOT be needed."""
        out = self._approve_and_baseline(_make_repo_unverified, force=False)
        self.assertIn("Requirements Baseline создан", out)
        self.assertNotIn("Baseline заблокирован", out)

    def test_forced_verification_is_recorded_distinctly(self):
        repo = _make_repo_unverified(self.tmp_dir)
        repo["history"] = [
            {"action": "req_verified", "req_id": "FR-001", "forced": True,
             "overridden_blockers": ["VI-001"]},
            {"action": "req_verified", "req_id": "FR-002"},
        ]
        save_test_repo(repo)
        prepare_approval_package(
            project_name=PROJECT, package_id="APKG-001", package_title="Pkg",
            req_ids_json='["FR-001", "FR-002"]', approach="predictive",
        )
        record_approval_decision(
            project_name=PROJECT, package_id="APKG-001", stakeholder_name="Sponsor",
            stakeholder_raci="accountable", decision="approved",
        )
        create_requirements_baseline(
            project_name=PROJECT, package_id="APKG-001",
            baseline_version="v1.0", decided_by="Sponsor",
        )
        content = self._record_content()
        self.assertIn("верифицировано с обходом", content.lower())
        self.assertIn("FR-001", content)
        self.assertNotIn("Вошло в baseline без верификации 7.2", content)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


class TestApprovalRecordAccuracy(BaseMCPTest):
    """The feature's thesis is that the Approval Record must carry the fact rather
    than a console warning — which only holds if what it records is TRUE."""

    def _package_nothing_was_approved_in(self):
        """Only a CONSULTED stakeholder responded, so no Accountable/Responsible ever
        said yes and every requirement stays pending — the baseline ends up empty.

        Two earlier attempts at this scenario do not work, and both are worth knowing:
        an A/R rejection is now a hard block `force` does not lift, and a PARTIAL
        req_decisions list does not leave the rest pending — `decision` is a blanket
        position that the list only refines.
        """
        _make_repo_unverified(self.tmp_dir)
        _open_package(req_ids=["FR-001", "FR-002"])
        _record(stakeholder="Consulted Carl", raci="consulted", decision="approved")

    def test_record_does_not_name_non_baselined_reqs_as_baselined(self):
        """The record speaks about the BASELINE. Reporting over the whole package
        listed a REJECTED requirement under 'Baselined without 7.2 verification' and
        said it 'was approved' — a false statement in an official artifact."""
        self._package_nothing_was_approved_in()
        with patch("skills.requirements_approve_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            create_requirements_baseline(
                project_name=PROJECT, package_id="APKG-001",
                baseline_version="v1.0", decided_by="Иванов", force=True)
            record = mock_sa.call_args[0][0]

        if "Вошло в baseline без верификации 7.2" in record:
            section = record.split("Вошло в baseline без верификации 7.2", 1)[1]
            section = section.split("###", 1)[0]
            for rid in ("FR-001", "FR-002"):
                self.assertNotIn(rid, section,
                                 "nothing entered the baseline, so nothing may be "
                                 "reported as baselined")

    def test_unknown_and_override_are_not_claimed_about_the_same_req(self):
        """`known` was a per-PACKAGE flag while `forced` came from live history, so a
        snapshot-less package could declare verification undeterminable and then name
        a specific override — two contradictory claims in one artifact."""
        _make_repo_with_verified(self.tmp_dir)
        repo = load_test_repo(PROJECT)
        repo.setdefault("history", []).append({
            "action": "req_verified", "req_id": "FR-001", "forced": True,
            "date": str(date.today()),
        })
        save_test_repo(repo)
        _open_package(req_ids=["FR-001"])

        history = _load_approval_history(PROJECT)
        del history["packages"]["APKG-001"]["verification_snapshot"]
        _save_approval_history(PROJECT, history)

        dashboard = check_approval_status(project_name=PROJECT, package_id="APKG-001")
        if "override" in dashboard.lower():
            self.assertNotIn("created before the verification check", dashboard,
                             "cannot be unknowable and overridden at the same time")

    def test_live_history_is_not_discarded_for_a_snapshotless_package(self):
        """Durable evidence sitting in history must not be thrown away just because
        the package predates the snapshot."""
        _make_repo_with_verified(self.tmp_dir)
        repo = load_test_repo(PROJECT)
        repo.setdefault("history", []).append({
            "action": "req_verified", "req_id": "FR-001", "date": str(date.today()),
        })
        save_test_repo(repo)
        _open_package(req_ids=["FR-001"])
        history = _load_approval_history(PROJECT)
        del history["packages"]["APKG-001"]["verification_snapshot"]
        _save_approval_history(PROJECT, history)

        dashboard = check_approval_status(project_name=PROJECT, package_id="APKG-001")
        self.assertIn("1 из 1", dashboard,
                      "FR-001 is verified in the durable history — that is knowable")


class TestForceIsNotOneFlagForEverything(BaseMCPTest):
    """`force` used to lift four independent gates at once, so an analyst forcing past
    a lapsed deadline also baselined over a live objection — without being told.

    Overriding a PERSON who said no is a different decision from overriding process
    state, so it needs a different act; and every override that IS allowed is named.
    """

    def _reject_from_accountable(self):
        _make_repo_with_verified(self.tmp_dir)
        _open_package(req_ids=["FR-001", "FR-002"])
        _record(decision="rejected", rejection_reason="Conflicts with the SLA",
                req_decisions=[
                    {"req_id": "FR-001", "decision": "rejected",
                     "rejection_reason": "Conflicts with the SLA"},
                ])

    def test_force_does_not_lift_an_accountable_rejection(self):
        self._reject_from_accountable()
        result = create_requirements_baseline(
            project_name=PROJECT, package_id="APKG-001",
            baseline_version="v1.0", decided_by="Иванов", force=True)
        self.assertIn("❌", result)
        self.assertIn("НЕ снимается флагом `force`", result)

    def test_the_rejection_block_names_who_objected_and_why(self):
        self._reject_from_accountable()
        result = create_requirements_baseline(
            project_name=PROJECT, package_id="APKG-001",
            baseline_version="v1.0", decided_by="Иванов", force=True)
        self.assertIn("Иванов", result)
        self.assertIn("Conflicts with the SLA", result)

    def test_no_baseline_is_written_when_the_hard_gate_blocks(self):
        self._reject_from_accountable()
        create_requirements_baseline(
            project_name=PROJECT, package_id="APKG-001",
            baseline_version="v1.0", decided_by="Иванов", force=True)
        history = _load_approval_history(PROJECT)
        self.assertEqual(history.get("baselines", []), [],
                         "a заблокирован baseline must leave no record behind")

    def test_process_gates_are_still_forceable_and_named(self):
        """The other three remain overridable — the point is that they are recorded
        by name, not that they are blocked."""
        _make_repo_with_verified(self.tmp_dir)
        _open_package(req_ids=["FR-001", "FR-002"])
        _record(stakeholder="Consulted Carl", raci="consulted", decision="approved")

        заблокирован = create_requirements_baseline(
            project_name=PROJECT, package_id="APKG-001",
            baseline_version="v1.0", decided_by="Иванов")
        self.assertIn("❌", заблокирован)
        self.assertIn("незакрытые согласования", заблокирован)

        with patch("skills.requirements_approve_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            forced = create_requirements_baseline(
                project_name=PROJECT, package_id="APKG-001",
                baseline_version="v1.0", decided_by="Иванов", force=True)
            record = mock_sa.call_args[0][0]

        self.assertNotIn("❌", forced)
        self.assertIn("незакрытые согласования", record)
        self.assertIn("force", record.lower())

    def test_the_record_stores_which_gates_were_overridden(self):
        """"force_created: true" alone tells a later reader that a rule was bypassed
        but not which one — the first question an auditor asks."""
        _make_repo_with_verified(self.tmp_dir)
        _open_package(req_ids=["FR-001", "FR-002"])
        _record(stakeholder="Consulted Carl", raci="consulted", decision="approved")
        with patch("skills.requirements_approve_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Saved"
            create_requirements_baseline(
                project_name=PROJECT, package_id="APKG-001",
                baseline_version="v1.0", decided_by="Иванов", force=True)

        history = _load_approval_history(PROJECT)
        snapshot = history["baselines"][-1]
        self.assertTrue(snapshot["force_created"])
        self.assertIn("незакрытые согласования", snapshot["forced_gates"])


class TestApprovalPackageShowsRequirementText(BaseMCPTest):
    """The package card read `description` / `acceptance_criteria` off the graph
    NODE — fields 7.1 never writes there (the text lives in the spec .md). The
    signing package therefore contained only titles: a stakeholder was asked to
    approve requirements they could not read, and the tool flagged nothing
    (reproduced live). The card now falls back to the spec file, the way 7.2's
    quality checks already do. Owner had the same shape one field over:
    `_register_in_repo` hard-coded `"owner": ""` and dropped the creating call's
    owner argument on the floor."""

    def _spec_project(self):
        import skills.requirements_spec_mcp as mod71
        mod71.create_functional_requirement(
            "pkgtext", req_id="FR-001", req_type="functional",
            title="Automated claim triage",
            description="The system SHALL auto-triage incoming claims within 30 seconds of submission.",
            rationale="Removes the manual full-review pipeline.",
            priority="High", owner="Elena Vasquez",
            business_goal_ids_json="[]")
        mod71.create_user_story(
            "pkgtext", story_id="US-001", title="Adjuster sees extracted data",
            role="Claims Adjuster",
            action="review auto-extracted claim fields",
            benefit="save 40 minutes per claim",
            acceptance_criteria_json=json.dumps([
                "Every extracted field shows its source location on hover",
                "Corrections are logged for retraining",
            ]),
            priority="Medium", business_goal_ids_json="[]")

    def test_package_contains_statement_ac_and_owner(self):
        self._spec_project()
        out = prepare_approval_package(
            "pkgtext", package_id="APKG-100", package_title="Readable package",
            req_ids_json='["FR-001", "US-001"]', approach="predictive")
        self.assertIn("SHALL auto-triage incoming claims", out,
                      "the statement must be readable in the signing package")
        self.assertIn("source location on hover", out,
                      "acceptance criteria must be readable in the signing package")
        self.assertIn("Elena Vasquez", out,
                      "the owner the creating call named must reach the package")


if __name__ == "__main__":
    unittest.main(verbosity=2)
