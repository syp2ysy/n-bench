# Knowledge Tree Contract

The knowledge tree turns deep paper cards into a survey spine. It is not a paper list and not a post-hoc article outline.

Required public artifacts:

- `outputs/knowledge_tree.yml`
- `state/paper_clusters.jsonl`
- `state/taxonomy_candidates.yml`
- `state/spine_decision.md`

Compatibility artifacts such as `outputs/contribution_tree.yml`, synthesis dossiers, argument graphs, and section evidence plans may remain, but they must trace back to the public knowledge-tree artifacts.

Every top-level tree branch needs:

- a field-native name and definition
- included A/B papers from `state/paper_cards/`
- excluded nearby topics or drift risks
- shared assumptions or capability boundaries
- method, benchmark, limitation, or failure-mode evidence
- related-survey taxonomy support or an explicit taxonomy delta
- representative papers and supporting papers

`state/spine_decision.md` must answer:

1. how existing related surveys organize the topic
2. what those surveys cover and miss
3. which candidate taxonomies were considered
4. why the selected spine is better for the current paper corpus
5. how each major section maps to paper-card evidence and related-survey deltas

Python helpers may validate schema, coverage, and traceability. They must not fabricate semantic clusters or taxonomy choices. Knowledge-tree and spine decisions are worker outputs or repaired article-planning outputs, then validated by gates and Gate 7 reviewers.
