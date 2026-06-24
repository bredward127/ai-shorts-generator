"""Pydantic schema for the image-first script/scene JSON the LLM returns.

v2: no on-screen text. Each scene is a distinct cinematic image + one spoken line.
The only text the viewer sees is the karaoke captions.
"""
from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class Scene(BaseModel):
    index: int = Field(..., description="1-based scene order")
    image_prompt: str = Field(
        ..., description="A vivid, DISTINCT cinematic scene that illustrates the line. "
        "Describe subject, setting, lighting, mood, composition. No text in the image."
    )
    narration: str = Field(..., description="One spoken sentence for this scene")
    motion_prompt: str = Field(
        "", description="If this is the hero scene, what should move (for Wan i2v)"
    )
    hero: bool = Field(False, description="Mark ONE scene as the hero for optional Wan motion")


class Script(BaseModel):
    topic: str
    slug: str = Field(..., description="kebab-case file-safe slug")
    scenes: List[Scene] = Field(..., min_length=4, max_length=6)
    # Per-platform social copy.
    youtube_title: str
    youtube_description: str
    tiktok_caption: str
    x_caption: str
    hashtags: List[str]
