import numpy as np

from app.rag.chunker import chunk_text, window_transcript
from app.rag.similarity import LexicalIndex, cosine_scores, normalize_rows, tokenize, top_k


def test_short_text_is_one_chunk():
    assert chunk_text("One paragraph only.", 500) == ["One paragraph only."]


def test_paragraphs_are_packed_up_to_the_limit_and_never_split_needlessly():
    text = "\n\n".join(["a" * 100, "b" * 100, "c" * 100])
    chunks = chunk_text(text, 250)
    assert chunks == ["a" * 100 + "\n\n" + "b" * 100, "c" * 100]


def test_an_oversized_paragraph_is_split_at_sentence_ends():
    paragraph = " ".join(f"Sentence number {i} is here." for i in range(30))
    chunks = chunk_text(paragraph, 200)
    assert len(chunks) > 1 and all(len(c) <= 200 for c in chunks) and " ".join(chunks).split() == paragraph.split()


def test_one_enormous_sentence_is_cut_rather_than_kept_whole():
    chunks = chunk_text("x" * 1000, 300)
    assert [len(c) for c in chunks] == [300, 300, 300, 100]


def test_blank_text_makes_no_chunks():
    assert chunk_text("  \n\n  ", 100) == []


def test_transcript_segments_are_grouped_into_timed_windows():
    segments = [(0.0, 20.0, "Welcome."), (20.0, 40.0, "Today: recursion."), (40.0, 70.0, "A base case stops it."), (70.0, 100.0, "Next, loops."), (100.0, 120.0, "Done.")]
    windows = window_transcript(segments, 60, 1000)
    # a window closes as soon as adding the next segment would stretch it past the target length
    assert [(w.start, w.end) for w in windows] == [(0.0, 40.0), (40.0, 100.0), (100.0, 120.0)]
    assert windows[0].text == "Welcome. Today: recursion."


def test_transcript_windows_respect_the_character_cap_and_start_order():
    segments = [(10.0, 12.0, "b" * 30), (0.0, 2.0, "a" * 30)]
    windows = window_transcript(segments, 600, 40)
    assert [w.text[0] for w in windows] == ["a", "b"]


def test_tokenize_drops_stopwords_and_keeps_code_words():
    assert tokenize("How does the C++ std::vector work?") == ["c++", "std", "vector", "work"]


def test_cosine_prefers_the_closer_vector_and_top_k_breaks_ties_by_position():
    matrix = normalize_rows(np.asarray([[1.0, 0.0], [0.7, 0.7], [0.0, 1.0], [1.0, 0.0]], dtype=np.float32))
    scores = cosine_scores([1.0, 0.0], matrix)
    assert [i for i, _ in top_k(scores, 3)] == [0, 3, 1]


def test_a_vector_of_the_wrong_size_or_zero_length_scores_nothing():
    matrix = normalize_rows(np.asarray([[1.0, 0.0]], dtype=np.float32))
    assert float(cosine_scores([1.0, 0.0, 0.0], matrix)[0]) == 0.0
    assert float(cosine_scores([0.0, 0.0], matrix)[0]) == 0.0


def test_lexical_scores_rank_the_passage_that_covers_the_question():
    index = LexicalIndex(["Recursion needs a base case", "A for loop repeats code", "Sorting arranges items in order"])
    scores = index.scores("what is a base case in recursion")
    assert int(np.argmax(scores)) == 0 and scores[0] > scores[1]


def test_a_question_word_no_passage_contains_lowers_the_score():
    index = LexicalIndex(["Recursion needs a base case"])
    assert float(index.scores("recursion quantum")[0]) < float(index.scores("recursion")[0])
    assert float(index.scores("quantum")[0]) == 0.0
