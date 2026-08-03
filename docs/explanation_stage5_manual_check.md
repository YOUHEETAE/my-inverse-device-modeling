# Stage 5 integrated explanation check

Run the GUI with the project Conda environment and generate the 700 nm / 300 nm pair.
Keep both curves selected for the Field Map.

## Automatic explanation

1. In I-V Curve, press `Analyze`.
   - The answer should connect observations, mechanisms, metrics and trade-offs.
   - Internal IDs such as `ev_...` must not appear.
2. In Field Map, select `Electric field` and press `Analyze`.
   - The answer should describe named regions and spatial meaning.
   - It should identify I-V metrics to check, not claim that Field alone proves their change.
3. Repeat with `Electron density`, `Total current density` and `Energy band (1D)`.
   - Carrier/current maps must not be described as terminal current.
   - Energy band must retain its model-derived limitation.

## Interactive questions

Start a new Field Map chat after selecting both devices. The status should contain
`I-V 근거 연동`.

1. `Drain 쪽 전계 변화는 물리적으로 무슨 뜻이야?`
   - Expect spatial observation, physical interpretation, I-V check and limitation.
2. `같은 소자의 실제 DIBL과 Vth 결과도 같이 설명해줘.`
   - I-V directions may be stated as separate verified observations.
   - The answer must not say that the Field pattern proved or caused those changes.
3. `그러면 breakdown이 발생한 거야?`
   - Expect a rejection of that conclusion and an explanation of additional validation.
4. `Electric field 자체가 무엇인지 설명해줘.`
   - Expect a theory answer without unnecessary current-result claims.
5. Change the Field display without starting a new chat.
   - The conversation must remain on the frozen snapshot and show `화면 변경됨`.
6. Press `새 대화`.
   - The next question must use the newly selected display.

## Provider failures

For HTTP 429, the answer area should show the exact failed stage and recommended wait.
Retrying the identical question after an answer-stage failure should reuse the intent
checkpoint. HTTP 413 should instruct the user to reduce context or change the service
limit rather than suggesting that waiting will solve it.

## Automated regression

```powershell
python tests\run_all.py
```
