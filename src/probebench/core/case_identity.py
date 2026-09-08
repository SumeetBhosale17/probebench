"""Content-addressed case identity (invariant 11, D-012).

Two keys, because they answer different questions:

* ``case_key`` is the DESIGN POINT - which cell of the experiment a case
  occupies. It survives a change to how the prompt is built, which is why it
  is the only key the pre-1.2 archive can ever join on.
* ``case_fingerprint`` is the CONTENT ADDRESS - a digest over everything
  determining the model's input. It asserts strict comparability, and it is
  MEANT to stop matching once construction changes, so it will correctly stop
  joining across models after LIMITATIONS 1.1 is fixed.

Nothing benchmark-specific lives here. A family declares which components its
identity depends on; this module only decides how a component set is
serialised and hashed, so two families cannot quietly disagree about it.
"""

import hashlib
import json
from collections.abc import Mapping
from typing import Any

# The component SET is itself versioned. Adding a component later changes
# every fingerprint, and without this a reader cannot tell "the model's input
# changed" from "we started hashing one more thing" (D-012).
FINGERPRINT_VERSION = "fp1"


class ComponentError(ValueError):
    """A component set cannot be hashed reproducibly."""


def sha256_text(text: str) -> str:
    """Digest of a UTF-8 string.

    Used for the prompt, which is deliberately NEVER stored: a 128k-token
    haystack per case would make the archive unreadable, while the digest
    still detects filler-corpus drift, which is the property we need.
    """

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def short_digest(text: str, length: int = 8) -> str:
    """A short content address, for use inside a human-facing key.

    Used for the needle segment of case_key (D-015): the needle text is
    present in every archived record, so a digest keeps the migration a pure
    function of the record, which a line index could not.
    """

    return sha256_text(text)[:length]


def format_depth(depth: float) -> str:
    """Render a depth for a key or a fingerprint component.

    Two decimals, matching case_key's ``d{depth:.2f}`` segment, so the two
    keys can never disagree about which cell a case is in.
    """

    return f"{depth:.2f}"


def fingerprint(components: Mapping[str, Any]) -> str:
    """Hash a component set into a case fingerprint.

    Serialisation is canonical - sorted keys, no whitespace - because a
    fingerprint that depends on dict insertion order is not a fingerprint.
    """

    _reject_floats(components)

    payload = json.dumps(
        {"fingerprint_version": FINGERPRINT_VERSION, **dict(components)},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )

    return sha256_text(payload)


def _reject_floats(value: Any, path: str = "") -> None:
    """Refuse raw floats anywhere in a component set.

    0.1 + 0.2 and 0.3 serialise differently, so a float reaching the digest
    makes the fingerprint depend on how a number was arrived at rather than on
    what it is. Callers pass depths through format_depth() instead. Booleans
    are fine - bool is an int subclass and JSON-stable.
    """

    if isinstance(value, float):
        raise ComponentError(
            f"Float component at {path or '<root>'}: {value!r}. "
            "Format it as a string (see format_depth) so the digest is stable."
        )

    if isinstance(value, Mapping):
        for key, item in value.items():
            _reject_floats(item, f"{path}.{key}" if path else str(key))

    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _reject_floats(item, f"{path}[{index}]")
