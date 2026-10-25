import sqlite3

from werkzeug.security import check_password_hash, generate_password_hash


class UserRepository:
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
            "username": row[1],
            "email": row[2],
            "password_hash": row[3],
            "role": row[4],
            "status": row[5],
            "created_at": row[6],
        }

    def create_user(self, username, email, password, role="user"):
        password_hash = generate_password_hash(password)
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO users (username, email, password_hash, role, status)
                VALUES (?, ?, ?, ?, 'pending')
                """,
                (username, email, password_hash, role),
            )
            connection.commit()
            return cursor.lastrowid

    def get_by_username(self, username):
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE username = ?",
                (username,),
            ).fetchone()
        return self._normalize_row(row)

    def get_by_id(self, user_id):
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
        return self._normalize_row(row)

    def get_pending_users(self):
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM users WHERE status = 'pending' ORDER BY created_at DESC"
            ).fetchall()
        return [self._normalize_row(row) for row in rows]

    def verify_user(self, username, password):
        user = self.get_by_username(username)
        if not user:
            return None
        if not check_password_hash(user["password_hash"], password):
            return None
        if user["status"] != "approved":
            return None
        return user

    def approve_user(self, user_id):
        with self._connect() as connection:
            connection.execute(
                "UPDATE users SET status = 'approved' WHERE id = ?",
                (user_id,),
            )
            connection.commit()

    def reject_user(self, user_id):
        with self._connect() as connection:
            connection.execute(
                "UPDATE users SET status = 'rejected' WHERE id = ?",
                (user_id,),
            )
            connection.commit()

    def ensure_default_admin(self):
        if self.get_by_username("admin") is None:
            self.create_user("admin", "admin@lab.local", "admin@123", role="admin")
            with self._connect() as connection:
                connection.execute(
                    "UPDATE users SET status = 'approved' WHERE username = 'admin'"
                )
                connection.commit()
