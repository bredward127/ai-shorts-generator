"""Pydantic schema for the ad-planner's messaging brief + DIY shot list."""
from __future__ import annotations

from typing import List, Literal

from pydantic import BaseModel, Field


class FeatureBenefit(BaseModel):
    feature: str = Field(..., description="A physical feature of the product")
    benefit: str = Field(..., description="What that feature actually does for the buyer")


class AdBrief(BaseModel):
    hook: str = Field(..., description="First line — stops the scroll for this specific audience")
    problem: str = Field(..., description="One sentence naming the annoyance the audience recognizes in themselves")
    features: List[FeatureBenefit] = Field(..., min_length=2, max_length=5)
    value_props: List[str] = Field(..., min_length=2, max_length=4,
                                    description="Short scannable bullets, 3-6 words each, benefit-first")
    cta: str = Field(..., description="Plain, low-friction call to action; never invented urgency/pricing")


class AdShot(BaseModel):
    name: str = Field(..., description="Short shot name, e.g. 'In bed, hands-free'")
    proves: str = Field(..., description="Which line from the brief this shot supports")
    angle: str = Field(..., description="Camera angle and distance, concrete, e.g. 'eye-level, ~2.5 ft, 3/4 turn'")
    framing: str = Field(..., description="What fills the frame and how tight")
    lighting: str = Field(..., description="Light direction and quality")
    background: str = Field(..., description="Background/surface guidance")
    props: str = Field("", description="What to include in frame, if anything")
    mistake: str = Field(..., description="The #1 mistake that ruins this exact shot")
    motion: str = Field("", description="How to move the phone while filming this shot as a "
                        "3-5 second video clip, e.g. 'slow push in toward the pockets' or "
                        "'hold still, then tilt up to the screen'")
    diagram_layout: Literal["wide", "macro", "profile"] = Field(
        ..., description="Which floor-plan sketch fits this shot: 'wide' for a "
        "context/hero shot with the camera a couple feet back, 'macro' for a tight "
        "feature close-up under a foot away, 'profile' for a pure side view that "
        "shows the product's silhouette/shape."
    )


class AdVideoScene(BaseModel):
    index: int = Field(..., description="1-based scene order")
    narration: str = Field(..., description="One spoken voiceover sentence for this scene")
    shot_index: int = Field(..., description="1-based number of the shot from the shot list "
                            "whose footage plays under this line; 0 if no shot fits")
    visual_description: str = Field(..., description="What's on screen, as a vivid image "
                                    "description — used to generate a fallback visual only "
                                    "if the creator has no footage for this scene")


class AdVideoScript(BaseModel):
    scenes: List[AdVideoScene] = Field(..., min_length=4, max_length=6)
    youtube_title: str
    youtube_description: str
    tiktok_caption: str
    x_caption: str
    hashtags: List[str]


class AdPlan(BaseModel):
    product_name: str
    slug: str = Field(..., description="kebab-case file-safe slug")
    brief: AdBrief
    shots: List[AdShot] = Field(..., min_length=2, max_length=4)
