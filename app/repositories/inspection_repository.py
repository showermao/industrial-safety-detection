import json
import sqlite3


class InspectionRepository:
    def __init__(self, database_path):
        self.database_path = database_path

    def create(self, result, actor_id=None, source="manual"):
        with sqlite3.connect(self.database_path) as connection:
            cursor = connection.execute(
                """INSERT INTO inspection_records
                (status, status_label, comparison_time, problem_description,
                 detections_json, image_data, source, actor_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (result["status"], result.get("status_label"), result["comparison_time"],
                 result["problem_description"], json.dumps(result.get("detections", []), ensure_ascii=False),
                 result.get("image"), source, actor_id),
            )
            connection.commit()
            return cursor.lastrowid

    def list_recent(self, limit=100):
        with sqlite3.connect(self.database_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                "SELECT * FROM inspection_records ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        records = []
        for row in rows:
            record = dict(row)
            record["detections"] = json.loads(record.pop("detections_json") or "[]")
            records.append(record)
        return records
