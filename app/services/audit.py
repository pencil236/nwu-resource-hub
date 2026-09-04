import json

from sqlalchemy.orm import Session

from app.models import AuditLog


def add_audit(
    db: Session,
    action: str,
    target_type: str,
    target_id: str,
    actor_id: str | None,
    details: dict | None = None,
    request_id: str | None = None,
) -> None:
    db.add(
        AuditLog(
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=json.dumps(details or {}, ensure_ascii=False),
            request_id=request_id,
        )
    )
