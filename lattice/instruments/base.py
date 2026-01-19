"""Base classes for financial instruments."""

import dag


class Instrument(dag.Model):
    """
    Base class for all financial instruments.

    Instruments are dag.Model subclasses with computed functions
    for pricing and risk calculations.
    """
    pass
