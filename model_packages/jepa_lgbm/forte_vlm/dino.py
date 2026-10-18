"""Spatial pooling masks for image encoders on full-frame letterboxed video."""
import numpy as np


def region_masks(box, resolution=384, patch=16):
    if resolution % patch:
        raise ValueError('Resolution must be divisible by patch size')
    top, left, height, width = box
    centers = np.arange(resolution // patch) * patch + patch / 2
    yy, xx = np.meshgrid(centers, centers, indexing='ij')
    visible = (yy >= top) & (yy < top + height) & (xx >= left) & (xx < left + width)
    masks = [visible] + [visible & (yy < top + height / 2 if upper else yy >= top + height / 2)
                         & (xx < left + width / 2 if western else xx >= left + width / 2)
                         for upper in [True, False] for western in [True, False]]
    if any(not m.any() for m in masks):
        raise ValueError('Empty spatial region')
    return np.stack(masks)
