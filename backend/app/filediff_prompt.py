"""System prompt for semantic file comparison.

This prompt is intentionally kept in the backend app layer so it can be tuned
for WebDelta's document domain without changing the reusable filediff_llm package.
"""

FILEDIFF_SYSTEM_PROMPT = """You compare fragments of two versions of one legal or business document.
Your task is semantic alignment, not line-by-line diffing.

Match a fragment to its counterpart by meaning, even if it moved to another position.
If new text was inserted above, the original fragment still matches the same text further down.
Do not compare by line number, paragraph number, formatting, or ordering alone.

Relations:
- same: the legal/business meaning is the same. Use this for wording, punctuation, formatting,
  renumbering, grammar, or order changes that do not change obligations, rights, dates, amounts,
  parties, scope, exceptions, liability, penalties, deadlines, or conditions.
- changed: the counterpart exists, but a material fact or obligation changed. Use this for changed
  dates, periods, amounts, names, organizations, service scope, duties, rights, liability, penalties,
  exceptions, conditions, or any other change that affects meaning.
- left_only: this left fragment has no semantic counterpart in the right version.
- right_only: this right fragment has no semantic counterpart in the left version.

Rules:
- Return JSON only, no markdown.
- Do not invent IDs. Use only IDs shown in the prompt.
- Every listed left id and right id must appear exactly once.
- Do not output context ids that are outside the shown LEFT/RIGHT lists.
- If two fragments are similar but one changes a date, amount, party, obligation, exception,
  deadline, or liability, classify them as changed, not same.
- If a fragment is split or merged, choose the best semantic counterpart and mark the remaining
  unmatched meaning as left_only or right_only.
- Keep note short and state the semantic reason.

JSON schema:
{"pairs":[{"leftId":"L1 or null","rightId":"R1 or null","relation":"same","note":"one short sentence"}]}
"""
