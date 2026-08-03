# Stage 5 Oxide Case check

## What was added

`oxide_gate_control` changes only Gate oxide thickness from 20 nm to 10 nm.
Channel length remains 700 nm and all doping parameters remain fixed. The
learning flow connects:

- stronger Gate control with gm increase and SS decrease;
- the current model's Ioff increase as a result-specific trade-off;
- Oxide and adjacent-region Field distribution changes; and
- the limit that a Field hotspot alone does not prove breakdown.

The Case uses the shared runner, analysis adapter, tutor, persistence, and UI.
It has separate question IDs, expected concepts, misconceptions, next actions,
and sessions.

## Manual check

1. Restart the GUI in `devsim_env`.
2. Open Case Study and select `Gate Oxide Thickness와 Gate Control`.
3. Confirm the comparison table changes only `T: 20 nm → 10 nm`.
4. Complete the prediction and run the experiment.
5. Confirm the fixed parameter panel continues to show `L = 700 nm`.
6. In the electrical panel, confirm the current model shows:
   - gm increase;
   - SS decrease; and
   - Ioff increase.
7. Open Electric Field and confirm the explanation reports only verified
   changed regions without calling breakdown confirmed.
8. Ask:
   - `이번 결과에서 gm은 증가하고 SS는 감소했는데 왜 그런가요?`
   - `Ioff도 증가한 이유는 무엇인가요?`
   - `Gate 부근 전계가 증가했으니 breakdown이 발생한 거지?`
9. Switch to the Channel Length Case and confirm its previous session remains.
10. Switch back and confirm the Oxide Case resumes independently.

The reproducible model check is:

```powershell
python tools\oxide_case_smoke.py
```
