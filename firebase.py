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

    def join_room(self, member_name: str) -> dict:
        ret = {"joined": False, "pending": False}
        db = firestore.client()
        doc = db.collection("rooms").document(
            self.room_id).get()

        # ルームが無いなら参加しない
        if not doc.exists:
            return ret

        # 既に参加済みなら参加許可
        if self.is_member():
            ret["joined"] = True
            return ret

        members = doc.to_dict()["users"]
        settings = doc.to_dict()["settings"]
        if settings["on_new_member_request"] == "always":
            # 誰でも参加可能
            self.__join(member_name)
            ret["joined"] = True

        elif settings["on_new_member_request"] == "vote" or \
                settings["on_new_member_request"] == "accept_by_mods" or \
                settings["on_new_member_request"] == "accept_by_owner":
            # 承認待ち
            db.collection("pending_users").add({
                "id": self.uid,
                "is_approved": None,
            }, self.uid)
            db.collection("rooms").document(self.room_id).collection("pending").add({
                "name": member_name,
                "id": self.uid,
                "is_accepted": False,
                "approval": 0,
                "required": int(len(members.keys())/100*settings["accept_rate"]),
                "size": len(members.keys()),
                "voted": []
            }, member_name)

            ret["pending"] = True

        return ret

    def vote(self, vote_for: str, accepted: bool) -> dict:
        # TODO: Androidアプリ側の実装をしてからデバッグする
        ret = {"voted": False}
        db = firestore.client()

        # このユーザーが投票中かどうか確認
        pending_doc = db.collection("rooms").document(self.room_id).collection(
            "pending").document(vote_for).get()
        if not pending_doc.exists:
            # 投票中でないならなにもしない
            return ret

        # 投票済みならなにもしない
        if vote_for in pending_doc.to_dict()["voted"]:
            ret["voted"] = True
            return ret

        # 投票
        now = pending_doc.to_dict()
        if accepted:
            # 承認
            if now["approval"] + 1 >= now["required"]:
                # 投票による承認
                pending_doc.set({
                    "is_accepted": True,
                    "approval": now["approval"] + 1,
                    "voted": now["voted"] + [self.uid],
                }, merge=True)

                name = db.collection("rooms").document(self.room_id) \
                    .collection("pending").document(vote_for).to_dict()["name"]
                self.__join(name)

            else:
                # 投票結果未確定
                pending_doc.set({
                    "approval": now["approval"] + 1,
                    "voted": now["voted"] + [self.uid],
                }, merge=True)

        else:
            # 否認
            if now["size"] - len(now["voted"])-1 + now["approval"] < now["required"]:
                # 投票結果確定(否認)
                pending_doc.set({
                    "is_accepted": False,
                    "voted": now["voted"] + [self.uid],
                }, merge=True)

            else:
                # 投票結果未確定
                pending_doc.set({
                    "voted": now["voted"] + [self.uid],
                }, merge=True)
        ret["voted"] = True
        return ret

    def __join(self, member_name=None):
        if (member_name is None):
            member_name = self.get_name()
        db = firestore.client()
        db.collection("rooms").document(self.room_id).collection("members").add({
            "name": member_name,
            "id": self.uid,
            "weight": 1.0,
            "role": "NORMAL",
        }, member_name)
        db.collection("rooms").document(self.room_id).set({
            "users": {
                self.uid: member_name,
            },
        }, merge=True)
