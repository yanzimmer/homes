import sqlite3
from flask import Blueprint, request, jsonify
import jwt
from functools import wraps
from common import connect


def ensure_contract_templates_schema():
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS contract_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            content_html TEXT NOT NULL,
            created_at DATETIME DEFAULT (DATETIME('now')),
            updated_at DATETIME DEFAULT (DATETIME('now'))
        )
        """
    )
    conn.commit()
    conn.close()


templates_bp = Blueprint("contract_templates", __name__, url_prefix="/api/contract-templates")


def token_required_bp(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
        if not token:
            return jsonify({"error": "缺少认证令牌"}), 401
        try:
            data = jwt.decode(token, "homes_rental_secret_key", algorithms=["HS256"])  # 与主应用一致
            conn = connect()
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT * FROM admins WHERE username = ?", (data.get("username"),))
            except sqlite3.OperationalError as e:
                # 友好提示数据库未初始化或路径不一致
                conn.close()
                return jsonify({"error": f"数据库未初始化或不可用：{e}"}), 500
            user_data = cursor.fetchone()
            conn.close()
            if not user_data:
                return jsonify({"error": "无效的认证令牌"}), 401
            current_user = {
                "id": user_data[0],
                "username": user_data[1],
                "full_name": user_data[3],
            }
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "认证令牌已过期，请重新登录"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "无效的认证令牌"}), 401
        return f(current_user=current_user, *args, **kwargs)
    return decorated


@templates_bp.route("", methods=["GET"])
@token_required_bp
def list_templates(current_user):
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, description, created_at, updated_at FROM contract_templates ORDER BY updated_at DESC")
    rows = cursor.fetchall()
    conn.close()
    templates = [
        {
            "id": r[0],
            "name": r[1],
            "description": r[2],
            "created_at": r[3],
            "updated_at": r[4],
        }
        for r in rows
    ]
    return jsonify({"templates": templates})


@templates_bp.route("/<int:tid>", methods=["GET"])
@token_required_bp
def get_template(current_user, tid: int):
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, description, content_html, created_at, updated_at FROM contract_templates WHERE id = ?", (tid,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "模板不存在"}), 404
    tpl = {
        "id": row[0],
        "name": row[1],
        "description": row[2],
        "content_html": row[3],
        "created_at": row[4],
        "updated_at": row[5],
    }
    return jsonify({"template": tpl})


@templates_bp.route("", methods=["POST"])
@token_required_bp
def add_template(current_user):
    data = request.json or {}
    name = data.get("name")
    content_html = data.get("content_html")
    description = data.get("description", "")
    if not name or not content_html:
        return jsonify({"error": "缺少必填字段 name 或 content_html"}), 400
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO contract_templates (name, description, content_html, updated_at) VALUES (?, ?, ?, DATETIME('now'))",
        (name, description, content_html),
    )
    tid = cursor.lastrowid
    conn.commit()
    conn.close()
    return jsonify({"message": "模板已创建", "id": tid})


@templates_bp.route("/<int:tid>", methods=["PUT"])
@token_required_bp
def update_template(current_user, tid: int):
    data = request.json or {}
    allowed = {"name", "description", "content_html"}
    updates = {k: v for k, v in data.items() if k in allowed}
    if not updates:
        return jsonify({"error": "没有有效的更新字段"}), 400
    conn = connect()
    cursor = conn.cursor()
    # 动态更新
    for k, v in updates.items():
        cursor.execute(f"UPDATE contract_templates SET {k} = ?, updated_at = DATETIME('now') WHERE id = ?", (v, tid))
    if cursor.rowcount == 0:
        conn.close()
        return jsonify({"error": "模板不存在"}), 404
    conn.commit()
    conn.close()
    return jsonify({"message": "模板已更新"})


@templates_bp.route("/<int:tid>", methods=["DELETE"])
@token_required_bp
def delete_template(current_user, tid: int):
    """删除模板时总是连同删除关联合同。"""
    conn = connect()
    cursor = conn.cursor()
    try:
        # 检查模板是否存在
        cursor.execute("SELECT id FROM contract_templates WHERE id = ?", (tid,))
        if not cursor.fetchone():
            conn.close()
            return jsonify({"error": "模板不存在"}), 404

        # 查询并删除所有关联合同
        cursor.execute("SELECT COUNT(*) FROM contracts WHERE template_id = ?", (tid,))
        linked_count = cursor.fetchone()[0] or 0
        cursor.execute("DELETE FROM contracts WHERE template_id = ?", (tid,))

        # 删除模板
        cursor.execute("DELETE FROM contract_templates WHERE id = ?", (tid,))
        conn.commit()
        conn.close()

        return jsonify({
            "message": f"模板已删除，并删除了 {linked_count} 条关联合同",
            "contracts_deleted": linked_count
        })
    except sqlite3.OperationalError as e:
        try:
            conn.rollback()
        except Exception:
            pass
        conn.close()
        return jsonify({"error": f"数据库繁忙或不可用：{e}"}), 503
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        conn.close()
        return jsonify({"error": f"删除失败：{e}"}), 500


@templates_bp.route("/<int:tid>/render", methods=["POST"])
@token_required_bp
def render_template(current_user, tid: int):
    """使用传入的数据渲染模板：占位符语法 {{key}}"""
    data = request.json or {}
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT content_html FROM contract_templates WHERE id = ?", (tid,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "模板不存在"}), 404
    html = row[0] or ""
    # 简单替换：{{key}} -> value
    try:
        for k, v in (data.get("vars") or {}).items():
            placeholder = f"{{{{{k}}}}}"
            html = html.replace(placeholder, str(v))
        return jsonify({"rendered_html": html})
    except Exception as e:
        return jsonify({"error": f"渲染失败: {e}"}), 500