from dataclasses import dataclass, field


@dataclass
class NiahCase:
    """Input defining one long-range dependency experiment."""

    case_id: str
    context: str
    question: str

    expected_answer: str
    needle: str

    target_tokens: int
    actual_tokens: int
    depth: float

    model_options: dict

    # What was actually planted, and where it landed.
    #
    # `depth` above is what was REQUESTED. `needle_inventory` carries what was
    # realised, per block, with a role - which is the whole economic argument
    # for the taxonomy: a rule tier can separate "returned a distractor" from
    # "fabricated a value" offline, without re-running a model, only if the
    # record says what was in the haystack (build order step 4).
    #
    # Defaulted so the field is additive: every existing construction site keeps
    # working, and a case built without an inventory is distinguishable from one
    # built with an empty one only by there being no such thing as the latter.
    needle_inventory: list[dict] = field(default_factory=list)

    # The realised depth of the TARGET block. Differs from `depth` because the
    # block displaces filler after it (J-030 measures the related token-count
    # effect); at k>1 the earlier blocks displace it too.
    realised_depth: float | None = None

    # Filler tokens surviving the budget after every block is accounted for.
    # At k=1 this is `target_tokens - len(needle_tokens)`; it is recorded so the
    # background length is a measurement rather than a re-derivation.
    filler_tokens_used: int | None = None

    @property
    def prompt(self) -> str:
        return f"{self.context}\n\nQuestion: {self.question}"
