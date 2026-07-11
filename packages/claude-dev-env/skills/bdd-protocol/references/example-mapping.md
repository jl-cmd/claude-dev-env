# Example Mapping (Smart & Molak §6.4)

Lightweight, breadth-first discovery before code. Sessions are typically **25–30 minutes**.

## Core moves

- State **rules**, then ask for an **example of each** rule. Examples often use **"The one where …"** phrasing (Daniel Terhorst-North; sometimes called "Friends episode notation").
- For each example, probe with **"What if …?"**, **"Is this always the case?"**, **"Are there examples where this rule behaves differently?"** Probes can surface **new rules**; add examples for those rules.
- **Pink cards**: questions that cannot be answered yet — **park** them; do not pretend they are specifications.

## Chat algorithm (solo-friendly)

1. **Restate the rule or feature** until it is clearly defined.
2. Generate **3–5** "the one where …" examples from simple to complex.
3. For each example, run the **three probes** above.
4. If probes reveal a **new rule** or materially different behavior, add **2–3** examples for that rule and continue probing.
5. Repeat until examples for each rule are probed.
6. Compile **rules + examples + parked questions**; confirm with the user before automating tests.
7. **Time-box** discovery; proceed to failing tests only after the map is agreed.

## Parking lot discipline

Unanswered questions stay **out of automated tests** until resolved or explicitly accepted as follow-up work.
