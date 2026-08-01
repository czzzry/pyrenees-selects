from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Mapping


OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"


def _output_text(response: Mapping[str, Any]) -> str:
    direct = response.get("output_text")
    if isinstance(direct, str) and direct:
        return direct
    for item in response.get("output") or []:
        if not isinstance(item, Mapping) or item.get("type") != "message":
            continue
        for content in item.get("content") or []:
            if isinstance(content, Mapping) and content.get("type") == "output_text":
                text = content.get("text")
                if isinstance(text, str) and text:
                    return text
    raise ValueError("The assistant response did not contain a proposal.")


def propose_sequence(
    context: Mapping[str, Any],
    *,
    api_key: str,
    model: str = "gpt-5-mini",
    user_direction: str = "",
    endpoint: str = OPENAI_RESPONSES_URL,
    opener: Any = urllib.request.urlopen,
) -> dict[str, Any]:
    """Ask OpenAI for a structured, non-executing sequence proposal.

    The API key is accepted for this call only and is never persisted. The
    assistant receives the portable manifest, not media bytes or local paths.
    """
    if not api_key.strip():
        raise ValueError("An API key is required for the built-in assistant.")
    selections = list(context.get("selections") or [])
    eligible = [item for item in selections if item.get("decision") in {"keep", "maybe"}]
    if not eligible:
        raise ValueError("Save at least one keep or maybe selection before requesting a sequence.")
    selection_ids = [str(item["id"]) for item in eligible]
    prompt = (
        "You are an editorial assistant inside a local video pre-editor. Propose one ordered first cut "
        "using only the supplied keep or maybe selection IDs. Respect the project intent and target duration "
        "as editorial guidance, not an absolute cap. Good unused material may remain as alternates. Never invent "
        "IDs. Explain the narrative logic briefly. The user will inspect and approve this proposal before it is applied."
    )
    if user_direction.strip():
        prompt += f"\n\nAdditional direction from the user: {user_direction.strip()[:4_000]}"
    schema = {
        "type": "object",
        "properties": {
            "selection_ids": {
                "type": "array", "items": {"type": "string", "enum": selection_ids}, "uniqueItems": True,
            },
            "explanation": {"type": "string"},
        },
        "required": ["selection_ids", "explanation"],
        "additionalProperties": False,
    }
    body = {
        "model": model.strip() or "gpt-5-mini",
        "store": False,
        "instructions": prompt,
        "input": json.dumps(context, separators=(",", ":")),
        "text": {"format": {"type": "json_schema", "name": "selects_sequence_proposal", "strict": True, "schema": schema}},
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key.strip()}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with opener(request, timeout=90) as response:
            raw = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read()).get("error", {}).get("message")
        except Exception:
            detail = None
        raise ValueError(detail or f"The assistant request failed with HTTP {exc.code}.") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise ValueError(f"Could not reach the assistant provider: {exc}") from exc
    proposal = json.loads(_output_text(raw))
    if not isinstance(proposal, dict):
        raise ValueError("The assistant proposal was not a JSON object.")
    proposed_ids = proposal.get("selection_ids")
    if not isinstance(proposed_ids, list) or not all(item in selection_ids for item in proposed_ids):
        raise ValueError("The assistant proposed an unknown selection.")
    return {
        "kind": "sequence",
        "payload": {"selection_ids": proposed_ids, "name": "Assistant first cut"},
        "explanation": str(proposal.get("explanation") or ""),
        "provider": "openai",
        "model": body["model"],
    }
