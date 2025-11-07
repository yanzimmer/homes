import argparse
import json
import hashlib
from datetime import date
import os
import sys
import shutil

# 允许从父目录导入 common 模块
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from common import connect, DB_NAME


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def ensure_tables():
    """Create all required tables if missing and ensure recovery columns."""
    conn = connect()
    cur = conn.cursor()

    # rooms
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            building TEXT,
            floor INTEGER,
            room_no TEXT UNIQUE NOT NULL,
            room_type TEXT,
            price REAL,
            status TEXT DEFAULT '空闲'
        )
        """
    )

    # tenants
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS tenants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            gender TEXT,
            nation TEXT,
            birth_date DATE,
            id_card TEXT UNIQUE,
            address TEXT,
            issuing_authority TEXT,
            valid_from DATE,
            valid_to DATE,
            front_img TEXT,
            back_img TEXT,
            phone TEXT,
            emergency_contact_name TEXT,
            emergency_contact_phone TEXT,
            check_in_date DATE,
            check_out_date DATE,
            room_id INTEGER,
            remarks TEXT,
            status TEXT DEFAULT '在住',
            FOREIGN KEY (room_id) REFERENCES rooms(id)
        )
        """
    )

    # tenant_moves
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS tenant_moves (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER,
            old_room_id INTEGER,
            new_room_id INTEGER,
            move_date DATE,
            remarks TEXT,
            FOREIGN KEY (tenant_id) REFERENCES tenants(id),
            FOREIGN KEY (old_room_id) REFERENCES rooms(id),
            FOREIGN KEY (new_room_id) REFERENCES rooms(id)
        )
        """
    )

    # admins base table
    cur.execute(
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
    # ensure recovery columns
    cur.execute("PRAGMA table_info(admins)")
    cols = {row[1] for row in cur.fetchall()}
    if "recovery_phrase_hash" not in cols:
        cur.execute("ALTER TABLE admins ADD COLUMN recovery_phrase_hash TEXT")
    if "security_question" not in cols:
        cur.execute("ALTER TABLE admins ADD COLUMN security_question TEXT")
    if "security_answer_hash" not in cols:
        cur.execute("ALTER TABLE admins ADD COLUMN security_answer_hash TEXT")

    # repair_records
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS repair_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            building TEXT,
            room_no TEXT NOT NULL,
            repair_type TEXT,
            description TEXT,
            report_date DATE,
            report_by TEXT,
            status TEXT DEFAULT '待处理',
            repair_date DATE,
            repair_cost REAL,
            repair_person TEXT,
            remarks TEXT,
            FOREIGN KEY (room_no) REFERENCES rooms(room_no)
        )
        """
    )

    # contract_templates (合同模板)
    cur.execute(
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

    # contracts (合同档案)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS contracts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_id INTEGER NOT NULL,
            tenant_name TEXT,
            id_card TEXT,
            room_no TEXT,
            start_date TEXT,
            end_date TEXT,
            rent REAL,
            rendered_html TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT
        )
        """
    )

    conn.commit()
    conn.close()


def seed_demo_data():
    """Insert logical demo data across rooms, tenants, moves, repairs, templates, and contracts.

    Idempotent: skips seeding if rooms or tenants already have data.
    """
    conn = connect()
    cur = conn.cursor()

    # If already seeded (rooms exist), skip
    cur.execute("SELECT COUNT(*) FROM rooms")
    room_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM tenants")
    tenant_count = cur.fetchone()[0]
    if room_count > 0 or tenant_count > 0:
        conn.close()
        print("ℹ️ 跳过演示数据：数据库已有房间或租户记录")
        return False

    # 1) Rooms: 两座楼，若干房型与价格
    rooms = [
        ("A座", 1, "A101", "单人间", 198.0),
        ("A座", 1, "A102", "双人间", 258.0),
        ("A座", 2, "A201", "单人间", 208.0),
        ("A座", 2, "A202", "套房", 398.0),
        ("A座", 3, "A301", "单人间", 228.0),
        ("B座", 1, "B101", "双人间", 268.0),
        ("B座", 1, "B102", "单人间", 198.0),
        ("B座", 2, "B201", "套房", 428.0),
        ("B座", 2, "B202", "单人间", 218.0),
    ]
    for building, floor, room_no, room_type, price in rooms:
        cur.execute(
            "INSERT INTO rooms (building, floor, room_no, room_type, price, status) VALUES (?, ?, ?, ?, ?, '空闲')",
            (building, floor, room_no, room_type, price),
        )

    # 提前查房间 id 映射
    cur.execute("SELECT id, room_no FROM rooms")
    room_map = {r[1]: r[0] for r in cur.fetchall()}

    # 2) Tenants: 若干在住与已退租，覆盖关键字段
    tenants = [
        {
            "name": "张三",
            "gender": "男",
            "nation": "汉族",
            "birth_date": "1992-03-15",
            "id_card": "11010519920315001X",
            "address": "北京市朝阳区幸福路88号",
            "issuing_authority": "北京市公安局朝阳分局",
            "valid_from": "2018-01-01",
            "valid_to": "2028-01-01",
            "phone": "13800000001",
            "emergency_contact_name": "王五",
            "emergency_contact_phone": "13900000001",
            "check_in_date": "2024-06-01",
            "check_out_date": "2025-06-01",
            "room_no": "A101",
            "remarks": "长期客",
            "status": "在住",
        },
        {
            "name": "李四",
            "gender": "女",
            "nation": "汉族",
            "birth_date": "1995-08-20",
            "id_card": "110105199508200029",
            "address": "北京市海淀区中关村大街1号",
            "issuing_authority": "北京市公安局海淀分局",
            "valid_from": "2019-05-01",
            "valid_to": "2029-05-01",
            "phone": "13800000002",
            "emergency_contact_name": "赵六",
            "emergency_contact_phone": "13900000002",
            "check_in_date": "2025-01-15",
            "check_out_date": "2025-12-31",
            "room_no": "A102",
            "remarks": "旅游客",
            "status": "在住",
        },
        {
            "name": "王强",
            "gender": "男",
            "nation": "汉族",
            "birth_date": "1988-11-02",
            "id_card": "110105198811020037",
            "address": "天津市河西区解放南路100号",
            "issuing_authority": "天津市公安局河西分局",
            "valid_from": "2017-03-01",
            "valid_to": "2027-03-01",
            "phone": "13800000003",
            "emergency_contact_name": "王芳",
            "emergency_contact_phone": "13900000003",
            "check_in_date": "2023-12-01",
            "check_out_date": "2024-12-01",
            "room_no": "A201",
            "remarks": "已退租样本",
            "status": "已退租",
        },
        {
            "name": "赵敏",
            "gender": "女",
            "nation": "汉族",
            "birth_date": "1999-02-10",
            "id_card": "110105199902100058",
            "address": "上海市浦东新区世纪大道200号",
            "issuing_authority": "上海市公安局浦东分局",
            "valid_from": "2020-09-01",
            "valid_to": "2030-09-01",
            "phone": "13800000004",
            "emergency_contact_name": "赵勇",
            "emergency_contact_phone": "13900000004",
            "check_in_date": "2025-02-01",
            "check_out_date": "2025-08-01",
            "room_no": "B201",
            "remarks": "短租",
            "status": "在住",
        },
        {
            "name": "周杰",
            "gender": "男",
            "nation": "汉族",
            "birth_date": "1985-07-07",
            "id_card": "110105198507070015",
            "address": "广州市天河区体育西路12号",
            "issuing_authority": "广州市公安局天河分局",
            "valid_from": "2016-06-01",
            "valid_to": "2026-06-01",
            "phone": "13800000005",
            "emergency_contact_name": "周丽",
            "emergency_contact_phone": "13900000005",
            "check_in_date": "2025-03-10",
            "check_out_date": "2025-12-10",
            "room_no": "B102",
            "remarks": "公司团体入住",
            "status": "在住",
        },
    ]

    for t in tenants:
        room_id = room_map.get(t["room_no"])  # may be None if mapping fails
        cur.execute(
            """
            INSERT INTO tenants (
                name, gender, nation, birth_date, id_card, address, issuing_authority,
                valid_from, valid_to, front_img, back_img,
                phone, emergency_contact_name, emergency_contact_phone,
                check_in_date, check_out_date, room_id, remarks, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '', '', ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                t["name"], t["gender"], t.get("nation", "汉族"), t.get("birth_date"), t["id_card"], t.get("address", ""),
                t.get("issuing_authority", ""), t.get("valid_from"), t.get("valid_to"),
                t["phone"], t["emergency_contact_name"], t["emergency_contact_phone"],
                t["check_in_date"], t["check_out_date"], room_id, t.get("remarks", ""), t.get("status", "在住"),
            ),
        )

    # 3) Moves: 示例一次换房记录（李四 从 A102 -> A201）
    try:
        cur.execute("SELECT id FROM tenants WHERE name = ?", ("李四",))
        tenant_row = cur.fetchone()
        if tenant_row:
            tenant_id = tenant_row[0]
            old_room_id = room_map.get("A102")
            new_room_id = room_map.get("A201")
            cur.execute(
                "INSERT INTO tenant_moves (tenant_id, old_room_id, new_room_id, move_date, remarks) VALUES (?, ?, ?, ?, ?)",
                (tenant_id, old_room_id, new_room_id, "2025-02-20", "房型升级，调房一次"),
            )
            # 同步租户当前房号到新房间（示例）
            if new_room_id:
                cur.execute("UPDATE tenants SET room_id = ? WHERE id = ?", (new_room_id, tenant_id))
    except Exception:
        pass

    # 4) Repairs: 示例两条
    repairs = [
        ("A座", "A102", "空调维修", "空调不制冷，已更换压缩机", "2025-02-18", "李四", "已完成", "2025-02-19", 320.0, "张师傅", "保内"),
        ("B座", "B201", "热水器", "热水器漏水，待排查", "2025-03-01", "赵敏", "待处理", None, None, None, "尽快安排"),
    ]
    for r in repairs:
        cur.execute(
            """
            INSERT INTO repair_records (
                building, room_no, repair_type, description, report_date, report_by, status, repair_date, repair_cost, repair_person, remarks
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            r,
        )

    # 5) Contract templates: 一份通用模板
    cur.execute("SELECT COUNT(*) FROM contract_templates")
    tpl_count = cur.fetchone()[0]
    if tpl_count == 0:
        tpl_html = (
            "<h1>租赁合同</h1>"
            "<p>甲方（房东）：{{landlord}}</p>"
            "<p>乙方（租客）：{{name}}（身份证号：{{id_card}}）</p>"
            "<p>租赁房屋：{{room_no}}，租期：{{start_date}} 至 {{end_date}}，租金：{{rent}} 元/月。</p>"
            "<p>双方遵守相关条款。</p>"
        )
        cur.execute(
            "INSERT INTO contract_templates (name, description, content_html, updated_at) VALUES (?, ?, ?, DATETIME('now'))",
            ("标准租赁合同", "适用于普通房间租赁的模板", tpl_html),
        )

    # 6) Contracts: 为在住租户生成合同副本（渲染后入库）
    cur.execute("SELECT id FROM contract_templates ORDER BY id LIMIT 1")
    tpl_row = cur.fetchone()
    tpl_id = tpl_row[0] if tpl_row else 1
    landlord = "某某公寓运营方"
    # 选取在住租户生成合同
    cur.execute(
        "SELECT t.name, t.id_card, r.room_no, t.check_in_date, t.check_out_date FROM tenants t LEFT JOIN rooms r ON r.id = t.room_id WHERE t.status = '在住'"
    )
    for row in cur.fetchall():
        name, id_card, room_no, start_date, end_date = row
        rent = 0.0
        try:
            cur.execute("SELECT price FROM rooms WHERE room_no = ?", (room_no,))
            pr = cur.fetchone()
            if pr:
                rent = float(pr[0])
        except Exception:
            rent = 0.0
        rendered_html = (
            f"<h1>租赁合同</h1>"
            f"<p>甲方（房东）：{landlord}</p>"
            f"<p>乙方（租客）：{name}（身份证号：{id_card}）</p>"
            f"<p>租赁房屋：{room_no}，租期：{start_date} 至 {end_date}，租金：{rent} 元/月。</p>"
        )
        cur.execute(
            """
            INSERT INTO contracts (template_id, tenant_name, id_card, room_no, start_date, end_date, rent, rendered_html)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (tpl_id, name, id_card, room_no, start_date, end_date, rent, rendered_html),
        )

    # 7) 根据租户入住情况更新房间状态
    cur.execute(
        """
        UPDATE rooms
        SET status = CASE
            WHEN EXISTS (
                SELECT 1 FROM tenants t
                WHERE t.room_id = rooms.id
                  AND t.status = '在住'
                  AND DATE('now') BETWEEN t.check_in_date AND t.check_out_date
            ) THEN '已入住'
            ELSE '空闲'
        END
        """
    )

    conn.commit()
    conn.close()
    print("✅ 已插入演示数据：房间、租户、调房、维修、合同模板与合同")


def create_default_admin(username: str = "admin", password: str = "123456", full_name: str = "管理员"):
    """Create default admin if not exists."""
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT id FROM admins WHERE username = ?", (username,))
    if cur.fetchone():
        conn.close()
        return False, f"管理员 {username} 已存在"
    cur.execute(
        "INSERT INTO admins (username, password_hash, full_name) VALUES (?, ?, ?)",
        (username, sha256(password), full_name),
    )
    conn.commit()
    conn.close()
    return True, f"管理员 {username} 已创建"


def summarize(compact: bool = False):
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    tables = [r[0] for r in cur.fetchall()]
    if compact:
        lines = [f"{t}:{cur.execute('SELECT COUNT(*) FROM ' + t).fetchone()[0]}" for t in tables]
        print("DB:" + DB_NAME)
        print(" | ".join(lines))
        conn.close()
        return
    summary = {"db_path": DB_NAME, "tables": {}}
    for t in tables:
        try:
            cur.execute("SELECT COUNT(*) FROM " + t)
            count = cur.fetchone()[0]
            cur.execute("PRAGMA table_info(" + t + ")")
            cols = [{"name": r[1], "type": r[2]} for r in cur.fetchall()]
            summary["tables"][t] = {"count": count, "columns": cols}
        except Exception as e:
            summary["tables"][t] = {"error": str(e)}
    conn.close()
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def ensure_sql_dir_and_migrate_db():
    """Ensure sql directory exists and migrate old DB if found at root.

    Old path: Backend System/hotel.db
    New path: Backend System/sql/hotel.db
    """
    base_dir = os.path.dirname(os.path.dirname(__file__))
    old_path = os.path.join(base_dir, "hotel.db")
    new_path = DB_NAME
    os.makedirs(os.path.dirname(new_path), exist_ok=True)
    if os.path.exists(old_path) and not os.path.exists(new_path):
        try:
            shutil.move(old_path, new_path)
            print(f"已迁移数据库到: {new_path}")
        except Exception as e:
            print(f"迁移数据库失败: {e}")


def main():
    parser = argparse.ArgumentParser(description="初始化/检查酒店管理数据库")
    parser.add_argument("--init", action="store_true", help="创建缺失的表和必要列")
    parser.add_argument("--create-default-admin", action="store_true", help="若无管理员则创建默认 admin/123456")
    parser.add_argument("--summarize", action="store_true", help="输出当前数据库的表与行数概览")
    parser.add_argument("--compact", action="store_true", help="以紧凑格式输出表名与行数")
    parser.add_argument("--seed-demo-data", action="store_true", help="插入有逻辑的演示数据（若已存在数据则跳过）")
    args = parser.parse_args()

    # Ensure new sql directory and migrate old db if needed
    ensure_sql_dir_and_migrate_db()

    if args.init:
        ensure_tables()
        print("✅ 表结构已确保存在并更新。")

    if args.create_default_admin:
        created, msg = create_default_admin()
        print(("✅ " if created else "ℹ️ ") + msg)

    if args.seed_demo_data:
        seeded = seed_demo_data()

    if args.summarize or (not args.init and not args.create_default_admin):
        summarize(compact=args.compact)


if __name__ == "__main__":
    main()