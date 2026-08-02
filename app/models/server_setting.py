"""Key-value store for server-wide settings (SMTP, feature flags, etc.)."""
from app.extensions import db


class ServerSetting(db.Model):
    __tablename__ = 'server_setting'

    key = db.Column(db.String(80), primary_key=True)
    value = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f'<ServerSetting {self.key}>'
