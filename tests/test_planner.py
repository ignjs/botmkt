import unittest

from db import normalize_investment_profile
from services.planner import build_rules_based_plan


class PlannerTests(unittest.TestCase):
    def test_normalize_profile_applies_expected_values(self):
        profile = normalize_investment_profile(
            {
                "risk_tolerance": 6,
                "investment_horizon": "mediano",
                "max_position_pct": 30,
                "max_country_pct": 70,
                "max_sector_pct": 45,
                "max_drawdown_pct": 10,
                "preferred_strategy": "mixta",
                "cash_buffer_pct": 12,
            }
        )

        self.assertEqual(profile["risk_tolerance"], 6)
        self.assertEqual(profile["investment_horizon"], "mediano")
        self.assertEqual(profile["cash_buffer_pct"], 12.0)

    def test_build_rules_based_plan_includes_core_sections(self):
        profile = normalize_investment_profile({})
        diagnosis = {
            "portfolio_summary": {"risk_score": 7, "risk_label": "medio"},
            "rule_breaches": [
                {"severity": "high", "message": "AAPL supera el límite por posición."}
            ],
            "warnings": [],
            "suggested_actions": [
                {"action": "Reducir AAPL al rango objetivo."},
                {"action": "Mantener 10% en caja táctica."},
                {"action": "Pausar compras en el mismo mercado."},
            ],
        }

        plan = build_rules_based_plan(profile, diagnosis)

        self.assertIn("Plan semanal de ejecución", plan)
        self.assertIn("Estado general", plan)
        self.assertIn("Riesgo general actual", plan)
        self.assertIn("Urgencia", plan)


if __name__ == "__main__":
    unittest.main()
