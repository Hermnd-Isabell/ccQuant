"""
Option chain management.
"""

from datetime import datetime
from collections import defaultdict

from ccquant.core.constant import OptionType
from ccquant.core.object import ContractData


class OptionChain:
    """
    Manages all option contracts for a single underlying asset.
    Organized by expiry date and strike price for quick T-quote lookup.
    """

    def __init__(self, underlying_vt_symbol: str) -> None:
        """
        :param underlying_vt_symbol: vt_symbol of the underlying (e.g., "510050.SSE")
        """
        self.underlying_vt_symbol: str = underlying_vt_symbol

        # expiry -> strike -> {CALL: ContractData, PUT: ContractData}
        self._chain: dict[
            datetime,
            dict[float, dict[OptionType, ContractData | None]]
        ] = defaultdict(lambda: defaultdict(lambda: {OptionType.CALL: None, OptionType.PUT: None}))

        # vt_symbol -> ContractData for fast lookup
        self._contracts: dict[str, ContractData] = {}

    def add_contract(self, contract: ContractData) -> None:
        """
        Add an option contract to the chain.
        """
        if contract.product.value != "Option":
            raise ValueError(f"Contract {contract.vt_symbol} is not an option")

        expiry = contract.option_expiry
        strike = contract.option_strike
        option_type = contract.option_type

        if expiry is None or strike is None or option_type is None:
            raise ValueError(f"Contract {contract.vt_symbol} missing option fields")

        self._chain[expiry][strike][option_type] = contract
        self._contracts[contract.vt_symbol] = contract

    def get_contract(self, vt_symbol: str) -> ContractData | None:
        """
        Get contract by vt_symbol.
        """
        return self._contracts.get(vt_symbol)

    def get_contract_by_strike(
        self,
        expiry: datetime,
        strike: float,
        option_type: OptionType
    ) -> ContractData | None:
        """
        Get contract by expiry, strike and option type.
        """
        return self._chain.get(expiry, {}).get(strike, {}).get(option_type)

    @property
    def expiries(self) -> list[datetime]:
        """
        Sorted list of available expiry dates.
        """
        return sorted(self._chain.keys())

    def strikes(self, expiry: datetime) -> list[float]:
        """
        Sorted list of strike prices for a given expiry.
        """
        return sorted(self._chain.get(expiry, {}).keys())

    def contracts_for_expiry(self, expiry: datetime) -> list[ContractData]:
        """
        Return all contracts for a specific expiry date.
        """
        result: list[ContractData] = []
        for strike_dict in self._chain.get(expiry, {}).values():
            for contract in strike_dict.values():
                if contract:
                    result.append(contract)
        return result

    def atm_contracts(
        self,
        expiry: datetime,
        underlying_price: float
    ) -> dict[OptionType, ContractData | None]:
        """
        Find the ATM (closest strike) CALL and PUT contracts for a given expiry.
        """
        strikes = self.strikes(expiry)
        if not strikes:
            return {OptionType.CALL: None, OptionType.PUT: None}

        atm_strike = min(strikes, key=lambda s: abs(s - underlying_price))
        return self._chain[expiry][atm_strike]

    def all_contracts(self) -> list[ContractData]:
        """
        Return all contracts in the chain.
        """
        return list(self._contracts.values())

    def __len__(self) -> int:
        return len(self._contracts)
