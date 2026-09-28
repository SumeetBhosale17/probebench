"""The keyed needle inventory (D-022).

One template, k+1 subjects, uniform values. Only the subject distinguishes two
needles, so a wrong answer equal to a planted code is NECESSARILY a
discrimination failure rather than "that needle's wording was harder" - which is
what LIMITATIONS 1.9 measured at 19 points of accuracy across NIAH's six.

`value` is stored explicitly rather than parsed back out of the sentence.
NIAH's `extract_expected_answer` splits on " is ", which happens to work here and
returns `'the one recorded for the north tower'` for a multi-hop pointer; it
exists for the legacy needle file and the keyed families should be free of it.
"""

import json
from dataclasses import dataclass

# Uniformity is enforced by test, not by convention: every needle must render to
# the same token count and the same value shape, or length and shape become the
# confound the uniform template was adopted to delete.
NEEDLE_TEMPLATE = "The access code for {subject} is {value}."
QUESTION_TEMPLATE = "What is the access code for {subject}?"


@dataclass(frozen=True)
class KeyedNeedle:
    """One subject and the code belonging to it."""

    id: str
    subject: str
    value: str

    @property
    def text(self) -> str:
        return NEEDLE_TEMPLATE.format(subject=self.subject, value=self.value)

    @property
    def question(self) -> str:
        return QUESTION_TEMPLATE.format(subject=self.subject)


def load_keyed_needles(path: str) -> list[KeyedNeedle]:
    """Load the keyed inventory, preserving file order.

    File order is the selection order for decoys, so it is part of the design
    rather than incidental - which is why a case records the ids it used rather
    than trusting the file to stay put.
    """

    needles: list[KeyedNeedle] = []

    with open(path, encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue

            row = json.loads(line)
            needles.append(KeyedNeedle(id=row["id"], subject=row["subject"], value=row["value"]))

    if len({n.value for n in needles}) != len(needles):
        raise ValueError("Two keyed needles share a value: a wrong answer would be ambiguous.")

    if len({n.subject for n in needles}) != len(needles):
        raise ValueError("Two keyed needles share a subject: the question would be ambiguous.")

    return needles
