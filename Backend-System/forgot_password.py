import hashlib
from common import connect

def ensure_schema():
    """Ensure admins table exists and has recovery fields for forgot password."""
    conn = connect()
    cursor = conn.cursor()

    # Ensure base admins table exists
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT,
            created_at DATE DEFAULT (DATE('now'))
        )
        """
    )

    # Inspect existing columns
    cursor.execute("PRAGMA table_info(admins)")
    cols = {row[1] for row in cursor.fetchall()}

    # Add recovery phrase hash column
    if 'recovery_phrase_hash' not in cols:
        cursor.execute("ALTER TABLE admins ADD COLUMN recovery_phrase_hash TEXT")
    # Add security question text column
    if 'security_question' not in cols:
        cursor.execute("ALTER TABLE admins ADD COLUMN security_question TEXT")
    # Add security answer hash column
    if 'security_answer_hash' not in cols:
        cursor.execute("ALTER TABLE admins ADD COLUMN security_answer_hash TEXT")

    conn.commit()
    conn.close()

def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def verify_and_reset_password(username: str, answer: str, new_password: str):
    """仅通过安全问题答案找回并重置密码。"""
    ensure_schema()
    conn = connect()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, security_question, security_answer_hash FROM admins WHERE username = ?",
        (username,)
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False, "用户不存在"

    admin_id, sec_q, sec_ans_hash = row

    if not sec_ans_hash:
        conn.close()
        return False, "未设置安全问题答案，无法找回"
    if sha256(answer) != sec_ans_hash:
        conn.close()
        return False, "问题答案不正确"

    # 更新密码
    new_hash = sha256(new_password)
    cursor.execute("UPDATE admins SET password_hash = ? WHERE id = ?", (new_hash, admin_id))
    conn.commit()
    conn.close()
    return True, "密码重置成功"

def set_recovery_info(username: str, recovery_phrase: str | None = None, security_question: str | None = None, security_answer: str | None = None):
    """Helper to set recovery phrase and/or security question/answer for a user."""
    ensure_schema()
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM admins WHERE username = ?", (username,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False, "用户不存在"
    admin_id = row[0]

    updates = []
    params = []
    if recovery_phrase is not None:
        updates.append("recovery_phrase_hash = ?")
        params.append(sha256(recovery_phrase))
    if security_question is not None:
        updates.append("security_question = ?")
        params.append(security_question)
    if security_answer is not None:
        updates.append("security_answer_hash = ?")
        params.append(sha256(security_answer))

    if not updates:
        conn.close()
        return False, "无更新内容"

    params.append(admin_id)
    cursor.execute(f"UPDATE admins SET {', '.join(updates)} WHERE id = ?", params)
    conn.commit()
    conn.close()
    return True, "找回信息已更新"