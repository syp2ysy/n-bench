# Scenario Definition Contract

`state/scenario_definitions.yml` defines how the surveyed object changes across contexts before synthesis begins.

For system-object topics, define scenarios where the system object means different things. Example: navigation memory is spatial state, EQA memory is evidence provenance, manipulation memory is object/task state, and lifelong memory is maintainable user/environment state.

For method-family topics, define task, application, or domain contexts where the method target changes.

For benchmark/evaluation topics, define capability contexts, metrics, confounders, and unsupported claims.

For risk/threat topics, define assets, threat actors, attack surfaces, defenses, and evaluation contexts.

For application-domain topics, define domain tasks, data/workflows, deployment constraints, and evaluation contexts.

Each scenario/context needs:

- scenario/context/domain name;
- object or capability definition;
- required fields or variables;
- typical benchmarks or evaluation settings;
- evaluation pressure;
- failure risks or confounders;
- unsuitable claims that the article must not overstate.

The article may teach these definitions, but must not mention this state file or expose internal routing labels.
