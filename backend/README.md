# Backend

`backend/explanation` owns the post-prediction analysis pipeline:

- Payload schema and numerical Evidence extraction
- Curve and Field interpretation
- deterministic Mock rendering
- Groq/OpenAI-compatible provider integration
- language-polish validation, fallback, warnings, and cache handling

The production flow is:

`model result → Analyzer → interpretation → Mock → optional LLM polish`

Python and Mock remain the analysis authority. The external LLM only rewrites the
validated content blocks. Frontend code calls this package but does not implement
analysis rules.
