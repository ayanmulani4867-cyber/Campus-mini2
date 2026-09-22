from flask import Blueprint, request, jsonify
from extensions import db
from models import Event
from utils.auth import roles_required, login_required, current_user
from utils.validators import require_fields, validate_date

bp = Blueprint("events", __name__, url_prefix="/api/events")


@bp.get("")
@login_required
def list_events():
    events = Event.query.order_by(Event.event_date.asc()).all()
    return jsonify({"success": True, "data": [e.to_dict() for e in events]})


@bp.post("")
@roles_required("faculty", "admin")
def create_event():
    user = current_user()
    data = request.get_json(silent=True) or {}
    require_fields(data, ["title", "date"])
    event_date = validate_date(data["date"])

    event = Event(
        title=data["title"].strip(),
        description=data.get("description"),
        category=data.get("category", "General"),
        event_date=event_date,
        location=data.get("location"),
        created_by_id=user.id,
    )
    db.session.add(event)
    db.session.commit()
    return jsonify({"success": True, "data": event.to_dict()}), 201


@bp.delete("/<int:event_id>")
@roles_required("faculty", "admin")
def delete_event(event_id):
    event = Event.query.get(event_id)
    if not event:
        return jsonify({"success": False, "error": "Event not found."}), 404
    db.session.delete(event)
    db.session.commit()
    return jsonify({"success": True})
