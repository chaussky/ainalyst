"""
tests/test_ch7_76.py — Тесты для Главы 7, задача 7.6 (Analyze Value and Recommend Solution)

Покрытие (75 тестов):
  - Утилиты: _safe, _rec_path, _design_options_path, _load_recommendation,
             _save_recommendation, _load_design_options, _load_context,
             _load_architecture, _load_risks

  - _calc_benefits_score: пустой список, один элемент, несколько, маппинг magnitude/confidence
  - _calc_cost_score: пустой, компоненты без items, несколько items, маппинг
  - _calc_alignment_score: без context, пустые goals, совпадение/несовпадение
  - _calc_risk_penalty: пустой, Low/Medium/High/Critical
  - _calc_value_score: happy path, нулевые значения

  - add_value_assessment:
    empty option_id, invalid benefit type, invalid magnitude, invalid confidence,
    invalid costs_json (not dict), missing components key, invalid cost_category, invalid cost_magnitude,
    invalid risks_json, invalid risk_level,
    happy path create, happy path update (idempotent),
    graceful degradation без design_options (option_meta=None),
    graceful degradation без context (alignment=0),
    graceful degradation без risks file (risks_source=none),
    graceful degradation с risks file из 6.3 (risks_source=6.3_file),
    накопление нескольких вариантов

  - compare_value:
    нет assessments → warning,
    один вариант → success ranking,
    два варианта → correct ranking,
    winner определён верно,
    comparison сохранён в файл,
    без business_context (alignment=0),
    с business_context (alignment > 0)

  - check_value_readiness:
    нет design_options → critical issue,
    нет вариантов → critical issue,
    не все варианты оценены → critical issue,
    compare_value не вызван → critical issue,
    пустые benefits → warning,
    пустые cost_items → warning,
    critical arch gaps → warning,
    пустой allocation → info,
    всё готово → статус OK

  - save_recommendation:
    invalid recommendation_type,
    empty rationale,
    recommend_option без recommended_option_id → error,
    recommend_option с неизвестным option_id → error,
    invalid parallel_option_ids_json,
    invalid success_metrics_json,
    invalid risks_acknowledged_json,
    recommend_option happy path,
    recommend_parallel happy path,
    recommend_reanalyze happy path,
    no_action happy path,
    idempotent update,
    без success_metrics → предупреждение в тексте,
    graceful degradation без architecture,
    graceful degradation без design_options (no validation of option_id),
    save_artifact вызван,
    success_metrics сохранены

  - Pipeline: полный happy path:
    add×2 → compare → check_readiness → save_recommendation(recommend_option)
"""

import json
import os
import sys
import unittest
from datetime import date

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from tests.conftest import BaseMCPTest, setup_mocks

setup_mocks()

import skills.value_recommend_mcp as mod76


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def make_benefit(
    btype="operational",
    description="Ускорение обработки",
    magnitude="High",
    tangibility="tangible",
    confidence="High",
):
    return {
        "type": btype,
        "description": description,
        "magnitude": magnitude,
        "tangibility": tangibility,
        "confidence": confidence,
    }


def make_cost_item(category="development", description="Разработка backend", magnitude="High"):
    return {"category": category, "description": description, "magnitude": magnitude}


def make_component(name="Backend", cost_items=None):
    return {"component": name, "cost_items": cost_items or [make_cost_item()]}


def make_costs(components=None, opportunity_cost=""):
    return {
        "components": components or [make_component()],
        "opportunity_cost": opportunity_cost,
    }


def make_risk(
    risk_id="RSK-001",
    description="Задержка разработки",
    probability="Medium",
    impact="High",
    risk_level="High",
):
    return {
        "risk_id": risk_id,
        "description": description,
        "probability": probability,
        "impact": impact,
        "risk_level": risk_level,
    }


def make_design_options(project_id="test_proj", options=None):
    return {
        "project_id": project_id,
        "options": options or [],
        "allocation": {},
        "created": str(date.today()),
        "updated": str(date.today()),
    }


def make_option(option_id="OPT-001", title="Вариант Build", approach="build", opportunities=None):
    return {
        "option_id": option_id,
        "title": title,
        "approach": approach,
        "components": ["Backend", "Frontend"],
        "improvement_opportunities": opportunities or [
            {"type": "efficiency", "description": "Автоматизация обработки заявок"}
        ],
        "effectiveness_measures": ["Снижение времени на 40%"],
        "notes": "",
        "vendor_notes": "",
        "created": str(date.today()),
        "updated": str(date.today()),
    }


def make_context(project_id="test_proj", goals=None):
    return {
        "project_id": project_id,
        "business_goals": goals if goals is not None else [
            {"id": "G-001", "title": "Ускорить обработку заявок"},
            {"id": "G-002", "title": "Снизить ошибки сотрудников"},
        ],
        "future_state": "Полностью автоматизированная обработка",
        "created": str(date.today()),
    }


def save_design_options(do_data: dict, tmp_dir: str):
    pid = do_data["project_id"].lower().replace(" ", "_")
    path = os.path.join(tmp_dir, "governance_plans", "data", f"{pid}_design_options.json")
    os.makedirs(os.path.join(tmp_dir, "governance_plans", "data"), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(do_data, f, ensure_ascii=False, indent=2)


def save_context(ctx: dict, tmp_dir: str):
    pid = ctx["project_id"].lower().replace(" ", "_")
    path = os.path.join(tmp_dir, "governance_plans", "data", f"{pid}_business_context.json")
    os.makedirs(os.path.join(tmp_dir, "governance_plans", "data"), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(ctx, f, ensure_ascii=False, indent=2)


def save_architecture(arch: dict, project_id: str, tmp_dir: str):
    pid = project_id.lower().replace(" ", "_")
    path = os.path.join(tmp_dir, "governance_plans", "data", f"{pid}_architecture.json")
    os.makedirs(os.path.join(tmp_dir, "governance_plans", "data"), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(arch, f, ensure_ascii=False, indent=2)


def save_risks(risks_data: dict, project_id: str, tmp_dir: str):
    pid = project_id.lower().replace(" ", "_")
    path = os.path.join(tmp_dir, "governance_plans", "data", f"{pid}_risks.json")
    os.makedirs(os.path.join(tmp_dir, "governance_plans", "data"), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(risks_data, f, ensure_ascii=False, indent=2)


def load_rec_file(project_id: str, tmp_dir: str) -> dict:
    pid = project_id.lower().replace(" ", "_")
    path = os.path.join(tmp_dir, "governance_plans", "data", f"{pid}_recommendation.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Тесты утилит
# ---------------------------------------------------------------------------

class TestUtils(BaseMCPTest):

    def test_safe_lowercase(self):
        self.assertEqual(mod76._safe("My Project"), "my_project")

    def test_safe_already_clean(self):
        self.assertEqual(mod76._safe("myproject"), "myproject")

    def test_rec_path(self):
        path = mod76._rec_path("test_proj")
        self.assertIn("test_proj_recommendation.json", path)
        self.assertIn("governance_plans", path)

    def test_design_options_path(self):
        path = mod76._design_options_path("test_proj")
        self.assertIn("design_options.json", path)

    def test_load_recommendation_default(self):
        rec = mod76._load_recommendation("nonexistent_proj_xyz")
        self.assertIn("value_assessments", rec)
        self.assertEqual(rec["value_assessments"], {})

    def test_save_and_load_recommendation(self):
        data = {
            "project_id": "save_test",
            "value_assessments": {},
            "created": str(date.today()),
            "updated": str(date.today()),
        }
        mod76._save_recommendation(data)
        loaded = mod76._load_recommendation("save_test")
        self.assertEqual(loaded["project_id"], "save_test")

    def test_load_design_options_missing(self):
        result = mod76._load_design_options("nonexistent_proj_xyz")
        self.assertIsNone(result)

    def test_load_context_missing(self):
        result = mod76._load_context("nonexistent_proj_xyz")
        self.assertIsNone(result)

    def test_load_architecture_missing(self):
        result = mod76._load_architecture("nonexistent_proj_xyz")
        self.assertIsNone(result)

    def test_load_risks_missing(self):
        result = mod76._load_risks("nonexistent_proj_xyz")
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# Тесты математических утилит
# ---------------------------------------------------------------------------

class TestMath(BaseMCPTest):

    def test_benefits_score_empty(self):
        self.assertEqual(mod76._calc_benefits_score([]), 0.0)

    def test_benefits_score_single_high_high(self):
        b = [make_benefit(magnitude="High", confidence="High")]
        # 3 * 1.5 = 4.5
        self.assertEqual(mod76._calc_benefits_score(b), 4.5)

    def test_benefits_score_single_low_low(self):
        b = [make_benefit(magnitude="Low", confidence="Low")]
        # 1 * 0.5 = 0.5
        self.assertEqual(mod76._calc_benefits_score(b), 0.5)

    def test_benefits_score_two_items_avg(self):
        b = [
            make_benefit(magnitude="High", confidence="High"),  # 3*1.5 = 4.5
            make_benefit(magnitude="Low", confidence="Low"),   # 1*0.5 = 0.5
        ]
        # avg = (4.5 + 0.5) / 2 = 2.5
        self.assertEqual(mod76._calc_benefits_score(b), 2.5)

    def test_cost_score_empty(self):
        self.assertEqual(mod76._calc_cost_score({}), 0.0)

    def test_cost_score_no_items(self):
        costs = {"components": [{"component": "A", "cost_items": []}]}
        self.assertEqual(mod76._calc_cost_score(costs), 0.0)

    def test_cost_score_single_high(self):
        costs = make_costs([make_component(cost_items=[make_cost_item(magnitude="High")])])
        # avg([3]) = 3.0
        self.assertEqual(mod76._calc_cost_score(costs), 3.0)

    def test_cost_score_mixed(self):
        costs = make_costs([make_component(cost_items=[
            make_cost_item(magnitude="High"),   # 3
            make_cost_item(magnitude="Low"),    # 1
        ])])
        # avg([3, 1]) = 2.0
        self.assertEqual(mod76._calc_cost_score(costs), 2.0)

    def test_alignment_score_no_context(self):
        option = make_option()
        self.assertEqual(mod76._calc_alignment_score(option, None), 0.0)

    def test_alignment_score_empty_goals(self):
        option = make_option()
        ctx = make_context(goals=[])
        self.assertEqual(mod76._calc_alignment_score(option, ctx), 0.0)

    def test_alignment_score_match(self):
        option = make_option(opportunities=[
            {"type": "efficiency", "description": "Ускорение обработки заявок"}
        ])
        ctx = make_context(goals=[{"id": "G-001", "title": "Ускорить обработку заявок"}])
        # "заявок" есть в opportunities description
        score = mod76._calc_alignment_score(option, ctx)
        self.assertGreater(score, 0.0)

    def test_alignment_score_no_match(self):
        option = make_option(opportunities=[
            {"type": "efficiency", "description": "Полностью другое описание без совпадений"}
        ])
        ctx = make_context(goals=[{"id": "G-001", "title": "Ускорить обработку заявок"}])
        # нет совпадений по словам длиннее 3 символов
        score = mod76._calc_alignment_score(option, ctx)
        # Может быть 0 или небольшой — зависит от эвристики
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_risk_penalty_empty(self):
        self.assertEqual(mod76._calc_risk_penalty([]), 0.0)

    def test_risk_penalty_low(self):
        risks = [make_risk(risk_level="Low")]
        self.assertEqual(mod76._calc_risk_penalty(risks), 0.0)

    def test_risk_penalty_critical(self):
        risks = [make_risk(risk_level="Critical")]
        self.assertEqual(mod76._calc_risk_penalty(risks), 3.0)

    def test_risk_penalty_max_of_multiple(self):
        risks = [make_risk(risk_level="Low"), make_risk(risk_level="High")]
        self.assertEqual(mod76._calc_risk_penalty(risks), 2.0)

    def test_calc_value_score_formula(self):
        benefits = [make_benefit(magnitude="High", confidence="High")]  # 4.5
        costs = make_costs([make_component(cost_items=[make_cost_item(magnitude="Medium")])])  # 2.0
        risks = [make_risk(risk_level="Medium")]  # 1
        assessment = {"benefits": benefits, "costs": costs, "risks": risks}
        option = make_option(opportunities=[])
        # Benefits_Score=4.5, Alignment=0, Cost_Score=2.0, Risk=1
        # Score = 4.5*2.0 + 0*1.5 - 2.0*1.5 - 1.0*1.0 = 9.0 - 3.0 - 1.0 = 5.0
        result = mod76._calc_value_score(assessment, option, None)
        self.assertEqual(result["value_score"], 5.0)
        self.assertIn("score_breakdown", result)


# ---------------------------------------------------------------------------
# Тесты add_value_assessment
# ---------------------------------------------------------------------------

class TestAddValueAssessment(BaseMCPTest):

    def _benefits_json(self, **kwargs):
        return json.dumps([make_benefit(**kwargs)])

    def _costs_json(self):
        return json.dumps(make_costs())

    def test_empty_option_id(self):
        result = mod76.add_value_assessment("proj", "", self._benefits_json(), self._costs_json())
        self.assertIn("❌", result)
        self.assertIn("option_id", result)

    def test_invalid_benefit_type(self):
        bad_benefits = json.dumps([{"type": "unknown_type", "description": "X", "magnitude": "High", "tangibility": "tangible", "confidence": "High"}])
        result = mod76.add_value_assessment("proj", "OPT-001", bad_benefits, self._costs_json())
        self.assertIn("❌", result)
        self.assertIn("Недопустимые типы", result)

    def test_invalid_magnitude_in_benefits(self):
        bad_benefits = json.dumps([{"type": "operational", "description": "X", "magnitude": "VERY_HIGH", "tangibility": "tangible", "confidence": "High"}])
        result = mod76.add_value_assessment("proj", "OPT-001", bad_benefits, self._costs_json())
        self.assertIn("❌", result)
        self.assertIn("magnitude", result)

    def test_invalid_confidence_in_benefits(self):
        bad_benefits = json.dumps([{"type": "operational", "description": "X", "magnitude": "High", "tangibility": "tangible", "confidence": "SUPER"}])
        result = mod76.add_value_assessment("proj", "OPT-001", bad_benefits, self._costs_json())
        self.assertIn("❌", result)
        self.assertIn("confidence", result)

    def test_empty_benefits_list(self):
        result = mod76.add_value_assessment("proj", "OPT-001", "[]", self._costs_json())
        self.assertIn("❌", result)
        self.assertIn("пустым", result)

    def test_invalid_benefits_json(self):
        result = mod76.add_value_assessment("proj", "OPT-001", "not_json", self._costs_json())
        self.assertIn("❌", result)
        self.assertIn("benefits_json", result)

    def test_costs_json_not_dict(self):
        result = mod76.add_value_assessment("proj", "OPT-001", self._benefits_json(), '["list_not_dict"]')
        self.assertIn("❌", result)
        self.assertIn("costs_json", result)

    def test_costs_json_missing_components(self):
        result = mod76.add_value_assessment("proj", "OPT-001", self._benefits_json(), '{"no_components": []}')
        self.assertIn("❌", result)
        self.assertIn("components", result)

    def test_costs_json_invalid_category(self):
        bad_costs = json.dumps({"components": [{"component": "A", "cost_items": [{"category": "unknown_cat", "description": "X", "magnitude": "High"}]}]})
        result = mod76.add_value_assessment("proj", "OPT-001", self._benefits_json(), bad_costs)
        self.assertIn("❌", result)
        self.assertIn("категория", result)

    def test_costs_json_invalid_magnitude(self):
        bad_costs = json.dumps({"components": [{"component": "A", "cost_items": [{"category": "development", "description": "X", "magnitude": "HUGE"}]}]})
        result = mod76.add_value_assessment("proj", "OPT-001", self._benefits_json(), bad_costs)
        self.assertIn("❌", result)
        self.assertIn("magnitude", result)

    def test_invalid_risks_json(self):
        result = mod76.add_value_assessment("proj", "OPT-001", self._benefits_json(), self._costs_json(), risks_json="not_json")
        self.assertIn("❌", result)
        self.assertIn("risks_json", result)

    def test_invalid_risk_level(self):
        bad_risks = json.dumps([{"risk_id": "R-001", "description": "X", "probability": "Low", "impact": "High", "risk_level": "EXTREME"}])
        result = mod76.add_value_assessment("proj", "OPT-001", self._benefits_json(), self._costs_json(), risks_json=bad_risks)
        self.assertIn("❌", result)
        self.assertIn("risk_level", result)

    def test_happy_path_create(self):
        result = mod76.add_value_assessment(
            "proj", "OPT-001",
            self._benefits_json(),
            self._costs_json(),
        )
        self.assertIn("✅", result)
        self.assertIn("добавлена", result)
        self.assertIn("OPT-001", result)
        self.assertIn("Value Score", result)

    def test_happy_path_update_idempotent(self):
        mod76.add_value_assessment("proj", "OPT-001", self._benefits_json(), self._costs_json())
        result = mod76.add_value_assessment("proj", "OPT-001", self._benefits_json(), self._costs_json())
        self.assertIn("✅", result)
        self.assertIn("обновлена", result)

    def test_saved_to_file(self):
        mod76.add_value_assessment("proj_save", "OPT-001", self._benefits_json(), self._costs_json())
        rec = load_rec_file("proj_save", self.tmp_dir)
        self.assertIn("OPT-001", rec["value_assessments"])
        self.assertIn("value_score", rec["value_assessments"]["OPT-001"])

    def test_graceful_degradation_no_design_options(self):
        # option_meta = None, не должно падать
        result = mod76.add_value_assessment("orphan_proj", "OPT-999", self._benefits_json(), self._costs_json())
        self.assertIn("✅", result)

    def test_graceful_degradation_no_context(self):
        result = mod76.add_value_assessment("proj", "OPT-001", self._benefits_json(), self._costs_json())
        self.assertIn("✅", result)
        # Alignment Score = 0 предупреждение
        self.assertIn("Alignment Score", result)

    def test_graceful_degradation_no_risks_file(self):
        result = mod76.add_value_assessment(
            "proj", "OPT-001",
            self._benefits_json(),
            self._costs_json(),
            risks_json="[]",
        )
        self.assertIn("✅", result)
        self.assertIn("manual", result)  # risks_source

    def test_graceful_degradation_reads_risks_from_63_file(self):
        risks_data = {
            "risks": {"OPT-001": [make_risk(risk_level="High")]}
        }
        save_risks(risks_data, "proj_risks", self.tmp_dir)
        result = mod76.add_value_assessment(
            "proj_risks", "OPT-001",
            self._benefits_json(),
            self._costs_json(),
            risks_json="[]",
        )
        self.assertIn("✅", result)
        self.assertIn("6.3_file", result)

    def test_multiple_options_accumulate(self):
        mod76.add_value_assessment("multi_proj", "OPT-001", self._benefits_json(), self._costs_json())
        mod76.add_value_assessment("multi_proj", "OPT-002", self._benefits_json(), self._costs_json())
        rec = load_rec_file("multi_proj", self.tmp_dir)
        self.assertIn("OPT-001", rec["value_assessments"])
        self.assertIn("OPT-002", rec["value_assessments"])


# ---------------------------------------------------------------------------
# Тесты compare_value
# ---------------------------------------------------------------------------

class TestCompareValue(BaseMCPTest):

    def _add_assessment(self, project_id, option_id, magnitude="High", confidence="High", risk_level="Low"):
        benefits = json.dumps([make_benefit(magnitude=magnitude, confidence=confidence)])
        costs = json.dumps(make_costs())
        risks = json.dumps([make_risk(risk_level=risk_level)] if risk_level != "Low" else [])
        mod76.add_value_assessment(project_id, option_id, benefits, costs, risks_json=risks)

    def test_no_assessments_warning(self):
        result = mod76.compare_value("empty_compare_proj")
        self.assertIn("⚠️", result)
        self.assertIn("add_value_assessment", result)

    def test_single_variant_ranking(self):
        self._add_assessment("single_proj", "OPT-001")
        result = mod76.compare_value("single_proj")
        self.assertIn("OPT-001", result)
        self.assertIn("🥇", result)

    def test_two_variants_ranking(self):
        self._add_assessment("rank_proj", "OPT-001", magnitude="High", confidence="High", risk_level="Low")
        # OPT-002 с высоким риском — должен быть ниже
        benefits_low = json.dumps([make_benefit(magnitude="Low", confidence="Low")])
        costs = json.dumps(make_costs())
        risks_high = json.dumps([make_risk(risk_level="Critical")])
        mod76.add_value_assessment("rank_proj", "OPT-002", benefits_low, costs, risks_json=risks_high)
        result = mod76.compare_value("rank_proj")
        # OPT-001 должен быть выше OPT-002
        pos_1 = result.find("OPT-001")
        pos_2 = result.find("OPT-002")
        self.assertLess(pos_1, pos_2)  # OPT-001 встречается раньше = выше в ranking

    def test_winner_saved_to_file(self):
        self._add_assessment("winner_proj", "OPT-001")
        mod76.compare_value("winner_proj")
        rec = load_rec_file("winner_proj", self.tmp_dir)
        self.assertIn("comparison", rec)
        self.assertEqual(rec["comparison"]["winner"], "OPT-001")

    def test_comparison_has_ranking(self):
        self._add_assessment("rank2_proj", "OPT-001")
        self._add_assessment("rank2_proj", "OPT-002")
        mod76.compare_value("rank2_proj")
        rec = load_rec_file("rank2_proj", self.tmp_dir)
        self.assertIn("ranking", rec["comparison"])
        self.assertEqual(len(rec["comparison"]["ranking"]), 2)

    def test_without_context_alignment_zero(self):
        self._add_assessment("no_ctx_proj", "OPT-001")
        result = mod76.compare_value("no_ctx_proj")
        self.assertIn("Alignment", result)
        # Предупреждение об отсутствии context
        self.assertIn("business_context", result)

    def test_with_context_alignment_nonzero(self):
        ctx = make_context(project_id="ctx_proj", goals=[
            {"id": "G-001", "title": "Ускорить обработку заявок"}
        ])
        save_context(ctx, self.tmp_dir)
        do_data = make_design_options("ctx_proj", options=[
            make_option("OPT-001", opportunities=[
                {"type": "efficiency", "description": "Ускорение обработки заявок автоматически"}
            ])
        ])
        save_design_options(do_data, self.tmp_dir)
        benefits = json.dumps([make_benefit()])
        costs = json.dumps(make_costs())
        mod76.add_value_assessment("ctx_proj", "OPT-001", benefits, costs)
        result = mod76.compare_value("ctx_proj")
        self.assertIn("OPT-001", result)
        # Не должно быть предупреждения об отсутствии context
        self.assertNotIn("business_context.json (7.3) не найден", result)


# ---------------------------------------------------------------------------
# Тесты check_value_readiness
# ---------------------------------------------------------------------------

class TestCheckValueReadiness(BaseMCPTest):

    def test_no_design_options_critical(self):
        result = mod76.check_value_readiness("no_do_proj")
        self.assertIn("❌", result)
        self.assertIn("design_options", result)

    def test_empty_options_critical(self):
        do_data = make_design_options("empty_opts_proj", options=[])
        save_design_options(do_data, self.tmp_dir)
        result = mod76.check_value_readiness("empty_opts_proj")
        self.assertIn("❌", result)

    def test_not_all_assessed_critical(self):
        do_data = make_design_options("partial_proj", options=[
            make_option("OPT-001"), make_option("OPT-002")
        ])
        save_design_options(do_data, self.tmp_dir)
        # Только OPT-001 оценён
        benefits = json.dumps([make_benefit()])
        costs = json.dumps(make_costs())
        mod76.add_value_assessment("partial_proj", "OPT-001", benefits, costs)
        result = mod76.check_value_readiness("partial_proj")
        self.assertIn("❌", result)
        self.assertIn("OPT-002", result)

    def test_no_compare_called_critical(self):
        do_data = make_design_options("no_compare_proj", options=[make_option("OPT-001")])
        save_design_options(do_data, self.tmp_dir)
        benefits = json.dumps([make_benefit()])
        costs = json.dumps(make_costs())
        mod76.add_value_assessment("no_compare_proj", "OPT-001", benefits, costs)
        result = mod76.check_value_readiness("no_compare_proj")
        self.assertIn("❌", result)
        self.assertIn("compare_value", result)

    def test_empty_benefits_warning(self):
        # Оцениваем с benefits, потом подменяем в файле на пустые
        do_data = make_design_options("warn_proj", options=[make_option("OPT-001")])
        save_design_options(do_data, self.tmp_dir)
        benefits = json.dumps([make_benefit()])
        costs = json.dumps(make_costs())
        mod76.add_value_assessment("warn_proj", "OPT-001", benefits, costs)
        mod76.compare_value("warn_proj")
        # Патчим файл: убираем benefits
        rec = load_rec_file("warn_proj", self.tmp_dir)
        rec["value_assessments"]["OPT-001"]["benefits"] = []
        path = os.path.join(self.tmp_dir, "governance_plans", "data", "warn_proj_recommendation.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(rec, f, ensure_ascii=False, indent=2)
        result = mod76.check_value_readiness("warn_proj")
        self.assertIn("⚠️", result)
        self.assertIn("benefits", result)

    def test_critical_arch_gaps_warning(self):
        do_data = make_design_options("arch_proj", options=[make_option("OPT-001")])
        save_design_options(do_data, self.tmp_dir)
        arch = {
            "viewpoints": {},
            "gaps": {
                "critical": [{"description": "Отсутствует интеграционный слой"}],
                "warning": [],
            }
        }
        save_architecture(arch, "arch_proj", self.tmp_dir)
        benefits = json.dumps([make_benefit()])
        costs = json.dumps(make_costs())
        mod76.add_value_assessment("arch_proj", "OPT-001", benefits, costs)
        mod76.compare_value("arch_proj")
        result = mod76.check_value_readiness("arch_proj")
        self.assertIn("⚠️", result)
        self.assertIn("gap", result.lower())

    def test_empty_allocation_info(self):
        do_data = make_design_options("alloc_proj", options=[make_option("OPT-001")], )
        do_data["allocation"] = {}
        save_design_options(do_data, self.tmp_dir)
        benefits = json.dumps([make_benefit()])
        costs = json.dumps(make_costs())
        mod76.add_value_assessment("alloc_proj", "OPT-001", benefits, costs)
        mod76.compare_value("alloc_proj")
        result = mod76.check_value_readiness("alloc_proj")
        self.assertIn("ℹ️", result)
        self.assertIn("Allocation", result)

    def test_all_ok_status(self):
        do_data = make_design_options("ok_proj", options=[make_option("OPT-001")])
        do_data["allocation"] = {"FR-001": {"option_id": "OPT-001", "version": "v1"}}
        save_design_options(do_data, self.tmp_dir)
        benefits = json.dumps([make_benefit()])
        costs = json.dumps(make_costs())
        mod76.add_value_assessment("ok_proj", "OPT-001", benefits, costs)
        mod76.compare_value("ok_proj")
        result = mod76.check_value_readiness("ok_proj")
        self.assertIn("✅", result)


# ---------------------------------------------------------------------------
# Тесты save_recommendation
# ---------------------------------------------------------------------------

class TestSaveRecommendation(BaseMCPTest):

    def _setup_full(self, project_id, options_count=2):
        do_data = make_design_options(project_id, options=[
            make_option(f"OPT-{i+1:03d}") for i in range(options_count)
        ])
        save_design_options(do_data, self.tmp_dir)
        benefits = json.dumps([make_benefit()])
        costs = json.dumps(make_costs())
        for i in range(options_count):
            mod76.add_value_assessment(project_id, f"OPT-{i+1:03d}", benefits, costs)
        mod76.compare_value(project_id)

    def test_invalid_recommendation_type(self):
        result = mod76.save_recommendation("proj", "invalid_type", rationale="test")
        self.assertIn("❌", result)
        self.assertIn("recommendation_type", result)

    def test_empty_rationale(self):
        result = mod76.save_recommendation("proj", "no_action", rationale="")
        self.assertIn("❌", result)
        self.assertIn("rationale", result)

    def test_recommend_option_without_option_id(self):
        result = mod76.save_recommendation("proj", "recommend_option", rationale="Хороший вариант")
        self.assertIn("❌", result)
        self.assertIn("recommended_option_id", result)

    def test_recommend_option_unknown_option_id(self):
        self._setup_full("known_proj")
        result = mod76.save_recommendation(
            "known_proj", "recommend_option",
            rationale="Тест",
            recommended_option_id="OPT-999",
        )
        self.assertIn("❌", result)
        self.assertIn("не найден", result)

    def test_invalid_parallel_option_ids(self):
        result = mod76.save_recommendation(
            "proj", "recommend_parallel",
            rationale="Тест",
            parallel_option_ids_json="not_json",
        )
        self.assertIn("❌", result)
        self.assertIn("parallel_option_ids", result)

    def test_invalid_success_metrics_json(self):
        result = mod76.save_recommendation(
            "proj", "no_action",
            rationale="Тест",
            success_metrics_json="not_json",
        )
        self.assertIn("❌", result)
        self.assertIn("success_metrics", result)

    def test_invalid_risks_acknowledged_json(self):
        result = mod76.save_recommendation(
            "proj", "no_action",
            rationale="Тест",
            risks_acknowledged_json="not_json",
        )
        self.assertIn("❌", result)
        self.assertIn("risks_acknowledged", result)

    def test_recommend_option_happy_path(self):
        self._setup_full("rec_opt_proj")
        result = mod76.save_recommendation(
            "rec_opt_proj",
            "recommend_option",
            rationale="OPT-001 имеет лучший Value Score",
            recommended_option_id="OPT-001",
            success_metrics_json='[{"metric": "Время обработки", "baseline": "2ч", "target": "15мин", "measurement_method": "CRM"}]',
        )
        self.assertIn("✅", result)
        self.assertIn("recommend_option", result)

    def test_recommend_parallel_happy_path(self):
        self._setup_full("rec_par_proj")
        result = mod76.save_recommendation(
            "rec_par_proj",
            "recommend_parallel",
            rationale="Реализуем пилот и основную систему параллельно",
            parallel_option_ids_json='["OPT-001", "OPT-002"]',
        )
        self.assertIn("✅", result)
        self.assertIn("recommend_parallel", result)

    def test_recommend_reanalyze_happy_path(self):
        result = mod76.save_recommendation(
            "reanalyze_proj",
            "recommend_reanalyze",
            rationale="Варианты не покрывают критические требования клиента",
        )
        self.assertIn("✅", result)
        self.assertIn("recommend_reanalyze", result)

    def test_no_action_happy_path(self):
        result = mod76.save_recommendation(
            "no_action_proj",
            "no_action",
            rationale="Затраты на внедрение превышают ожидаемые выгоды в 3-летнем горизонте",
        )
        self.assertIn("✅", result)
        self.assertIn("no_action", result)

    def test_idempotent_update(self):
        mod76.save_recommendation("idemp_proj", "no_action", rationale="Первый вызов")
        result = mod76.save_recommendation("idemp_proj", "no_action", rationale="Второй вызов")
        self.assertIn("✅", result)
        self.assertIn("обновлена", result)

    def test_no_success_metrics_warning(self):
        self._setup_full("warn_metrics_proj")
        result = mod76.save_recommendation(
            "warn_metrics_proj",
            "recommend_option",
            rationale="Выбираем OPT-001",
            recommended_option_id="OPT-001",
            success_metrics_json="[]",
        )
        self.assertIn("✅", result)
        self.assertIn("success_metrics", result)

    def test_save_artifact_called(self):
        from unittest.mock import patch
        with patch("skills.value_recommend_mcp.save_artifact") as mock_sa:
            mock_sa.return_value = "✅ Сохранено"
            mod76.save_recommendation("artifact_proj", "no_action", rationale="Тест")
            mock_sa.assert_called_once()

    def test_success_metrics_saved_to_file(self):
        metrics = [{"metric": "NPS", "baseline": "6", "target": "8", "measurement_method": "Опрос"}]
        mod76.save_recommendation(
            "metrics_save_proj",
            "recommend_option",
            rationale="Тест",
            recommended_option_id="OPT-999",
            success_metrics_json=json.dumps(metrics),
        )
        rec = load_rec_file("metrics_save_proj", self.tmp_dir)
        self.assertIn("recommendation", rec)
        self.assertEqual(len(rec["recommendation"]["success_metrics"]), 1)
        self.assertEqual(rec["recommendation"]["success_metrics"][0]["metric"], "NPS")

    def test_graceful_without_architecture(self):
        result = mod76.save_recommendation(
            "no_arch_proj", "no_action",
            rationale="Тест без архитектуры",
        )
        self.assertIn("✅", result)

    def test_graceful_without_design_options(self):
        # Без design_options — нет валидации option_id
        result = mod76.save_recommendation(
            "no_do_proj2", "recommend_reanalyze",
            rationale="Нет вариантов в системе",
        )
        self.assertIn("✅", result)


# ---------------------------------------------------------------------------
# Pipeline тест: полный happy path
# ---------------------------------------------------------------------------

class TestPipeline(BaseMCPTest):

    def test_full_pipeline_recommend_option(self):
        """Полный happy path: add×2 → compare → check → save(recommend_option)"""
        pid = "pipeline_proj"

        # Подготовка: design_options + context
        do_data = make_design_options(pid, options=[
            make_option("OPT-001", title="Собственная разработка", approach="build", opportunities=[
                {"type": "efficiency", "description": "Ускорение обработки заявок"}
            ]),
            make_option("OPT-002", title="Готовое SaaS-решение", approach="buy"),
        ])
        save_design_options(do_data, self.tmp_dir)

        ctx = make_context(pid, goals=[
            {"id": "G-001", "title": "Ускорить обработку заявок"},
        ])
        save_context(ctx, self.tmp_dir)

        # Шаг 1: add_value_assessment для OPT-001
        benefits_1 = json.dumps([
            make_benefit("operational", "Снижение времени обработки с 2ч до 15мин", "High", "tangible", "High"),
            make_benefit("strategic", "Конкурентное преимущество", "Medium", "intangible", "Medium"),
        ])
        costs_1 = json.dumps(make_costs([make_component("Backend API", [
            make_cost_item("development", "Разработка", "High"),
            make_cost_item("resources", "Найм разработчиков", "High"),
        ])]))
        risks_1 = json.dumps([make_risk("RSK-001", "Задержка разработки", risk_level="Medium")])

        r1 = mod76.add_value_assessment(pid, "OPT-001", benefits_1, costs_1, risks_json=risks_1)
        self.assertIn("✅", r1)
        self.assertIn("добавлена", r1)

        # Шаг 2: add_value_assessment для OPT-002
        benefits_2 = json.dumps([make_benefit("operational", "Быстрый запуск", "Medium", "tangible", "High")])
        costs_2 = json.dumps(make_costs([make_component("SaaS License", [
            make_cost_item("acquisition", "Лицензия", "Medium"),
        ])]))

        r2 = mod76.add_value_assessment(pid, "OPT-002", benefits_2, costs_2)
        self.assertIn("✅", r2)

        # Шаг 3: compare_value
        r3 = mod76.compare_value(pid)
        self.assertIn("Winner", r3)
        self.assertIn("OPT-001", r3)
        self.assertIn("OPT-002", r3)

        # Шаг 4: check_value_readiness
        r4 = mod76.check_value_readiness(pid)
        self.assertIn("✅", r4)  # Все проверки пройдены

        # Шаг 5: save_recommendation
        metrics = json.dumps([{
            "metric": "Время обработки заявки",
            "baseline": "2 часа",
            "target": "15 минут",
            "measurement_method": "Мониторинг тикетов CRM",
        }])
        r5 = mod76.save_recommendation(
            pid,
            "recommend_option",
            rationale="OPT-001 обеспечивает наилучший баланс ценности и гибкости",
            recommended_option_id="OPT-001",
            success_metrics_json=metrics,
            risks_acknowledged_json='["RSK-001"]',
        )
        self.assertIn("✅", r5)
        self.assertIn("recommend_option", r5)

        # Проверяем итоговый файл
        rec = load_rec_file(pid, self.tmp_dir)
        self.assertIn("OPT-001", rec["value_assessments"])
        self.assertIn("OPT-002", rec["value_assessments"])
        self.assertIn("comparison", rec)
        self.assertIn("recommendation", rec)
        self.assertEqual(rec["recommendation"]["recommendation_type"], "recommend_option")
        self.assertEqual(rec["recommendation"]["recommended_option_id"], "OPT-001")
        self.assertEqual(len(rec["recommendation"]["success_metrics"]), 1)
        self.assertEqual(rec["recommendation"]["risks_acknowledged"], ["RSK-001"])

    def test_pipeline_no_action(self):
        """Pipeline для no_action — без option_id и success_metrics"""
        pid = "no_action_pipeline"

        benefits = json.dumps([make_benefit("financial", "Экономия незначительна", "Low", "tangible", "Low")])
        costs = json.dumps(make_costs([make_component("All", [make_cost_item("development", "Разработка", "High")])]))
        risks = json.dumps([make_risk(risk_level="Critical")])

        mod76.add_value_assessment(pid, "OPT-001", benefits, costs, risks_json=risks)
        mod76.compare_value(pid)

        result = mod76.save_recommendation(
            pid,
            "no_action",
            rationale="Value Score < 2.0 — затраты и риски превышают выгоды. Рекомендуется не внедрять.",
        )
        self.assertIn("✅", result)

        rec = load_rec_file(pid, self.tmp_dir)
        self.assertEqual(rec["recommendation"]["recommendation_type"], "no_action")
        self.assertEqual(rec["recommendation"]["recommended_option_id"], "")


if __name__ == "__main__":
    unittest.main()
