"""
tests/test_ch7_71.py — Tests for Chapter 7, task 7.1 (Specify and Model Requirements)

Coverage (~70 tests):
  - Utilities: _repo_path, _load_repo, _save_repo, _register_in_repo, _specs_dir,
             _find_confirmed_artifact, _save_spec
  - analyze_elicitation_context: file found, context_text fallback, both absent
  - create_user_story: success, not enough AC, bad JSON, duplicate in the registry
  - create_functional_requirement: all three types, invalid type, related_ids
  - create_use_case: success, alternatives/exceptions, without secondary actors
  - generate_use_case_diagram: UC present, no UC, actor from the specification file
  - create_business_process: success, .md and .puml files, registration
  - create_data_dictionary: success, bad JSON, empty list
  - create_erd: success, cardinality notation, bad JSON
  - build_coverage_matrix: with requirements, without requirements, coverage flags
  - Integration: full pipeline (analyze -> create -> coverage)
"""

import json
import os
import sys
import unittest
from datetime import date

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Mocks are applied via conftest
from tests.conftest import BaseMCPTest, make_test_repo, save_test_repo, load_test_repo

import skills.requirements_spec_mcp as mod71
from skills.common import data_path


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def make_spec_repo(project_id: str, requirements: list = None) -> dict:
    """Creates and saves a 5.1 repository with the given requirements."""
    repo = {
        "project": project_id,
        "formality_level": "Standard",
        "created": str(date.today()),
        "updated": str(date.today()),
        "requirements": requirements or [],
        "links": [],
        "history": [],
    }
    return repo


def save_spec_repo(repo: dict, governance_dir: str = "governance_plans/data") -> str:
    """Saves the 5.1 repository for the tests."""
    safe = repo["project"].lower().replace(" ", "_")
    path = os.path.join(governance_dir, f"{safe}_traceability_repo.json")
    os.makedirs(governance_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(repo, f, ensure_ascii=False, indent=2)
    return path


def load_spec_repo(project_id: str, governance_dir: str = "governance_plans/data") -> dict:
    """Loads the 5.1 repository."""
    safe = project_id.lower().replace(" ", "_")
    path = data_path(project_id, f"{safe}_traceability_repo.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def make_confirmed_artifact_reports(project_id: str, content: str = None) -> str:
    """Creates a test 4.3 artifact in the REAL producer layout and returns the path.

    The 4.3 producer (save_confirmed_elicitation_result -> save_artifact) writes to
    reports/<project_id>/4_3_confirmed_result_<timestamp>.md (project_id is the FOLDER,
    NOT part of the filename). This helper reproduces that real contract, unlike the
    legacy make_confirmed_artifact which wrote to a flat data/ with pid in the name.
    """
    from skills.common import report_dir_for
    d = report_dir_for(project_id)
    os.makedirs(d, exist_ok=True)
    filename = "4_3_confirmed_result_20260101_000000.md"
    path = os.path.join(d, filename)
    artifact_content = content or """# Confirmed elicitation results

## Business objectives

1. Reduce application processing time to 2 days
2. Automate the distribution of applications between managers
3. Provide process transparency for the customer
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(artifact_content)
    return path


def make_confirmed_artifact(project_id: str, content: str = None) -> str:
    """Creates a test 4.3 artifact and returns the path."""
    safe = project_id.lower().replace(" ", "_")
    filename = f"4_3_{safe}_confirmed_test.md"
    path = os.path.join("governance_plans", "data", filename)
    os.makedirs(os.path.join("governance_plans", "data"), exist_ok=True)
    artifact_content = content or f"""# Confirmed elicitation results

## Business objectives

1. Reduce application processing time to 2 days
2. Automate the distribution of applications between managers
3. Provide process transparency for the customer

## Elicited needs

- Managers want to see all active applications in one place
- The head wants to receive reports on manager performance
- The customer wants to know the status of their application

## Non-functional requirements

- The system must operate 24/7
- Response time no more than 3 seconds
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(artifact_content)
    return path


# ---------------------------------------------------------------------------
# 7.1 — Utility tests
# ---------------------------------------------------------------------------

class TestSpecUtilities(unittest.TestCase):

    def test_repo_path_normalizes_spaces(self):
        path = mod71._repo_path("My Project")
        self.assertNotIn(" ", path)
        self.assertIn("my_project", path)
        self.assertIn("traceability_repo.json", path)

    def test_repo_path_lowercase(self):
        path = mod71._repo_path("CRM 2024")
        self.assertIn("crm_2024", path)

    def test_specs_dir_format(self):
        # issue #1: specs in data/<project>/specs/ (new nested layout)
        d = mod71._specs_dir("crm_2024")
        self.assertIn(os.path.join("crm_2024", "specs"), d)
        self.assertIn("governance_plans", d)

    def test_specs_dir_normalizes_spaces(self):
        d = mod71._specs_dir("My Project")
        self.assertNotIn(" ", d)
        self.assertIn(os.path.join("my_project", "specs"), d)

    def test_load_repo_empty_when_missing(self):
        """Loading a non-existent repository returns an empty structure."""
        repo = mod71._load_repo("nonexistent_project_xyz")
        self.assertEqual(repo["project"], "nonexistent_project_xyz")
        self.assertEqual(repo["requirements"], [])
        self.assertEqual(repo["links"], [])
        self.assertEqual(repo["history"], [])

    def test_load_repo_preserves_formality(self):
        repo = mod71._load_repo("nonexistent_project_xyz")
        self.assertIn("formality_level", repo)

    def test_cardinality_map_complete(self):
        """All required cardinality types are present in the notation."""
        # Check via create_erd with different cardinality values
        expected = [
            "one-to-one", "one-to-many", "many-to-one",
            "many-to-many", "zero-or-one-to-many"
        ]
        # Make sure the mapping exists in the module
        # (indirect check via the string in the source)
        import inspect
        source = inspect.getsource(mod71.create_erd)
        for card in expected:
            self.assertIn(card, source)


class TestRegisterInRepo(BaseMCPTest):
    """Tests for the _register_in_repo function (ADR-022)."""

    P = "reg_test_proj"

    def test_register_creates_repo_if_missing(self):
        """If the repository does not exist — creates it."""
        mod71._register_in_repo(self.P, "FR-001", "functional", "Test", "test.md")
        repo = load_spec_repo(self.P)
        self.assertEqual(len(repo["requirements"]), 1)
        self.assertEqual(repo["requirements"][0]["id"], "FR-001")

    def test_register_status_is_draft(self):
        mod71._register_in_repo(self.P, "FR-001", "functional", "Test", "test.md")
        repo = load_spec_repo(self.P)
        self.assertEqual(repo["requirements"][0]["status"], "draft")

    def test_register_version_is_1_0(self):
        mod71._register_in_repo(self.P, "US-001", "user_story", "Story", "test.md")
        repo = load_spec_repo(self.P)
        self.assertEqual(repo["requirements"][0]["version"], "1.0")

    def test_register_writes_history(self):
        mod71._register_in_repo(self.P, "UC-001", "use_case", "Scenario", "test.md")
        repo = load_spec_repo(self.P)
        self.assertTrue(len(repo["history"]) > 0)
        self.assertEqual(repo["history"][0]["req_id"], "UC-001")

    def test_register_no_duplicate(self):
        """Re-registering one ID does not create a duplicate."""
        mod71._register_in_repo(self.P, "FR-001", "functional", "Test", "test.md")
        mod71._register_in_repo(self.P, "FR-001", "functional", "Test v2", "test2.md")
        repo = load_spec_repo(self.P)
        count = sum(1 for r in repo["requirements"] if r["id"] == "FR-001")
        self.assertEqual(count, 1)

    def test_register_duplicate_returns_info(self):
        mod71._register_in_repo(self.P, "FR-001", "functional", "Test", "test.md")
        result = mod71._register_in_repo(self.P, "FR-001", "functional", "Test v2", "test2.md")
        self.assertIn("is already registered", result)

    def test_register_priority_stored(self):
        mod71._register_in_repo(self.P, "BR-001", "business_rule", "Rule", "test.md", "High")
        repo = load_spec_repo(self.P)
        self.assertEqual(repo["requirements"][0]["priority"], "High")

    def test_register_multiple_different_ids(self):
        for i in range(5):
            mod71._register_in_repo(self.P, f"FR-{i:03d}", "functional", f"Req {i}", "test.md")
        repo = load_spec_repo(self.P)
        self.assertEqual(len(repo["requirements"]), 5)


# ---------------------------------------------------------------------------
# 7.1.1 — analyze_elicitation_context
# ---------------------------------------------------------------------------

class TestAnalyzeElicitationContext(BaseMCPTest):

    P = "analyze_test"

    def test_returns_guide_when_no_file_no_text(self):
        """Without a file and without text — returns instructions."""
        result = mod71.analyze_elicitation_context(self.P)
        self.assertIn("not found", result)
        self.assertIn("context_text", result)

    def test_uses_file_when_found(self):
        """If the 4.3 file is found — uses it."""
        make_confirmed_artifact(self.P)
        result = mod71.analyze_elicitation_context(self.P)
        self.assertIn("File found", result)
        self.assertNotIn("not found", result.split("##")[0])

    def test_uses_context_text_when_no_file(self):
        """If the file is not found but context_text is passed — uses the text."""
        result = mod71.analyze_elicitation_context(
            "nonexistent_project_42",
            context_text="Business objectives: 1. Speed up the process. Stakeholder needs: ..."
        )
        self.assertIn("manually", result)

    def test_shows_analysis_guide(self):
        """The result contains the analysis instructions for Claude Code."""
        make_confirmed_artifact(self.P)
        result = mod71.analyze_elicitation_context(self.P)
        self.assertIn("Analysis instructions", result)

    def test_shows_classification_table(self):
        """The result contains the requirement types table."""
        result = mod71.analyze_elicitation_context(
            "proj_text", context_text="Contents of the 4.3 artifact"
        )
        self.assertIn("user_story", result)
        self.assertIn("functional", result)

    def test_context_text_overrides_file_not_found(self):
        """context_text allows working without a file."""
        result = mod71.analyze_elicitation_context(
            "completely_new_project_99",
            context_text="Requirements: an application tracking system is needed"
        )
        self.assertNotIn("Options", result)
        self.assertIn("Next step", result)


# ---------------------------------------------------------------------------
# 7.1.2 — create_user_story
# ---------------------------------------------------------------------------

class TestCreateUserStory(BaseMCPTest):

    P = "us_test"

    def _make(self, story_id="US-001", criteria=None):
        if criteria is None:
            criteria = ["The system saves the application with an ID", "The manager receives a notification"]
        return mod71.create_user_story(
            project_id=self.P,
            story_id=story_id,
            title="Create a loan application",
            role="Manager",
            action="create a new application",
            benefit="the application enters the processing queue",
            acceptance_criteria_json=json.dumps(criteria),
            priority="High",
            source_artifact="governance_plans/4_3_test_confirmed.md",
        )

    def test_success_contains_story_id(self):
        result = self._make()
        self.assertIn("US-001", result)

    def test_success_contains_as_a(self):
        result = self._make()
        self.assertIn("As a", result)
        self.assertIn("I want", result)
        self.assertIn("So that", result)

    def test_success_contains_acceptance_criteria(self):
        result = self._make()
        self.assertIn("Acceptance Criteria", result)
        self.assertIn("The system saves the application with an ID", result)

    def test_success_registers_in_repo(self):
        self._make()
        repo = load_spec_repo(self.P)
        ids = [r["id"] for r in repo["requirements"]]
        self.assertIn("US-001", ids)

    def test_registered_type_is_user_story(self):
        self._make()
        repo = load_spec_repo(self.P)
        req = next(r for r in repo["requirements"] if r["id"] == "US-001")
        self.assertEqual(req["type"], "user_story")

    def test_registered_status_is_draft(self):
        self._make()
        repo = load_spec_repo(self.P)
        req = next(r for r in repo["requirements"] if r["id"] == "US-001")
        self.assertEqual(req["status"], "draft")

    def test_creates_md_file(self):
        self._make()
        specs_dir = mod71._specs_dir(self.P)
        files = os.listdir(specs_dir)
        self.assertTrue(any("us_001" in f for f in files))

    def test_too_few_criteria_returns_error(self):
        """Fewer than 2 criteria — error."""
        result = mod71.create_user_story(
            project_id=self.P, story_id="US-002", title="T",
            role="R", action="A", benefit="B",
            acceptance_criteria_json=json.dumps(["Only one criterion"]),
        )
        self.assertIn("❌", result)
        self.assertIn("At least 2", result)

    def test_invalid_json_returns_error(self):
        result = mod71.create_user_story(
            project_id=self.P, story_id="US-003", title="T",
            role="R", action="A", benefit="B",
            acceptance_criteria_json="not JSON",
        )
        self.assertIn("❌", result)

    def test_notes_included_when_provided(self):
        result = mod71.create_user_story(
            project_id=self.P, story_id="US-004", title="T",
            role="R", action="A", benefit="B",
            acceptance_criteria_json=json.dumps(["AC1", "AC2"]),
            notes="Important context for the developer",
        )
        self.assertIn("Important context for the developer", result)

    def test_multiple_stories_no_duplication_in_repo(self):
        """Several stories — each is registered once."""
        for i in range(3):
            self._make(story_id=f"US-{i + 1:03d}")
        repo = load_spec_repo(self.P)
        ids = [r["id"] for r in repo["requirements"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_priority_stored_in_repo(self):
        self._make()
        repo = load_spec_repo(self.P)
        req = next(r for r in repo["requirements"] if r["id"] == "US-001")
        self.assertEqual(req["priority"], "High")


# ---------------------------------------------------------------------------
# 7.1.3 — create_functional_requirement
# ---------------------------------------------------------------------------

class TestCreateFunctionalRequirement(BaseMCPTest):

    P = "fr_test"

    def _make(self, req_id="FR-001", req_type="functional"):
        return mod71.create_functional_requirement(
            project_id=self.P,
            req_id=req_id,
            req_type=req_type,
            title="Automatic distribution of applications",
            description="The system SHALL automatically distribute applications.",
            rationale="Reduces the load on managers.",
            priority="High",
            owner="Department head",
            source_artifact="governance_plans/4_3_test.md",
        )

    def test_functional_success(self):
        result = self._make("FR-001", "functional")
        self.assertIn("FR-001", result)
        self.assertIn("Functional requirement", result)

    def test_non_functional_success(self):
        result = self._make("NFR-001", "non_functional")
        self.assertIn("NFR-001", result)
        self.assertIn("Non-functional requirement", result)

    def test_business_rule_success(self):
        result = self._make("BR-001", "business_rule")
        self.assertIn("BR-001", result)
        self.assertIn("Business rule", result)

    def test_invalid_type_returns_error(self):
        result = mod71.create_functional_requirement(
            project_id=self.P, req_id="XX-001", req_type="unknown_type",
            title="T", description="D", rationale="R",
        )
        self.assertIn("❌", result)
        self.assertIn("req_type", result)

    def test_registers_functional_type_in_repo(self):
        self._make("FR-001", "functional")
        repo = load_spec_repo(self.P)
        req = next(r for r in repo["requirements"] if r["id"] == "FR-001")
        self.assertEqual(req["type"], "functional")

    def test_registers_non_functional_type(self):
        self._make("NFR-001", "non_functional")
        repo = load_spec_repo(self.P)
        req = next(r for r in repo["requirements"] if r["id"] == "NFR-001")
        self.assertEqual(req["type"], "non_functional")

    def test_registers_business_rule_type(self):
        self._make("BR-001", "business_rule")
        repo = load_spec_repo(self.P)
        req = next(r for r in repo["requirements"] if r["id"] == "BR-001")
        self.assertEqual(req["type"], "business_rule")

    def test_creates_md_file(self):
        self._make()
        specs_dir = mod71._specs_dir(self.P)
        files = os.listdir(specs_dir)
        self.assertTrue(any("fr_001" in f for f in files))

    def test_related_ids_valid_json(self):
        result = mod71.create_functional_requirement(
            project_id=self.P, req_id="FR-002", req_type="functional",
            title="T", description="D", rationale="R",
            related_ids_json='["BR-001", "UC-001"]',
        )
        self.assertIn("BR-001", result)
        self.assertIn("UC-001", result)

    def test_related_ids_invalid_json_fallback(self):
        """Invalid related_ids_json — does not crash, just ignores it."""
        result = mod71.create_functional_requirement(
            project_id=self.P, req_id="FR-003", req_type="functional",
            title="T", description="D", rationale="R",
            related_ids_json="not_json",
        )
        self.assertIn("FR-003", result)
        # Must not crash with a registration error
        repo = load_spec_repo(self.P)
        ids = [r["id"] for r in repo["requirements"]]
        self.assertIn("FR-003", ids)

    def test_constraints_included_when_provided(self):
        result = mod71.create_functional_requirement(
            project_id=self.P, req_id="FR-004", req_type="functional",
            title="T", description="D", rationale="R",
            constraints="Works only during business hours (9:00-18:00)",
        )
        self.assertIn("Constraints", result)
        self.assertIn("business hours", result)

    def test_formulation_hint_in_output(self):
        """The output contains a statement hint for the type."""
        result = self._make("FR-005", "functional")
        self.assertIn("SHALL", result)


# ---------------------------------------------------------------------------
# 7.1.4 — create_use_case
# ---------------------------------------------------------------------------

class TestCreateUseCase(BaseMCPTest):

    P = "uc_test"

    def _make(self, uc_id="UC-001"):
        return mod71.create_use_case(
            project_id=self.P,
            uc_id=uc_id,
            title="Review the application",
            primary_actor="Credit analyst",
            precondition="Application in status 'Under review'",
            postcondition="Application approved or rejected",
            trigger="The analyst opens the application",
            main_scenario="1. The analyst opens the application.\n2. The system displays the data.",
            priority="High",
            source_artifact="governance_plans/4_3_test.md",
        )

    def test_success_contains_uc_id(self):
        result = self._make()
        self.assertIn("UC-001", result)

    def test_success_contains_actors(self):
        result = self._make()
        self.assertIn("Credit analyst", result)

    def test_success_contains_happy_path(self):
        result = self._make()
        self.assertIn("Happy Path", result)

    def test_success_contains_precondition(self):
        result = self._make()
        self.assertIn("Precondition", result)

    def test_registers_use_case_type(self):
        self._make()
        repo = load_spec_repo(self.P)
        req = next(r for r in repo["requirements"] if r["id"] == "UC-001")
        self.assertEqual(req["type"], "use_case")

    def test_creates_md_file(self):
        self._make()
        specs_dir = mod71._specs_dir(self.P)
        files = os.listdir(specs_dir)
        self.assertTrue(any("uc_001" in f for f in files))

    def test_alt_scenarios_included(self):
        result = mod71.create_use_case(
            project_id=self.P, uc_id="UC-002",
            title="Apply for a loan",
            primary_actor="Customer",
            precondition="Customer is authorized",
            postcondition="Application created",
            trigger="The customer clicked 'Submit application'",
            main_scenario="1. The customer fills in the form.\n2. The system saves it.",
            alt_scenarios="1a. The customer entered incorrect data: the system raises an error.",
        )
        self.assertIn("Alternative", result)
        self.assertIn("incorrect data", result)

    def test_exc_scenarios_included(self):
        result = mod71.create_use_case(
            project_id=self.P, uc_id="UC-003",
            title="Get a certificate",
            primary_actor="Customer",
            precondition="Authorized",
            postcondition="Certificate issued",
            trigger="Customer request",
            main_scenario="1. The customer requests a certificate.",
            exc_scenarios="Xa. The service is unavailable: notify the customer.",
        )
        self.assertIn("Exception", result)

    def test_secondary_actors_included(self):
        result = mod71.create_use_case(
            project_id=self.P, uc_id="UC-004",
            title="Check the scoring",
            primary_actor="Analyst",
            secondary_actors="Scoring system, Security service",
            precondition="Application is open",
            postcondition="Scoring obtained",
            trigger="Analyst request",
            main_scenario="1. The analyst requests the scoring.",
        )
        self.assertIn("Security service", result)


# ---------------------------------------------------------------------------
# 7.1.5 — generate_use_case_diagram
# ---------------------------------------------------------------------------

class TestGenerateUseCaseDiagram(BaseMCPTest):

    P = "ucd_test"

    def _seed_use_cases(self):
        """Create several UCs in the repository."""
        repo = make_spec_repo(self.P, [
            {"id": "UC-001", "type": "use_case", "title": "Submit an application",
             "version": "1.0", "status": "draft", "priority": "High", "added": str(date.today())},
            {"id": "UC-002", "type": "use_case", "title": "Review an application",
             "version": "1.0", "status": "draft", "priority": "High", "added": str(date.today())},
            {"id": "FR-001", "type": "functional", "title": "FR not UC",
             "version": "1.0", "status": "draft", "priority": "Medium", "added": str(date.today())},
        ])
        save_spec_repo(repo)

    def test_no_use_cases_returns_warning(self):
        """If there are no UCs — returns a warning."""
        repo = make_spec_repo(self.P, [
            {"id": "FR-001", "type": "functional", "title": "FR",
             "version": "1.0", "status": "draft", "added": str(date.today())}
        ])
        save_spec_repo(repo)
        result = mod71.generate_use_case_diagram(self.P, "Test")
        self.assertIn("⚠️", result)
        self.assertIn("Use Cases", result)

    def test_generates_plantuml(self):
        self._seed_use_cases()
        result = mod71.generate_use_case_diagram(self.P, "CRM system")
        self.assertIn("@startuml", result)
        self.assertIn("@enduml", result)

    def test_contains_system_boundary(self):
        self._seed_use_cases()
        result = mod71.generate_use_case_diagram(self.P, "CRM system")
        self.assertIn("CRM system", result)

    def test_all_ucs_on_diagram(self):
        self._seed_use_cases()
        result = mod71.generate_use_case_diagram(self.P, "CRM")
        self.assertIn("Submit an application", result)
        self.assertIn("Review an application", result)

    def test_fr_not_on_diagram(self):
        """Functional requirements do not appear on the UC Diagram."""
        self._seed_use_cases()
        result = mod71.generate_use_case_diagram(self.P, "CRM")
        # FR-001 should be in the table but not as a UC
        # The diagram must not contain "FR not UC" as a usecase
        puml_block = result.split("```plantuml")[1].split("```")[0] if "```plantuml" in result else result
        self.assertNotIn("FR not UC", puml_block)

    def test_creates_puml_file(self):
        self._seed_use_cases()
        mod71.generate_use_case_diagram(self.P, "CRM", diagram_name="test_diagram")
        specs_dir = mod71._specs_dir(self.P)
        files = os.listdir(specs_dir)
        self.assertTrue(any("test_diagram.puml" in f for f in files))

    def test_custom_diagram_name(self):
        self._seed_use_cases()
        result = mod71.generate_use_case_diagram(self.P, "CRM", diagram_name="my_uc_diagram")
        self.assertIn("my_uc_diagram", result)


# ---------------------------------------------------------------------------
# 7.1.6 — create_business_process
# ---------------------------------------------------------------------------

class TestCreateBusinessProcess(BaseMCPTest):

    P = "bp_test"

    def _make(self, bp_id="BP-001"):
        return mod71.create_business_process(
            project_id=self.P,
            bp_id=bp_id,
            title="Application processing",
            process_owner="Department head",
            trigger="The customer submits an application",
            outcome="Application approved or closed",
            participants="Manager, Analyst, System",
            steps="1. Manager: accept the application.\n2. Analyst: check the documents.\n3. System: notify the customer.",
            priority="High",
            source_artifact="governance_plans/4_3_test.md",
        )

    def test_success_contains_bp_id(self):
        result = self._make()
        self.assertIn("BP-001", result)

    def test_success_contains_trigger(self):
        result = self._make()
        self.assertIn("The customer submits an application", result)

    def test_success_contains_plantuml(self):
        """ADR-024: must contain a PlantUML Activity Diagram."""
        result = self._make()
        self.assertIn("@startuml", result)
        self.assertIn("@enduml", result)

    def test_success_contains_activity_start_stop(self):
        result = self._make()
        self.assertIn("start", result)
        self.assertIn("stop", result)

    def test_creates_md_file(self):
        """ADR-024: creates a .md file."""
        self._make()
        specs_dir = mod71._specs_dir(self.P)
        files = os.listdir(specs_dir)
        self.assertTrue(any("bp_001" in f and f.endswith(".md") for f in files))

    def test_creates_puml_file(self):
        """ADR-024: creates a .puml file."""
        self._make()
        specs_dir = mod71._specs_dir(self.P)
        files = os.listdir(specs_dir)
        self.assertTrue(any("bp_001" in f and f.endswith(".puml") for f in files))

    def test_registers_in_repo(self):
        self._make()
        repo = load_spec_repo(self.P)
        ids = [r["id"] for r in repo["requirements"]]
        self.assertIn("BP-001", ids)

    def test_registered_type_is_business_process(self):
        self._make()
        repo = load_spec_repo(self.P)
        req = next(r for r in repo["requirements"] if r["id"] == "BP-001")
        self.assertEqual(req["type"], "business_process")

    def test_business_rules_included(self):
        result = mod71.create_business_process(
            project_id=self.P, bp_id="BP-002",
            title="Loan disbursement",
            process_owner="Director",
            trigger="Decision made",
            outcome="Loan disbursed",
            participants="Teller",
            steps="1. Teller: hand out the money.",
            business_rules="Maximum amount — 1,000,000.",
        )
        self.assertIn("Business rules", result)
        self.assertIn("1,000,000", result)

    def test_metrics_included(self):
        result = mod71.create_business_process(
            project_id=self.P, bp_id="BP-003",
            title="Document verification",
            process_owner="Analyst",
            trigger="Application received",
            outcome="Documents verified",
            participants="Analyst",
            steps="1. Analyst: checks.",
            metrics="Average time: 30 minutes.",
        )
        self.assertIn("Process metrics", result)


# ---------------------------------------------------------------------------
# 7.1.7 — create_data_dictionary
# ---------------------------------------------------------------------------

class TestCreateDataDictionary(BaseMCPTest):

    P = "dd_test"

    def _make_entities(self):
        return json.dumps([
            {
                "name": "Application",
                "description": "Loan application",
                "attributes": [
                    {"name": "id", "type": "Integer", "required": True,
                     "constraints": "PK, AUTO_INCREMENT", "description": "Application ID"},
                    {"name": "status", "type": "Enum", "required": True,
                     "constraints": "draft|submitted|approved|rejected", "description": "Status"},
                ],
                "business_rules": ["The status changes only per business rules"]
            }
        ])

    def test_success_contains_dd_id(self):
        result = mod71.create_data_dictionary(
            self.P, "DD-001", "CRM entities", self._make_entities()
        )
        self.assertIn("DD-001", result)

    def test_success_contains_entity_name(self):
        result = mod71.create_data_dictionary(
            self.P, "DD-001", "CRM entities", self._make_entities()
        )
        self.assertIn("Application", result)

    def test_success_contains_attributes_table(self):
        result = mod71.create_data_dictionary(
            self.P, "DD-001", "CRM entities", self._make_entities()
        )
        self.assertIn("Data type", result)
        self.assertIn("Required", result)

    def test_success_contains_attribute_values(self):
        result = mod71.create_data_dictionary(
            self.P, "DD-001", "CRM entities", self._make_entities()
        )
        self.assertIn("Integer", result)
        self.assertIn("AUTO_INCREMENT", result)

    def test_success_contains_business_rules(self):
        result = mod71.create_data_dictionary(
            self.P, "DD-001", "CRM entities", self._make_entities()
        )
        self.assertIn("Business rules", result)

    def test_registers_in_repo(self):
        mod71.create_data_dictionary(self.P, "DD-001", "CRM entities", self._make_entities())
        repo = load_spec_repo(self.P)
        ids = [r["id"] for r in repo["requirements"]]
        self.assertIn("DD-001", ids)

    def test_registered_type_is_data_dictionary(self):
        mod71.create_data_dictionary(self.P, "DD-001", "T", self._make_entities())
        repo = load_spec_repo(self.P)
        req = next(r for r in repo["requirements"] if r["id"] == "DD-001")
        self.assertEqual(req["type"], "data_dictionary")

    def test_creates_md_file(self):
        mod71.create_data_dictionary(self.P, "DD-001", "Entities", self._make_entities())
        specs_dir = mod71._specs_dir(self.P)
        files = os.listdir(specs_dir)
        self.assertTrue(any("dd_001" in f for f in files))

    def test_invalid_json_returns_error(self):
        result = mod71.create_data_dictionary(self.P, "DD-002", "T", "not JSON")
        self.assertIn("❌", result)

    def test_empty_list_returns_error(self):
        result = mod71.create_data_dictionary(self.P, "DD-003", "T", "[]")
        self.assertIn("❌", result)

    def test_multiple_entities(self):
        entities = json.dumps([
            {"name": "Client", "description": "Client", "attributes": [
                {"name": "id", "type": "Integer", "required": True, "constraints": "PK", "description": "ID"}
            ], "business_rules": []},
            {"name": "Manager", "description": "Manager", "attributes": [
                {"name": "id", "type": "Integer", "required": True, "constraints": "PK", "description": "ID"}
            ], "business_rules": []},
        ])
        result = mod71.create_data_dictionary(self.P, "DD-004", "All entities", entities)
        self.assertIn("Client", result)
        self.assertIn("Manager", result)


# ---------------------------------------------------------------------------
# 7.1.8 — create_erd
# ---------------------------------------------------------------------------

class TestCreateERD(BaseMCPTest):

    P = "erd_test"

    def _make_entities(self):
        return json.dumps([
            {"name": "Application", "pk": "id", "attributes": ["client_id FK", "status Enum"]},
            {"name": "Client", "pk": "id", "attributes": ["name String", "tin String"]},
        ])

    def _make_relations(self):
        return json.dumps([
            {"from": "Application", "to": "Client", "cardinality": "many-to-one", "label": "belongs to"}
        ])

    def test_success_contains_erd_id(self):
        result = mod71.create_erd(self.P, "ERD-001", "Core entities",
                                   self._make_entities(), self._make_relations())
        self.assertIn("ERD-001", result)

    def test_success_contains_plantuml(self):
        """ADR-025: contains a PlantUML ER Diagram."""
        result = mod71.create_erd(self.P, "ERD-001", "T",
                                   self._make_entities(), self._make_relations())
        self.assertIn("@startuml", result)
        self.assertIn("@enduml", result)

    def test_plantuml_contains_entities(self):
        result = mod71.create_erd(self.P, "ERD-001", "T",
                                   self._make_entities(), self._make_relations())
        self.assertIn("Application", result)
        self.assertIn("Client", result)

    def test_plantuml_contains_relation_notation(self):
        result = mod71.create_erd(self.P, "ERD-001", "T",
                                   self._make_entities(), self._make_relations())
        # many-to-one -> }o--||
        self.assertIn("}o--||", result)

    def test_plantuml_contains_relation_label(self):
        result = mod71.create_erd(self.P, "ERD-001", "T",
                                   self._make_entities(), self._make_relations())
        self.assertIn("belongs to", result)

    def test_registers_in_repo(self):
        mod71.create_erd(self.P, "ERD-001", "T",
                          self._make_entities(), self._make_relations())
        repo = load_spec_repo(self.P)
        ids = [r["id"] for r in repo["requirements"]]
        self.assertIn("ERD-001", ids)

    def test_registered_type_is_erd(self):
        mod71.create_erd(self.P, "ERD-001", "T",
                          self._make_entities(), self._make_relations())
        repo = load_spec_repo(self.P)
        req = next(r for r in repo["requirements"] if r["id"] == "ERD-001")
        self.assertEqual(req["type"], "erd")

    def test_creates_md_file(self):
        mod71.create_erd(self.P, "ERD-001", "Entities", self._make_entities(), self._make_relations())
        specs_dir = mod71._specs_dir(self.P)
        files = os.listdir(specs_dir)
        self.assertTrue(any("erd_001" in f and f.endswith(".md") for f in files))

    def test_creates_puml_file(self):
        """ADR-025: creates a .puml file."""
        mod71.create_erd(self.P, "ERD-001", "Entities", self._make_entities(), self._make_relations())
        specs_dir = mod71._specs_dir(self.P)
        files = os.listdir(specs_dir)
        self.assertTrue(any("erd_001" in f and f.endswith(".puml") for f in files))

    def test_invalid_entities_json_returns_error(self):
        result = mod71.create_erd(self.P, "ERD-002", "T", "not JSON", "[]")
        self.assertIn("❌", result)

    def test_empty_relations_no_error(self):
        """An empty relationships list — not an error."""
        result = mod71.create_erd(self.P, "ERD-003", "T", self._make_entities(), "[]")
        self.assertIn("ERD-003", result)
        self.assertNotIn("❌", result)

    def test_one_to_many_notation(self):
        relations = json.dumps([{"from": "A", "to": "B", "cardinality": "one-to-many", "label": "has"}])
        entities = json.dumps([
            {"name": "A", "pk": "id", "attributes": []},
            {"name": "B", "pk": "id", "attributes": []},
        ])
        result = mod71.create_erd(self.P, "ERD-004", "T", entities, relations)
        self.assertIn("||--o{", result)


# ---------------------------------------------------------------------------
# 7.1.9 — build_coverage_matrix
# ---------------------------------------------------------------------------

class TestBuildCoverageMatrix(BaseMCPTest):

    P = "cov_test"

    def test_no_requirements_returns_warning(self):
        """Empty repository — returns a warning."""
        save_spec_repo(make_spec_repo(self.P, []))
        result = mod71.build_coverage_matrix(self.P)
        self.assertIn("⚠️", result)

    def test_with_requirements_shows_matrix(self):
        """With requirements — shows the matrix."""
        repo = make_spec_repo(self.P, [
            {"id": "FR-001", "type": "functional", "title": "Test",
             "version": "1.0", "status": "draft", "added": str(date.today()),
             "source_artifact": "governance_plans/4_3_cov_test_confirmed.md"},
        ])
        save_spec_repo(repo)
        make_confirmed_artifact(self.P)
        result = mod71.build_coverage_matrix(self.P)
        self.assertIn("coverage matrix", result)

    def test_deprecated_excluded(self):
        """Deprecated requirements are not included in the matrix."""
        repo = make_spec_repo(self.P, [
            {"id": "FR-001", "type": "functional", "title": "Active",
             "version": "1.0", "status": "draft", "added": str(date.today()),
             "source_artifact": ""},
            {"id": "FR-DEP", "type": "functional", "title": "Deprecated",
             "version": "1.0", "status": "deprecated", "added": str(date.today()),
             "source_artifact": ""},
        ])
        save_spec_repo(repo)
        result = mod71.build_coverage_matrix(self.P)
        # FR-001 should be present, FR-DEP should not
        self.assertIn("FR-001", result)
        self.assertNotIn("FR-DEP", result)

    def test_shows_summary_table(self):
        repo = make_spec_repo(self.P, [
            {"id": "FR-001", "type": "functional", "title": "Test",
             "version": "1.0", "status": "draft", "added": str(date.today()), "source_artifact": ""},
        ])
        save_spec_repo(repo)
        result = mod71.build_coverage_matrix(self.P)
        self.assertIn("Summary", result)
        self.assertIn("Requirements in the registry", result)

    def test_over_engineering_flag_triggers(self):
        """10+ requirements for one objective -> over-engineering flag."""
        reqs = [
            {"id": f"FR-{i:03d}", "type": "functional", "title": f"Req {i}",
             "version": "1.0", "status": "draft", "added": str(date.today()), "source_artifact": ""}
            for i in range(12)
        ]
        save_spec_repo(make_spec_repo(self.P, reqs))
        result = mod71.build_coverage_matrix(self.P)
        self.assertIn("🟡", result)

    def test_reads_business_goals_from_artifact(self):
        """If a 4.3 artifact exists — uses its business objectives."""
        make_confirmed_artifact(self.P, content="""## Business objectives

1. Reduce application processing time
2. Automate distribution
""")
        repo = make_spec_repo(self.P, [
            {"id": "FR-001", "type": "functional", "title": "Test",
             "version": "1.0", "status": "draft", "added": str(date.today()), "source_artifact": ""},
        ])
        save_spec_repo(repo)
        result = mod71.build_coverage_matrix(self.P)
        # At least one business objective from the file should be mentioned
        self.assertTrue(
            "Reduce" in result or "Automate" in result,
            "Business objectives from the 4.3 artifact were not found in the matrix"
        )


# ---------------------------------------------------------------------------
# Integration tests — full pipeline
# ---------------------------------------------------------------------------

class TestIntegrationPipeline(BaseMCPTest):
    """
    Verify that the created artifacts interact correctly.
    """

    P = "integration_test"

    def test_full_pipeline_spec_to_repo(self):
        """
        Full pipeline: create US + FR + UC -> all are registered in repository 5.1.
        """
        mod71.create_user_story(
            project_id=self.P, story_id="US-001", title="Story",
            role="User", action="perform an action", benefit="obtain a result",
            acceptance_criteria_json=json.dumps(["AC1", "AC2"]),
        )
        mod71.create_functional_requirement(
            project_id=self.P, req_id="FR-001", req_type="functional",
            title="Requirement", description="The system SHALL...", rationale="Because"
        )
        mod71.create_use_case(
            project_id=self.P, uc_id="UC-001", title="Scenario",
            primary_actor="Actor", precondition="Condition", postcondition="Result",
            trigger="Trigger", main_scenario="1. The actor acts. 2. The system responds.",
        )

        repo = load_spec_repo(self.P)
        ids = {r["id"] for r in repo["requirements"]}
        self.assertIn("US-001", ids)
        self.assertIn("FR-001", ids)
        self.assertIn("UC-001", ids)

    def test_specs_dir_created_with_files(self):
        """
        After creating artifacts the specs folder exists and contains files.
        """
        mod71.create_user_story(
            project_id=self.P, story_id="US-001", title="Story",
            role="R", action="A", benefit="B",
            acceptance_criteria_json=json.dumps(["AC1", "AC2"]),
        )
        mod71.create_functional_requirement(
            project_id=self.P, req_id="FR-001", req_type="functional",
            title="T", description="D", rationale="O",
        )
        specs_dir = mod71._specs_dir(self.P)
        self.assertTrue(os.path.isdir(specs_dir))
        files = os.listdir(specs_dir)
        self.assertGreater(len(files), 0)

    def test_coverage_matrix_after_creation(self):
        """
        After creating several requirements the coverage matrix builds without errors.
        """
        for i in range(3):
            mod71.create_functional_requirement(
                project_id=self.P, req_id=f"FR-{i + 1:03d}", req_type="functional",
                title=f"Requirement {i + 1}", description="D", rationale="R",
            )
        result = mod71.build_coverage_matrix(self.P)
        self.assertNotIn("⚠️", result.split("##")[0])
        self.assertIn("matrix", result)

    def test_uc_diagram_after_use_cases_created(self):
        """
        generate_use_case_diagram sees UCs created via create_use_case.
        """
        for i in range(2):
            mod71.create_use_case(
                project_id=self.P, uc_id=f"UC-{i + 1:03d}",
                title=f"Scenario {i + 1}",
                primary_actor="Actor",
                precondition="Condition", postcondition="Result",
                trigger="Trigger", main_scenario="1. Step.",
            )
        result = mod71.generate_use_case_diagram(self.P, "Test system")
        self.assertIn("@startuml", result)
        self.assertIn("Scenario 1", result)
        self.assertIn("Scenario 2", result)

    def test_all_types_registered_correctly(self):
        """
        All artifact types are registered with the correct type in the repository.
        """
        mod71.create_user_story(
            project_id=self.P, story_id="US-001", title="Story",
            role="R", action="A", benefit="B",
            acceptance_criteria_json=json.dumps(["AC1", "AC2"]),
        )
        mod71.create_functional_requirement(
            project_id=self.P, req_id="FR-001", req_type="functional",
            title="FR", description="D", rationale="R",
        )
        mod71.create_use_case(
            project_id=self.P, uc_id="UC-001", title="UC",
            primary_actor="A", precondition="P", postcondition="R",
            trigger="T", main_scenario="1. Step.",
        )
        mod71.create_business_process(
            project_id=self.P, bp_id="BP-001", title="Process",
            process_owner="Owner", trigger="Trigger", outcome="Result",
            participants="Participant", steps="1. Participant: step.",
        )
        mod71.create_data_dictionary(
            project_id=self.P, dd_id="DD-001", title="Entities",
            entities_json=json.dumps([{
                "name": "E", "description": "D",
                "attributes": [{"name": "id", "type": "Integer", "required": True,
                                "constraints": "PK", "description": "ID"}],
                "business_rules": []
            }])
        )
        mod71.create_erd(
            project_id=self.P, erd_id="ERD-001", title="ERD",
            entities_json=json.dumps([{"name": "E", "pk": "id", "attributes": []}]),
            relations_json="[]",
        )

        repo = load_spec_repo(self.P)
        type_map = {r["id"]: r["type"] for r in repo["requirements"]}

        self.assertEqual(type_map["US-001"], "user_story")
        self.assertEqual(type_map["FR-001"], "functional")
        self.assertEqual(type_map["UC-001"], "use_case")
        self.assertEqual(type_map["BP-001"], "business_process")
        self.assertEqual(type_map["DD-001"], "data_dictionary")
        self.assertEqual(type_map["ERD-001"], "erd")


# ---------------------------------------------------------------------------
# 7.1 audit regressions (2026-07-19): producer(4.3)/consumer(7.1) contract + hybrid matrix
# ---------------------------------------------------------------------------

class TestConfirmedArtifactRealLayout(BaseMCPTest):
    """Bug 7.1-A: the 4.3 producer writes to reports/<pid>/4_3_confirmed_result_<ts>.md,
    but the consumer only searched flat data/ with pid-in-filename masks -> never found it."""

    P = "layout_test"

    def test_find_confirmed_artifact_in_reports_layout(self):
        path = make_confirmed_artifact_reports(self.P)
        found = mod71._find_confirmed_artifact(self.P)
        self.assertIsNotNone(found, "consumer must find the artifact in the real reports/<pid>/ layout")
        self.assertEqual(os.path.abspath(found), os.path.abspath(path))

    def test_find_confirmed_artifact_still_finds_legacy_data_layout(self):
        # backward compat: the old flat data/ fixture must still be found
        path = make_confirmed_artifact(self.P)
        found = mod71._find_confirmed_artifact(self.P)
        self.assertIsNotNone(found)
        self.assertEqual(os.path.abspath(found), os.path.abspath(path))

    def test_analyze_finds_real_producer_artifact(self):
        make_confirmed_artifact_reports(self.P)
        result = mod71.analyze_elicitation_context(self.P)
        self.assertIn("File found", result)
        self.assertNotIn("not found", result.split("##")[0])


class TestCoverageMatrixHybrid(BaseMCPTest):
    """Bug 7.1-B: the goal<->requirement mapping compared a file PATH (source_artifact)
    against goal TEXT, so every requirement fell into the first goal and all other goals
    were falsely flagged 🔴 uncovered. Hybrid (B1+B3): no fake per-goal flags; goals as a
    checklist; explicit limitation note pointing to check_coverage (5.1)."""

    P = "hybrid_test"

    def _multi_goal_artifact(self):
        make_confirmed_artifact(self.P, content="""## Business objectives

1. Alpha goal reduce processing time
2. Beta goal automate the routing
3. Gamma goal transparency for clients
""")

    def test_no_false_per_goal_uncovered_when_requirements_exist(self):
        self._multi_goal_artifact()
        save_spec_repo(make_spec_repo(self.P, [
            {"id": "FR-001", "type": "functional", "title": "Auto route",
             "version": "1.0", "status": "draft", "added": str(date.today()),
             "source_artifact": "governance_plans/reports/hybrid_test/4_3_confirmed_result_x.md"},
            {"id": "FR-002", "type": "functional", "title": "Transparency",
             "version": "1.0", "status": "draft", "added": str(date.today()),
             "source_artifact": "governance_plans/reports/hybrid_test/4_3_confirmed_result_x.md"},
        ]))
        result = mod71.build_coverage_matrix(self.P)
        self.assertNotIn("Uncovered business objectives", result)
        # Beta/Gamma must NOT be flagged as red-uncovered lines
        self.assertNotIn("🔴", result)

    def test_goals_shown_as_checklist(self):
        self._multi_goal_artifact()
        save_spec_repo(make_spec_repo(self.P, [
            {"id": "FR-001", "type": "functional", "title": "T",
             "version": "1.0", "status": "draft", "added": str(date.today()), "source_artifact": ""},
        ]))
        result = mod71.build_coverage_matrix(self.P)
        self.assertIn("Alpha goal reduce processing time", result)
        self.assertIn("Beta goal automate the routing", result)
        self.assertIn("Gamma goal transparency for clients", result)

    def test_matrix_notes_traceability_limitation_and_points_to_check_coverage(self):
        save_spec_repo(make_spec_repo(self.P, [
            {"id": "FR-001", "type": "functional", "title": "T",
             "version": "1.0", "status": "draft", "added": str(date.today()), "source_artifact": ""},
        ]))
        result = mod71.build_coverage_matrix(self.P)
        self.assertIn("check_coverage", result)

    def test_over_engineering_hint_still_present(self):
        # keep the global over-engineering signal (>= 10 reqs, no goals)
        reqs = [
            {"id": f"FR-{i:03d}", "type": "functional", "title": f"Req {i}",
             "version": "1.0", "status": "draft", "added": str(date.today()), "source_artifact": ""}
            for i in range(12)
        ]
        save_spec_repo(make_spec_repo(self.P, reqs))
        result = mod71.build_coverage_matrix(self.P)
        self.assertIn("🟡", result)

    # --- C1: objectives come from the REAL source (6.2), not the 4.3 artifact ---

    def test_goals_read_from_6_2_graph_nodes(self):
        """6.2 registers business_goal nodes in the 5.1 repo; the matrix must use them
        as the objectives checklist, not fall back to synthetic source grouping."""
        save_spec_repo(make_spec_repo(self.P, [
            {"id": "BG-001", "type": "business_goal", "title": "Cut processing time to 2 days",
             "version": "1.0", "status": "confirmed", "added": str(date.today()), "source_artifact": ""},
            {"id": "FR-001", "type": "functional", "title": "Auto route",
             "version": "1.0", "status": "draft", "added": str(date.today()), "source_artifact": ""},
        ]))
        result = mod71.build_coverage_matrix(self.P)
        # must appear as a checklist objective, not as a requirement row
        self.assertIn("- [ ] Cut processing time to 2 days", result)

    def test_business_goal_node_not_counted_as_requirement(self):
        """A business_goal node is an objective, not a spec requirement — it must not inflate
        the requirements count nor appear in the requirements list."""
        save_spec_repo(make_spec_repo(self.P, [
            {"id": "BG-001", "type": "business_goal", "title": "Goal one",
             "version": "1.0", "status": "confirmed", "added": str(date.today()), "source_artifact": ""},
            {"id": "FR-001", "type": "functional", "title": "Req one",
             "version": "1.0", "status": "draft", "added": str(date.today()), "source_artifact": ""},
        ]))
        result = mod71.build_coverage_matrix(self.P)
        self.assertIn("| Requirements in the registry | 1 |", result)

    def test_goals_read_from_future_state_goals_file(self):
        """If goals are not in the graph (register_in_traceability=False) but the 6.2 file
        exists, read objectives from future_state_goals.json."""
        from skills.common import data_path
        import os as _os
        safe = self.P.lower().replace(" ", "_")
        path = data_path(self.P, f"{safe}_future_state_goals.json")
        _os.makedirs(_os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"goals": [
                {"id": "BG-001", "goal_title": "Improve NPS to 60", "description": "d",
                 "objectives": [], "linked_business_needs": []},
            ]}, f)
        save_spec_repo(make_spec_repo(self.P, [
            {"id": "FR-001", "type": "functional", "title": "Feature",
             "version": "1.0", "status": "draft", "added": str(date.today()), "source_artifact": ""},
        ]))
        result = mod71.build_coverage_matrix(self.P)
        self.assertIn("Improve NPS to 60", result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
