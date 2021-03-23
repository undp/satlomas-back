from numbers import Number
from typing import Dict, List, Tuple

import numpy as np

HexColor = str
# TODO: Represent ColorMap as a Dict[Number, HexColor]
ColorMap = List[Tuple[Number, HexColor]]
DiscreteColorMap = Dict[Number, List[int]]


def rescale_to_byte(v, min_value, max_value) -> np.ndarray:
    # Rescale to range 1-255 (so we can have 0 as nodata later)
    norm_v = (v - min_value) / (max_value - min_value)
    return np.round(np.clip(norm_v * 255, 0, 255)).astype(np.uint8)


def hex_to_dec_string(value):
    return np.array(
        [int(value[i:j], 16) for i, j in [(0, 2), (2, 4), (4, 6)]] + [255], np.uint8
    )


def build_lut_cmap(cmap: ColorMap) -> DiscreteColorMap:
    # Build lookup table from color map
    res = []
    min_value, max_value = cmap[0][0], cmap[-1][0]

    for i, (v, color) in enumerate(cmap):
        rgb_color = hex_to_dec_string(color[1:])
        if i == 0:
            res.append((0, rgb_color))
        else:
            prev_v = cmap[i - 1][0]
            min_v = rescale_to_byte(prev_v, min_value=min_value, max_value=max_value)
            max_v = rescale_to_byte(v, min_value=min_value, max_value=max_value)
            values = np.arange(min_v, max_v + 1, dtype=np.uint8)

            prev_rgb_color = hex_to_dec_string(cmap[i - 1][1][1:])
            colors = np.round(
                np.linspace(prev_rgb_color, rgb_color, len(values))
            ).astype(np.uint8)
            for value, color in zip(values, colors):
                res.append((value, color))

    return {v: list(color) for v, color in res}


def apply_cmap(data: np.ndarray, colormap: ColorMap) -> Tuple[np.ndarray, np.ndarray]:
    """Apply colormap to data"""
    discrete_cmap = build_lut_cmap(colormap)
    return apply_discrete_cmap(data, discrete_cmap)


def apply_discrete_cmap(
    data: np.ndarray, colormap: DiscreteColorMap
) -> Tuple[np.ndarray, np.ndarray]:
    """Apply discrete colormap.

    Args:
        data (numpy.ndarray): 1D image array to translate to RGB.
        colormap (dict): Discrete ColorMap dictionary.

    Returns:
        tuple: Data (numpy.ndarray) and Alpha band (numpy.ndarray).

    Examples:
        >>> data = numpy.random.randint(0, 3, size=(1, 256, 256))
            cmap = {
                0, [0, 0, 0, 0],
                1: [255, 255, 255, 255],
                2: [255, 0, 0, 255],
                3: [255, 255, 0, 255],
            }
            data, mask = apply_discrete_cmap(data, cmap)
            assert data.shape == (3, 256, 256)

    """
    res = np.zeros((data.shape[1], data.shape[2], 4), dtype=np.uint8)

    for k, v in colormap.items():
        res[data[0] == k] = v

    data = np.transpose(res, [2, 0, 1])

    return data[:-1], data[-1]
