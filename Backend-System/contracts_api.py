from flask import Blueprint, request, jsonify
import sqlite3
import datetime
import jwt

from common import connect, SECRET_KEY


def ensure_contracts_schema():
    conn = connect()
    cur = conn.cursor()
    # Create table if missing (with complete schema)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS contracts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER,
            template_id INTEGER,
            tenant_name TEXT,
            id_card TEXT,
            room_no TEXT,
            start_date TEXT,
            end_date TEXT,
            rent REAL,
            rendered_html TEXT,
            created_at TEXT,
            updated_at TEXT
        )
        """
    )
    # Ensure required columns exist for older schemas
    cur.execute("PRAGMA table_info(contracts)")
    existing_cols = {row[1] for row in cur.fetchall()}
    def add_col(name: str, type_def: str):
        if name not in existing_cols:
            cur.execute(f"ALTER TABLE contracts ADD COLUMN {name} {type_def}")
    add_col("room_id", "INTEGER")
    add_col("tenant_id", "INTEGER")
    add_col("template_id", "INTEGER")
    add_col("tenant_name", "TEXT")
    add_col("id_card", "TEXT")
    add_col("room_no", "TEXT")
    add_col("start_date", "TEXT")
    add_col("end_date", "TEXT")
    add_col("rent", "REAL")
    add_col("rendered_html", "TEXT")
    add_col("created_at", "TEXT")
    add_col("updated_at", "TEXT")
    conn.commit()
    conn.close()


contracts_bp = Blueprint("contracts", __name__, url_prefix="/api/contracts")


@contracts_bp.before_request
def require_token():
    # 允许 CORS 预检请求通过
    if request.method == "OPTIONS":
        return None
    # 简单 JWT 校验（Bearer Token）
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify({"message": "Missing or invalid token"}), 401
    token = auth_header.split(" ", 1)[1]
    try:
        jwt.decode(token, SECRET_KEY, algorithms=["HS256"])  # Validate signature
    except Exception:
        return jsonify({"message": "Unauthorized"}), 401


@contracts_bp.route("", methods=["POST"])  # POST /api/contracts
def create_contract():
    payload = request.get_json(force=True) or {}
    template_id = payload.get("template_id")
    vars_obj = payload.get("vars") or {}

    if not template_id:
        return jsonify({"message": "template_id is required"}), 400

    # Load template html
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT content_html, name FROM contract_templates WHERE id = ?", (template_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify({"message": "Template not found"}), 404
    content_html, template_name = row

    # Simple placeholder replacement: {{key}} => value
    rendered = content_html
    for k, v in vars_obj.items():
        rendered = rendered.replace("{{" + str(k) + "}}", str(v))

    # Extract common fields (optional)
    tenant_name = vars_obj.get("name") or vars_obj.get("tenant_name")
    id_card = vars_obj.get("id_card") or vars_obj.get("idCard")
    room_no = vars_obj.get("room_no") or vars_obj.get("roomNo")
    start_date = vars_obj.get("start_date") or vars_obj.get("startDate")
    end_date = vars_obj.get("end_date") or vars_obj.get("endDate")
    rent = vars_obj.get("rent")

    # Resolve tenant_id if possible (prefer id_card, fallback to name+room_no)
    tenant_id = None
    try:
        if id_card:
            cur.execute("SELECT id FROM tenants WHERE id_card = ? LIMIT 1", (id_card,))
            r = cur.fetchone()
            if r:
                tenant_id = r[0]
        if tenant_id is None and tenant_name:
            if room_no:
                cur.execute(
                    """
                    SELECT t.id FROM tenants t
                    LEFT JOIN rooms r ON r.id = t.room_id
                    WHERE t.name = ? AND r.room_no = ?
                    LIMIT 1
                    """,
                    (tenant_name, room_no),
                )
                r = cur.fetchone()
                if r:
                    tenant_id = r[0]
            if tenant_id is None:
                cur.execute("SELECT id FROM tenants WHERE name = ? LIMIT 1", (tenant_name,))
                r = cur.fetchone()
                if r:
                    tenant_id = r[0]
        # Fallback: 仅通过房号找到在住租户（不校验姓名）
        if tenant_id is None and room_no:
            cur.execute(
                """
                SELECT t.id FROM tenants t
                JOIN rooms r ON r.id = t.room_id
                WHERE r.room_no = ?
                LIMIT 1
                """,
                (room_no,),
            )
            r = cur.fetchone()
            if r:
                tenant_id = r[0]
    except Exception:
        # 如果查询异常，不阻塞保存流程；tenant_id 保持 None
        tenant_id = tenant_id

    # 外键与非空约束严格校验：无法解析则返回 400

    # Resolve room_id if possible (prefer room_no, fallback via tenant_id)
    room_id = None
    try:
        if room_no:
            cur.execute("SELECT id FROM rooms WHERE room_no = ? LIMIT 1", (room_no,))
            r = cur.fetchone()
            if r:
                room_id = r[0]
        if room_id is None and tenant_id and tenant_id != 0:
            cur.execute("SELECT room_id FROM tenants WHERE id = ? LIMIT 1", (tenant_id,))
            r = cur.fetchone()
            if r and r[0] is not None:
                room_id = r[0]
    except Exception:
        room_id = room_id

    # 校验必填字段（根据现有库约束）
    missing = []
    if tenant_id is None:
        missing.append("tenant_id")
    if room_id is None:
        missing.append("room_id")
    if not start_date:
        missing.append("start_date")
    if not end_date:
        missing.append("end_date")
    if rent in (None, ""):
        missing.append("rent")
    # 尝试将租金转为数值
    try:
        rent = float(rent) if rent is not None else rent
    except Exception:
        missing.append("rent")
    if missing:
        conn.close()
        return jsonify({
            "message": "缺少必填字段或无法解析，请先在租户/房间中补齐信息",
            "missing": missing
        }), 400
    cur.execute(
        """
        INSERT INTO contracts (
            tenant_id, room_id, template_id, tenant_name, id_card, room_no, start_date, end_date, rent, rendered_html, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """,
        (
            tenant_id,
            room_id,
            template_id,
            tenant_name,
            id_card,
            room_no,
            start_date,
            end_date,
            rent,
            rendered,
        ),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()

    return jsonify({"id": new_id, "message": "Contract saved", "template_name": template_name}), 201


@contracts_bp.route("", methods=["GET"])  # GET /api/contracts
def list_contracts():
    page = int(request.args.get("page", 1))
    page_size = int(request.args.get("page_size", 10))
    offset = (page - 1) * page_size

    conn = connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, template_id, tenant_name, room_no, start_date, end_date, rent, created_at FROM contracts ORDER BY id DESC LIMIT ? OFFSET ?",
        (page_size, offset),
    )
    rows = cur.fetchall()
    cur.execute("SELECT COUNT(*) FROM contracts")
    total = cur.fetchone()[0]
    conn.close()

    items = []
    for r in rows:
        items.append(
            {
                "id": r[0],
                "template_id": r[1],
                "tenant_name": r[2],
                "room_no": r[3],
                "start_date": r[4],
                "end_date": r[5],
                "rent": r[6],
                "created_at": r[7],
            }
        )

    return jsonify({"items": items, "total": total, "page": page, "page_size": page_size})


@contracts_bp.route("/<int:contract_id>", methods=["GET"])  # GET /api/contracts/:id
def get_contract(contract_id: int):
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, template_id, tenant_name, id_card, room_no, start_date, end_date, rent, rendered_html, created_at FROM contracts WHERE id = ?",
        (contract_id,),
    )
    r = cur.fetchone()
    conn.close()
    if not r:
        return jsonify({"message": "Not found"}), 404
    return jsonify(
        {
            "id": r[0],
            "template_id": r[1],
            "tenant_name": r[2],
            "id_card": r[3],
            "room_no": r[4],
            "start_date": r[5],
            "end_date": r[6],
            "rent": r[7],
            "rendered_html": r[8],
            "created_at": r[9],
        }
    )


@contracts_bp.route("/<int:contract_id>", methods=["PUT"])  # PUT /api/contracts/:id
def update_contract(contract_id: int):
    payload = request.get_json(force=True) or {}
    vars_obj = payload.get("vars") or {}

    conn = connect()
    cur = conn.cursor()
    # 找到旧合同以获取模板ID
    cur.execute("SELECT template_id FROM contracts WHERE id = ?", (contract_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify({"message": "Not found"}), 404
    template_id = row[0]

    # 读取模板HTML
    cur.execute("SELECT content_html, name FROM contract_templates WHERE id = ?", (template_id,))
    trow = cur.fetchone()
    if not trow:
        conn.close()
        return jsonify({"message": "Template not found"}), 404
    content_html, template_name = trow

    # 简单占位符替换
    rendered = content_html
    for k, v in vars_obj.items():
        rendered = rendered.replace("{{" + str(k) + "}}", str(v))

    # 提取字段
    tenant_name = vars_obj.get("name") or vars_obj.get("tenant_name")
    id_card = vars_obj.get("id_card") or vars_obj.get("idCard")
    room_no = vars_obj.get("room_no") or vars_obj.get("roomNo")
    start_date = vars_obj.get("start_date") or vars_obj.get("startDate")
    end_date = vars_obj.get("end_date") or vars_obj.get("endDate")
    rent = vars_obj.get("rent")

    # 解析 tenant_id
    tenant_id = None
    try:
        if id_card:
            cur.execute("SELECT id FROM tenants WHERE id_card = ? LIMIT 1", (id_card,))
            r = cur.fetchone()
            if r:
                tenant_id = r[0]
        if tenant_id is None and tenant_name:
            if room_no:
                cur.execute(
                    """
                    SELECT t.id FROM tenants t
                    LEFT JOIN rooms r ON r.id = t.room_id
                    WHERE t.name = ? AND r.room_no = ?
                    LIMIT 1
                    """,
                    (tenant_name, room_no),
                )
                r = cur.fetchone()
                if r:
                    tenant_id = r[0]
            if tenant_id is None:
                cur.execute("SELECT id FROM tenants WHERE name = ? LIMIT 1", (tenant_name,))
                r = cur.fetchone()
                if r:
                    tenant_id = r[0]
        if tenant_id is None and room_no:
            cur.execute(
                """
                SELECT t.id FROM tenants t
                JOIN rooms r ON r.id = t.room_id
                WHERE r.room_no = ?
                LIMIT 1
                """,
                (room_no,),
            )
            r = cur.fetchone()
            if r:
                tenant_id = r[0]
    except Exception:
        tenant_id = tenant_id

    # 解析 room_id
    room_id = None
    try:
        if room_no:
            cur.execute("SELECT id FROM rooms WHERE room_no = ? LIMIT 1", (room_no,))
            r = cur.fetchone()
            if r:
                room_id = r[0]
        if room_id is None and tenant_id and tenant_id != 0:
            cur.execute("SELECT room_id FROM tenants WHERE id = ? LIMIT 1", (tenant_id,))
            r = cur.fetchone()
            if r and r[0] is not None:
                room_id = r[0]
    except Exception:
        room_id = room_id

    # 校验必填
    missing = []
    if tenant_id is None:
        missing.append("tenant_id")
    if room_id is None:
        missing.append("room_id")
    if not start_date:
        missing.append("start_date")
    if not end_date:
        missing.append("end_date")
    if rent in (None, ""):
        missing.append("rent")
    try:
        rent = float(rent) if rent is not None else rent
    except Exception:
        missing.append("rent")
    if missing:
        conn.close()
        return jsonify({
            "message": "缺少必填字段或无法解析，请先在租户/房间中补齐信息",
            "missing": missing
        }), 400

    # 更新合同
    cur.execute(
        """
        UPDATE contracts
        SET tenant_id = ?, room_id = ?, template_id = ?, tenant_name = ?, id_card = ?, room_no = ?, start_date = ?, end_date = ?, rent = ?, rendered_html = ?, updated_at = datetime('now')
        WHERE id = ?
        """,
        (
            tenant_id,
            room_id,
            template_id,
            tenant_name,
            id_card,
            room_no,
            start_date,
            end_date,
            rent,
            rendered,
            contract_id,
        ),
    )
    conn.commit()
    conn.close()

    return jsonify({"id": contract_id, "message": "Contract updated", "template_name": template_name}), 200