# AI Quality, Grounding, and Anti-Hallucination Rules

## 1. AI is optional
Asset catalog, manual metadata editing, submission tracking, and deterministic similarity checks must work without an LLM.

## 2. Allowed AI tasks in the MVP
- Suggest draft titles, descriptions, and keywords from user-provided context.
- Help categorize rejection notes as a suggestion.
- Summarize patterns in records, while showing the underlying counts and time period.

## 3. Forbidden claims
The application must not claim:
- an image will be accepted or rejected by a stock platform;
- a keyword will guarantee ranking or sales;
- an asset is legally safe or free of intellectual-property risk based solely on AI output;
- an inferred rejection reason is the platform's official reason unless the user provided that reason;
- an insight is statistically reliable when the sample is too small.

## 4. Output handling
- Treat model output as untrusted input.
- Validate structured output with a schema.
- Set input/output limits and timeouts.
- Show AI-generated metadata as a draft requiring user approval.
- Preserve the previous value until the user explicitly saves a replacement.
- If output is invalid or the model is unavailable, show an honest error and allow manual work.

## 5. Evidence and uncertainty
- Distinguish user-provided facts, computed results, and AI suggestions.
- Display sample size for analytics.
- Explain similarity thresholds and algorithm limitations.
- Do not fabricate citations, official rules, or platform requirements.
- When platform rules are needed, direct users to current official contributor guidance rather than pretending a local model knows the latest rules.

## 6. Evaluation
Maintain a small versioned evaluation set of representative assets and metadata tasks.
Evaluate:
- factual consistency with the provided image/context;
- keyword relevance and redundancy;
- invalid or unsupported claims;
- latency and memory use on target hardware;
- failure behavior when the model is unavailable.

Do not select a model based only on benchmark marketing. Test it on the actual laptop and sample workflow.
