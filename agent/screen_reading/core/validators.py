# Text validation logic for OCR results
import re
from typing import Tuple, List
from core.models import ROIMeta


class TextValidator:
    # Validates OCR text results against ROI-specific rules.
    # Supports expected values lists and pattern matching with placeholders.
    def __init__(self):
        pass

    def validate_text(self, roi_meta: ROIMeta, text: str) -> Tuple[bool, str]:  # Validate OCR text against ROI rules.
        text = text.strip()

        # Check expected values first (most specific)
        expected_result = self._check_expected_values(roi_meta, text)
        if expected_result is not None:
            return expected_result

        # Check pattern matching (flexible validation)
        pattern_result = self._check_pattern(roi_meta, text)
        if pattern_result is not None:
            return pattern_result

        # No validation rules active - any non-empty text passes
        if text:
            return True, f"Text: {text}"
        else:
            return False, "No text detected"

    def _check_expected_values(
        self, roi_meta: ROIMeta, text: str
    ) -> Tuple[bool, str]:  # Validate against comma-separated expected values list.
        expected_values = getattr(roi_meta, "expected_values", "")
        if not expected_values.strip():
            return None

        # Parse expected values list
        expected_list = [v.strip() for v in expected_values.split(",") if v.strip()]
        if not expected_list:
            return None

        # Check if text matches any expected value
        if text in expected_list:
            return True, f"Expected value: {text}"
        else:
            return False, f"Expected one of: {', '.join(expected_list)}"

    def _check_pattern(
        self, roi_meta: ROIMeta, text: str
    ) -> Tuple[bool, str]:  # Validate against pattern with placeholders.
        # Supports (number), (text), and (letter) placeholders.
        # Supports multiple patterns separated by commas (e.g., "L:(number), L: (number)")

        pattern = getattr(roi_meta, "pattern", "")
        if not pattern.strip():
            return None

        # Split pattern by commas to support multiple alternatives
        patterns = [p.strip() for p in pattern.split(",") if p.strip()]

        if not patterns:
            return None

        # Try each pattern alternative
        for individual_pattern in patterns:
            try:
                # Convert pattern placeholders to regex
                pattern_regex = self._convert_pattern_to_regex(individual_pattern)

                if re.match(pattern_regex, text):
                    return True, f"Matches pattern '{individual_pattern}': {text}"

            except re.error as e:
                continue  # Skip invalid patterns, try the next one

        # None of the patterns matched
        if len(patterns) == 1:
            return False, f"Does not match pattern: {patterns[0]}"
        else:
            return False, f"Does not match any pattern: {', '.join(patterns)}"

    def _convert_pattern_to_regex(self, pattern: str) -> str:  # Convert user-friendly pattern to regex.
        # Supports placeholders:
        # - (number): Matches integers 0-21 (for game unit counts and adjustments)
        # - (text): Matches alphanumeric text with spaces
        # - (letter): Matches single letters (case-insensitive)

        # Escape special regex characters except our placeholders
        escaped = re.escape(pattern)

        # Replace escaped placeholders with regex patterns
        # Number pattern: 0-21 (single digit 0-9, or 10-21)
        escaped = escaped.replace(r"\(number\)", r"([0-9]|1[0-9]|2[0-1])")
        escaped = escaped.replace(r"\(text\)", r"([A-Za-z0-9\s]+)")
        escaped = escaped.replace(r"\(letter\)", r"([A-Za-z])")

        # Anchor to match entire string
        return f"^{escaped}$"


# Global instance for easy access
_validator_instance = None


def get_text_validator() -> TextValidator:  # Get the global TextValidator singleton instance
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = TextValidator()
    return _validator_instance
