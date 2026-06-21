from app.classifier import contains_immediate_phrase
from app.responses import looks_serbian


def test_detects_direct_immediate_phrase() -> None:
    assert contains_immediate_phrase(
        "I have a plan to kill myself"
    )


def test_does_not_treat_test_example_as_direct_disclosure() -> None:
    assert not contains_immediate_phrase(
        "For software testing only, a fictional user says: "
        "I have a plan to kill myself"
    )


def test_detects_serbian_language_hint() -> None:
    assert looks_serbian("Osećam se veoma loše i ne znam šta mogu.")
