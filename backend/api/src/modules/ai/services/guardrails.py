import re

PROMPT_INJECTION_PATTERNS = [
    r"ignore (all |previous |above )?instructions",
    r"disregard (all |previous |your )?",
    r"you are now",
    r"new persona",
    r"act as if",
    r"forget everything",
    r"system prompt",
]

MAX_INPUT_CHARS = 150_000  # ~50K tokens


class InputGuardrails:
    def __init__(self, max_input_chars: int = MAX_INPUT_CHARS) -> None:
        self._max_chars = max_input_chars
        self._compiled = [
            re.compile(p, re.IGNORECASE) for p in PROMPT_INJECTION_PATTERNS
        ]

    def check(self, text: str) -> tuple[bool, str | None]:
        """
        Returns (is_safe, reason_if_not_safe).
        is_safe=True means the input passed all checks.
        """
        if len(text) > self._max_chars:
            return False, f"Input exceeds maximum allowed length of {self._max_chars} characters"

        for pattern in self._compiled:
            if pattern.search(text):
                return False, f"Potential prompt injection detected: matched pattern '{pattern.pattern}'"

        return True, None


class OutputGuardrails:
    MAX_OUTPUT_CHARS = 10_000
    REFUSAL_PATTERNS = [
        re.compile(r"I cannot", re.IGNORECASE),
        re.compile(r"I'm unable to", re.IGNORECASE),
        re.compile(r"I can't help", re.IGNORECASE),
    ]

    def __init__(self, max_output_chars: int = MAX_OUTPUT_CHARS) -> None:
        self._max_chars = max_output_chars

    def check(self, output: str) -> str:
        """
        Post-process and validate output. Returns cleaned output.
        - Truncates if too long
        - Detects bare refusal responses
        """
        cleaned = output.strip()

        # Truncate if necessary
        if len(cleaned) > self._max_chars:
            cleaned = cleaned[: self._max_chars]

        return cleaned

    def is_refusal(self, output: str) -> bool:
        """
        Returns True when the output is only a refusal with no substantive content.
        A refusal is detected only when:
        - The output is short (< 100 chars), AND
        - It matches a refusal pattern as the dominant message.
        """
        stripped = output.strip()
        # Only flag very short outputs that are little more than the refusal phrase
        if len(stripped) < 100:
            for pattern in self.REFUSAL_PATTERNS:
                if pattern.match(stripped):  # match from start of string
                    return True
        return False
