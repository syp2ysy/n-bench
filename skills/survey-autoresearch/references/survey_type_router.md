# Survey Type Router

Use this before taxonomy lock and before article planning. Also write `state/topic_diagnosis.yml`; see `references/topic_diagnosis.md`.

Do not choose only one rigid template. Select:

- one `primary_survey_type`;
- one or more `secondary_lenses`;
- a section grammar that tells the writer how each section should argue.

## 1. System-Object Survey

Use when the topic names a system, architecture, memory, planner, world model, retrieval system, controller, interface, or comparable composed object.

Main spine:
- system model;
- components or nodes;
- representations and interfaces;
- lifecycle operations;
- controller or downstream interface;
- evaluation and ablation protocol.

Tasks and benchmarks are evaluation settings, not the default spine.

Section grammar:
- Introduction: field shift -> fragmented existing views -> system object -> framework -> contributions.
- Foundations: definitions -> running example -> boundary cases.
- System model: node model -> node interactions -> why tasks are evaluation settings.
- Method families: family bottleneck -> mechanism comparison -> representative case -> benchmark tie -> implication.
- Benchmarks: capability -> protocol -> metric -> baseline -> confounder -> missing ablation.
- Open problems: evidence gap -> why current methods fail -> concrete research move.

## 2. Method-Family Survey

Use when the topic names a family of methods such as uncertainty quantification, prompting, multimodal learning, optimization, alignment, retrieval, or planning.

Main spine:
- problem setting and definitions;
- taxonomy dimensions;
- method families;
- assumptions and trade-offs;
- benchmark and metric landscape;
- applications and open challenges.

Do not force controller/action-interface fields unless the method family actually needs them.

Section grammar:
- Introduction: field shift -> method-family gap -> taxonomy lens -> contributions.
- Method sections: assumption -> mechanism family -> comparison -> evidence -> limitation.
- Benchmark section: metric target -> dataset/protocol -> baseline -> confounder.
- Open problems: unresolved assumption -> missing evidence -> testable next step.

## 3. Benchmark Or Evaluation Survey

Use when the topic names datasets, benchmarks, evaluation protocols, robustness tests, safety evaluations, or leaderboards.

Main spine:
- capabilities being operationalized;
- dataset/task construction;
- metrics and baselines;
- confounders and diagnostic controls;
- benchmark coverage gaps;
- recommendations for future protocols.

Section grammar:
- Capability section: capability definition -> protocol -> metric -> baseline -> confounder.
- Comparison section: benchmark family -> coverage difference -> diagnostic limitation.
- Recommendation section: missing test -> concrete protocol modification.

## 4. Application-Domain Survey

Use when the topic is a domain such as healthcare, education, laboratory robotics, finance, or materials discovery.

Main spine:
- domain workflows and tasks;
- data sources and constraints;
- method families;
- evaluation and deployment;
- regulation, risk, and practical barriers;
- research agenda.

Section grammar:
- Domain foundations: workflow -> data constraint -> decision point.
- Method sections: domain need -> method family -> evidence -> deployment barrier.
- Agenda: practical gap -> dataset/protocol/resource move.

## 5. Risk Or Threat Survey

Use when the topic is security, privacy, robustness, misuse, governance, or trustworthiness.

Main spine:
- assets and threat model;
- attack or failure surfaces;
- defenses and mitigations;
- evaluation protocols;
- open risks and policy or deployment implications.

Section grammar:
- Threat model: asset -> adversary/failure mode -> assumption.
- Attack/defense sections: surface -> mechanism -> evidence -> mitigation limitation.
- Evaluation: scenario -> metric -> baseline -> residual risk.

## Routing Artifact

Record the chosen route in `state/topic_diagnosis.yml`:
- primary survey type;
- secondary lenses;
- domain pressures;
- evidence norm;
- recommended structure;
- excluded templates;
- section grammar.

Also summarize the decision in `state/scope_audit.md` for human readability.
