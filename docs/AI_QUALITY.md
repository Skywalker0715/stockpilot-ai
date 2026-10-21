# AI Quality, Grounding, and Anti-Hallucination Rules

These rules are binding on every AI feature in the app. They describe the
Cohere integration as it is actually implemented, not an aspiration.

## 1. AI is optional
Asset catalog, manual metadata editing, submission tracking, image upload,
Vision Insights history, and deterministic summary metrics must work without
an LLM. `GET /api/v1/ai/status` reports the real configuration state — it
never hardcodes "AI is on" or "AI is off".

## 2. Allowed AI tasks in the MVP
- Suggest draft titles, descriptions, and keywords from the uploaded image
  (`POST /api/v1/ai/analyze`).
- Analyze an uploaded image for visual attributes, commercial use ideas,
  keyword gaps, and metadata quality (`POST /api/v1/vision/analyze/{id}`).
- Summarize patterns in records, while showing the underlying counts and
  time period (computed locally, not by a model).

## 3. Forbidden claims
The application must not claim:
- an image will be accepted or rejected by a stock platform;
- a keyword will guarantee ranking or sales;
- an asset is legally safe or free of intellectual-property risk based solely on AI output;
- an inferred rejection reason is the platform's official reason unless the user provided that reason;
- an insight is statistically reliable when the sample is too small;
- that a "commercial use idea" is measured demand — it is a suggestion.

Vision Insights content is labeled as AI-generated observation throughout the
UI. Nothing in it is market demand, search volume, sales volume, or ranking
data, and the API does not claim otherwise.

## 4. Output handling
- Treat model output as untrusted input. It is parsed, validated, and
  normalized before it reaches the UI or the database.
- Validate structured output against the response schema and the Pydantic
  response models.
- Set input/output limits and timeouts:
  - images are downscaled to a 1280 px longest side before upload;
  - the response token budget is 2048 (raised from 1024 after measurement
    showed a compliant 50-keyword answer peaks at ~1205 tokens);
  - decoding is pinned to greedy (`temperature=0`) because unconstrained
    sampling produced a runaway keyword list that hit the token cap in 3 of
    5 measured runs;
  - the whole request is bounded by `STOCKPILOT_AI_TIMEOUT` (default 60 s).
- Show AI-generated metadata as a **draft** requiring user approval.
  `POST /api/v1/ai/analyze` persists nothing; saving is a separate
  `PATCH /api/v1/assets/{id}`.
- Vision Insights never edits the asset's metadata. Suggested keywords must
  be applied explicitly by the user.
- Preserve the previous value until the user explicitly saves a replacement.
- If output is invalid or the model is unavailable, show an honest error and
  allow manual work.

## 5. Consent
Both AI endpoints require explicit `consent: true`, validated server-side by
a Pydantic field validator. The frontend shows a consent notice plus an
explicit checkbox — "I agree to send this image to Cohere for AI analysis" —
on both the Generate and Vision Insights screens. The action button is
disabled until the checkbox is ticked, so no image can leave the machine
without an affirmative action. Consent is re-requested for every new image:
it is reset on upload, when reopening a different asset, and when the screen
is reset. Without consent the request is rejected with `422` and no call to
Cohere is made.

## 6. Evidence and uncertainty
- Distinguish user-provided facts, computed results, and AI suggestions.
- Display sample size for analytics.
- Explain similarity thresholds and algorithm limitations.
- Do not fabricate citations, official rules, or platform requirements.
- When platform rules are needed, direct users to current official contributor guidance rather than pretending a local model knows the latest rules.

## 7. Provider failure handling

Every non-success outcome from Cohere raises `CohereServiceError` with an
actionable message and an HTTP status. Analysis is never reported as
successful unless a parseable, schema-valid response was actually received.
No exception is swallowed and no fake success is returned.

| Upstream condition | Status | Message shown |
| --- | --- | --- |
| No `COHERE_API_KEY` | `503` | Names the variable, `.env`, and the key URL; reminds the user that manual editing always works |
| Rate limited (429) | `429` | "Wait a moment and try again" |
| Key rejected (401/403) | `502` | Names `COHERE_API_KEY` and `.env`; points at the dashboard |
| Model not found (404) | `502` | Names the active model and `STOCKPILOT_AI_MODEL` |
| Other 4xx | `502` | Provider message plus "check the image and try again" |
| Other 5xx | `502` | "Cohere service error (HTTP n). Try again later." |
| Timeout | `504` | States the configured timeout; suggests a smaller image or a later retry |
| Connection error | `502` | "Cannot reach Cohere — check your connection" |
| Unreadable body | `502` | "Cohere returned an unreadable response" |
| Not valid JSON | `502` | "Cohere returned a response that is not valid JSON" |
| JSON but not an object | `502` | "Cohere returned JSON that is not an object" |
| **Schema echo** | `502` | "Cohere returned the response schema instead of an analysis" |
| Missing/blank required section | `502` | Names the missing section (visual attributes, gap analysis, quality review) |

### The schema-echo failure mode

Cohere's structured-output mode does not guarantee the model returns an
*instance* of the supplied schema. With the deeply nested vision schema the
model sometimes replies with the schema document itself — echoing
`type`/`properties`/`required` and filling the properties with placeholder
strings.

Two defenses are in place:

1. **Prevention.** The prompt appends a concrete JSON skeleton showing the
   exact expected shape, and explicitly forbids emitting the schema keys.
2. **Detection.** The parser recognizes an echoed schema (top-level
   `properties`/`required` without `visual_attributes`) and rejects it with a
   specific `502` message, instead of the misleading "missing usable visual
   attributes" that the generic shape check used to produce.

## 8. Evaluation
Maintain a small versioned evaluation set of representative assets and metadata tasks.
Evaluate:
- factual consistency with the provided image/context;
- keyword relevance and redundancy;
- invalid or unsupported claims;
- latency and memory use on target hardware;
- failure behavior when the model is unavailable.

Do not select a model based only on benchmark marketing. Test it on the actual laptop and sample workflow.

The offline suite in `tests/` covers the parsing, validation, and failure
paths with a mocked transport. `tests/smoke_live.py` exercises the real
provider end-to-end and is kept separate from the offline suite.

