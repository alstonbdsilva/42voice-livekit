"""
Name Service for Caller Name Extraction, Normalization, Spelling Parsing, Dynamic STT Keywords, and State Management.
"""

import re
import json
import logging
from typing import Optional, Dict, Any, Tuple, List

logger = logging.getLogger("voice-agent.name_service")

# Map of common letter spoken sounds to single letters for phonetic spelling fallback
SPOKEN_LETTER_MAP = {
    "A": "A", "AY": "A", "EI": "A",
    "B": "B", "BEE": "B",
    "C": "C", "SEE": "C",
    "D": "D", "DEE": "D",
    "E": "E",
    "F": "F", "EFF": "F",
    "G": "G", "GEE": "G",
    "H": "H", "AITCH": "H",
    "I": "I", "EYE": "I",
    "J": "J", "JAY": "J",
    "K": "K", "KAY": "K",
    "L": "L", "ELL": "L",
    "M": "M", "EMM": "M", "EM": "M",
    "N": "N", "ENN": "N", "EN": "N",
    "O": "O", "OH": "O",
    "P": "P", "PEE": "P",
    "Q": "Q", "CUE": "Q",
    "R": "R", "AR": "R", "ARE": "R",
    "S": "S", "ESS": "S",
    "T": "T", "TEE": "T",
    "U": "U", "YOU": "U",
    "V": "V", "VEE": "V",
    "W": "W", "DOUBLE YOU": "W", "DOUBLEU": "W",
    "X": "X", "EX": "X",
    "Y": "Y", "WHY": "Y",
    "Z": "Z", "ZEE": "Z", "ZED": "Z"
}

DIGIT_WORDS = {"zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"}

# Non-name verb words to reject sentence fragments like "calling about billing"
NON_NAME_VERBS = {
    "calling", "trying", "asking", "here", "wondering", "looking", "going",
    "interested", "just", "having", "needing", "speaking", "using", "getting",
    "checking", "following", "hoping", "requesting", "inquiring", "about", "to", "for"
}


def build_stt_keywords(agent_data: Optional[Dict[str, Any]] = None, max_hints: int = 20, default_weight: float = 3.0) -> List[Tuple[str, float]]:
    """
    Build dynamic STT keyword boost tuples (word/phrase, weight) for Deepgram STT
    from the current call's agent configuration.

    Includes ONLY confirmed, structured system entities:
    - Agent display name ('name' / 'agent_name')
    - Client / Organization name ('client_name')

    Does NOT hardcode any caller names, static entity lists, or arbitrary KB text.
    """
    if not agent_data or not isinstance(agent_data, dict):
        return []

    raw_candidates = []

    # 1. Agent display name (e.g. "Agent Alpha")
    agent_name = agent_data.get("name") or agent_data.get("agent_name")
    if agent_name and isinstance(agent_name, str):
        raw_candidates.append(agent_name)

    # 2. Client / Organization name (e.g. "Company Alpha")
    client_name = agent_data.get("client_name")
    if client_name and isinstance(client_name, str):
        raw_candidates.append(client_name)

    seen_lower = set()
    cleaned_entities = []
    ignore_terms = {"voice agent", "unknown", "agent", "digital ai assistant", "assistant", "system", "default"}

    for candidate in raw_candidates:
        clean = candidate.strip()
        clean_lower = clean.lower()

        # Skip empty, long prose (>40 chars), URLs, numeric-only strings, or generic system terms
        if not clean or len(clean) < 2 or len(clean) > 40:
            continue
        if clean_lower in ignore_terms:
            continue
        if clean.isdigit() or re.match(r"^[\d\s\.\,\+\-]+$", clean):
            continue
        if clean_lower.startswith("http://") or clean_lower.startswith("https://") or "www." in clean_lower:
            continue
        if clean_lower in seen_lower:
            continue

        seen_lower.add(clean_lower)
        cleaned_entities.append(clean)

        if len(cleaned_entities) >= max_hints:
            break

    # Return deterministically sorted list of (entity, default_weight) tuples
    return [(entity, default_weight) for entity in sorted(cleaned_entities)]


def parse_caller_name(text: str) -> Optional[str]:
    """
    Extract caller name generically from input text such as:
    'My name is Alex.' -> 'Alex'
    'I am John' -> 'John'
    'No, Alex.' -> 'Alex'
    'It's Alex' -> 'Alex'
    'Alex' -> 'Alex'

    Rejects non-name sentences like 'I am calling about billing'.
    """
    if not text or not text.strip():
        return None

    clean_text = text.strip()

    # Regex patterns for name phrase extraction, including caller corrections
    patterns = [
        r"(?:my name is|i am|this is|call me|name's|i'm)\s+([A-Za-z\s'\-]+)",
        r"(?:no,?\s+|actually,?\s+|it's\s+|no\s+it's\s+)+([A-Za-z\s'\-]+)",
        r"^([A-Za-z\s'\-]+)$"
    ]

    for pattern in patterns:
        match = re.search(pattern, clean_text, re.IGNORECASE)
        if match:
            candidate = match.group(1).strip()
            # Clean trailing punctuation
            candidate = re.sub(r"[^\w\s'\-]", "", candidate).strip()
            words = candidate.split()
            
            # Name candidate validations:
            # 1. Reject if empty or has digits/digit words
            if not candidate or any(w.lower() in DIGIT_WORDS or w.isdigit() for w in words):
                continue

            # 2. Reject if candidate is too long (> 3 words) or starts with a non-name verb phrase (e.g. "calling about billing")
            if len(words) > 3:
                continue
            if words[0].lower() in NON_NAME_VERBS:
                continue

            # Return capitalized name
            return " ".join(word.capitalize() for word in words)

    return None


def normalize_spelled_name(text: str) -> Tuple[Optional[str], bool]:
    """
    Normalize letter-by-letter spelled names or detect numeric rejection generically.
    Returns (normalized_name, is_valid)
    Examples:
    'A B C D' -> ('Abcd', True)
    'A. B. C. D.' -> ('Abcd', True)
    'Seven four eight eight eight' -> (None, False)
    '7 4 8 8 8' -> (None, False)
    """
    if not text or not text.strip():
        return None, False

    clean = text.strip()

    # Check for digits or digit words
    words = [w.lower().strip(".,!?:;") for w in clean.split()]
    has_digits = any(w.isdigit() or w in DIGIT_WORDS for w in words)
    if has_digits:
        logger.warning(f"[Spelling] Input contains digits or numeric words: '{clean}' -> REJECTED")
        return None, False

    # Check for single-letter sequence e.g. "A B C D" or "A. B. C. D."
    letters = []
    tokens = re.split(r"[\s\.\-]+", clean)
    tokens = [t.strip().upper() for t in tokens if t.strip()]

    for token in tokens:
        if len(token) == 1 and token.isalpha():
            letters.append(token)
        elif token in SPOKEN_LETTER_MAP:
            letters.append(SPOKEN_LETTER_MAP[token])

    if len(letters) >= 2 and len(letters) == len(tokens):
        result = "".join(letters).capitalize()
        logger.info(f"[Spelling] Successfully normalized spelled name '{clean}' -> '{result}'")
        return result, True

    # Fallback to single word if all alphabetic
    if len(tokens) == 1 and tokens[0].isalpha():
        result = tokens[0].capitalize()
        return result, True

    return None, False


class NameCaptureState:
    """State machine for tracking caller name capture, corrections, and spelling retries."""
    def __init__(self, max_spelling_retries: int = 2):
        self.state = "WAITING_FOR_NAME"
        self.captured_name: Optional[str] = None
        self.spelling_retries = 0
        self.max_spelling_retries = max_spelling_retries

    def process_utterance(self, transcript: str) -> Dict[str, Any]:
        """
        Process utterance and return action recommendation for the voice agent.
        """
        # Check for explicit caller correction phrase e.g. "No, <Name>" or "It's <Name>"
        is_correction = bool(re.search(r"(?:no,?\s+|actually,?\s+|it's\s+|no\s+it's\s+)", transcript, re.IGNORECASE))
        extracted = parse_caller_name(transcript)

        if is_correction and extracted:
            self.captured_name = extracted
            self.state = "NAME_ACCEPTED"
            logger.info(f"[NameState] Caller correction processed: updated captured name to '{self.captured_name}'")
            return {"action": "corrected", "name": self.captured_name}

        if self.state == "NAME_ACCEPTED":
            return {"action": "continue", "name": self.captured_name}

        if self.state in ["WAITING_FOR_NAME_SPELLING", "SPELLING_RETRY"]:
            spelled_name, is_valid = normalize_spelled_name(transcript)
            if is_valid and spelled_name:
                self.captured_name = spelled_name
                self.state = "NAME_ACCEPTED"
                logger.info(f"[NameState] Name accepted from spelling: '{self.captured_name}'")
                return {"action": "accept", "name": self.captured_name}
            else:
                self.spelling_retries += 1
                if self.spelling_retries >= self.max_spelling_retries:
                    self.state = "NAME_ACCEPTED"
                    logger.warning(f"[NameState] Max spelling retries ({self.max_spelling_retries}) reached. Continuing without forcing retry.")
                    return {"action": "continue_without_spelling", "name": self.captured_name}
                else:
                    self.state = "SPELLING_RETRY"
                    logger.info(f"[NameState] Invalid spelling attempt #{self.spelling_retries}. Prompting letter-by-letter retry.")
                    return {"action": "retry_spelling", "retry_count": self.spelling_retries}

        # Initial WAITING_FOR_NAME state
        if extracted:
            self.captured_name = extracted
            self.state = "NAME_ACCEPTED"
            logger.info(f"[NameState] Name accepted directly: '{self.captured_name}'")
            return {"action": "accept", "name": self.captured_name}

        # If transcript is empty or ambiguous
        return {"action": "request_name"}



