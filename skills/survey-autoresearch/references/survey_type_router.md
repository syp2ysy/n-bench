# Survey Type Router

Use this before taxonomy lock and before article planning.

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

## 3. Benchmark Or Evaluation Survey

Use when the topic names datasets, benchmarks, evaluation protocols, robustness tests, safety evaluations, or leaderboards.

Main spine:
- capabilities being operationalized;
- dataset/task construction;
- metrics and baselines;
- confounders and diagnostic controls;
- benchmark coverage gaps;
- recommendations for future protocols.

## 4. Application-Domain Survey

Use when the topic is a domain such as healthcare, education, laboratory robotics, finance, or materials discovery.

Main spine:
- domain workflows and tasks;
- data sources and constraints;
- method families;
- evaluation and deployment;
- regulation, risk, and practical barriers;
- research agenda.

## 5. Risk Or Threat Survey

Use when the topic is security, privacy, robustness, misuse, governance, or trustworthiness.

Main spine:
- assets and threat model;
- attack or failure surfaces;
- defenses and mitigations;
- evaluation protocols;
- open risks and policy or deployment implications.

## Routing Artifact

Record the chosen route in `state/scope_audit.md`:
- selected survey type;
- why this type fits the topic;
- which templates are used;
- which templates are intentionally not used;
- how tasks, benchmarks, and applications will appear in the outline.
