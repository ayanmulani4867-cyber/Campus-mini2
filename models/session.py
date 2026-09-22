from datetime import datetime
from extensions import db


class UserSession(db.Model):
    __tablename__ = "user_sessions"

    id = db.Column(db.String(64), primary_key=True)  # Cryptographic URL-safe token
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_activity = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    user = db.relationship("User", backref=db.backref("user_sessions", cascade="all, delete-orphan", lazy="dynamic"))

    def to_dict(self):
        return {
            "id": self.id,
            "userId": self.user_id,
            "role": self.role,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "lastActivity": self.last_activity.isoformat() if self.last_activity else None,
            "isActive": self.is_active,
        }
