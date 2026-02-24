import os
import json

class SessionManager:
    @staticmethod
    def save_session(file_path, session_data):
        try:
            with open(file_path, 'w') as f:
                json.dump(session_data, f, indent=4)
            return True, "Session saved successfully"
        except Exception as e:
            return False, f"Failed to save session: {e}"

    @staticmethod
    def load_session(file_path):
        if not os.path.exists(file_path):
            return False, None, "File does not exist"
        try:
            with open(file_path, 'r') as f:
                session_data = json.load(f)
            return True, session_data, "Success"
        except Exception as e:
            return False, None, f"Failed to load session: {e}"
