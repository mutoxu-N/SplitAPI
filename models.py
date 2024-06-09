from pydantic import BaseModel
from enum import Enum


class Role(Enum):
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
    id: str | None
    weight: int
    role: int
