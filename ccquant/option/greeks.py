"""
Greeks data structure and aggregation helpers.
"""

from dataclasses import dataclass


@dataclass
class Greeks:
    """
    Greeks for a single option contract or an aggregated portfolio.
    All values are in "per contract" or "per portfolio" terms.
    """

    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    rho: float = 0.0

    def __add__(self, other: "Greeks") -> "Greeks":
        return Greeks(
            delta=self.delta + other.delta,
            gamma=self.gamma + other.gamma,
            theta=self.theta + other.theta,
            vega=self.vega + other.vega,
            rho=self.rho + other.rho,
        )

    def __sub__(self, other: "Greeks") -> "Greeks":
        return Greeks(
            delta=self.delta - other.delta,
            gamma=self.gamma - other.gamma,
            theta=self.theta - other.theta,
            vega=self.vega - other.vega,
            rho=self.rho - other.rho,
        )

    def __mul__(self, scalar: float) -> "Greeks":
        return Greeks(
            delta=self.delta * scalar,
            gamma=self.gamma * scalar,
            theta=self.theta * scalar,
            vega=self.vega * scalar,
            rho=self.rho * scalar,
        )

    def __rmul__(self, scalar: float) -> "Greeks":
        return self.__mul__(scalar)

    def to_dict(self) -> dict[str, float]:
        return {
            "delta": self.delta,
            "gamma": self.gamma,
            "theta": self.theta,
            "vega": self.vega,
            "rho": self.rho,
        }
