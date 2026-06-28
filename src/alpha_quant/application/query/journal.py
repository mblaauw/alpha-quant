"""Journal query service — immutable event timeline from audit events."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from alpha_quant.application.query.shared import with_uow


class JournalService:
    def list_entries(
        self,
        cursor: str | None = None,
        limit: int = 200,
    ) -> dict[str, object]:
        def _query(uow: Any) -> dict[str, object]:
            rows = uow.store.session.execute(
                text("""
                    SELECT ae.event_id, ae.event_type, ae.payload_json, ae.created_at,
                           dr.run_kind
                    FROM audit.audit_event ae
                    LEFT JOIN run.decision_run dr ON dr.decision_run_id = ae.decision_run_id
                    ORDER BY ae.created_at DESC
                    LIMIT :lim
                """),
                {"lim": limit},
            ).fetchall()

            items: list[dict[str, object]] = []
            for r in rows:
                ts = r._mapping["created_at"]
                event_type: str = r._mapping["event_type"]
                event_parts = event_type.split(".")
                category = event_parts[1] if len(event_parts) > 1 else event_parts[0]
                message = _format_event_message(event_type, r)
                items.append(
                    {
                        "id": r._mapping["event_id"],
                        "timestamp": str(ts) if ts else None,
                        "category": category,
                        "message": message,
                    }
                )

            return {"items": items, "next_cursor": None}

        return with_uow(_query)


def _format_event_message(event_type: str, row: Any) -> str:
    import json

    parts = event_type.split(".")
    # event_type is like "command.candidate.modify.requested"
    # or "command.decision_run.create.requested"
    if len(parts) >= 3 and parts[0] == "command":
        cmd_action = parts[-2] if len(parts) >= 3 else ""
        cmd_type = parts[1]
        name_map = {
            "decision_run": "Run decision cycle",
            "candidate": "Candidate action",
            "order": "Order",
            "position": "Position",
            "halt": "Halt",
        }
        action_map = {
            "create": "created",
            "modify": "modified",
            "approve": "approved",
            "reject": "rejected",
            "submit": "submitted",
            "cancel": "cancelled",
            "flatten": "flattened",
            "set_stop": "stop updated",
            "set_risk_method": "risk method changed",
        }
        base = name_map.get(cmd_type, cmd_type.replace("_", " "))
        action = action_map.get(cmd_action, cmd_action)
        base = f"{base} {action}"
    elif len(parts) >= 2 and parts[0] == "run":
        status_map = {
            "reserved": "reserved",
            "started": "started",
            "completed": "completed",
            "failed": "failed",
        }
        base = f"Decision run {status_map.get(parts[-1], parts[-1])}"
    else:
        base = event_type.replace("_", " ").replace(".", " — ")

    run_kind = row._mapping["run_kind"]
    if run_kind:
        base += f" ({run_kind})"

    try:
        payload = json.loads(row._mapping["payload_json"])
        symbol = payload.get("symbol")
        if symbol:
            base += f" — {symbol}"
        reason = payload.get("reason")
        if reason:
            base += f" · {reason[:40]}"
    except json.JSONDecodeError, TypeError:
        pass
    return base
