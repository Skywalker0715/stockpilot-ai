# Product Definition — StockPilot AI

**Status:** Draft for validation  
**Working name:** StockPilot AI  
**Product type:** Full-stack web application  
**Primary user:** Independent AI stock creator / stock contributor

## 1. Product vision
Help independent stock creators organize their own assets, prepare metadata, detect near-duplicates in their own libraries, and learn from their own review history—without requiring paid APIs or unauthorized access to stock-platform accounts.

## 2. Problem statement
Creators may manage many images across folders and spreadsheets. Titles, keywords, submission status, rejection notes, and follow-up actions can become fragmented. Generic keyword generators solve only one slice of this workflow.

The problem is a hypothesis. Validate it with the creator's actual workflow before committing to features.

## 3. Product promise
A creator can keep a clear, searchable record of their assets and use transparent checks to prepare and review work more consistently.

## 4. Target users
- Primary: solo AI stock creators managing their own generated assets.
- Secondary (later): small teams that manage shared stock libraries.

## 5. Non-goals
- Not an Adobe Stock uploader or account automation tool.
- Not a way to bypass review or guarantee acceptance or sales.
- Not a source of secret platform data, private APIs, or scraped account information.
- Not a replacement for platform-specific contributor rules.
- Not a generic AI chat application.
- No required Google Maps, Google Places, or paid LLM API.

## 6. Proposed differentiator
A creator-owned workflow workspace combining:
1. asset library and metadata,
2. local visual near-duplicate checks,
3. submission/review history,
4. rejection-note categorization,
5. evidence-based personal workflow insights.

This is a hypothesis, not a claim of market uniqueness. Competitor research and user testing must validate it.

## 7. Product principles
- Creator-owned data first.
- Evidence over confident-sounding guesses.
- Explain what is checked and what is not.
- Local-first and cost-aware.
- Small, reliable workflows before advanced AI.
- No dark patterns, fabricated analytics, or fake AI activity.

## 8. Success criteria for the first usable release
- A user can create/import assets and edit metadata.
- Similarity results are reproducible and explain the comparison threshold.
- Review status and rejection notes can be recorded and filtered.
- Any generated metadata is editable and never silently overwrites user content.
- The app remains useful when no LLM is configured.
- Tests cover critical workflows and data persistence.

## 9. Open questions
- Which stock platforms will be supported first? Start with manual tracking and CSV import/export unless research supports more.
- Which file formats will be supported?
- Should images remain on the user's machine, or be copied into application storage?
- Which LLM (if any) performs acceptably on the user's 8 GB RAM laptop?
- Which competitor gap is confirmed by interviews and hands-on testing?
