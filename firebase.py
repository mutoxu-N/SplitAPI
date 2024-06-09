# libs
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
from firebase_admin import auth
from models import Role, Settings

# サービスアカウントでログイン
cred = credentials.Certificate("firebase_secret.json")
firebase_admin.initialize_app(cred)


class FirebaseApi:
    uid = None
    room_id = None

    def __init__(self, token: str, room_id: str) -> None:
        self.room_id = room_id

        try:
            info = auth.verify_id_token(token)
            self.uid = info['uid']

        except auth.InvalidIdTokenError:
            print(f"Invalid Token: {token[:80]}...")

    def __is_valid_uid(self) -> bool:
        return self.uid is not None

    def reset_firestore(self) -> None:
        if not self.__is_valid_uid():
            return

        # リセット
        db = firestore.client()
        # db.collection("pending_users").document(self.uid)
        room_AB12C3 = db.collection("rooms").document("AB12C3")
        room_AB12C3.set({
            "settings": {"name": "sample room"},
            "users": {
                self.uid: "sample member",
            },
        })

        room_AB12C3.collection("members").add({
            "name": "sample member",
            "id": self.uid,
            "weight": 1.0,
            "role": "OWNER",
        }, "sample member")

        room_AB12C3.collection("pending").add({
            "name": "pending member",
            "id": self.uid,
            "is_accepted": False,
            "approval": 0,
            "required": 1,
            "size": 1,
            "voted": []
        }, "pending member")

        room_AB12C3.collection("receipts").add({
            "stuff": "item",
            "paid": self.uid,
            "buyers": [self.uid],
            "payment": 2500,
            "reported_by": "sample member",
            "timestamp": firestore.SERVER_TIMESTAMP,
        })

    def is_member(self) -> bool:
        # ルームのメンバーか否かを判定
        if self.uid is None:
            return False
        db = firestore.client()
        members = set(db.collection("rooms").document(
            self.room_id).get(["users"]).to_dict()["users"].keys())
        return self.uid in members

    def get_name(self) -> str:
        # ルーム内の表示名を取得
        if not self.is_member():
            return None

        db = firestore.client()
        return db.collection("rooms").document(
            self.room_id).get(["users"]).to_dict()["users"][self.uid]

    def get_role(self) -> Role:
        # ルーム内の役職を取得
        db = firestore.client()
        name = self.get_name()
        role = db.collection("rooms").document(self.room_id).collection(
            "members").document(name).get(["role"]).to_dict()["role"]
        return Role.of(role)

    def check_if_room_exists(self) -> bool:
        db = firestore.client()
        room = db.collection("rooms").document(self.room_id).get()
        if room.exists:
            return True
        else:
            return False

    def create_room(self, settings: Settings, owner_name: str) -> None:
        db = firestore.client()
        db.collection("rooms").document(self.room_id).set({
            "settings": {
                "split_unit": settings.split_unit,
                "permission_receipt_create": settings.permission_receipt_create,
                "permission_receipt_create": settings.permission_receipt_edit,
                "on_new_member_request": settings.on_new_member_request,
                "accept_rate": settings.accept_rate,
            },
            "users": {
                self.uid: owner_name,
            },
        })
        db.collection("rooms").document(self.room_id).collection("members").add({
            "name": owner_name,
            "id": self.uid,
            "weight": 1.0,
            "role": "OWNER",
        }, owner_name)
