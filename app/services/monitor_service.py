from app.repositories.alert_repository import AlertRepository, AuditRepository


class MonitoringService:
    def __init__(self, database_path):
        self.alert_repository = AlertRepository(database_path)
        self.audit_repository = AuditRepository(database_path)

    def dashboard_regions(self):
        return [
            {"name": "實驗室 A", "status": "normal", "summary": "設備正常，無異常事件"},
            {"name": "實驗室 B", "status": "attention", "summary": "安全帽稽核待確認"},
            {"name": "實驗室 C", "status": "warning", "summary": "警示事件已記錄"},
        ]

    def create_alert(self, area_name, event_type, severity, notes, actor_id=None):
        alert_id = self.alert_repository.create_alert(area_name, event_type, severity, notes, actor_id)
        self.audit_repository.create_audit(
            alert_id=alert_id,
            action="created",
            actor_id=actor_id,
            details=f"Created alert for {area_name}: {event_type} ({severity})",
        )
        return self.alert_repository.list_recent_alerts(limit=1)[0]

    def get_recent_alerts(self):
        return self.alert_repository.list_recent_alerts(limit=5)

    def get_recent_audits(self):
        return self.audit_repository.list_recent_audits(limit=5)
