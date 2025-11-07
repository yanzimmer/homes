import sqlite3
from flask import Blueprint, request, jsonify

from auth_api import token_required
from common import connect


moves_bp = Blueprint('moves', __name__, url_prefix='/api')


@moves_bp.route('/moves', methods=['GET'])
@token_required
def api_list_moves(current_user):
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT tm.id, t.name, rf.room_no, rt.room_no, tm.move_date
        FROM tenant_moves tm
        JOIN tenants t ON tm.tenant_id=t.id
        JOIN rooms rf ON tm.old_room_id=rf.id
        JOIN rooms rt ON tm.new_room_id=rt.id
        ORDER BY tm.move_date DESC
        """
    )
    rows = cursor.fetchall()
    conn.close()

    moves = []
    for row in rows:
        moves.append({
            'id': row[0],
            'tenant_name': row[1],
            'from_room': row[2],
            'to_room': row[3],
            'move_date': row[4],
        })

    return jsonify({'moves': moves})


@moves_bp.route('/moves/tenant', methods=['POST'])
@token_required
def api_move_tenant(current_user):
    data = request.json
    if not data:
        return jsonify({'error': '缺少请求数据'}), 400

    move_type = data.get('move_type', 1)
    to_room = data.get('to_room')

    if not to_room:
        return jsonify({'error': '缺少目标房间参数'}), 400

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM rooms WHERE room_no=?", (to_room,))
    room = cursor.fetchone()
    if not room:
        conn.close()
        return jsonify({'error': f'房间 {to_room} 不存在'}), 404

    to_room_id = room[0]

    moved_tenants = []
    errors = []

    if move_type == 1:
        tenant_id = data.get('tenant_id')
        if not tenant_id:
            conn.close()
            return jsonify({'error': '选择租户搬迁模式下缺少租户ID参数'}), 400

        cursor.execute(
            """
            SELECT t.id, t.name, r.id, r.room_no
            FROM tenants t
            JOIN rooms r ON t.room_id=r.id
            WHERE t.id=? AND t.status='在住'
            """,
            (tenant_id,),
        )

        tenant = cursor.fetchone()
        if not tenant:
            conn.close()
            return jsonify({'error': f'租户ID {tenant_id} 不存在或不是在住状态'}), 404

        tenant_id, tenant_name, from_room_id, from_room_no = tenant

        try:
            cursor.execute("UPDATE tenants SET room_id=? WHERE id=?", (to_room_id, tenant_id))

            cursor.execute(
                """
                INSERT INTO tenant_moves (tenant_id, old_room_id, new_room_id, move_date)
                VALUES (?, ?, ?, DATE('now'))
                """,
                (tenant_id, from_room_id, to_room_id),
            )

            moved_tenants.append(
                {
                    'tenant_id': tenant_id,
                    'tenant_name': tenant_name,
                    'from_room': from_room_no,
                    'to_room': to_room,
                }
            )
        except sqlite3.Error as e:
            errors.append(f'处理租户 {tenant_name} 时出错: {str(e)}')

    elif move_type == 2:
        from_room = data.get('from_room')
        if not from_room:
            conn.close()
            return jsonify({'error': '整间搬迁模式下缺少源房间参数'}), 400

        cursor.execute("SELECT id FROM rooms WHERE room_no=?", (from_room,))
        from_room_result = cursor.fetchone()
        if not from_room_result:
            conn.close()
            return jsonify({'error': f'房间 {from_room} 不存在'}), 404

        from_room_id = from_room_result[0]

        cursor.execute(
            "SELECT id, name FROM tenants WHERE room_id=? AND status='在住'",
            (from_room_id,),
        )
        tenants = cursor.fetchall()
        if not tenants:
            conn.close()
            return jsonify({'error': f'房间 {from_room} 没有在住租户'}), 400

        for tenant_id, tenant_name in tenants:
            try:
                cursor.execute(
                    "UPDATE tenants SET room_id=? WHERE id=?",
                    (to_room_id, tenant_id),
                )

                cursor.execute(
                    """
                    INSERT INTO tenant_moves (tenant_id, old_room_id, new_room_id, move_date)
                    VALUES (?, ?, ?, DATE('now'))
                    """,
                    (tenant_id, from_room_id, to_room_id),
                )

                moved_tenants.append(
                    {
                        'tenant_id': tenant_id,
                        'tenant_name': tenant_name,
                        'from_room': from_room,
                        'to_room': to_room,
                    }
                )
            except sqlite3.Error as e:
                errors.append(f'处理租户 {tenant_name} 时出错: {str(e)}')

    else:
        conn.close()
        return jsonify({'error': '不支持的搬迁方式'}), 400

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
        """
    )

    conn.commit()
    conn.close()

    return jsonify({'message': '已完成搬迁操作', 'moved_tenants': moved_tenants, 'errors': errors})


@moves_bp.route('/moves/room', methods=['POST'])
@token_required
def api_move_room(current_user):
    data = request.json
    if not data or not all(k in data for k in ('from_room_no', 'to_room_no')):
        return jsonify({'error': '缺少必要参数'}), 400

    from_room_no = data['from_room_no']
    to_room_no = data['to_room_no']

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM rooms WHERE room_no=?", (from_room_no,))
    from_room = cursor.fetchone()
    if not from_room:
        conn.close()
        return jsonify({'error': f'房间 {from_room_no} 不存在'}), 404

    from_room_id = from_room[0]

    cursor.execute("SELECT id FROM rooms WHERE room_no=?", (to_room_no,))
    to_room = cursor.fetchone()
    if not to_room:
        conn.close()
        return jsonify({'error': f'房间 {to_room_no} 不存在'}), 404

    to_room_id = to_room[0]

    cursor.execute(
        "SELECT id, name FROM tenants WHERE room_id=? AND status='在住'",
        (from_room_id,),
    )
    tenants = cursor.fetchall()
    if not tenants:
        conn.close()
        return jsonify({'error': f'房间 {from_room_no} 没有在住租户'}), 400

    moved_tenants = []

    for tenant_id, tenant_name in tenants:
        cursor.execute("UPDATE tenants SET room_id=? WHERE id=?", (to_room_id, tenant_id))

        cursor.execute(
            """
            INSERT INTO tenant_moves (tenant_id, from_room_id, to_room_id, move_date)
            VALUES (?, ?, ?, DATE('now'))
            """,
            (tenant_id, from_room_id, to_room_id),
        )

        moved_tenants.append({'tenant_id': tenant_id, 'tenant_name': tenant_name})

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
        """
    )

    conn.commit()
    conn.close()

    return jsonify({'message': f'已将房间 {from_room_no} 的所有租户搬迁至 {to_room_no}', 'moved_tenants': moved_tenants})


@moves_bp.route('/moves/<int:move_id>', methods=['DELETE'])
@token_required
def api_delete_move(current_user, move_id):
    """删除一条搬迁记录。

    仅删除 tenant_moves 表中的历史记录，不影响当前房间与租户状态。
    """
    conn = connect()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM tenant_moves WHERE id = ?", (move_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return jsonify({'error': f'搬迁记录ID {move_id} 不存在'}), 404

        cursor.execute("DELETE FROM tenant_moves WHERE id = ?", (move_id,))
        if cursor.rowcount == 0:
            conn.close()
            return jsonify({'error': f'搬迁记录ID {move_id} 不存在'}), 404
        conn.commit()
        conn.close()
        return jsonify({'message': f'搬迁记录 {move_id} 已删除'})
    except sqlite3.OperationalError:
        # 数据库锁等并发问题，提示稍后重试
        conn.close()
        return jsonify({'error': '数据库繁忙，请稍后重试'}), 503
    except sqlite3.Error as e:
        conn.close()
        return jsonify({'error': str(e)}), 500