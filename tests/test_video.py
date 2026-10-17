import io
import base64

import av
import pytest
from PIL import Image

from backend.video import metadata, sample


def test_source_pts_and_decodable_jpeg(tmp_path):
    path = tmp_path / 'generated.mov'
    with av.open(str(path), 'w') as output:
        stream = output.add_stream('mpeg4', rate=10)
        stream.width, stream.height = 64, 64
        stream.pix_fmt = 'yuv420p'
        for i in range(20):
            frame = av.VideoFrame.from_image(Image.new('RGB', (64, 64), (i * 10, 0, 0)))
            for packet in stream.encode(frame):
                output.mux(packet)
        for packet in stream.encode():
            output.mux(packet)
    assert 1.9 <= metadata(path) <= 2.1
    frames = sample(path, [.34, 1.22])
    assert .34 <= frames[0].timestamp <= .45
    assert 1.22 <= frames[1].timestamp <= 1.35
    evidence = frames[0].evidence()
    assert evidence['timestamp_sec'] == round(frames[0].timestamp, 4)
    assert Image.open(io.BytesIO(base64.b64decode(evidence['image_base64']))).format == 'JPEG'


def test_corrupt_file_fails_explicitly(tmp_path):
    path = tmp_path / 'bad.mov'
    path.write_bytes(b'not a movie')
    with pytest.raises(Exception):
        metadata(path)
