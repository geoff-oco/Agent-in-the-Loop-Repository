"""Template matching functionality for detecting action cards and other game elements."""

import os
import logging
from typing import List, Optional
from dataclasses import dataclass

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Template matching configuration
DEFAULT_THRESHOLD = 0.92
DEFAULT_SCALES = [0.9, 1.0, 1.1]


@dataclass
class MatchResult:
    """Result of template matching for a single detected element."""

    x: int
    y: int
    width: int
    height: int
    confidence: float
    template_name: str
    is_locked: bool = False


class TemplateMatcher:
    """Template matching for detecting game elements."""

    def __init__(self, threshold: float = DEFAULT_THRESHOLD, scales: List[float] = None):
        self.threshold = threshold
        self.scales = scales or DEFAULT_SCALES.copy()

        logger.debug(f"TemplateMatcher initialized: threshold={threshold}, scales={self.scales}")

    def find_matches(self, screen_image: np.ndarray, template_paths: List[str], mask_path: str = None):
        """Find template matches using multiple templates."""
        try:
            all_matches = []

            base_mask = self._load_mask(mask_path)

            for template_path in template_paths:
                if not os.path.exists(template_path):
                    logger.warning(f"Template file not found: {template_path}")
                    continue

                template = cv2.imread(template_path, cv2.IMREAD_COLOR)
                if template is None:
                    logger.warning(f"Could not load template: {template_path}")
                    continue

                template_name = os.path.basename(template_path)
                is_locked = self._determine_lock_status(template_name)
                template_mask = self._prepare_template_mask(base_mask, template)

                template_matches = self._match_template_multiscale(
                    screen_image, template, template_mask, template_name, is_locked
                )
                all_matches.extend(template_matches)

            filtered_matches = self._filter_overlapping_matches(all_matches)
            logger.info(f"Found {len(filtered_matches)} matches after filtering from {len(all_matches)} candidates")

            return filtered_matches

        except Exception as e:
            logger.error(f"Template matching failed: {e}")
            return []

    def match_single_template(self, screen_image: np.ndarray, template_path: str, mask_path: str = None):
        """Find matches for single template."""
        return self.find_matches(screen_image, [template_path], mask_path)

    def load_template(self, template_path):
        """Load template image from file."""
        try:
            if not os.path.exists(template_path):
                logger.error(f"Template file not found: {template_path}")
                return None

            template = cv2.imread(template_path, cv2.IMREAD_COLOR)
            if template is None:
                logger.error(f"Could not load template image: {template_path}")
                return None

            logger.debug(f"Loaded template: {template_path} ({template.shape})")
            return template

        except Exception as e:
            logger.error(f"Failed to load template {template_path}: {e}")
            return None

    def _load_mask(self, mask_path):
        if not mask_path or not os.path.exists(mask_path):
            return None

        try:
            mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)
            if mask is not None:
                logger.debug(f"Loaded mask: {mask_path} ({mask.shape})")
            return mask
        except Exception as e:
            logger.warning(f"Failed to load mask {mask_path}: {e}")
            return None

    def _determine_lock_status(self, template_name: str) -> bool:
        return "locked" in template_name.lower() and "unlocked" not in template_name.lower()

    def _prepare_template_mask(self, base_mask, template):
        if base_mask is None:
            return None

        try:
            if base_mask.shape[:2] != template.shape[:2]:
                resized_mask = cv2.resize(base_mask, (template.shape[1], template.shape[0]))
                return resized_mask
            return base_mask.copy()
        except Exception as e:
            logger.warning(f"Failed to prepare template mask: {e}")
            return None

    def _match_template_multiscale(
        self,
        screen_image: np.ndarray,
        template: np.ndarray,
        template_mask: Optional[np.ndarray],
        template_name: str,
        is_locked: bool,
    ):
        """Perform multi-scale template matching."""
        matches = []

        for scale in self.scales:
            try:
                if scale != 1.0:
                    new_width = int(template.shape[1] * scale)
                    new_height = int(template.shape[0] * scale)
                    scaled_template = cv2.resize(template, (new_width, new_height))

                    if template_mask is not None:
                        scaled_mask = cv2.resize(template_mask, (new_width, new_height))
                    else:
                        scaled_mask = None
                else:
                    scaled_template = template
                    scaled_mask = template_mask

                if scaled_mask is not None:
                    method = cv2.TM_CCORR_NORMED
                    result = cv2.matchTemplate(screen_image, scaled_template, method, mask=scaled_mask)
                else:
                    method = cv2.TM_CCOEFF_NORMED
                    result = cv2.matchTemplate(screen_image, scaled_template, method)

                locations = np.where(result >= self.threshold)

                for y, x in zip(locations[0], locations[1]):
                    matches.append(
                        MatchResult(
                            x=x,
                            y=y,
                            width=scaled_template.shape[1],
                            height=scaled_template.shape[0],
                            confidence=float(result[y, x]),
                            template_name=template_name,
                            is_locked=is_locked,
                        )
                    )

            except Exception as e:
                logger.warning(f"Template matching failed for scale {scale}: {e}")
                continue

        logger.debug(f"Template '{template_name}' found {len(matches)} matches across {len(self.scales)} scales")
        return matches

    def _filter_overlapping_matches(self, matches: List[MatchResult], overlap_threshold: float = 0.5):
        """Filter overlapping matches by confidence."""
        if not matches:
            return []

        sorted_matches = sorted(matches, key=lambda m: m.confidence, reverse=True)
        filtered = []

        for match in sorted_matches:
            has_significant_overlap = any(
                self._calculate_overlap(match, accepted) > overlap_threshold for accepted in filtered
            )

            if not has_significant_overlap:
                filtered.append(match)

        logger.debug(f"Filtered {len(sorted_matches)} matches down to {len(filtered)} non-overlapping matches")
        return filtered

    def _calculate_overlap(self, match1: MatchResult, match2: MatchResult) -> float:
        """Calculate IoU overlap ratio between matches."""
        x1 = max(match1.x, match2.x)
        y1 = max(match1.y, match2.y)
        x2 = min(match1.x + match1.width, match2.x + match2.width)
        y2 = min(match1.y + match1.height, match2.y + match2.height)

        if x2 <= x1 or y2 <= y1:
            return 0.0

        intersection = (x2 - x1) * (y2 - y1)
        area1 = match1.width * match1.height
        area2 = match2.width * match2.height
        union = area1 + area2 - intersection

        return intersection / union if union > 0 else 0.0
