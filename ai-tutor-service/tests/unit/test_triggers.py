import pytest

from app.domain.enums import ConversationMode, EscalationCategory
from app.tutor.triggers import asks_for_human, asks_for_solution, cited_numbers, lookups_wanted, sensitive_category

LEARNING, SUPPORT = ConversationMode.LEARNING, ConversationMode.SUPPORT


@pytest.mark.parametrize("text", ["Can I talk to a human?", "please connect me to support", "I need a person", "I want a human agent", "let me speak with my teacher"])
def test_asking_for_a_person_is_recognised(text):
    assert asks_for_human(text)


@pytest.mark.parametrize("text", ["Explain how a support vector machine works", "What does the human genome project have to do with this?", "how do I talk to a database from python"])
def test_course_content_that_mentions_the_same_words_is_not_a_request_for_a_person(text):
    assert not asks_for_human(text)


@pytest.mark.parametrize(
    ("text", "category"),
    [
        ("I want a refund", EscalationCategory.BILLING),
        ("I was charged twice", None),  # "charged twice" alone is not one of the first-person phrasings; support mode below catches looser ones
        ("I was accused of cheating in my test", EscalationCategory.INTEGRITY),
        ("I can't log in to my account", EscalationCategory.ACCESS),
        ("I was removed from the batch", EscalationCategory.ACCESS),
    ],
)
def test_first_person_matters_of_money_integrity_and_access_escalate_in_any_conversation(text, category):
    assert sensitive_category(text, LEARNING) == category


def test_a_course_about_payments_is_not_mistaken_for_a_billing_problem():
    assert sensitive_category("How does a payment gateway work?", LEARNING) is None
    assert sensitive_category("Explain how plagiarism detection tools compare code", LEARNING) is None


@pytest.mark.parametrize(
    ("text", "category"),
    [("How do I pay my fee?", EscalationCategory.BILLING), ("my test was flagged for integrity", EscalationCategory.INTEGRITY), ("my password does not work", EscalationCategory.ACCESS)],
)
def test_the_support_assistant_matches_looser_phrasings(text, category):
    assert sensitive_category(text, SUPPORT) == category


def test_an_ordinary_question_escalates_nothing():
    assert sensitive_category("What is a base case?", SUPPORT) is None


def test_lookups_are_chosen_from_the_question():
    assert lookups_wanted("Is my enrolment active and did I pass the test?") == {"enrolment", "attempts"}
    assert lookups_wanted("Where is my certificate?") == {"certificates"}
    assert lookups_wanted("What is recursion?") == set()


def test_asking_for_the_solution_is_recognised():
    assert asks_for_solution("just give me the full code")
    assert asks_for_solution("Show me the solution")
    assert not asks_for_solution("what does this error mean")


def test_cited_numbers_are_returned_once_in_order():
    assert cited_numbers("Use a base case [2]. It stops [1]. Again [2].") == [2, 1]
    assert cited_numbers("no citations here") == []
