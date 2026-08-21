# Design

## Source of truth
- Status: Active
- Last refreshed: 2026-08-21
- Primary product surfaces: Desktop Case Study learning flow and its Case selection cover.
- Evidence reviewed: `frontend/visualization/case_study/panel.py`, `backend/learning/progress.py`, `backend/learning/configs/*.json`, `tests/test_case_study_ui_contract.py`, and the user-approved Case Study flow in this thread.

## Brand
- Personality: Technical, calm, evidence-led, and learner-focused.
- Trust signals: Verified simulation values, explicit comparison conditions, persistent learner records, and clear boundaries between the canonical Case and exploratory runs.
- Avoid: Gamified scoring, unexplained recommendations, provider diagnostics, dense session-management controls, and decorative visual noise.

## Product goals
- Goals: Make the learner's progress and available Cases immediately scannable; connect prediction, observation, interpretation, and the model explanation; preserve personal learning history; keep optional parameter exploration on the final page.
- Non-goals: Difficulty-based content variants, forced review recommendations, or making placeholder Cases executable before their learning content exists.
- Success signals: A learner can identify their current Case and next available action at a glance, resume safely, and distinguish available Cases from planned Cases.

## Personas and jobs
- Primary personas: Semiconductor learners using model results to understand device behavior.
- User jobs: Select a Case, understand its comparison, record a prediction, inspect evidence, explain the result, revisit the final explanation, and run optional follow-up experiments.
- Key contexts of use: Desktop application sessions that may be stopped and resumed later.

## Information architecture
- Primary navigation: Case list as the home surface; `Case 목록` returns to it from an active Case.
- Core routes/screens: Case selection followed by four persistent learning pages: `Case 이해`, `초기 예측`, `결과 관찰`, and `최종 설명`.
- Content hierarchy: Personal progress first, an optional inline learning-record disclosure second, available Case cards third, and planned disabled Case cards last.
- Learning-page access: `Case 이해` is always available; each later page unlocks only after the learner reaches it. Completed sessions reopen with all four pages available.
- Open-Case header: Show only `← Case 목록`, the Case number/title, the active learning-record name/status, and a `학습 기록` disclosure. Case selection belongs to the cover rather than a second selector inside the Case.
- Progress semantics: Each of the four page buttons owns a short segment above it. Green reports a reached curriculum page, gray reports a locked page, and the blue active-button treatment reports the page currently being viewed. Revisiting an earlier page must not reduce reached progress.
- Case-understanding hierarchy: Case background, one central learning question, concrete learning objectives, evidence to inspect in Curve/Field views, and the controlled baseline/comparison conditions.

## Design principles
- Principle 1: Show one clear primary action for each Case state. A completed Case may pair the primary `결과 보기` action with a visually smaller `새 세션 시작` action so review and a new attempt are both available without entering the old record.
- Principle 2: Put personal progress in the page instead of a modal dialog.
- Tradeoffs: The cover uses vertical scrolling so eight Cases remain readable without compressing card content.

## Visual language
- Color: Reuse the existing neutral text, blue active, green completed, amber prerequisite, and gray disabled states.
- Typography: Reuse Tk default fonts with clear title, status, body, and metadata hierarchy.
- Spacing/layout rhythm: Two equal-width cards per row with consistent padding and a full-width progress summary.
- Shape/radius/elevation: Reuse native `ttk.LabelFrame` and button treatments.
- Motion: No required motion; state changes must not depend on animation.
- Imagery/iconography: Text-first; no new imagery is required.

## Components
- Existing components to reuse: `ttk.Frame`, `ttk.LabelFrame`, `ttk.Progressbar`, `ttk.Button`, `ttk.Scrollbar`, and the existing Case/session repository.
- New/changed components: Inline learning-progress summary, a two-level disclosure for all records and each Case's records, scrollable Case grid, disabled planned-Case cards, one state-aware primary action per available Case, a slim open-Case header, collapsible record management, and an always-visible four-step segmented learning navigation.
- Open-Case record management: Keep the current record name and state visible. In the single-row `학습 기록` disclosure, keep selected-record actions on the left as `불러오기 → 이름 변경 → 삭제`, and place `현재 학습 → 새 학습 시작 → 현재 학습 초기화` on the right. Do not expose record cloning or a second management disclosure.
- Completed learning summary: Order the page as `핵심 정리 → 질문별 내 답변/확인된 결과 → 전체 모범 답안 → 내 학습 피드백 → 필요한 경우 다시 확인할 근거`. Render every prediction and observation with one shared question-card structure; question configuration may change only its short title, linked metrics, confirmed answer, and model-answer copy. A selection verdict must not overstate the quality of the learner's written reason. Do not expose internal concept IDs.
- Question review cards: Keep `내 답변`, `확인된 결과`, and `비교` aligned in one row; show only electrical metrics linked to that question; preserve a written reason at full wrapped height without an internal scrollbar; and present the question-level model answer as result, physical basis, and meaning or interpretation boundary.
- Question review density: Preserve every question-level explanation, but render its subsection labels inline inside one compact explanation block and minimize nested padding. Do not solve vertical length by hiding content behind a click or by narrowing the full summary into a persistent side column.
- Canonical model answer: Preserve the deterministic grounded content, but render each bracketed section as a full-width visible card instead of one long text block. Render electrical parameter changes as aligned rows for metric, actual change, direction, and physical explanation. Do not add an accordion or a second scroll region.
- Personalized closing feedback: Place `잘 이해한 부분` and `보완할 부분` side by side and ground both in the learner's submitted answers. Move the non-personalized core summary to the top of the page, omit scores or grades, and hide `다시 확인할 근거` when neither Curve nor Field needs review.
- Completed-page tabs: Use one flat row—`학습 요약`, `I–V Curve`, `Field Map`, and `AI 자유 질문`. The summary owns the model answer and personalized closing feedback; the other tabs own evidence review and follow-up exploration without nesting another result notebook.
- AI free questions: Treat broad references such as the current simulation, the whole result, or every metric as direct current-result questions. Keep metric-direction implications internal to the tutor, separate metric-specific gain/loss from overall design suitability, and keep target-dependent quantities such as Vth explicitly conditional.
- Variants and states: Not started, in progress, completed, prerequisite locked, and planned/disabled.
- Token/component ownership: Case Study UI owns its local layout while preserving existing application-wide Tk styling.

## Accessibility
- Target standard: Keyboard-operable native controls with readable status text that does not rely on color alone.
- Keyboard/focus behavior: All available actions remain reachable through normal Tk focus traversal; disabled Cases use disabled buttons.
- Contrast/readability: Statuses include text labels and use existing high-contrast foreground colors.
- Screen-reader semantics: Native labels and buttons carry descriptive text.
- Reduced motion and sensory considerations: No required animation or flashing content.

## Responsive behavior
- Supported breakpoints/devices: Existing desktop window sizes.
- Layout adaptations: A two-column Case grid sits inside a vertical scroll container; card content wraps within its column.
- Touch/hover differences: No hover-only actions or information.

## Interaction states
- Loading: Model execution remains an internal transient state, not a learner-visible curriculum step.
- Learning navigation: Emphasize the selected page typographically without appending `현재`; future pages retain the explicit `잠김` label.
- Header status: Do not reserve an empty status row; show status text only when an operation has a message to report.
- Empty: The progress summary explains when no learning record exists, the learning-record disclosure is disabled, and available cards show `시작 전`.
- Error: Existing recoverable session errors remain available without deleting saved records.
- Success: Completed cards expose `결과 보기` as their single primary action.
- Submitted answers: Initial predictions and observations become read-only review content after submission.
- Submitted-answer review: Preserve the original question, option controls, selected choices, and reason field in disabled form so review matches the answering context. Long reasons expand vertically inside the page instead of gaining their own scrollbar.
- Long answer review: The submitted-observation column scrolls independently and wraps every question and option so later questions are never clipped.
- Observation answering: The editable question list scrolls independently, wraps prompts and choices to the question-card borders, and keeps the submit action fixed at the bottom of the right column.
- Observation draft continuity: Preserve every selected option and written reason while the learner moves among I–V Curve, Field Map, and AI free questions or while an AI response causes the page to rerender. Draft answers remain scoped to their learning session and disappear only after submission or an explicit new session/reset.
- Observation question quality: Every Case uses two I–V questions and one Field Map question. Distractors should remain physically plausible until the learner compares the actual electrical parameters, Curve shape, and Field distribution. Make alternatives differ by metric definition, causal mechanism, matched-comparison pairing, or target constraint rather than by obviously careless wording. Avoid giveaway phrases such as `~만 본다`, `~없이`, `둘 중 하나`, `~라 확정한다`, or categorical proof claims; use the written reason to require a causal interpretation.
- Prediction scope: Case 01 asks separate single-choice questions for Ion, Ioff, and DIBL, while leaving Vth and SS for evidence-led discovery during observation. The whole prediction page scrolls as the content grows.
- Multi-condition prediction context: When a prediction asks the learner to choose among named candidates, repeat every candidate's actual parameter values and short design intent immediately above the questions. Candidate names alone are not sufficient evidence for a prediction, and the descriptions must not reveal simulated outcomes.
- Case 02 prediction scope: Ask separate single-choice-with-reason questions for gm, SS, and Ioff under the canonical 20 nm to 10 nm Oxide comparison. Phrase Ioff as a result prediction for the current model and fixed conditions rather than a universal thin-Oxide rule.
- Prediction reflection: The DIBL prediction also asks the learner to state their own definition before seeing the result.
- Prediction assessment semantics: A prediction is a hypothesis made before evidence, not a universal right-or-wrong claim. Compare it with the canonical run using `현재 결과와 일치`, `현재 결과와 일부 일치`, or `현재 결과와 다름`. A matching prediction may contribute a recognized concept, but a different prediction must not add a misconception, create a missing-concept correction, or lower the post-observation understanding level. Explain which condition-dependent effect dominated in the current Case.
- Observation entry: Show the result views and guided observation questions immediately after simulation; do not insert a separate `관찰 질문 시작` gate.
- Case 02 observation scope: Use exactly three reasoned questions that cross the Case's central learning goal—two I–V questions for the gm/SS evidence and the Gate-control-versus-Ioff trade-off, followed by one Field Map question about comparing the Gate–Oxide–Channel region under matched bias and color scale. Do not treat a hotspot alone as proof of breakdown or Ioff increase alone as proof of Oxide tunneling.
- Case 03 scope: Compare Body doping from 1×10¹⁶ to 5×10¹⁶ cm⁻³ with all other device conditions fixed. Ask predictions for Vth, Ioff, and Ion, then use two I–V questions and one Field Map question to connect the Vth shift, leakage reduction, drive-current cost, and Channel-near-surface electrostatic redistribution. Treat the result as a target-dependent Vth–Ioff design window, not a universal higher-is-better ranking.
- Case 04 scope: Compare Source/Drain doping from 1×10¹⁹ to 1×10²⁰ cm⁻³ with all other conditions fixed. Ask predictions for Ion, effective Ron, and DIBL, then use two I–V questions and one Field Map question to separate the on-state conduction benefit from increased Drain-bias sensitivity and Drain-side electrostatic redistribution. Never present effective Ron as a direct measurement of contact resistance alone.
- Case 05 scope: Compare LDD doping from 5×10¹⁷ to 5×10¹⁸ cm⁻³ with all other conditions fixed. Ask predictions for Ion, effective Ron, and Drain-near Electric Field, then use two I–V questions and one Field Map question to connect access conduction, gds/output-resistance cost, and the lower-LDD field-relief benefit. Do not claim quantified reliability improvement from Field reduction alone or treat effective Ron as LDD resistance only.
- Case 06 scope: Use a 2×2 comparison of L=700/300 nm and T=20/10 nm. Render all four Curve and Field conditions. Keep the compact electrical table grounded in the Short·Thick→Short·Thin pair, while the learning questions compare the matched Long Thick→Thin and Short Thick→Thin differences. Ask predictions for Short-Channel SS, DIBL, and recovery level, then use two I–V questions and one Field Map question to distinguish interaction, partial compensation, residual SCE, and Ioff cost. Do not infer interaction from a diagonal two-condition comparison or equate compensation with full Long-Channel recovery.
- Case 07 scope: Use a 2×2 comparison of SD=10¹⁹/10²⁰ cm⁻³ and LDD=5×10¹⁷/5×10¹⁸ cm⁻³. Render all four Curve and Field conditions. Compare matched LowLDD→HighLDD differences at each SD level, identify HighSD·HighLDD as the maximum-drive condition, and keep its Ioff·DIBL·Field cost visible. Do not infer separate effects from diagonal conditions or present maximum drive as a universal optimum.
- Case 08 scope: Present Drive, Leakage, Control, and Balanced candidate conditions. Apply Ion≥10 mA/µm, Ioff≤0.001 mA/µm, DIBL≤30 mV/V, and SS≤80 mV/dec simultaneously; Balanced is the only current-model candidate that passes all four. Use Control→Balanced as the compact primary comparison and all four candidates in Curve/Field views and the model explanation. Field review records remaining spatial electrostatic margin after electrical filtering; it does not replace the target check or prove reliability.
- Field summary evidence: Lead with the spatial change that was actually observed and connect it to the matching electrical parameter direction. State the remaining evidence boundary afterward; do not make a Field section read as a list of cautions.
- Persistent actions: A page-advance action must be packed outside expanding plot containers so regenerating a graph cannot push it below the visible viewport.
- Metric table stability: Always show the same canonical 11-row order in every Case: `Vth (low Vd)`, `Vth (high Vd)`, `Ion`, `Ioff`, `Ion/Ioff ratio`, `SS`, `DIBL`, `gm max`, `gds`, `Ron`, and `λ (CLM)`. Display `—` when a value cannot be extracted instead of removing the row. Use canonical capitalization, actual condition labels instead of generic Baseline/Comparison labels, seven significant digits at most, fixed row height, and non-draggable column separators. Keep the compact table only as wide as its four columns require so the observation and submitted-answer pane retains reading width.
- Saved-answer evaluation: When a saved session is reopened at observation-submitted state, resume evaluation automatically and show passive progress text; do not require a separate `저장된 답변 평가 계속` button.
- Final-page stability: As soon as evaluation finishes, automatically complete the learning record and show the four-tab final layout without a separate completion button.
- Result regeneration: Regenerating an I–V Curve or Field Map must return to the learning page and completed-page tab from which regeneration was requested; a completed session must not be sent back to `결과 관찰`.
- Multi-condition plot identity: Use actual compact parameter signatures in Curve and Field labels—such as `L700 T20` or `SD1e19 LDD5e17`—instead of qualitative aliases such as `Long·Thick`. For candidate-set Cases, retain the candidate name before the numeric signature. In I–V Curve plots, one stable color identifies a condition across every subplot, while line style alone identifies the fixed bias; the legend must label both encodings explicitly.
- Field evidence access: The Case Study Field Map selector exposes the same complete display catalog as `Structure / Field Map`.
- Disabled: No planned Case remains in the current eight-Case curriculum.
- Offline/slow network, if applicable: Core Case navigation and saved records remain local; provider failures follow existing recovery behavior.
- Direct result answers: Show the compact `AI 튜터 · 현재 결과` context, hide internal explanation-level labels, and omit generic follow-up prompts unless the response genuinely needs clarification.

## Content voice
- Tone: Concise, direct, and instructional.
- Terminology: Use `Case`, `진행 중`, `완료`, `결과 보기`, `이어서 하기`, and `준비 중` consistently.
- Microcopy rules: Describe what the action opens; call persisted sessions `학습 기록`; do not label system-selected review as a recommendation.
- Introduction copy: Explain the physical situation without revealing measured results, name the evidence surfaces the learner will use, and flag one premature conclusion to avoid before prediction.

## Implementation constraints
- Framework/styling system: Python Tkinter/ttk and Matplotlib.
- Design-token constraints: Extend existing colors and native widgets rather than introducing a new design-system layer.
- Performance constraints: Cover rendering must not run simulations or external LLM calls; interactive startup must create a responsive loading window before the large Curve and Field runtime models are loaded.
- Compatibility constraints: Existing saved sessions and all configured Cases must remain usable.
- Test/screenshot expectations: Keep source-level UI contracts and application smoke checks current; verify the cover can render and scroll in the desktop smoke test when the runtime environment is available.

## Open questions
- [ ] Decide whether repeated completed attempts need a dedicated record page / product owner / does not block the cover redesign.
- [ ] Refine card spacing and visible rows after reviewing the running UI / product owner / visual polish.
- [ ] Choose a professional, case-independent vocabulary and compact placement for beneficial/adverse/neutral metric impact / product owner / affects the electrical metric table width and interpretation.
- [ ] Define canonical-versus-exploratory Curve/Field runs and which result the AI question uses / product owner / required before adding 700–300 nm pair selection.
