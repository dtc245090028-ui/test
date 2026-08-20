from app.extensions import db
from datetime import datetime, timezone

class AIInteractionLog(db.Model):
    __tablename__ = 'ai_interaction_logs'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    feature_type = db.Column(db.String(50), nullable=False) # 'inventory_report', 'reorder_suggestion'
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    prompt_input = db.Column(db.Text, nullable=False)
    ai_response = db.Column(db.Text, nullable=False)
    model_used = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    user = db.relationship('User', backref=db.backref('ai_logs', lazy=True))

    def to_dict(self):
        return {
            "id": self.id,
            "feature_type": self.feature_type,
            "user_id": self.user_id,
            "prompt_input": self.prompt_input,
            "ai_response": self.ai_response,
            "model_used": self.model_used,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
