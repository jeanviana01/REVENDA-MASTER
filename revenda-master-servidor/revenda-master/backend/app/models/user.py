def get_by_id(db, user_id):
    return db.execute("SELECT id, username, password_hash, session_version FROM users WHERE id = ?", (user_id,)).fetchone()


def get_by_username(db, username):
    return db.execute("SELECT id, username, password_hash, session_version FROM users WHERE username = ?", (username,)).fetchone()


def create(db, username, password_hash):
    cur = db.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, password_hash))
    db.commit()
    return cur.lastrowid


def set_password(db, user_id, password_hash):
    db.execute("UPDATE users SET password_hash = ?, session_version = session_version + 1 WHERE id = ?", (password_hash, user_id))
    db.commit()


def bump_session(db, user_id):
    """Invalida todas as sessões abertas do usuário (usado no logout e na troca de senha)."""
    db.execute("UPDATE users SET session_version = session_version + 1 WHERE id = ?", (user_id,))
    db.commit()
    return db.execute("SELECT session_version FROM users WHERE id = ?", (user_id,)).fetchone()["session_version"]
