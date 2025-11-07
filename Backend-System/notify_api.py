from flask import Blueprint, request, jsonify

from auth_api import token_required
import expiry_notification_config as notify_config
from email.mime.text import MIMEText
from email.header import Header
import smtplib


notify_bp = Blueprint('notify', __name__, url_prefix='/api')


@notify_bp.route('/notification-config', methods=['GET'])
@token_required
def get_notification_config(current_user):
    """获取租期到期通知配置"""
    config = notify_config.get_config()
    return jsonify(config)


@notify_bp.route('/notification-config', methods=['PUT'])
@token_required
def update_notification_config(current_user):
    """更新租期到期通知配置"""
    data = request.json
    if not data:
        return jsonify({'error': '请提供配置数据'}), 400

    valid, message = notify_config.validate_config(data)
    if not valid:
        return jsonify({'error': message}), 400

    success, result = notify_config.update_config(data)
    if success:
        return jsonify(result)
    else:
        return jsonify({'error': f'更新配置失败: {result}'}), 500


@notify_bp.route('/test-email', methods=['POST'])
@token_required
def api_test_email(current_user):
    data = request.json or {}

    cfg = notify_config.get_config() or {}
    smtp_config = data.get('smtp_config') or cfg.get('smtp_config') or {}
    recipient = data.get('recipient') or smtp_config.get('username')
    sender = data.get('sender') or smtp_config.get('username') or 'system@example.com'
    subject = data.get('subject') or '测试邮件'
    content = data.get('content') or '这是一封测试邮件，用于验证SMTP配置是否正常。'

    required_keys = ['server', 'port', 'username', 'password', 'use_tls']
    if not smtp_config or any(k not in smtp_config for k in required_keys):
        return jsonify({'error': '请提供完整的 smtp_config: server, port, username, password, use_tls'}), 400
    if not recipient:
        return jsonify({'error': '缺少收件人 recipient'}), 400

    try:
        msg = MIMEText(content, 'plain', 'utf-8')
        msg['From'] = sender or smtp_config['username']
        msg['To'] = recipient
        msg['Subject'] = Header(subject, 'utf-8')

        port = int(smtp_config.get('port', 587))
        use_tls = bool(smtp_config.get('use_tls', True))
        use_ssl = bool(data.get('use_ssl')) or port == 465

        if use_ssl:
            server = smtplib.SMTP_SSL(smtp_config['server'], port, timeout=10)
        else:
            server = smtplib.SMTP(smtp_config['server'], port, timeout=10)
            server.ehlo()
            if use_tls:
                server.starttls()
                server.ehlo()

        server.login(smtp_config['username'], smtp_config['password'])
        envelope_from = smtp_config['username']
        server.sendmail(envelope_from, [recipient], msg.as_string())
        server.quit()
        return jsonify({'success': True, 'message': '测试邮件发送成功'})
    except Exception as e:
        return jsonify({'success': False, 'error': f'测试邮件发送失败: {str(e)}'}), 502


@notify_bp.route('/test-sms', methods=['POST'])
@token_required
def api_test_sms(current_user):
    """测试短信发送（模拟/校验参数）"""
    data = request.json or {}
    sms_config = data.get('sms_config') or {}

    required_keys = [
        'secret_id', 'secret_key', 'app_id', 'sign_name',
        'tenant_template_id', 'landlord_template_id'
    ]
    missing = [k for k in required_keys if k not in sms_config]
    if missing:
        return jsonify({'error': f"缺少必要参数: {', '.join(missing)}"}), 400

    template_id = data.get('template_id', sms_config.get('tenant_template_id'))
    template_params = data.get('template_params', {
        'name': '张三',
        'room_no': '1-101',
        'check_out_date': '2025-01-01',
    })

    return jsonify({
        'success': True,
        'message': '短信发送配置校验完成（模拟）。若要真实发送，请集成短信平台SDK。',
        'payload': {
            'template_id': template_id,
            'template_params': template_params,
            'sign_name': sms_config.get('sign_name'),
            'app_id': sms_config.get('app_id'),
        },
    })