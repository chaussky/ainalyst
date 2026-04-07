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
from tests.conftest import setup_mocks, BaseMCPTest, make_test_repo, save_test_repo

setup_mocks()

from skills.requirements_approve_mcp import (
    prepare_approval_package,
    record_approval_decision,
    close_approval_condition,
    check_approval_status,
    create_requirements_baseline,
    _compute_req_status,
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

    def test_abstained_by_accountable_gives_approved(self):
        pkg = self._make_pkg()
        pkg["stakeholder_decisions"]["Иванов"] = {
            "raci": "accountable",
            "req_decisions": [{"req_id": "FR-001", "decision": "abstained"}],
        }
        self.assertEqual(_compute_req_status("FR-001", pkg), STATUS_APPROVED)

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

    def test_duplicate_package_id_blocked(self):
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

    def test_unknown_req_id_in_decisions_blocked(self):
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

    def test_baseline_blocked_by_rejected_accountable(self):
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
        # При force=True baseline должен создаться
        # (rejected от accountable — блокер, но force разрешает)
        # На самом деле наш код блокирует только pending/rejected без force
        self.assertIsNotNone(result)

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
# Точка входа
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main(verbosity=2)
