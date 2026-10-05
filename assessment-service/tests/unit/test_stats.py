from app.services.stats_service import compute_stats


def test_no_data_gives_no_statistics():
    assert compute_stats([], min_sample=30).sample_size == 0
    assert compute_stats([], min_sample=30).difficulty_index is None


def test_difficulty_is_the_average_share_of_marks_earned():
    computed = compute_stats([(1.0, 90), (0.5, 60), (0.0, 20), (1.0, 80)], min_sample=30)
    assert computed.difficulty_index == 0.625 and computed.sample_size == 4


def test_discrimination_needs_a_meaningful_sample():
    assert compute_stats([(1.0, 90), (0.0, 10)] * 5, min_sample=30).discrimination is None


def test_a_question_strong_students_get_right_and_weak_students_get_wrong_discriminates_well():
    rows = [(1.0, 80 + n % 20) for n in range(20)] + [(0.0, n % 20) for n in range(20)]
    computed = compute_stats(rows, min_sample=30)
    assert computed.discrimination == 1.0 and computed.difficulty_index == 0.5


def test_a_question_everyone_gets_right_or_wrong_regardless_of_ability_does_not_discriminate():
    rows = [(1.0, n * 2.5) for n in range(40)]
    assert compute_stats(rows, min_sample=30).discrimination == 0.0


def test_a_question_only_weak_students_get_right_discriminates_negatively():
    rows = [(0.0, 60 + n) for n in range(20)] + [(1.0, n) for n in range(20)]
    assert compute_stats(rows, min_sample=30).discrimination == -1.0
