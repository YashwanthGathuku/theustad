import pytest

from gatelib import claims


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("The fix is complete and all tests pass.", True),
        ("I am not done and have not completed the work.", False),
        ("Do all the tests pass?", False),
        ("It isn't working yet.", False),
        ("Fixed the crash; ready to merge.", True),
        ("This should work.", True),
        ("I still need to fix test_invoice.", False),
        ("I am working on it.", False),
        ("Parser tests pass, but the task is not complete.", False),
    ],
)
def test_required_spec_cases(text, expected):
    assert bool(claims.find_claims(text)) is expected


def test_claim_records_sentence_and_phrases_in_textual_order():
    found = claims.find_claims("The fix is complete and all tests pass.")

    assert len(found) == 1
    assert found[0].sentence == "The fix is complete and all tests pass."
    assert found[0].phrases == ["complete", "all tests pass"]


def test_multiple_claiming_sentences_return_separate_claims():
    found = claims.find_claims("The crash is fixed. All tests pass!")

    assert [claim.sentence for claim in found] == [
        "The crash is fixed.",
        "All tests pass!",
    ]
    assert [claim.phrases for claim in found] == [["fixed"], ["All tests pass"]]


@pytest.mark.parametrize(
    "text",
    [
        "The fix is not complete.",
        "The fix isn't complete.",
        "The fix is never done.",
        "No tests pass.",
        "I haven't completed the fix.",
        "The fix hasn't been completed.",
        "The changes aren't complete.",
        "I don't think the fix is complete.",
        "The report doesn't prove the fix is complete.",
        "I didn't complete the fix.",
        "I won't say the fix is complete.",
        "I cannot say the fix is complete.",
        "I can't say the fix is complete.",
        "I am unable to say the fix is complete.",
        "Tests pass, but verification is not complete yet.",
        "Tests pass, but I still need to fix the invoice.",
        "Tests pass, but test_invoice is still failing.",
        "Tests pass, but the task is incomplete.",
        "I am working on a change that should work.",
    ],
)
def test_negation_and_progress_tokens_suppress_the_sentence(text):
    assert claims.find_claims(text) == []


@pytest.mark.parametrize(
    "text",
    [
        "I am not done. The previous error said tests pass.",
        "The previous output says tests pass. I am still working on it.",
        "Tests pass, but the task is incomplete. I am checking the remaining work.",
        "I haven't completed the work. Do all the tests pass?",
        "This should work? I still need to verify test_invoice.",
        "No fix is complete. I am working on it.",
        "The old log showed all tests pass. The task is not done.",
    ],
)
def test_mixed_sentence_adversarial_messages_do_not_claim_completion(text):
    assert claims.find_claims(text) == []


def test_questions_are_suppressed_even_when_they_contain_claim_phrases():
    assert claims.find_claims("The fix is complete?") == []
    assert claims.find_claims("Should this work?") == []


def test_standalone_working_is_not_a_claim_but_is_working_is():
    assert claims.find_claims("Working.") == []
    assert claims.find_claims("The parser is working.")[0].phrases == ["is working"]


def test_empty_or_unrelated_text_has_no_claims():
    assert claims.find_claims("") == []
    assert claims.find_claims("Investigated the parser and found the cause.") == []
