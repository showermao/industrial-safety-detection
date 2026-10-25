import sqlite3


class AlertRepository:
    def __init__(self, database_path):
        self.database_path = database_path

    def _connect(self):
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _normalize_row(row):
        if row is None:
            return None
        if hasattr(row, "keys"):
            return {key: row[key] for key in row.keys()}
        return {
            "id": row[0],
            "area_name": row[1],
            "event_type": row[2],
            "severity": row[3],
            "notes": row[4],
            "actor_id": row[5],
            "created_at": row[6],
        }

    def create_alert(self, area_name, event_type, severity, notes, actor_id=None):
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO alerts (area_name, event_type, severity, notes, actor_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (area_name, event_type, severity, notes, actor_id),
            )
            connection.commit()
            return cursor.lastrowid

    def list_recent_alerts(self, limit=10):
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM alerts
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._normalize_row(row) for row in rows]


class AuditRepository:
    def __init__(self, database_path):
        self.database_path = database_path

    def _connect(self):
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _normalize_row(row):
        if row is None:
            return None
        if hasattr(row, "keys"):
            return {key: row[key] for key in row.keys()}
        return {
            "id": row[0],
            "alert_id": row[1],
            "action": row[2],
            "actor_id": row[3],
            "details": row[4],
            "created_at": row[5],
        }

    def create_audit(self, alert_id, action, actor_id=None, details=None):
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO audit_logs (alert_id, action, actor_id, details)
                VALUES (?, ?, ?, ?)
                """,
                (alert_id, action, actor_id, details),
            )
            connection.commit()

    def list_recent_audits(self, limit=10):
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM audit_logs
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._normalize_row(row) for row in rows]
