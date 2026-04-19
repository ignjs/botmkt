from dataclasses import dataclass

from domain.entities.position import Position


@dataclass
class Portfolio:
    """Contenedor de posiciones del usuario."""

    positions: list[Position]
