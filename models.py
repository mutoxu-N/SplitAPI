from pydantic import BaseModel
from enum import IntEnum
from firebase_admin.firestore import SERVER_TIMESTAMP


class Role(IntEnum):
    OWNER = 3
    MODERATOR = 2
    NORMAL = 1

    @classmethod
    def of(self, role_name: str):
        for e in Role:
            if e.name == role_name.upper():
                return e
        raise ValueError(f"{role_name} is not a valid Role")


class Settings(BaseModel):
    name: str
    split_unit: int
    permission_receipt_create: str
    permission_receipt_edit: str
    on_new_member_request: str
    accept_rate: int


class Receipt(BaseModel):
    id: str
    stuff: str
    paid: list[str]
    buyers: list[str]
    payment: int
    reported_by: str
    timestamp: str


class User(BaseModel):
    name: str
    uid: str | None
    weight: float
    role: int


class Receipt(BaseModel):
    id: str | None
    stuff: str
    paid: str
    buyers: list[str]
    payment: int
    reported_by: str
    timestamp: str | None

    def toMap(self):
        return {
            "id": self.id,
            "stuff": self.stuff,
            "paid": self.paid,
            "buyers": self.buyers,
            "payment": self.payment,
            "reported_by": self.reported_by,
            "timestamp": SERVER_TIMESTAMP,
        }
