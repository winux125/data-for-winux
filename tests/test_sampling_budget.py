"""Sampling guarantees, not event recall measurements."""
from backend.pipeline import observation_windows


def test_long_video_has_bounded_overview_and_jepa_focus():
    windows = observation_windows(180, 80)
    assert [len(w) for w in windows] == [24, 7]
    assert windows[0][0] == 0
    assert windows[0][-1] == 179.95
    assert windows[1][0] == 75
    assert windows[1][-1] == 85


def test_short_video_and_edge_peak_stay_inside_duration():
    for duration in (.1, 10, 24, 25, 180):
        for peak in (None, 0, duration):
            windows = observation_windows(duration, peak)
            assert len(windows) <= 2
            assert sum(map(len, windows)) <= 31
            assert all(0 <= t < duration for w in windows for t in w)
