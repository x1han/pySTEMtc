"""Exact port of ``java.util.Random`` (JDK 8), as documented by its Javadoc.

Used for the fixed-seed streams STEM relies on: permutation subsampling
(``Random(9873287)``), sampled model profiles (``Random(3733246)``) and
K-means restarts (``Random(2211)``).  Pure Python integer arithmetic; the
48-bit LCG state is exact, so the double/int streams match Java bitwise.
"""

from __future__ import annotations


class JavaRandom:
    """Bit-exact replica of ``java.util.Random``."""

    MULTIPLIER = 0x5DEECE66D
    ADDEND = 0xB
    MASK = (1 << 48) - 1

    __slots__ = ("_seed",)

    def __init__(self, seed: int):
        self._seed = (seed ^ self.MULTIPLIER) & self.MASK

    def next(self, bits: int) -> int:
        """Java ``next(bits)``: advances the LCG and returns the top ``bits``.

        The result is a signed Java ``int``: for ``bits == 32`` the raw value
        is reinterpreted as two's complement (the ``(int)`` cast in Java);
        for ``bits <= 31`` the value is already non-negative.
        """
        self._seed = (self._seed * self.MULTIPLIER + self.ADDEND) & self.MASK
        value = self._seed >> (48 - bits)
        if bits == 32 and value >= (1 << 31):
            value -= 1 << 32
        return value

    def next_double(self) -> float:
        # ((long)next(26) << 27) + next(27)) * 0x1.0p-53
        return ((self.next(26) << 27) + self.next(27)) * 2.0**-53

    def next_int(self, bound: int | None = None) -> int:
        """Java ``nextInt()`` (``bound=None``) or ``nextInt(bound)``."""
        if bound is None:
            return self.next(32)
        if bound <= 0:
            raise ValueError("bound must be positive")
        m = bound - 1
        if (bound & m) == 0:
            # power of two: (int)((bound * (long)next(31)) >> 31)
            return (bound * self.next(31)) >> 31
        while True:
            bits = self.next(31)
            val = bits % bound
            # Java evaluates `bits - val + (bound-1)` in int arithmetic, which
            # wraps for results >= 2**31; replicate the wrap before testing.
            if ((bits - val + m + (1 << 31)) % (1 << 32)) - (1 << 31) >= 0:
                return val
