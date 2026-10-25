from app.repositories.user_repository import UserRepository


class AuthService:
    def __init__(self, database_path):
        self.user_repository = UserRepository(database_path)

    def register_user(self, username, email, password, role="user"):
        if self.user_repository.get_by_username(username):
            raise ValueError("username already exists")

        user_id = self.user_repository.create_user(username, email, password, role)
        return self.user_repository.get_by_id(user_id)

    def authenticate(self, username, password):
        return self.user_repository.verify_user(username, password)

    def list_pending_users(self):
        return self.user_repository.get_pending_users()

    def approve_user(self, user_id):
        self.user_repository.approve_user(user_id)

    def reject_user(self, user_id):
        self.user_repository.reject_user(user_id)
