import hashlib
from datetime import datetime, timedelta
from functools import wraps

import jwt
from flask import Blueprint, request, jsonify, make_response

from common import connect, SECRET_KEY, JWT_EXPIRATION_DELTA
import forgot_password as fp


auth_bp = Blueprint('auth', __name__, url_prefix='/api')


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]

        if not token:
            return jsonify({'error': '缺少认证令牌'}), 401

        try:
            data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])

            conn = connect()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM admins WHERE username = ?", (data['username'],))
            user_data = cursor.fetchone()
            conn.close()

            if not user_data:
                return jsonify({'error': '无效的认证令牌'}), 401

            current_user = {
                'id': user_data[0],
                'username': user_data[1],
                'full_name': user_data[3]
            }
        except jwt.ExpiredSignatureError:
            return jsonify({'error': '认证令牌已过期，请重新登录'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': '无效的认证令牌'}), 401

        # 成功认证后：活动续期——签发一个新的令牌并通过响应头返回
        response = f(current_user=current_user, *args, **kwargs)
        try:
            new_expiry = datetime.utcnow() + timedelta(seconds=JWT_EXPIRATION_DELTA)
            new_token = jwt.encode(
                {
                    'username': current_user['username'],
                    'full_name': current_user['full_name'],
                    'exp': new_expiry,
                },
                SECRET_KEY,
                algorithm="HS256",
            )
            resp = make_response(response)
            resp.headers['X-Refreshed-Token'] = new_token
            resp.headers['X-Token-Expires'] = new_expiry.isoformat()
            return resp
        except Exception:
            # 如果续期失败，不影响原始响应
            return response

    return decorated


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.json
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'error': '请提供用户名和密码'}), 400

    username = data.get('username')
    password = data.get('password')
    password_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()

    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, username, full_name FROM admins WHERE username = ? AND password_hash = ?",
        (username, password_hash),
    )
    user = cursor.fetchone()
    conn.close()

    if not user:
        return jsonify({'error': '用户名或密码错误'}), 401

    token_expiry = datetime.utcnow() + timedelta(seconds=JWT_EXPIRATION_DELTA)
    token = jwt.encode(
        {'username': user[1], 'full_name': user[2], 'exp': token_expiry},
        SECRET_KEY,
        algorithm="HS256",
    )

    return jsonify({'token': token, 'username': user[1], 'full_name': user[2], 'expires': token_expiry.isoformat()})


@auth_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    data = request.json or {}
    username = data.get('username')
    answer = data.get('answer')
    new_password = data.get('new_password')

    if not username or not answer or not new_password:
        return jsonify({'error': '请提供用户名、问题答案以及新密码'}), 400

    ok, msg = fp.verify_and_reset_password(username, answer, new_password)
    if ok:
        return jsonify({'message': msg})
    else:
        return jsonify({'error': msg}), 400


@auth_bp.route('/verify-token', methods=['GET'])
@token_required
def verify_token(current_user):
    return jsonify({'message': '令牌有效'})


@auth_bp.route('/change-password', methods=['POST'])
@token_required
def change_password(current_user):
    data = request.json
    if not data or not data.get('old_password') or not data.get('new_password'):
        return jsonify({'error': '请提供旧密码和新密码'}), 400

    old_password = data.get('old_password')
    new_password = data.get('new_password')
    old_password_hash = hashlib.sha256(old_password.encode("utf-8")).hexdigest()

    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM admins WHERE username = ? AND password_hash = ?",
        (current_user['username'], old_password_hash),
    )
    user = cursor.fetchone()
    if not user:
        conn.close()
        return jsonify({'error': '旧密码不正确'}), 401

    new_password_hash = hashlib.sha256(new_password.encode("utf-8")).hexdigest()
    cursor.execute(
        "UPDATE admins SET password_hash = ? WHERE username = ?",
        (new_password_hash, current_user['username']),
    )
    conn.commit()
    conn.close()

    return jsonify({'message': '密码修改成功'})