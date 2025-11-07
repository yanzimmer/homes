import sqlite3
from datetime import datetime

from flask import Blueprint, request, jsonify

from auth_api import token_required
from common import connect


rooms_bp = Blueprint('rooms', __name__, url_prefix='/api')


@rooms_bp.route('/rooms', methods=['GET'])
@token_required
def api_list_rooms(current_user):
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        """
    SELECT
        r.id,
        r.room_no,
        r.building,
        r.floor,
        r.room_type,
        r.price,
        CASE
            WHEN EXISTS (
                SELECT 1 FROM tenants t
                WHERE t.room_id = r.id
                  AND t.status = '在住'
                  AND DATE('now') BETWEEN t.check_in_date AND t.check_out_date
            ) THEN '已入住'
            ELSE '空闲'
        END AS current_status,
        (SELECT COUNT(*) FROM tenants t
         WHERE t.room_id = r.id
           AND t.status = '在住'
           AND DATE('now') BETWEEN t.check_in_date AND t.check_out_date) AS tenant_count
    FROM rooms r
    ORDER BY r.room_no
    """
    )
    rows = cursor.fetchall()
    conn.close()

    rooms = []
    for row in rows:
        rooms.append({
            'id': row[0],
            'room_no': row[1],
            'building': row[2],
            'floor': row[3],
            'room_type': row[4],
            'price': row[5],
            'status': row[6],
            'tenant_count': row[7],
        })

    return jsonify({'rooms': rooms})


@rooms_bp.route('/rooms/<room_no>/tenants', methods=['GET'])
@token_required
def api_get_room_tenants(current_user, room_no):
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM rooms WHERE room_no = ?", (room_no,))
    room = cursor.fetchone()
    if not room:
        conn.close()
        return jsonify({'error': f'房间 {room_no} 不存在'}), 404

    room_id = room[0]
    cursor.execute(
        """
        SELECT id, name, id_card, phone, gender, check_in_date, check_out_date, status
        FROM tenants 
        WHERE room_id = ? AND status = '在住'
        ORDER BY name
        """,
        (room_id,),
    )
    tenants_data = cursor.fetchall()
    conn.close()

    tenants = []
    for tenant in tenants_data:
        tenants.append({
            'id': tenant[0],
            'name': tenant[1],
            'id_card': tenant[2],
            'phone': tenant[3],
            'gender': tenant[4],
            'check_in_date': tenant[5],
            'check_out_date': tenant[6],
            'status': tenant[7],
        })

    return jsonify({'tenants': tenants})


@rooms_bp.route('/rooms/<room_no>/checkout', methods=['POST'])
@token_required
def api_checkout_room(current_user, room_no):
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM rooms WHERE room_no = ?", (room_no,))
    room = cursor.fetchone()
    if not room:
        conn.close()
        return jsonify({'error': f'房间 {room_no} 不存在'}), 404

    room_id = room[0]
    cursor.execute("SELECT id, name FROM tenants WHERE room_id = ? AND status = '在住'", (room_id,))
    tenants = cursor.fetchall()
    if not tenants:
        conn.close()
        return jsonify({'error': f'房间 {room_no} 没有在住租户'}), 400

    today = datetime.now().strftime('%Y-%m-%d')
    tenant_names = []
    for tenant in tenants:
        tenant_id, tenant_name = tenant
        cursor.execute("UPDATE tenants SET status = '已退租' WHERE id = ?", (tenant_id,))
        tenant_names.append(tenant_name)

    cursor.execute(
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
    WHERE id = ?
    """,
        (room_id,),
    )
    conn.commit()
    conn.close()

    return jsonify({'message': f'房间 {room_no} 已成功退租', 'tenants': tenant_names})


@rooms_bp.route('/rooms', methods=['POST'])
@token_required
def api_add_room(current_user):
    data = request.json
    if not data or not all(k in data for k in ('room_no', 'floor', 'room_type', 'price')):
        return jsonify({'error': '缺少必要参数'}), 400

    room_no = data['room_no']
    floor = data['floor']
    room_type = data['room_type']
    price = data['price']
    building = data.get('building', '')

    conn = connect()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO rooms (room_no, floor, room_type, price, building)
            VALUES (?, ?, ?, ?, ?)
            """,
            (room_no, floor, room_type, price, building),
        )
        room_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return jsonify({'message': f'房间 {room_no} 已添加', 'id': room_id, 'room_no': room_no})
    except sqlite3.Error as e:
        conn.close()
        return jsonify({'error': str(e)}), 500


@rooms_bp.route('/rooms/<room_no>', methods=['PUT'])
@token_required
def api_update_room(current_user, room_no):
    data = request.json
    if not data:
        return jsonify({'error': '缺少更新数据'}), 400

    allowed_fields = ['floor', 'room_type', 'price', 'building']
    update_data = {k: v for k, v in data.items() if k in allowed_fields}

    if not update_data:
        return jsonify({'error': '没有有效的更新字段'}), 400

    conn = connect()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT id FROM rooms WHERE room_no = ?", (room_no,))
        room = cursor.fetchone()
        if not room:
            conn.close()
            return jsonify({'error': f'房间 {room_no} 不存在'}), 404

        for key, value in update_data.items():
            cursor.execute(f"UPDATE rooms SET {key} = ? WHERE room_no = ?", (value, room_no))

        conn.commit()
        conn.close()
        return jsonify({'message': f'房间 {room_no} 信息已更新'})
    except sqlite3.Error as e:
        conn.close()
        return jsonify({'error': str(e)}), 500


@rooms_bp.route('/rooms/<int:room_id>', methods=['DELETE'])
@token_required
def api_delete_room(current_user, room_id):
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("SELECT room_no FROM rooms WHERE id=?", (room_id,))
    room = cursor.fetchone()
    if not room:
        conn.close()
        return jsonify({'error': f'房间ID {room_id} 不存在'}), 404

    room_no = room[0]
    # 仅当房间不存在在住租户时允许删除
    cursor.execute(
        """
        SELECT COUNT(*) FROM tenants
        WHERE room_id = ?
          AND status = '在住'
          AND DATE('now') BETWEEN check_in_date AND check_out_date
        """,
        (room_id,),
    )
    active_count = cursor.fetchone()[0]
    if active_count > 0:
        conn.close()
        return jsonify({'error': f'房间 {room_no} 有 {active_count} 位在住租户，请先办理退租后再删除'}), 400

    # 额外检查其他关联数据：即使没有在住租户，仍可能有退租租户、搬迁记录或维修记录导致外键约束失败
    cursor.execute("SELECT COUNT(*) FROM tenants WHERE room_id = ?", (room_id,))
    total_tenants = cursor.fetchone()[0]
    cursor.execute(
        "SELECT COUNT(*) FROM tenant_moves WHERE old_room_id = ? OR new_room_id = ?",
        (room_id, room_id),
    )
    moves_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM repair_records WHERE room_no = ?", (room_no,))
    repairs_count = cursor.fetchone()[0]

    if total_tenants > 0 or moves_count > 0 or repairs_count > 0:
        details = []
        if total_tenants > 0:
            details.append(f"租户档案 {total_tenants} 条（含已退租）")
        if moves_count > 0:
            details.append(f"搬迁记录 {moves_count} 条")
        if repairs_count > 0:
            details.append(f"维修记录 {repairs_count} 条")
        conn.close()
        return jsonify({'error': f'房间 {room_no} 存在关联数据，无法删除：' + '；'.join(details) + '。请先清理关联数据后再尝试删除。'}), 400

    try:
        cursor.execute("DELETE FROM rooms WHERE id = ?", (room_id,))
        if cursor.rowcount == 0:
            conn.close()
            return jsonify({'error': f'房间ID {room_id} 不存在'}), 404
        conn.commit()
        conn.close()
        return jsonify({'message': f'房间 {room_no} 已删除'})
    except sqlite3.Error as e:
        conn.close()
        return jsonify({'error': str(e)}), 500