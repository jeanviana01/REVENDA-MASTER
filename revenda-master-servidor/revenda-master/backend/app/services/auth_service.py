from ..errors import ApiError
from ..models import user as users
from ..security import DUMMY_HASH, hash_password, password_problem, verify_password


def authenticate(db, username, password):
    """Devolve o usuário se as credenciais estiverem certas; senão None (sempre gastando o mesmo esforço)."""
    user = users.get_by_username(db, username)
    ok = verify_password(password, user["password_hash"] if user else DUMMY_HASH)
    return user if (user and ok) else None


def change_password(db, user, current, new):
    if not verify_password(current, user["password_hash"]):
        raise ApiError(403, "wrong_password", "A senha atual está incorreta.")
    problem = password_problem(new, user["username"])
    if problem:
        raise ApiError(422, "weak_password", problem)
    users.set_password(db, user["id"], hash_password(new))
    return users.get_by_id(db, user["id"])


def create_or_reset(db, username, password, reset=False):
    problem = password_problem(password, username)
    if problem:
        raise ValueError(problem)
    existing = users.get_by_username(db, username)
    if existing and not reset:
        raise ValueError("Esse usuário já existe (use --reset para trocar a senha).")
    if existing:
        users.set_password(db, existing["id"], hash_password(password))
        return existing["id"], "atualizado"
    return users.create(db, username, hash_password(password)), "criado"
