# libs
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
from firebase_admin import auth
from models import Role, Settings, Member, Receipt

# サービスアカウントでログイン
cred = credentials.Certificate("/src/firebase_secret.json")
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

    def is_member(self) -> bool:
        # ルームのメンバーか否かを判定
        if self.uid is None:
            return False

        if not self.check_if_room_exists():
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

    def create_room(self, settings: Settings, owner_name: str) -> Member:
        db = firestore.client()
        db.collection("rooms").document(self.room_id).set({
            "settings": {
                "name": settings.name,
                "split_unit": settings.split_unit,
                "permission_receipt_create": settings.permission_receipt_create,
                "permission_receipt_edit": settings.permission_receipt_edit,
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
            "role": Role.OWNER,
        }, owner_name)

        return Member(
            name=owner_name,
            uid=self.uid,
            weight=1.0,
            role=Role.OWNER,
        )

    def join_room(self, member_name: str) -> dict:
        ret = {"joined": False, "pending": False}
        db = firestore.client()

        # ルームが無いなら参加しない
        if not self.check_if_room_exists():
            return ret

        # 既に参加済みなら参加許可
        if self.is_member():
            ret["joined"] = True
            doc = db.collection("rooms").document(self.room_id).get().to_dict()
            d = doc["users"]
            if self.uid in d:
                old_name = d[self.uid]
                d[self.uid] = member_name

                # ROOM/members を更新
                m = db.collection("rooms").document(self.room_id).collection(
                    "members").document(old_name).get().to_dict()
                self.edit_member(old_name, Member(
                    name=member_name,
                    uid=self.uid,
                    weight=m["weight"],
                    role=Role.of(m["role"]),
                ))

                # Room.users を更新
                db.collection("rooms").document(self.room_id).set({
                    "users": {
                        self.uid: member_name,
                    },
                }, merge=True)

            # pending_users を削除
            print("delete")
            db.collection("pending_users").document(self.uid).delete()
            db.collection("rooms").document(self.room_id).collection(
                "pending").document(self.uid).delete()

            ret["me"] = d
            return ret

        doc = db.collection("rooms").document(
            self.room_id).get()
        members = doc.to_dict()["users"]
        settings = doc.to_dict()["settings"]
        if settings["on_new_member_request"] == "always":
            # 誰でも参加可能
            self.__join(member_name, self.uid)
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
            }, self.uid)

            ret["pending"] = True

        return ret

    def cancel(self):
        db = firestore.client()
        db.collection("pending_users").document(self.uid).delete()
        db.collection("rooms").document(self.room_id).collection(
            "pending").document(self.uid).delete()

    def vote(self, vote_for: str, accepted: bool) -> dict:
        if not self.is_member():
            return False

        ret = {"voted": False}
        db = firestore.client()

        # このユーザーが投票中かどうか確認
        pending_ref = db.collection("rooms").document(self.room_id).collection(
            "pending").document(vote_for)
        pending_doc = pending_ref.get()
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
                pending_ref.delete()
                db.collection("pending_users").document(vote_for).set({
                    "is_approved": True,
                }, merge=True)

                self.__join(
                    pending_doc.to_dict()["name"],
                    pending_doc.to_dict()["id"],
                )

            else:
                # 投票結果未確定
                pending_ref.set({
                    "approval": now["approval"] + 1,
                    "voted": now["voted"] + [self.uid],
                }, merge=True)

        else:
            # 否認
            if now["size"] - len(now["voted"])-1 + now["approval"] < now["required"]:
                # 投票結果確定(否認)
                pending_ref.delete()

                db.collection("pending_users").document(vote_for).set({
                    "is_approved": None,
                }, merge=True)

            else:
                # 投票結果未確定
                pending_ref.set({
                    "voted": now["voted"] + [self.uid],
                }, merge=True)
        ret["voted"] = True
        return ret

    def accept(self, accept_for: str, accepted: bool):
        if not self.is_member():
            return False

        # ルーム設定が承認制か確認
        db = firestore.client()
        doc = db.collection("rooms").document(
            self.room_id).get()
        settings = doc.to_dict()["settings"]

        # このユーザーが参加待機中かどうか確認
        pending_ref = db.collection("rooms").document(self.room_id).collection(
            "pending").document(accept_for)
        pending_doc = pending_ref.get()
        if not pending_doc.exists:
            # 参加待機中でないならなにもしない
            return False

        role = self.get_role()
        if settings["on_new_member_request"] == "accept_by_mods":
            if role >= Role.MODERATOR:
                if accepted:
                    # 承認
                    self.__join(
                        pending_doc.to_dict()["name"],
                        pending_doc.to_dict()["id"],
                    )

                    db.collection("pending_users").document(accept_for).set({
                        "is_approved": True,
                    }, merge=True)
                    pending_ref.set({
                        "is_accepted": accepted,
                        "voted": [self.uid],
                    }, merge=True)

                else:
                    db.collection("pending_users").document(
                        accept_for).delete()
                    db.collection("rooms").document(self.room_id).collection(
                        "pending").document(accept_for).delete()
                return True

            else:
                return False

        if settings["on_new_member_request"] == "accept_by_owner":
            if role >= Role.OWNER:
                if accepted:
                    # 承認
                    self.__join(
                        pending_doc.to_dict()["name"],
                        pending_doc.to_dict()["id"],
                    )

                    db.collection("pending_users").document(accept_for).set({
                        "is_approved": True,
                    }, merge=True)
                    pending_ref.set({
                        "is_accepted": accepted,
                        "voted": [self.uid],
                    }, merge=True)

                else:
                    db.collection("pending_users").document(
                        accept_for).delete()
                    db.collection("rooms").document(self.room_id).collection(
                        "pending").document(accept_for).delete()
                return True

            else:
                return False

    def create_guest(self, user: str):
        if not self.is_member():
            return False

        if self.get_role() >= Role.MODERATOR:
            db = firestore.client()
            col = db \
                .collection("rooms").document(self.room_id) \
                .collection("members")
            col.add({
                "name": user,
                "id": None,
                "weight": 1.0,
                "role": Role.NORMAL,
            }, user)
            return True

        else:
            return False

    def delete_guest(self, user: str):
        if not self.is_member():
            return False

        if self.get_role() >= Role.MODERATOR:
            db = firestore.client()

            # check
            receipts = db \
                .collection("rooms").document(self.room_id) \
                .collection("receipts").list_documents()

            for r in receipts:
                if r.to_dict()["paid"] == user:
                    return False

            # delete
            for r in receipts:
                buyers = r.to_dict()["buyers"]
                if user in buyers:
                    r.set("buyers", buyers.remove(user))

            db.collection("rooms").document(self.room_id).collection(
                "members").document(user).delete()
            ref = db.collection("rooms").document(self.room_id)
            d: dict = ref.get().to_dict(["users"])
            d.pop(self.uid)
            ref.update({
                "users": d
            })
            return True

        else:
            return False

    def edit_member(self, old: str, new: Member):
        print(old, new)
        if not self.is_member():
            return False

        if self.get_role() >= Role.MODERATOR:
            db = firestore.client()
            doc = db \
                .collection("rooms").document(self.room_id) \
                .collection("members").document(old)

            old_role = None
            if doc.get().exists:
                old_role = doc.get().to_dict()["role"]
                doc.delete()
            col = db \
                .collection("rooms").document(self.room_id) \
                .collection("members")

            # オーナーの変更
            if new.role == Role.OWNER and old_role != Role.OWNER:
                members = db.collection("rooms").document(
                    self.room_id).collection("members").list_documents()
                print(members)
                for m in members:
                    print(m)
                    if m.get()["role"] == Role.OWNER:
                        m.set("role", Role.MODERATOR)

            # レシート更新
            receipts = db.collection("rooms").document(
                self.room_id).collection("receipts").list_documents()
            for receipt in receipts:
                r = receipt.get()
                d = r.to_dict()
                if d["paid"] == old:
                    d["paid"] = new.name

                if old in d["buyers"]:
                    d["buyers"].remove(old)
                    d["buyers"].append(new.name)

                print(d)
                receipt.set(d, merge=True)

            col.add({
                "name": new.name,
                "id": new.uid,
                "weight": new.weight,
                "role": new.role
            }, new.name)

            # Room.users を更新
            if new.uid is not None:
                db.collection("rooms").document(self.room_id).set({
                    "users": {
                        new.uid: new.name,
                    },
                }, merge=True)

            return True

        else:
            return False

    def edit_settings(self, settings: dict):
        if not self.is_member():
            return False

        if self.get_role() >= Role.OWNER:
            db = firestore.client()
            doc = db.collection("rooms").document(self.room_id)
            doc.set({
                "settings": {
                    "name": settings.name,
                    "split_unit": settings.split_unit,
                    "permission_receipt_create": settings.permission_receipt_create,
                    "permission_receipt_edit": settings.permission_receipt_edit,
                    "on_new_member_request": settings.on_new_member_request,
                    "accept_rate": settings.accept_rate,
                },
            }, merge=True)
            return True
        return False

    def room_delete(self):
        if not self.is_member():
            return False

        if self.get_role() >= Role.OWNER:
            db = firestore.client()
            room_ref = db.collection("rooms").document(self.room_id)
            pending = room_ref.collection("pending").list_documents()
            for p in pending:
                db.collection("pending_users").document(
                    p.get().to_dict()["id"]).get().delete()
            db.recursive_delete(room_ref)
            return True
        return False

    def add_receipt(self, receipt: Receipt):
        if not self.is_member():
            return False

        # 権限チェック
        role = self.get_role()
        perm = Role.of(self.__get_settings().permission_receipt_create)
        if role < perm:
            return False

        db = firestore.client()
        time, doc = db.collection("rooms").document(self.room_id) \
            .collection("receipts").add(receipt.toMap())
        doc.set({
            "id": doc.id,
            "reported_by": self.uid,
            "timestamp": time,
        }, merge=True)
        return True

    def edit_receipt(self, receipt_id: str, receipt: Receipt):
        if not self.is_member():
            return False

            # 権限チェック
        role = self.get_role()
        perm = Role.of(self.__get_settings().permission_receipt_create)
        if role < perm:
            return False

        db = firestore.client()
        doc = db.collection("rooms").document(self.room_id) \
            .collection("receipts").document(receipt_id)

        receipt.reported_by = self.uid
        doc.set(receipt.toMap(), merge=True)

        return True

    def __join(self, member_name=None, uid=None):
        if member_name is None or uid is None:
            member_name = self.get_name()
            uid = self.uid

        # メンバー名がかぶっていたら修正
        db = firestore.client()
        members = set(db.collection("rooms").document(
            self.room_id).get(["users"]).to_dict()["users"].values())
        old = member_name
        num = 0
        while member_name in members:
            num += 1
            member_name = f"{old} {num}"

        db.collection("rooms").document(self.room_id).collection("members").add({
            "name": member_name,
            "id": uid,
            "weight": 1.0,
            "role": 0,
        }, member_name)
        db.collection("rooms").document(self.room_id).set({
            "users": {
                uid: member_name,
            },
        }, merge=True)
        db.collection("rooms").document(self.room_id).collection(
            "pending").document(self.uid).delete()

    def __get_settings(self):
        db = firestore.client()
        doc = db.collection("rooms").document(self.room_id).get().to_dict()
        return Settings(
            name=doc["settings"]["name"],
            split_unit=doc["settings"]["split_unit"],
            permission_receipt_create=doc["settings"]["permission_receipt_create"],
            permission_receipt_edit=doc["settings"]["permission_receipt_edit"],
            on_new_member_request=doc["settings"]["on_new_member_request"],
            accept_rate=doc["settings"]["accept_rate"],
        )
