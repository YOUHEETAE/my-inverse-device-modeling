# Stage 6 learning portfolio

Stage 6 adds a cross-Case learning view without merging the sessions or
scientific evidence of different Cases.

## Portfolio contract

For every current Case configuration, the portfolio calculates:

- `not_started`, `in_progress`, `completed`, or `locked`;
- compatible session count and completed session count;
- the latest learning step and update time;
- completed and remaining expected concepts; and
- whether prerequisite Cases are complete.

Sessions whose saved experiment conditions no longer match the current Case
configuration are retained on disk but excluded from progress. This currently
separates any old 20 nm → 15 nm Oxide session from the released 20 nm → 10 nm
Case.

## Recommendation order

The deterministic recommendation does not call an LLM.

1. Resume an available Case that is already in progress.
2. Otherwise start the first not-started Case whose prerequisites are met.
3. If every Case is complete, recommend review.
4. If only locked Cases remain, direct the learner to complete prerequisites.

The curriculum order is:

1. Channel Length and Short Channel Effect
2. Gate Oxide Thickness and Gate Control

The Oxide Case uses the SCE Case as its recommendation prerequisite. The Case
selector remains available, so this is learning guidance rather than deletion
or forced navigation.

## GUI check

1. Restart the application and open Case Study.
2. Confirm the header displays `전체 Case 0/2 완료` or the value matching saved
   sessions.
3. Select `전체 학습 현황`.
4. Confirm both Cases appear with status, session count, concept progress, and
   latest learning time.
5. Confirm `추천 Case 열기` opens the recommended Case.
6. Complete the SCE Case and reopen the view.
7. Confirm the Oxide Case becomes the next recommendation.
8. Switch between Cases and confirm their histories remain isolated.
