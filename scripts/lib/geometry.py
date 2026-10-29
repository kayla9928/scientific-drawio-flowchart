from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Tuple


Point = Tuple[float, float]


@dataclass(frozen=True)
class Rect:
    cell_id: str
    x: float
    y: float
    width: float
    height: float

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def bottom(self) -> float:
        return self.y + self.height

    def anchor(self, x_fraction: float, y_fraction: float) -> Point:
        return (self.x + self.width * x_fraction, self.y + self.height * y_fraction)


def rectangles_overlap(a: Rect, b: Rect, epsilon: float = 0.0) -> bool:
    return (
        a.x < b.right - epsilon and a.right > b.x + epsilon
        and a.y < b.bottom - epsilon and a.bottom > b.y + epsilon
    )


def is_axis_aligned(a: Point, b: Point, epsilon: float) -> bool:
    return abs(a[0] - b[0]) <= epsilon or abs(a[1] - b[1]) <= epsilon


def segment_intersects_rect_interior(a: Point, b: Point, rect: Rect, epsilon: float) -> bool:
    if not is_axis_aligned(a, b, epsilon):
        return False
    left = rect.x + epsilon
    right = rect.right - epsilon
    top = rect.y + epsilon
    bottom = rect.bottom - epsilon
    if abs(a[0] - b[0]) <= epsilon:
        x = (a[0] + b[0]) / 2
        low, high = sorted((a[1], b[1]))
        return left < x < right and high > top and low < bottom
    y = (a[1] + b[1]) / 2
    low, high = sorted((a[0], b[0]))
    return top < y < bottom and high > left and low < right


def polyline_segments(points: Iterable[Point]) -> List[Tuple[Point, Point]]:
    values = list(points)
    return list(zip(values, values[1:]))
