from dataclasses import dataclass

@dataclass
class SpriteState:
    name: str
    animation: str
    direction: str = "south"

SPRITE_STATES = {
    "idle": SpriteState("idle","idle_loop"),
    "walk": SpriteState("walk","walk_cycle"),
    "work": SpriteState("work","typing"),
    "think": SpriteState("think","thinking"),
    "celebrate": SpriteState("celebrate","celebration"),
}