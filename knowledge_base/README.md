# Knowledge base

`nutrition_seed.json` is the small local knowledge base used by the RAG retriever
(`backend/app/ai/retriever.py`) of the nutrition assistant.

> **Educational demo data.** The 18 entries are general dietary information written for
> this course project. They have **not** been reviewed by a nutritionist or physician, are
> not authoritative, and are not medical advice. Authoritative product facts (prices, stock,
> nutrition numbers) always come from the database, never from this file.

## Format

```json
{
  "description": "...", "disclaimer": "...", "version": 1,
  "entries": [
    {
      "id": "nutrition_seed_001",
      "title": "short title",
      "text": "the snippet the assistant may cite",
      "tags": ["low_sodium"],
      "keywords": ["低鈉", "sodium"],
      "product_codes": [101]
    }
  ]
}
```

| Field | Meaning |
|---|---|
| `id` | Unique knowledge id. It is what the API returns in `sources` and what answers cite as `[id]`. |
| `tags` | Matched against the resident's preferences (`low_sodium`, `vegetarian`) and the question's topic. Entries about one product also carry the tag `product`. |
| `keywords` | Words that, when found in the question, strongly raise the entry's score (Chinese and English). |
| `product_codes` | Product codes (see the `products` table) this entry is about. |

The file is validated at load time (unique ids, required fields). A test also checks that
every referenced product code exists in the seed data and that every seeded product has an
entry. To use another file, set `KNOWLEDGE_BASE_PATH`.
