"""Base classes for financial instruments."""

import dag


class Instrument(dag.Model):
    """
    Base class for all financial instruments.

    Instruments are dag.Model subclasses with computed functions
    for pricing and risk calculations.
    """

    @dag.computed
    def Summary(self) -> str:
        """
        Human-readable summary of key instrument parameters.

        Override in subclasses to provide instrument-specific summaries.

        Example:
            option.Summary()  # "K=100 S=105 C"
            bond.Summary()    # "5% 10Y"
        """
        return type(self).__name__

    @dag.computed
    def MarketValue(self) -> float:
        """
        Current market value of the instrument.

        Override in subclasses to return Price(), Value(), or other
        appropriate valuation.

        Example:
            option.MarketValue()  # Returns option.Price()
            forward.MarketValue() # Returns forward.Value()
        """
        return 0.0
