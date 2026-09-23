import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("k20_video_engine.py")
spec = importlib.util.spec_from_file_location("k20_video_engine", MODULE_PATH)
engine = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(engine)


def test_20_transcripts_parse():
    episodes = engine.parse_episodes()
    assert len(episodes) == 20
    assert set(episodes) == set(range(1, 21))
    assert all(ep.title and ep.hook and ep.body and ep.cta for ep in episodes.values())


def test_search_map_complete():
    assert set(engine.EPISODE_SEARCH) == set(range(1, 21))


def test_srt_time():
    assert engine.srt_time(0) == "00:00:00,000"
    assert engine.srt_time(61.25) == "00:01:01,250"
