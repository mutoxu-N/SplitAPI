from enum import Enum


class Role(Enum):
    OWNER = 3
    MODERATOR = 2
    NORMAL = 1

    @classmethod
    def of(self, role_name: str):
        for e in Role:
            if e.name == role_name:
                return e
        raise ValueError(f"{role_name} is not a valid Role")
