# Frontend

Run the integrated desktop application with the project Conda environment:

```powershell
conda activate inverse-device-modeling
python frontend\app.py
```

`app.py` owns the integrated Tk workflow. `visualization/` contains reusable plot,
field-data, explanation-panel, and guide widgets. Model inference remains under
`ai/`; explanation analysis remains under `backend/`.

## Case Study workflow

Open `3. Case Study` and proceed through prediction, model execution, result
observation, feedback, and the recommended next action. The first topic compares
the 700 nm baseline with the 300 nm channel-length condition while keeping
`T`, `B`, `SD`, and `LDD` fixed.

The result view provides I–V curves, Potential/Electric Field maps, extracted
electrical parameters, and grounded free-form questions. I-V, Field Map, and
Case Study use the configured external AI provider without a public
Mock/provider selector. Without `GROQ_API_KEY`, model inference and deterministic
analysis remain available, while AI explanation areas show a clear connection
error and retry guidance rather than presenting a local answer as an LLM answer.

Sessions are restored from:

```text
runtime/learning_sessions/
```

Each saved session includes semantic dialogue state (current concept focus,
referenced result, pending clarification, and open experiment request) in
addition to the raw question history. Older session files are upgraded in
memory by rebuilding that state from their saved turns.

The Case header distinguishes:

- `계속하기`: load the selected saved session;
- `새 세션`: keep previous records and create another session;
- `현재 세션 초기화`: clear only the selected session after confirmation.
- `선택 세션 삭제`: permanently delete only the selected saved session after
  confirmation; if it was active, another saved session or a fresh session is
  opened.

Free-question answers show learner-facing route and relevance information,
friendly evidence labels, and whether clarification or another experiment is
required. Provider/model identifiers, machine evidence IDs, token usage, raw
provider messages, request IDs, and validation codes remain internal. A failed
external request is shown as an actionable AI connection error and is not
silently replaced by a Mock or local theory answer.

Completing a Case does not close the learning conversation. The completion view
keeps separate tabs for the summary, saved results, and free-form AI questions.
Question-example buttons only fill the input box; users can edit them or enter
any semiconductor-related question. If a recoverable model or feedback error
occurs, the error view states which saved step will be retried and preserves the
existing session.

In every result view, the compact electrical-parameter table remains fixed on
the right while the left side switches between I–V Curve, Field Map, and AI
free questions. Sending a question preserves the selected tab.

Run the model-backed Case Study smoke test with:

```powershell
python tools\case_study_smoke.py
```

Run the fast free-question quality audit without model inference with:

```powershell
python tools\tutor_quality_audit.py
```
