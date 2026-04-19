import re
from dataclasses import dataclass

from domain.exceptions import InvalidSymbolError


@dataclass(frozen=True)
class Symbol:
    """Ticker de instrumento con validación de formato."""

    value: str

    def __post_init__(self) -> None:
        cleaned = self.value.strip().upper()
        pattern = r'^[\^]?[A-Z0-9]{1,10}([.\-][A-Z0-9]{1,5})?$'
        if not re.match(pattern, cleaned):
            raise InvalidSymbolError(f"Símbolo inválido: '{self.value}'")
        object.__setattr__(self, "value", cleaned)

    def __str__(self) -> str:
        return self.value
