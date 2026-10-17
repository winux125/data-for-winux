"""Load all real models and make one visual call; no scripted inference."""
import sys
from pathlib import Path
import logging
logging.basicConfig(level=logging.INFO)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.pipeline import Pipeline
from backend.video import sample

p = Pipeline()
video = sys.argv[1]
frames = sample(video, [0, 1, 2, 3, 4, 5, 6])
print('VISUAL_OBSERVATION_COUNT', len(p.observer.observe(frames)), flush=True)
