"""Helpers for turning chat requests into concise image instructions."""

import re

IMAGE_REQUEST_SUFFIX = re.compile(
    r"\b(?:send|show|take|make|generate|create|draw)\s+(?:me\s+)?"
    r"(?:(?:a|an|some)\s+)?(?:photo|picture|image|pic|selfie|portrait)\b",
    re.IGNORECASE,
)
IMAGE_REQUEST_PREFIX = re.compile(
    r"^\s*(?:(?:please|can you|could you|would you)\s+)?"
    r"(?:(?:show|send|take|make|generate|create|draw)\s+(?:me\s+)?)",
    re.IGNORECASE,
)
IMAGE_TERMS = re.compile(r"\b(?:photo|picture|image|pic|selfie|portrait)\b", re.IGNORECASE)
IMAGE_COMMAND = re.compile(
    r"^\s*(?:(?:please|can you|could you|would you)\s+)?"
    r"(?:change\s+(?:my\s+)?(?:outfit\s+)?(?:to|into)|"
    r"put\s+(?:me\s+)?in(?:to)?|dress\s+me\s+in|wear(?:ing)?)\s+",
    re.IGNORECASE,
)
IMAGE_INTENT = re.compile(
    r"\b(?:image|picture|photo|pic|selfie|show me|send me|draw|take a photo|take a picture)\b",
    re.IGNORECASE,
)


def image_prompt_from_chat(message: str) -> str:
    message = re.sub(r"\bchage\b", "change", message, flags=re.IGNORECASE)
    message = re.sub(r"\badn\b", "and", message, flags=re.IGNORECASE)
    prompt = IMAGE_REQUEST_SUFFIX.sub("", message)
    prompt = IMAGE_REQUEST_PREFIX.sub("", prompt)
    prompt = IMAGE_TERMS.sub("", prompt)
    prompt = IMAGE_COMMAND.sub("", prompt)
    prompt = re.sub(r"\b(?:of|and|please)\b", " ", prompt, flags=re.IGNORECASE)
    prompt = re.sub(r"\s+", " ", prompt).strip(" ,.!?;:")
    return prompt or "a natural, relaxed pose"


def is_image_request(message: str) -> bool:
    return bool(IMAGE_INTENT.search(message))
