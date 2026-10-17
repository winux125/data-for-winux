"""Silent visual decoding. Evidence timestamps come from source PTS, not model text."""
import base64
import io
import math
from dataclasses import dataclass

import av
from PIL import Image


@dataclass
class Frame:
    timestamp: float
    image: Image.Image

    def evidence(self):
        stream = io.BytesIO()
        self.image.save(stream, format='JPEG', quality=88)
        return {'timestamp_sec': round(self.timestamp, 4),
                'image_base64': base64.b64encode(stream.getvalue()).decode('ascii')}


def metadata(path):
    with av.open(str(path)) as video:
        if not video.streams.video:
            raise ValueError('No video stream')
        stream = video.streams.video[0]
        duration = float(stream.duration * stream.time_base) if stream.duration else float(video.duration or 0) / av.time_base
        if not math.isfinite(duration) or not 0 < duration <= 180:
            raise ValueError('Video duration must be between 0 and 180 seconds')
        if stream.width * stream.height > 4096 * 2160:
            raise ValueError('Video resolution exceeds limit')
    return duration


def sample(path, targets):
    """Read sequentially once and select first decoded frame at/after each target."""
    targets = sorted(set(max(0., float(t)) for t in targets))
    frames, index = [], 0
    with av.open(str(path)) as video:
        stream = video.streams.video[0]
        stream.thread_type = 'AUTO'
        start = float((stream.start_time or 0) * stream.time_base)
        for decoded in video.decode(stream):
            if decoded.pts is None:
                continue
            timestamp = float(decoded.pts * stream.time_base) - start
            if index >= len(targets):
                break
            if timestamp + 1e-5 < targets[index]:
                continue
            image = decoded.to_image().convert('RGB')
            image.thumbnail((1280, 1280))
            frame = Frame(timestamp, image)
            while index < len(targets) and timestamp + 1e-5 >= targets[index]:
                frames.append(frame)
                index += 1
    if not frames:
        raise ValueError('No decodable frames')
    return frames
