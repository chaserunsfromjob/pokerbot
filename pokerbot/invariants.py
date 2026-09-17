"""The one way this package refuses to continue.

An invariant is a statement about the table that must be true on every hand:
chips add up, nobody pays more than they had, the side pots go to the right
seats. `EVALUATION_STRATEGY.md` section 4.5 lists the seven of them and is
explicit that a failure *aborts the run* rather than being reported and
counted, because a strength number measured on a table that mis-pays a pot is
a fiction.

So there is exactly one helper here, `require`, and the exception it raises is
deliberately not an `AssertionError`: the test suite's `conftest.py` recognises
it and stops the whole session at the first one.
"""


class InvariantViolation(Exception):
    """A table invariant failed. The run stops here; nothing is reported."""

    def __init__(self, invariant: str, message: str, context: object = None):
        self.invariant = invariant
        self.message = message
        self.context = context
        detail = f"{invariant} violated: {message}"
        if context is not None:
            detail = f"{detail}\ncontext: {context}"
        super().__init__(detail)


def require(condition: bool, invariant: str, message: str, context: object = None) -> None:
    """Raise `InvariantViolation` unless `condition` holds."""
    if not condition:
        raise InvariantViolation(invariant, message, context)
