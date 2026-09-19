"""
MarketMinds - Crop Grade Predictor (image-based)
=================================================
Lets a farmer upload a photo of their produce and get an automatic
Grade A / Grade B / Grade C suggestion instead of (or before) picking
it manually.

There's no labelled crop-quality image dataset in this project, so this
is NOT a trained CNN. It's a transparent, explainable heuristic built on
plain image statistics with Pillow + NumPy:

  1. Blemish / spot ratio  - dark or discoloured patches on the produce
     usually mean bruises, rot, or pest damage -> lower grade.
  2. Colour uniformity     - fresh, well-sorted produce tends to have a
     fairly consistent colour/hue across the frame; mixed ripe+unripe
     or damaged patches increase colour spread -> lower grade.
  3. Brightness / dullness - very dark or washed-out photos usually mean
     dull, aged, or poorly-lit produce -> lower grade (also flags bad
     photos so the farmer can retake them).

Each factor is scored 0-100 and combined into a single quality_score,
which is then mapped to Grade A / B / C using Config.QUALITY_GRADES.

This keeps the feature fully offline (no external API calls) and easy
to explain to a farmer or a judge: every grade comes with the reasons
behind it, in the app's own language settings.
"""

import io

import numpy as np
from PIL import Image, ImageOps

# Grade thresholds on the combined 0-100 quality_score.
# Tune these if farmers/judges feel the grading is too strict/lenient.
GRADE_THRESHOLDS = [
    (70, "Grade A"),
    (45, "Grade B"),
    (0, "Grade C"),
]

MAX_IMAGE_DIMENSION = 512  # downscale large photos before analysis, for speed


def _load_image(file_storage_or_bytes):
    """Accepts a Flask FileStorage, raw bytes, or a file-like object."""
    if hasattr(file_storage_or_bytes, "read"):
        raw = file_storage_or_bytes.read()
    else:
        raw = file_storage_or_bytes

    image = Image.open(io.BytesIO(raw))
    image = ImageOps.exif_transpose(image)  # respect phone camera orientation
    image = image.convert("RGB")

    image.thumbnail((MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION))
    return image


def _blemish_score(rgb_array):
    """
    Higher score = fewer visible blemishes/dark spots.
    Flags pixels much darker than the produce's own median brightness
    as likely bruises, mould, or pest damage.
    """
    gray = rgb_array.mean(axis=2)
    median_brightness = np.median(gray)

    # Pixels notably darker than the median are treated as blemishes.
    dark_threshold = median_brightness * 0.55
    blemish_ratio = float(np.mean(gray < dark_threshold))

    # 0% blemish -> 100 score, 30%+ blemish -> 0 score
    score = max(0.0, 100.0 - (blemish_ratio / 0.30) * 100.0)
    return score, blemish_ratio


def _uniformity_score(rgb_array):
    """
    Higher score = more uniform colour (well-ripened, evenly sorted produce).
    Uses hue spread in HSV space so lighting brightness doesn't skew it.
    """
    r, g, b = rgb_array[..., 0], rgb_array[..., 1], rgb_array[..., 2]
    r_, g_, b_ = r / 255.0, g / 255.0, b / 255.0

    maxc = np.max(np.stack([r_, g_, b_], axis=-1), axis=-1)
    minc = np.min(np.stack([r_, g_, b_], axis=-1), axis=-1)
    delta = maxc - minc + 1e-6

    hue = np.zeros_like(maxc)
    mask = maxc == r_
    hue[mask] = ((g_[mask] - b_[mask]) / delta[mask]) % 6
    mask = maxc == g_
    hue[mask] = ((b_[mask] - r_[mask]) / delta[mask]) + 2
    mask = maxc == b_
    hue[mask] = ((r_[mask] - g_[mask]) / delta[mask]) + 4
    hue = hue * 60.0

    # Ignore near-grey/background pixels (very low saturation) when
    # judging colour consistency of the produce itself.
    saturation = delta / (maxc + 1e-6)
    fg_mask = saturation > 0.15
    if np.count_nonzero(fg_mask) < 50:
        return 60.0, None  # not enough coloured pixels to judge; neutral score

    hue_std = float(np.std(hue[fg_mask]))

    # 0 deg spread -> 100 score, 40+ deg spread -> 0 score
    score = max(0.0, 100.0 - (hue_std / 40.0) * 100.0)
    return score, hue_std


def _brightness_score(rgb_array):
    """
    Higher score = well-lit, not overly dull/dark and not blown out.
    """
    gray = rgb_array.mean(axis=2)
    mean_brightness = float(np.mean(gray))  # 0-255

    # Ideal band ~ 90-200; penalize outside it.
    if 90 <= mean_brightness <= 200:
        score = 100.0
    elif mean_brightness < 90:
        score = max(0.0, (mean_brightness / 90.0) * 100.0)
    else:
        score = max(0.0, 100.0 - ((mean_brightness - 200.0) / 55.0) * 100.0)

    return score, mean_brightness


def _grade_from_score(score):
    for threshold, grade in GRADE_THRESHOLDS:
        if score >= threshold:
            return grade
    return GRADE_THRESHOLDS[-1][1]


def predict_grade_from_image(file_storage_or_bytes, language="English"):
    """
    Main entry point. Returns a dict:
        {
            "grade": "Grade A" | "Grade B" | "Grade C",
            "quality_score": float 0-100,
            "confidence": float 0-1,
            "reasons": [str, ...],   # already language-aware, short bullet points
        }
    Raises ValueError if the file isn't a readable image.
    """
    try:
        image = _load_image(file_storage_or_bytes)
    except Exception as exc:  # noqa: BLE001 - want to surface a clean message
        raise ValueError("Could not read this image. Please upload a clear JPG/PNG photo.") from exc

    rgb_array = np.asarray(image).astype(np.float32)

    blemish_pts, blemish_ratio = _blemish_score(rgb_array)
    uniform_pts, hue_std = _uniformity_score(rgb_array)
    bright_pts, mean_brightness = _brightness_score(rgb_array)

    # Weighted combination: blemishes matter most for grading produce,
    # then colour consistency, then photo lighting quality.
    quality_score = round(0.5 * blemish_pts + 0.3 * uniform_pts + 0.2 * bright_pts, 1)
    grade = _grade_from_score(quality_score)

    # Confidence: how far the score sits from the nearest grade boundary.
    boundaries = [t for t, _ in GRADE_THRESHOLDS if t > 0]
    distances = [abs(quality_score - b) for b in boundaries]
    nearest_gap = min(distances) if distances else 25.0
    confidence = round(min(0.95, 0.55 + (nearest_gap / 100.0)), 2)

    reasons = _build_reasons(language, blemish_ratio, hue_std, mean_brightness, grade)

    return {
        "grade": grade,
        "quality_score": quality_score,
        "confidence": confidence,
        "reasons": reasons,
    }


def _build_reasons(language, blemish_ratio, hue_std, mean_brightness, grade):
    hindi = language == "Hindi"
    reasons = []

    if blemish_ratio is not None:
        if blemish_ratio < 0.05:
            reasons.append("दाग-धब्बे लगभग नहीं दिखे" if hindi else "Very few blemishes/spots detected")
        elif blemish_ratio < 0.15:
            reasons.append("हल्के दाग-धब्बे दिखे" if hindi else "Some minor blemishes detected")
        else:
            reasons.append("ज्यादा दाग/खराबी दिखी" if hindi else "Noticeable spots/damage detected")

    if hue_std is not None:
        if hue_std < 15:
            reasons.append("रंग काफी एक जैसा है" if hindi else "Colour looks fairly uniform")
        elif hue_std < 30:
            reasons.append("रंग में थोड़ा अंतर है" if hindi else "Some colour variation seen")
        else:
            reasons.append("रंग में काफी अंतर है" if hindi else "High colour variation seen")

    if mean_brightness < 90:
        reasons.append("फोटो थोड़ी अंधेरी है, बेहतर रोशनी में दोबारा लें"
                        if hindi else "Photo looks a bit dark — try better lighting")
    elif mean_brightness > 200:
        reasons.append("फोटो में रोशनी बहुत तेज़ है" if hindi else "Photo looks slightly overexposed")

    return reasons
