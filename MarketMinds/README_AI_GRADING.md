# MarketMinds – AI Crop Photo Grading

The dashboard now supports AI-assisted visual grading for the supported crops.

## How it works
1. Farmer selects a crop.
2. Farmer uploads a JPG/PNG/WebP photo.
3. **Detect Grade from Photo** sends the image to the configured vision model.
4. MarketMinds receives a constrained `Grade A`, `Grade B`, or `Grade C` result, plus confidence and a short reason.
5. The returned grade is placed into the existing Quality Grade field and is used by the existing market/buyer logic.

## Configure the AI service
Copy `.env.example` to `.env` and set:

```text
MARKETMINDS_OPENAI_API_KEY=your_api_key_here
MARKETMINDS_VISION_MODEL=gpt-5.6-luna
```

The app uses Python's standard HTTPS client, so no extra AI SDK is required.

## Important
The grade is an **AI-assisted visual estimate**, not an official agricultural inspection. A photo cannot reliably determine hidden properties such as pesticide residue, moisture, taste, or internal damage. For production use, train/evaluate a crop-specific grading model against a properly labeled agricultural dataset and validate it with domain experts.

## Photo limits
- JPG, PNG, WebP
- Maximum 8 MB
