"""
tests/test_common_node_types.py — the shared root/goal node type set.

A traversal or skip-filter that knows only the legacy `business` type silently ignores
the real goals 6.1 and 6.2 register (`business_need`, `business_goal`). That single
incompleteness produced findings 7.3-A, 7.4-B, 7.4-C and the 5.4 `_has_br_path` defect,
so the set lives in ONE place and every consumer imports it.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests.conftest import setup_mocks

setup_mocks()

from skills.common import BUSINESS_NODE_TYPES


class TestBusinessNodeTypes(unittest.TestCase):

    def test_constant_holds_all_three_root_types(self):
        self.assertEqual(
            BUSINESS_NODE_TYPES, {"business", "business_goal", "business_need"}
        )

    def test_consumers_use_the_shared_set(self):
        """Binding identity, not equality: an equal-but-separate copy is exactly the
        drift this extraction removes."""
        import skills.requirements_validate_mcp as mod73
        import skills.requirements_architecture_mcp as mod74

        self.assertIs(mod73.BUSINESS_NODE_TYPES, BUSINESS_NODE_TYPES)
        self.assertIs(mod74.BUSINESS_NODE_TYPES, BUSINESS_NODE_TYPES)

    def test_derived_aliases_bind_the_full_shared_set(self):
        """These aliases used to pin the local snapshot BUSINESS_NODE_TYPES |
        {"test"} — written before `risk` / `change_request` / `solution_scope`
        existed, which is exactly how 7.3 reported risks as "requirements without
        traceability" and 7.4 diluted its coverage percentage. The aliases must BE
        the shared, growing set (identity, not an equal copy)."""
        import skills.requirements_validate_mcp as mod73
        import skills.requirements_architecture_mcp as mod74
        from skills.common import NON_REQUIREMENT_NODE_TYPES

        # Identity between the two consumers (their binding survives even the
        # importlib.reload(common) another test performs), plus content equality
        # with the current shared definition.
        self.assertIs(mod73.NON_REQUIREMENT_TYPES, mod74.SKIP_TYPES)
        self.assertEqual(mod73.NON_REQUIREMENT_TYPES, NON_REQUIREMENT_NODE_TYPES)
        self.assertIn("risk", mod73.NON_REQUIREMENT_TYPES)
        self.assertIn("change_request", mod73.NON_REQUIREMENT_TYPES)
        self.assertIn("solution_scope", mod73.NON_REQUIREMENT_TYPES)


if __name__ == "__main__":
    unittest.main()
