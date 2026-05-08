from enum import Enum


class UserType(Enum):
    ADMIN = "admin"
    INTERNAL = "internal"
    EXTERNAL = "external"


def get_user_type_by_id(type_id: int):
    match type_id:
        case 1:
            return UserType.ADMIN
        case 2:
            return UserType.INTERNAL
        case 3:
            return UserType.EXTERNAL
