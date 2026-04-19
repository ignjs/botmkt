import pytest

from domain.exceptions import InvalidSymbolError
from domain.value_objects.symbol import Symbol


def test_symbol_accepts_valid_formats() -> None:
    assert str(Symbol("AAPL")) == "AAPL"
    assert str(Symbol("IAM.SN")) == "IAM.SN"
    assert str(Symbol("^GSPC")) == "^GSPC"
    assert str(Symbol("BTC-USD")) == "BTC-USD"


def test_symbol_rejects_invalid() -> None:
    with pytest.raises(InvalidSymbolError):
        Symbol("***")
