from services.ai_service import (
    build_compare_prompt,
    build_earnings_prompt,
    build_entry_prompt,
    build_full_analysis_prompt,
    build_portfolio_builder_prompt,
    build_risk_prompt,
    build_screener_prompt,
)


def test_prompt_builders_include_expected_parameters():
    assert "AAPL" in build_full_analysis_prompt("AAPL")
    assert "growth" in build_screener_prompt("growth", "tecnología")
    assert "Microsoft" in build_earnings_prompt("Microsoft", "texto")
    assert "NVDA" in build_risk_prompt("NVDA")
    compare = build_compare_prompt("AAPL", "MSFT", "growth", "18m")
    assert "AAPL" in compare and "MSFT" in compare and "18m" in compare
    portfolio = build_portfolio_builder_prompt(5000, "valor", "12m", 5)
    assert "5" in portfolio and "valor" in portfolio
    assert "IAM.SN" not in build_entry_prompt("AAPL")
