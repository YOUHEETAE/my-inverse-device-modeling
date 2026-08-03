# Midpoint check after stages 1-3

This checkpoint verifies the accumulated LLM observability, answer-quality
contract, and session/UI stability before adding multiple Cases.

## Preparation

1. Close the GUI completely and start it in `devsim_env`.
2. Open the existing Channel Length Case.
3. Keep the Groq console open only if you want to compare its TPM values with
   the usage shown by the application.

## A. LLM calls and token accounting

1. Run I-V `Analyze`.
   - Confirm input, output, total tokens, API calls, request size, elapsed time,
     and model appear at the bottom.
2. Run the same I-V `Analyze` again without changing the curves.
   - Confirm it reports cache reuse, API 0 calls, and 0 tokens.
3. Run Field `Analyze`.
   - Confirm its usage is separate from the I-V usage.
4. Ask an I-V or Field free question.
   - A normal new question should generally show two API calls: intent and
     answer generation.
5. If a 429 occurs, confirm the exact provider error and wait are shown.
   - Confirm `최근 실패 재시도` counts down and becomes enabled.
   - On an answer-stage retry, confirm the saved intent checkpoint is reused.

## B. Answer quality and grounding

Ask the following in order:

1. `이번 결과에서 Vth가 왜 감소했나요?`
2. `그 변화가 생기는 물리적 이유는 무엇인가요?`
3. `채널을 300말고 200까지 줄이면 SCE가 더 증가하는 거지?`
4. Field: `fieldmap에서는 뭐를 보면 되는거야?`
5. Field: `hotspot이 있으니 breakdown이 발생한 거지?`
6. I-V: `Ion이 증가했으니 소자 성능이 무조건 좋아진 거지?`

Check that:

- the second question inherits the first question's subject;
- current-result answers use current evidence;
- 200 nm is described as a hypothetical condition requiring a new experiment;
- Field guidance describes display, scale, regions, physical meaning, and an
  I-V verification boundary;
- a Field hotspot alone is not called confirmed breakdown; and
- Ion improvement is balanced against leakage and electrostatic control.

Record any answer that is repetitive, merely restates values, exposes an
internal ID, confuses theory with a result, or is too shallow for the request.

## C. Session and UI persistence

1. Rename the current session.
2. Clone it and confirm the clone has a different short ID and retains the
   learning history.
3. In the clone, select `Field Map`, choose `Electric field`, then move to
   `AI 자유 질문`.
4. Close the GUI completely and reopen it.
5. Resume the clone and confirm its name, learning step, history, selected tab,
   and Field display are restored.
6. Switch back to the original session and confirm it was not modified by the
   clone.
7. Reset the clone and confirm its name remains while its learning content is
   cleared.
8. Delete only the clone and confirm the original remains.

## Feedback to collect

For each problem, capture:

- feature: Case, I-V, Field, or session;
- exact question or action;
- expected behavior;
- displayed answer or error;
- validation code, HTTP code, and token line when present; and
- whether retry, restart, or session switching changed the result.

## Gate before stage 4

Proceed to multi-Case architecture when:

- token accounting matches the actual call pattern;
- all six answer checks preserve result/theory/experiment boundaries;
- 429 retry does not require retyping the question;
- rename, clone, restart, reset, and delete preserve session isolation; and
- no saved session becomes unavailable after an ordinary GUI restart.
