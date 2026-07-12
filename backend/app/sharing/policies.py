from app.auth.models import User
from app.sharing.models import SharedStudy


def can_view(share: SharedStudy, user: User | None) -> bool:
    return bool(user and user.id == share.owner_id) or share.visibility in {'unlisted', 'public'}


def is_owner(share: SharedStudy, user: User) -> bool:
    return share.owner_id == user.id
