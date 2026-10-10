from math import ceil
from flask import Blueprint, request, jsonify
from extensions import db
from models import AuditLog
from utils.auth import roles_required

bp = Blueprint("audit", __name__, url_prefix="/api/audit")


@bp.get("")
@roles_required("admin")
def list_audit_logs():
    """Module 10: Centralized security and compliance audit trail inspection for Administrators."""
    q = AuditLog.query

    action = (request.args.get("action") or "").strip()
    if action:
        q = q.filter(AuditLog.action.ilike(f"%{action}%"))

    target_type = (request.args.get("targetType") or "").strip()
    if target_type:
        q = q.filter(AuditLog.target_type.ilike(f"%{target_type}%"))

    actor = (request.args.get("actor") or "").strip()
    if actor:
        q = q.filter(AuditLog.actor_email.ilike(f"%{actor}%"))

    total = q.count()

    try:
        page = max(1, int(request.args.get("page", 1)))
        limit = min(100, max(1, int(request.args.get("limit", 25))))
    except (ValueError, TypeError):
        page = 1
        limit = 25

    logs = q.order_by(AuditLog.id.desc()).offset((page - 1) * limit).limit(limit).all()

    return jsonify({
        "success": True,
        "data": [l.to_dict() for l in logs],
        "pagination": {
            "total": total,
            "page": page,
            "limit": limit,
            "totalPages": ceil(total / limit) if limit else 1
        }
    })
