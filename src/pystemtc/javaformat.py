"""Java text-formatting replicas needed for string-level golden comparisons.

Two formatters are ported:

- ``java_double_to_string``: the default ``double -> String`` conversion used
  by Java string concatenation (ST.java:2968-2975 prints Profile Model,
  ``# Genes Assigned`` and ``# Gene Expected`` this way).
- ``double_to_sz``: ``Util.doubleToSz`` (Util.java:156-196), used for the
  profile-table p-value column (ST.java:2975).

Both were spot-verified against the real JRE 1.8.0_451 via ``jjs`` and are
exercised end-to-end, at string level, by the 12 golden table comparisons:
the only observed deviation of JDK 8's legacy ``Double.toString`` from the
shortest round-trip representation (e.g. 2.82879384806159E17 -> "2.82879384806
159008E17") occurs at magnitudes >= 1e17, far outside the model-profile,
count and expected-value domains, so the shortest-digit approach is exact
there.
"""

from __future__ import annotations

import math
from decimal import Decimal, ROUND_HALF_EVEN


def java_double_to_string(d: float) -> str:
    """``java.lang.Double.toString(double)`` (JDK 8 documentation semantics).

    NaN/Infinity names, signed zero, plain decimal notation for
    1e-3 <= |d| < 1e7 with at least one fractional digit, and
    computerized scientific notation (``d.dddEexp``, exponent without a
    leading ``+``) otherwise.
    """
    if math.isnan(d):
        return "NaN"
    if d == math.inf:
        return "Infinity"
    if d == -math.inf:
        return "-Infinity"
    if d == 0.0:
        return "-0.0" if math.copysign(1.0, d) < 0 else "0.0"

    negative = math.copysign(1.0, d) < 0
    magnitude = abs(d)

    # Shortest round-trip digits for the magnitude (repr is correctly rounded
    # and shortest in CPython).
    text = repr(magnitude)
    if "e" in text:
        mantissa, _, exp_text = text.partition("e")
        exp10 = int(exp_text)
    else:
        mantissa, exp10 = text, 0
    if "." in mantissa:
        int_part, _, frac_part = mantissa.partition(".")
    else:
        int_part, frac_part = mantissa, ""
    concat = int_part + frac_part
    stripped = concat.lstrip("0")
    first_digit_pos = len(concat) - len(stripped)
    digits = stripped.rstrip("0") or "0"

    # value = 0.digits * 10**(exp10 + pointpos)  ->  D.ddd * 10**sci_exp
    sci_exp = exp10 + len(int_part) - first_digit_pos - 1

    if -3 <= sci_exp < 7:
        # plain decimal form
        if sci_exp >= 0:
            whole = digits[: sci_exp + 1]
            whole += "0" * (sci_exp + 1 - len(whole))
            frac = digits[sci_exp + 1 :]
        else:
            whole = "0"
            frac = "0" * (-sci_exp - 1) + digits
        if not frac:
            frac = "0"
        body = whole + "." + frac
    else:
        frac = digits[1:]
        if not frac:
            frac = "0"
        body = digits[0] + "." + frac + "E" + str(sci_exp)
    return ("-" + body) if negative else body


def _number_format(value: float, fraction_digits: int) -> str:
    """``NumberFormat.getInstance(Locale.ENGLISH)`` with min = max fraction
    digits (HALF_EVEN rounding on the exact binary double, thousands
    grouping) — the same rendering rule M1's genetable comparison uses."""
    quantized = Decimal(float(value)).quantize(
        Decimal(1).scaleb(-fraction_digits), rounding=ROUND_HALF_EVEN
    )
    return f"{quantized:,}"


def double_to_sz(dval: float) -> str:
    """``Util.doubleToSz`` (Util.java:156-196), line by line.

    dval <= 0 -> "0.00"; otherwise the 0.995-threshold decimal-scaling loop,
    with the E-notation branch (nexp < -2) recomputing the mantissa via
    ``Math.pow(10, log10(dval) - nexp)`` and NumberFormat with 1 fraction
    digit; the plain branch formats dval itself with 2 fraction digits.
    """
    if math.isnan(dval):
        # verified via jjs on JRE 1.8.0_451: NumberFormat.format(NaN) is a
        # single U+FFFD char, and Util.doubleToSz passes NaN to nf2.format
        return "\ufffd"
    if dval <= 0:
        return "0.00"

    dtempval = dval
    nexp = 0
    while (dtempval < 0.995) and (dtempval > 0):
        nexp -= 1
        dtempval = dtempval * 10

    if nexp < -2:
        dtempval = math.pow(10, math.log(dval) / math.log(10) - nexp)
        return _number_format(dtempval, 1) + "E" + str(nexp)
    return _number_format(dval, 2)
