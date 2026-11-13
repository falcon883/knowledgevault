"""KV-48: the passage shown for a search result is the part that matched."""

import pytest

from passage import best_passage, query_stems, stem

MARATHON = (
    "Training for a first marathon\n"
    "Most beginners need 16 to 20 weeks to prepare for 26.2 miles. If you can already run "
    "three miles comfortably, you have a good starting point.\n\n"
    "Build your weekly mileage slowly, by no more than about ten percent a week. Run three "
    "or four days a week, and make one of them the long run on the weekend. Add a mile to "
    "the long run most weeks and cut back every fourth week so your legs can recover.\n\n"
    "In the last two to three weeks, taper: keep the pace but reduce the mileage so you arrive "
    "at the start line fresh. Practise your race-day breakfast and your energy gels on long runs, "
    "and try not to wear anything new on race morning.\n\n"
    "On the day, start slower than feels necessary. Many first-timers run the first half too fast "
    "and struggle through the last six miles."
)


@pytest.mark.parametrize(
    "a, b",
    [
        ("vaccines", "vaccine"),
        ("running", "runs"),
        ("running", "run"),
        ("bubbles", "bubble"),
        ("miles", "mile"),
        ("preparing", "prepare"),
        ("weekly", "weeks"),
    ],
)
def test_stem_joins_forms_of_a_word(a, b):
    assert stem(a) == stem(b)


def test_stem_keeps_short_words_whole():
    assert stem("bus") == "bus"
    assert stem("red") == "red"


def test_query_stems_drop_filler_and_keep_numbers():
    stems = query_stems("How should I prepare to run 26 miles?")
    assert stem("prepare") in stems and stem("run") in stems and "26" in stems and stem("miles") in stems
    assert "how" not in stems and "should" not in stems and "to" not in stems


def test_picks_the_sentence_with_the_most_query_words():
    passage, matched = best_passage(MARATHON, "when should I taper and how far should I cut the mileage")
    assert passage.startswith("In the last two to three weeks, taper")
    assert "taper" in matched and "mileage" in matched


def test_passage_stays_within_the_limit():
    passage, _ = best_passage(MARATHON, "build weekly mileage slowly", limit=120)
    assert len(passage) <= 120
    # Only the one sentence fits, so it is shown whole, with no ellipsis.
    assert passage == "Build your weekly mileage slowly, by no more than about ten percent a week."


def test_a_sentence_longer_than_the_limit_is_cut_at_a_word():
    passage, _ = best_passage(MARATHON, "build weekly mileage slowly", limit=40)
    assert passage == "Build your weekly mileage slowly, by no…"
    assert len(passage) <= 41  # the limit plus the ellipsis


def test_continues_with_following_sentences_while_they_fit():
    passage, _ = best_passage("Cats purr. Dogs bark loudly. Birds sing at dawn.", "dogs", limit=300)
    assert passage == "Dogs bark loudly. Birds sing at dawn."


def test_falls_back_to_the_start_when_no_word_matches():
    passage, matched = best_passage(MARATHON, "quantum chromodynamics", limit=60)
    assert passage.startswith("Training for a first marathon")
    assert len(passage) <= 61
    assert matched == []


def test_query_of_only_filler_words_falls_back():
    passage, matched = best_passage("Cats purr. Dogs bark.", "what is the", limit=300)
    assert passage == "Cats purr. Dogs bark."
    assert matched == []


def test_tie_goes_to_the_earlier_sentence():
    passage, _ = best_passage("Cats purr softly. Cats nap often.", "cats", limit=17)
    assert passage.startswith("Cats purr")


def test_matched_words_are_unique_lowercase_and_in_order():
    _, matched = best_passage("Dogs bark. The dogs ran, and the dog barked.", "dog barking", limit=300)
    assert matched == ["dogs", "bark", "dog", "barked"]


def test_pilot_p4_wording_lands_on_the_sentence_about_weeks():
    passage, matched = best_passage(
        MARATHON, "A gradual weekly running plan for someone preparing for their first 26.2-mile race."
    )
    assert "weeks" in passage.lower()
    assert matched  # something to highlight


def test_empty_text_is_safe():
    assert best_passage("", "anything") == ("", [])
    assert best_passage("   \n  ", "anything") == ("", [])
