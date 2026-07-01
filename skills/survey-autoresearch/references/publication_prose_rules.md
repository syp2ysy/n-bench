# Publication Prose Rules

Use these rules on `outputs/review.md`, not on internal artifacts.

## Forbidden Or Suspicious Surface Forms

Remove or rewrite:
- 本节面向...
- 下面的表...
- 这个表的作用...
- 这个矩阵...
- 核心文献吸收矩阵
- 本文如何使用它
- 该工作在本文中被读作
- 记录重点是
- 本文要求把该工作放入
- 若原文没有完整报告，则将其作为证据缺口
- artifact, dossier, paper card, node card, section card, state file, gate check, workflow log
- repeated field labels such as `Problem:`, `Memory record:`, `Write policy:`, `Read policy:`, `Update policy:`, `Controller interface:`, `Benchmark / task:`, `Design lesson:`

Article prose may still refer to tables and sections, but the language should be scholarly rather than instructional.

Prefer:
- `Table 2 distinguishes method families by the memory object they maintain and by the failure modes their evaluations can reveal.`

Avoid:
- `下面的表是本文的中心方法谱系。`

## Case-Study Style

Bad article body:

```text
Problem:
Memory record:
Write policy:
Read policy:
Design lesson:
```

Good article body:

```text
The system matters because it makes one memory operation inspectable. It writes typed observations into a persistent record, retrieves them through a task-conditioned query, and exposes the retrieved state to the planner before action selection. This mechanism is useful for long-horizon settings, but the available evidence remains weak unless no-memory, wrong-memory, and stale-memory controls are reported.
```

## Repetition Control

Do not add repeated `深入讨论` sections to satisfy length gates. Merge repeated cross-task observations into one synthesis section with named findings.

If the final 20-25 percent of the review contains repeated headings or near-identical paragraphs, return to the article plan and rewrite the conclusion, take-home findings, and open problems.
