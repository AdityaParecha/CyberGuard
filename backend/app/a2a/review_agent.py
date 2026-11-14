import json
from datetime import datetime, timezone
from typing import Any

from a2a.helpers import (
    get_message_text,
    new_task_from_user_message,
    new_text_artifact_update_event,
    new_text_status_update_event,
)
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import TaskState


MAX_REQUEST_CHARS = 150000
MAX_RECORDS = 500


def review_investigation(payload: dict[str, Any]) -> dict[str, Any]:
    evidence = payload.get("evidence", [])
    hypotheses = payload.get("hypotheses", [])
    timeline = payload.get("timeline", [])

    if not isinstance(evidence, list):
        evidence = []

    if not isinstance(hypotheses, list):
        hypotheses = []

    if not isinstance(timeline, list):
        timeline = []

    evidence = evidence[:MAX_RECORDS]
    hypotheses = hypotheses[:MAX_RECORDS]
    timeline = timeline[:MAX_RECORDS]

    evidence_ids = {
        str(item.get("evidence_id"))
        for item in evidence
        if isinstance(item, dict) and item.get("evidence_id") is not None
    }

    findings = []

    for hypothesis in hypotheses:
        if not isinstance(hypothesis, dict):
            continue

        hypothesis_id = hypothesis.get("hypothesis_id", "unknown")
        status = str(hypothesis.get("status", "")).lower()

        linked_ids = []

        for field in (
            "evidence_ids",
            "supporting_evidence_ids",
            "related_evidence_ids",
        ):
            value = hypothesis.get(field)

            if isinstance(value, list):
                linked_ids.extend(str(item) for item in value)

        if status == "verified" and not linked_ids:
            findings.append({
                "severity": "high",
                "code": "VERIFIED_WITHOUT_LINKED_EVIDENCE",
                "record_id": str(hypothesis_id),
                "message": (
                    "A hypothesis is marked verified but has no linked "
                    "evidence IDs in the fields checked by this reviewer."
                ),
            })

        missing_ids = [
            item for item in linked_ids
            if item not in evidence_ids
        ]

        if missing_ids:
            findings.append({
                "severity": "medium",
                "code": "MISSING_EVIDENCE_REFERENCE",
                "record_id": str(hypothesis_id),
                "missing_evidence_ids": missing_ids,
                "message": "Some linked evidence IDs were not found.",
            })

    parsed_times = []

    for item in timeline:
        if not isinstance(item, dict):
            continue

        timestamp = item.get("timestamp")

        if not timestamp:
            continue

        try:
            parsed = datetime.fromisoformat(
                str(timestamp).replace("Z", "+00:00")
            )

            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)

            parsed_times.append(parsed)
        except ValueError:
            findings.append({
                "severity": "low",
                "code": "UNPARSEABLE_TIMELINE_TIMESTAMP",
                "record_id": str(item.get("evidence_id", "unknown")),
                "message": "A timeline timestamp could not be parsed.",
            })

    if parsed_times and parsed_times != sorted(parsed_times):
        findings.append({
            "severity": "medium",
            "code": "TIMELINE_ORDER_CHECK",
            "message": (
                "The supplied timeline timestamps are not in chronological "
                "order."
            ),
        })

    return {
        "review_agent": "CyberGuard A2A Forensic Reviewer",
        "review_status": (
            "review_required" if findings else "no_structural_issues_detected"
        ),
        "evidence_count": len(evidence),
        "hypothesis_count": len(hypotheses),
        "timeline_event_count": len(timeline),
        "findings": findings,
        "limitations": (
            "This agent checks structural consistency and references. "
            "It does not establish that an event occurred or that a person "
            "is responsible. Human forensic review remains necessary."
        ),
    }


class ForensicReviewExecutor(AgentExecutor):

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        task = context.current_task or new_task_from_user_message(
            context.message
        )

        await event_queue.enqueue_event(task)

        await event_queue.enqueue_event(
            new_text_status_update_event(
                task_id=task.id,
                context_id=task.context_id,
                state=TaskState.TASK_STATE_WORKING,
                text="Checking investigation evidence and references.",
            )
        )

        try:
            request_text = get_message_text(context.message, delimiter=" ")

            if len(request_text) > MAX_REQUEST_CHARS:
                raise ValueError("A2A review request exceeds the size limit.")

            payload = json.loads(request_text)

            if not isinstance(payload, dict):
                raise ValueError("A2A review input must be a JSON object.")

            result = review_investigation(payload)

            await event_queue.enqueue_event(
                new_text_artifact_update_event(
                    task_id=task.id,
                    context_id=task.context_id,
                    name="forensic_review",
                    text=json.dumps(result, ensure_ascii=False),
                )
            )

            await event_queue.enqueue_event(
                new_text_status_update_event(
                    task_id=task.id,
                    context_id=task.context_id,
                    state=TaskState.TASK_STATE_COMPLETED,
                    text="Forensic review completed.",
                )
            )

        except Exception as error:
            await event_queue.enqueue_event(
                new_text_status_update_event(
                    task_id=task.id,
                    context_id=task.context_id,
                    state=TaskState.TASK_STATE_FAILED,
                    text=f"Forensic review failed: {error}",
                )
            )

    async def cancel(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        return None