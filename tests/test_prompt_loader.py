import unittest

from utils.prompt_loader import PromptNotFoundError, PromptRenderError, load_prompt


class PromptLoaderTests(unittest.TestCase):
    def test_load_prompt_renders_variables(self):
        prompt = load_prompt(
            "portfolio_analysis",
            portfolio_table="| Símbolo | Valor |\n| AAPL | 100 |",
        )

        self.assertIn("Analiza la siguiente cartera", prompt)
        self.assertIn("AAPL", prompt)

    def test_missing_prompt_raises_clear_error(self):
        with self.assertRaises(PromptNotFoundError):
            load_prompt("prompt_que_no_existe")

    def test_missing_variable_raises_clear_error(self):
        with self.assertRaises(PromptRenderError):
            load_prompt("stock_analysis", symbol="AAPL")


if __name__ == "__main__":
    unittest.main()
