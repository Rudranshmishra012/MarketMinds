"""AI crop-quality grading for MarketMinds.

Uses an OpenAI vision-capable model when MARKETMINDS_OPENAI_API_KEY is set.
The returned grade is constrained to the three grades used by MarketMinds.
"""

import base64
import json
import os
import urllib.error
import urllib.request


ALLOWED_GRADES = {"Grade A", "Grade B", "Grade C"}
MODEL = os.environ.get("MARKETMINDS_VISION_MODEL", "gpt-5.6-luna")
API_URL = "https://api.openai.com/v1/responses"


def _extract_output_text(data):
    """Extract text from a Responses API response without depending on SDKs."""
    if isinstance(data.get("output_text"), str):
        return data["output_text"]
    chunks = []
    for item in data.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                chunks.append(content["text"])
    return "".join(chunks)


def analyze_crop_image(image_bytes, mime_type, crop):
    """Return {grade, confidence, reason} for a crop image.

    This is an AI-assisted visual estimate, not an official agricultural inspection.
    """
    api_key = os.environ.get("MARKETMINDS_OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("AI grading is not configured. Add MARKETMINDS_OPENAI_API_KEY to .env.")

    encoded = base64.b64encode(image_bytes).decode("ascii")
    prompt = f"""
You are the crop quality assistant inside MarketMinds.
The farmer selected this crop: {crop}.

Estimate a simple visual quality grade using ONLY what is visible in the image:
- Grade A: visually high quality, good/uniform appearance, little or no visible damage/defects.
- Grade B: acceptable/good marketable quality with some visible minor defects or variation.
- Grade C: visibly lower quality with substantial defects, damage, spoilage, discoloration, or poor appearance.

Do not invent hidden properties such as pesticide residue, taste, moisture, nutrition, or exact size unless visible.
If the image is unclear or the crop cannot be identified, still choose the most plausible grade but lower confidence.

Return ONLY valid JSON with exactly these keys:
{{"grade":"Grade A|Grade B|Grade C","confidence":0,"reason":"short explanation"}}
Confidence must be an integer from 0 to 100.
""".strip()

    payload = {
        "model": MODEL,
        "input": [{
            "role": "user",
            "content": [
                {"type": "input_text", "text": prompt},
                {"type": "input_image", "image_url": f"data:{mime_type};base64,{encoded}"},
            ],
        }],
        "max_output_tokens": 250,
    }

    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"AI service returned HTTP {exc.code}: {body[:300]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError("Could not reach the AI grading service.") from exc

    text = _extract_output_text(data).strip()
    try:
        result = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("AI returned an invalid grading response.") from exc

    grade = result.get("grade")
    if grade not in ALLOWED_GRADES:
        raise RuntimeError("AI returned an unsupported grade.")

    try:
        confidence = max(0, min(100, int(result.get("confidence", 0))))
    except (TypeError, ValueError):
        confidence = 0

    reason = str(result.get("reason", "Visual quality estimate based on the uploaded image."))[:500]
    return {"grade": grade, "confidence": confidence, "reason": reason}
