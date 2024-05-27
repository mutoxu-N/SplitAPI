# libs
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
from firebase_admin import auth


class FirebaseApi:
    uid = None

    def __init__(self, token: str) -> None:
        # サービスアカウントでログイン
        cred = credentials.Certificate("firebase_secret.json")
        firebase_admin.initialize_app(cred)

        try:
            info = auth.verify_id_token(token)
            self.uid = info['uid']

        except auth.InvalidIdTokenError:
            print(f"Invalid Token: {token[:80]}...")

    # データ追加
    def add(self, path: str, data: dict):
        db = firestore.client()
        query = db.collection(path)
        query.add(data)
