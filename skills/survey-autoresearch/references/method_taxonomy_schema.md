# Method Taxonomy Schema

Use this reference for `outputs/method_taxonomy.md`.

Required table:

```markdown
| Method family | Representation | Memory record | Write trigger | Read key | Update policy | Controller interface | Strength | Failure mode | Representative works | Best benchmarks |
```

Each method-family section in `review.md` should follow:

definition -> mechanism families -> worked examples -> comparison table -> benchmark tie-in -> failure mode -> design lesson.

Concept buckets such as "maps, vectors, retrieval" are not enough unless the table explains write/read/update/interface behavior.
