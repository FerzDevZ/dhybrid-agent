---
name: customer-support-rag
description: RAG integration — answer user queries from internal knowledge base, not training data
---

# Customer Support / Knowledge Base (RAG)

Routes user questions through an **internal knowledge base** (Retrieval-Augmented
Generation), not the model's training data. Answers cite sources so users can verify.

## Core loop

```
User Q --> [retrieve top-k passages] --> [rerank] --> [LLM synthesize with citations]
                ^ from internal KB                       grounded answer + source links
```

## Retriever (top-k)

- **Source connectors** (pick what your KB exposes):
  - REST search endpoint (`POST /kb/search {q, top_k}`) → returns `{text, url, score}`.
  - Elasticsearch/OpenSearch (`_msearch`) — `match` + `multi_match`.
  - Vector DB (Pinecone/Weaviate) — dense embed then top-k.
  - Plain docs folder — `src/dhybrid/tools/search.py` already wraps grep/rg for local files.
- **Pre-filter** — always restrict by `customer_id` / `workspace` scope if multi-tenant.
- **Min-score floor** — only admit passages with `score >= 0.35` (tunable).
- **Fallback** — if 0 passages pass the floor, return a *confident "I don't know from KB"*
  rather than hallucinating from model memory.

## Reranker (optional, boosts precision)

- Cross-encoder rerank (e.g. `Cohere/rerank-english-v3`) on top-k before synthesis.
- Or lightweight: sort by `score * 0.7 + (1.0 - token_count_penalty)` locally.

## Synthesization policy (what you append to system prompt)

```
You are a support agent. Answer ONLY from retrieved KB passages below.
- If no passage supports an answer, say: "I don't have that in the KB."
- Cite each claim with the passage [n] number.
- Summarize, do not echo verbatim unless < 1 sentence.
- If passages conflict, flag the conflict and recommend checking <source url>.
```

## Grounding rules

1. **Never** answer from training data alone when a KB query returned passages.
2. Every factual claim must cite `[n]` matching a retrieved passage.
3. If the user asks something not in KB: offer to (a) escalate to a human, or
   (b) file a KB-gap ticket (reuse `/ticket create` skill if available).
4. Strip sensitive fields (`customer_id`, internal URLs) from cited passages
   unless the user is authorized (check `ctx` auth scope).

## Commands (REPL)

- `/kb search <query>` — show raw retrieved passages + scores (debug).
- `/kb add-source <url|path>` — register a new connector source.
- `/kb answer "<q>"` — full RAG reply with citations (main path).
- `/kb scope <customer_id|workspace>` — set auth scope for retrieval.

## Recommended wiring

```
# env
KB_SEARCH_URL=https://kb.internal.company/api/search   # REST endpoint
KB_API_KEY=sk-...
KB_SCOPE=default

# flow (pseudo, reuse src/dhybrid/tools/web.py + llm)
passages = kb_search(query, top_k=8, scope=ctx.scope)
reranked = rerank(passages, query) or sorted(passages, key=score, reverse=True)
answer = llm_chat(system_prompt + format_passages(reranked), query)
```

## Trigger

User asks: "apa cara return", "syarat garansi", "cara reset password", "kebijakan X" —
bertautan ke domain support. Juga trigger otomatis bila pertanyaan meng mengandung
kata "peraturan", "kebijakan", "aturan", "procedure", "policy" dan KB terdaftar.

## Verification

- [ ] `/kb search` returns >=1 passage with score >= floor for a known query.
- [ ] RAG answer includes `[n]` citations that map to real passage URLs.
- [ ] For an unanswerable query (KB has 0 matches), agent says "I don't have that in the KB" — never hallucinates.
- [ ] No customer-scoped KB content leaks to unauthorized users.
- [ ] `/kb answer` is strictly shorter than echoing all passages (synthesis, not dump).
