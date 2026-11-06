from app.pipeline.transcoder import _targets_for


def test_ladder_only_includes_rungs_at_or_below_source_height() -> None:
    assert _targets_for(1080) == [(1080, "1080p"), (720, "720p"), (480, "480p")]
    assert _targets_for(720) == [(720, "720p"), (480, "480p")]
    assert _targets_for(480) == [(480, "480p")]


def test_a_source_smaller_than_the_smallest_rung_gets_one_native_rendition() -> None:
    assert _targets_for(360) == [(360, "native")]
