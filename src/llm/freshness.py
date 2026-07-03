"""Freshness tracking: detect overused phrases in recent published entries.

Scans recent Hugo posts for phrases that keep recurring, then builds prompt
directives that either ban a phrase (language tics like "End of entry") or
vary the treatment of it (real scene fixtures like the white van, which appear
daily in the camera frame and MUST remain mentionable).

Design rules:
- Phrases that name physical scene objects are NEVER banned. If the camera sees
  a white van every day, the diary must be allowed to talk about it. Instead,
  recurring fixtures get rotating "treatment" guidance (acknowledge briefly,
  note what changed, give it a designation, etc.).
- List sizes are randomized on every run - sometimes zero, sometimes several -
  so the prompt itself never becomes a static pattern.
- Everything is computed locally from files on disk. No LLM calls, no cost.
"""
import logging
import random
import re
from collections import Counter
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

# Common words that can't start/end a tracked phrase
STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "of", "in", "on", "at", "to", "for",
    "with", "from", "by", "as", "is", "are", "was", "were", "be", "been", "am",
    "it", "its", "this", "that", "these", "those", "my", "i", "you", "your",
    "he", "she", "they", "them", "their", "we", "our", "us", "his", "her",
    "so", "if", "then", "than", "not", "no", "yes", "up", "down", "out",
    "into", "over", "under", "about", "after", "before", "between", "while",
    "have", "has", "had", "do", "does", "did", "will", "would", "can", "could",
    "may", "might", "just", "more", "most", "some", "any", "each", "there",
    "here", "when", "where", "what", "who", "how", "why", "which", "one",
    "two", "three", "still", "yet", "also", "very", "now", "today",
}

# Words that indicate a phrase names a physical scene object. Phrases containing
# any of these are never banned - the camera may genuinely show them every day.
SCENE_OBJECT_WORDS = {
    "van", "truck", "car", "suv", "sedan", "vehicle", "bicycle", "scooter",
    "cart", "bus", "taxi", "flag", "sign", "balcony", "balconies", "lamp",
    "streetlamp", "lantern", "awning", "shutter", "shutters", "door", "window",
    "curb", "sidewalk", "pavement", "manhole", "pothole", "cone", "barricade",
    "bench", "trash", "dumpster", "planter", "pole", "wire", "neon", "railing",
    "dog", "cat", "bird", "pigeon", "horse", "mule", "carriage",
    # clothing - visible on pedestrians daily, must stay describable
    "shirt", "t-shirt", "dress", "hat", "cap", "jeans", "shorts", "jacket",
    "hoodie", "umbrella", "backpack", "sunglasses",
}

# Never tracked at all: the diary's own geography and identity. Banning the name
# of the street the robot watches would break the diary, not freshen it.
PROTECTED_PHRASES = {
    "bourbon street", "french quarter", "new orleans", "louisiana",
    "maintenance robot", "maintenance unit",
}

# Boilerplate tokens from post markdown that should never be tracked
JUNK_WORDS = {
    "observation", "posts", "http", "https", "png", "jpg", "jpeg", "cdt",
    "cst", "am", "pm", "b3n", "t5", "mnt", "b3t",
}

# Present-tense only: these must never prompt the robot to look up or cite past
# entries about the fixture - that memory cross-referencing is itself the tic.
FIXTURE_TREATMENTS = [
    "Treat it as a familiar regular: acknowledge it in a single clause without re-describing it, the way you'd nod at a neighbor you pass every day.",
    "Note one fresh sensory detail about it that you have never bothered to record - and only that.",
    "Mention it only if something about it seems different today; otherwise let its unremarked presence speak for itself.",
    "Refer to it obliquely, without naming it directly - a regular reader will know exactly what you mean.",
    "Let it be background: one breath, no analysis, the way a person stops noticing furniture in their own home.",
]


def _clean_post_text(raw: str) -> str:
    """Strip frontmatter, markdown syntax, links, and the scheduling footer."""
    text = re.sub(r"^\+\+\+.*?\+\+\+", "", raw, flags=re.DOTALL)
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)  # images
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)  # links -> label
    text = re.sub(r"\*Next scheduled observation:.*", "", text)
    return text


def _tokenize(text: str) -> List[str]:
    # [^\W\d_] = any unicode letter, so words like façades survive intact;
    # apostrophes/hyphens allowed inside a word so "city's" stays one token
    return re.findall(r"[^\W\d_](?:[^\W\d_]|['’-])*", text.lower())


def _phrase_ok(words: Tuple[str, ...]) -> bool:
    if words[0] in STOPWORDS or words[-1] in STOPWORDS:
        return False
    if any(w in JUNK_WORDS for w in words):
        return False
    if " ".join(words) in PROTECTED_PHRASES:
        return False
    content = [w for w in words if w not in STOPWORDS]
    if len(content) < 2 and len(words) > 1:
        return False
    if not any(len(w) > 3 for w in words):
        return False
    return True


def _is_scene_object(phrase: str) -> bool:
    return any(w in SCENE_OBJECT_WORDS for w in phrase.split())


def find_overused_phrases(posts_dir: Path, sample_size: Optional[int] = None) -> List[Tuple[str, int]]:
    """
    Scan recent posts for 2-4 word phrases that recur across many entries.

    Returns list of (phrase, num_posts_containing_it), most prevalent first.
    The sample window itself is randomized so the detector's blind spots shift
    from run to run.
    """
    files = sorted(Path(posts_dir).glob("*.md"))
    if len(files) < 4:
        return []
    if sample_size is None:
        sample_size = random.randint(8, 16)
    recent = files[-sample_size:]

    per_post_phrases = []
    for f in recent:
        try:
            words = _tokenize(_clean_post_text(f.read_text(encoding="utf-8")))
        except Exception as e:
            logger.warning(f"Freshness scan skipped {f.name}: {e}")
            continue
        phrases = set()
        for n in (2, 3, 4):
            for i in range(len(words) - n + 1):
                gram = tuple(words[i:i + n])
                if _phrase_ok(gram):
                    phrases.add(" ".join(gram))
        per_post_phrases.append(phrases)

    if len(per_post_phrases) < 4:
        return []

    counts = Counter()
    for phrases in per_post_phrases:
        counts.update(phrases)

    threshold = max(3, int(0.4 * len(per_post_phrases)))
    overused = [(p, c) for p, c in counts.items() if c >= threshold]

    # Drop phrases that are substrings of a longer overused phrase with
    # (nearly) the same prevalence - keep the most specific form.
    overused.sort(key=lambda pc: (-pc[1], -len(pc[0])))
    kept: List[Tuple[str, int]] = []
    for phrase, count in overused:
        if any(phrase in longer and count <= lcount + 1 for longer, lcount in kept):
            continue
        kept.append((phrase, count))
    return kept


def build_freshness_directives(overused: List[Tuple[str, int]],
                               image_description: Optional[str] = None) -> str:
    """
    Turn overused phrases into prompt directives.

    - Scene-object phrases (or any phrase present in today's image description)
      are fixtures: never banned, sometimes given rotating treatment guidance.
    - Everything else is a language tic, eligible for a randomly-sized ban list.
    """
    if not overused:
        return ""

    desc = (image_description or "").lower()
    fixtures, bannable = [], []
    for phrase, count in overused:
        if _is_scene_object(phrase) or (desc and phrase in desc):
            fixtures.append((phrase, count))
        else:
            bannable.append((phrase, count))

    parts = []

    # Ban list: variable size, sometimes absent entirely
    if bannable and random.random() < 0.85:
        pool = bannable[:10]
        k = random.randint(1, min(6, len(pool)))
        chosen = random.sample(pool, k)
        chosen.sort(key=lambda pc: -pc[1])
        phrase_list = ", ".join(f'"{p}"' for p, _ in chosen)
        parts.append(
            f"FRESHNESS: These exact phrases have appeared in many of your recent entries "
            f"and have become habits: {phrase_list}. Do not use them in this entry. "
            f"Say what you mean a different way."
        )

    # Fixture treatment: never a ban, rotating guidance, variable count
    if fixtures and random.random() < 0.7:
        k = 1 if len(fixtures) == 1 or random.random() < 0.7 else 2
        chosen = random.sample(fixtures[:6], min(k, len(fixtures)))
        names = " and ".join(f'"{p}"' for p, _ in chosen)
        treatment = random.choice(FIXTURE_TREATMENTS)
        if len(chosen) > 1:
            appeared, is_part = "have appeared", "they are real, recurring parts"
        else:
            appeared, is_part = "has appeared", "it is a real, recurring part"
        parts.append(
            f"FAMILIAR FIXTURE: {names} {appeared} in many of your recent entries - "
            f"{is_part} of your view, so do not pretend it isn't there. "
            f"But vary your treatment of it today: {treatment} "
            f"Do not query your memories about it or cite past observations of it - "
            f"handle it entirely in the present."
        )

    return "\n\n".join(parts)


def get_freshness_directives(posts_dir: Path, image_description: Optional[str] = None) -> str:
    """Convenience wrapper: scan + build, with logging. Never raises."""
    try:
        overused = find_overused_phrases(posts_dir)
        if overused:
            preview = ", ".join(f"{p} ({c})" for p, c in overused[:8])
            logger.info(f"🔄 Freshness scan found {len(overused)} overused phrase(s): {preview}")
        else:
            logger.info("🔄 Freshness scan found no overused phrases")
        directives = build_freshness_directives(overused, image_description)
        if directives:
            logger.info(f"🔄 Freshness directives:\n{directives}")
        return directives
    except Exception as e:
        logger.warning(f"Freshness tracking failed (continuing without it): {e}")
        return ""
