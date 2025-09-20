from dataclasses import dataclass


@dataclass
class Region:
    x: int
    y: int
    w: int
    h: int


@dataclass
class ColorLocation:
    x: int
    y: int
