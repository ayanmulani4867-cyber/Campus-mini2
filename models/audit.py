from datetime import datetime, timezone
import json
from flask import request, has_request_context
from extensions import db
from utils.auth import current_user


class AuditLog(db.Model):
    """Immutable audit trail for all academic results, assignment modifications, and administrative operations."""
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    actor_email = db.Column(db.String(150), nullable=True)
    actor_role = db.Column(db.String(30), nullable=True)
    action = db.Column(db.String(80), nullable=False, index=True)
    target_type = db.Column(db.String(60), nullable=True)
    target_id = db.Column(db.String(100), nullable=True)
    reason = db.Column(db.Text, nullable=True)
    details = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(60), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    user = db.relationship("User")

    def to_dict(self):
        return {
            "id": self.id,
            "userId": self.user_id,
            "actorEmail": self.actor_email,
            "actorRole": self.actor_role,
            "action": self.action,
            "targetType": self.target_type,
            "targetId": self.target_id,
            "reason": self.reason,
            "details": self.details,
            "ipAddress": self.ip_address,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }


def log_audit(action, target_type=None, target_id=None, reason=None, details=None, user=None):
    """Records an audit trail event securely within the active transaction."""
    try:
        actor = user or current_user()
        ip = None
        if has_request_context():
            ip = request.headers.get("X-Forwarded-For", request.remote_addr)
            if ip and "," in ip:
                ip = ip.split(",")[0].strip()

        detail_str = None
        if isinstance(details, (dict, list)):
            detail_str = json.dumps(details)
        elif details is not None:
            detail_str = str(details)

        entry = AuditLog(
            user_id=actor.id if actor else None,
            actor_email=actor.email if actor else "anonymous",
            actor_role=actor.role if actor else "system",
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            reason=reason,
            details=detail_str,
            ip_address=ip,
            created_at=datetime.now(timezone.utc)
        )
        db.session.add(entry)
        db.session.commit()
        return entry
    except Exception:
        db.session.rollback()
        return None
