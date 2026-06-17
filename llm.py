"""Optional LLM-backed interviewer commentary.

Picks a provider based on whichever API key is set in the environment:
- GROQ_API_KEY: free tier, runs Llama on Groq's hardware.
- ANTHROPIC_API_KEY: paid, runs Claude.

If neither is set, falls back to canned feedback so the app still works
end-to-end without any API key.
"""

import os

ANTHROPIC_MODEL = "claude-sonnet-4-6"
GROQ_MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = (
    "You are a senior data analyst conducting a SQL interview. You are reviewing "
    "a candidate's SQL query and their explanation of their approach, alongside "
    "whether the query produced the correct result. Give feedback like a real "
    "interviewer: acknowledge what's right, point out any inefficiencies or "
    "misunderstandings, and ask one short, natural follow-up question to probe "
    "their reasoning further. Keep it to 3-5 sentences. Do not repeat the question "
    "back verbatim."
)


def _user_message(question_prompt, candidate_sql, candidate_explanation, correct):
    return (
        f"Interview question:\n{question_prompt}\n\n"
        f"Candidate's SQL:\n{candidate_sql}\n\n"
        f"Candidate's explanation of their approach:\n{candidate_explanation or '(none given)'}\n\n"
        f"Result correctness (computed by executing the query): {'CORRECT' if correct else 'INCORRECT'}\n\n"
        "Respond as the interviewer."
    )


def _via_groq(user_msg: str) -> str:
    from groq import Groq
    client = Groq(api_key=os.environ["GROQ_API_KEY"])
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        max_tokens=400,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
    )
    return response.choices[0].message.content


def _via_anthropic(user_msg: str) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    response = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=400,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )
    return response.content[0].text


def interviewer_feedback(question_prompt: str, candidate_sql: str, candidate_explanation: str, correct: bool) -> str:
    user_msg = _user_message(question_prompt, candidate_sql, candidate_explanation, correct)

    if os.environ.get("GROQ_API_KEY"):
        try:
            return _via_groq(user_msg)
        except Exception:
            pass

    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            return _via_anthropic(user_msg)
        except Exception:
            pass

    verdict = "correct" if correct else "not quite right"
    return (
        "(Offline mode - set GROQ_API_KEY for free live interviewer feedback)\n"
        f"Your query result was {verdict}. Review the expected vs. your output below, "
        "and think about whether your joins/filters/aggregations match what was asked."
    )
