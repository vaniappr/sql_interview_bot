"""Optional LLM-backed interviewer commentary.

If ANTHROPIC_API_KEY is not set, falls back to canned feedback so the app
still works end-to-end without an API key.
"""

import os

MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = (
    "You are a senior data analyst conducting a SQL interview. You are reviewing "
    "a candidate's SQL query and their explanation of their approach, alongside "
    "whether the query produced the correct result. Give feedback like a real "
    "interviewer: acknowledge what's right, point out any inefficiencies or "
    "misunderstandings, and ask one short, natural follow-up question to probe "
    "their reasoning further. Keep it to 3-5 sentences. Do not repeat the question "
    "back verbatim."
)


def _client():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    import anthropic
    return anthropic.Anthropic(api_key=api_key)


def interviewer_feedback(question_prompt: str, candidate_sql: str, candidate_explanation: str, correct: bool) -> str:
    client = _client()
    if client is None:
        verdict = "correct" if correct else "not quite right"
        return (
            f"(Offline mode — set ANTHROPIC_API_KEY for live interviewer feedback)\n"
            f"Your query result was **{verdict}**. Review the expected vs. your output below, "
            "and think about whether your joins/filters/aggregations match what was asked."
        )

    user_msg = (
        f"Interview question:\n{question_prompt}\n\n"
        f"Candidate's SQL:\n{candidate_sql}\n\n"
        f"Candidate's explanation of their approach:\n{candidate_explanation or '(none given)'}\n\n"
        f"Result correctness (computed by executing the query): {'CORRECT' if correct else 'INCORRECT'}\n\n"
        "Respond as the interviewer."
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=400,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )
    return response.content[0].text
