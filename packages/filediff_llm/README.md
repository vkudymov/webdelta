# filediff-llm

Aligns paragraphs of two document versions by content, then asks an OpenAI-compatible model whether the remaining fragments still mean the same thing.

A paragraph inserted at the top does not mark every following paragraph as changed. Rewording with the same obligation is not a content change. A different number, date, or duty is.

```python
from filediff_llm import JsonlUsageStore, OpenAICompatibleProvider, align_and_compare

provider = OpenAICompatibleProvider(
    base_url="http://127.0.0.1:1234/v1",
    api_key="lm-studio",
    model="local-model",
)
diff = await align_and_compare(
    left_text,
    right_text,
    filename="contract.docx",
    provider=provider,
    usage=JsonlUsageStore("filediff-usage.jsonl"),
)
```

`list_models(base_url, api_key)` reads `GET /v1/models`. Swap `base_url` and `api_key` for a paid provider without changing callers. Token use is appended as JSONL.
