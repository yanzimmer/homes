#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import logging
from datetime import datetime

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('expiry_notification')

# 配置文件路径（迁移至 config 目录）
CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'config', 'notification_config.json')

# 默认配置已迁移至 init-scripts/init_notification_config.py

def ensure_config_file():
    """检查配置文件是否存在（不再自动写入默认配置）。"""
    if not os.path.exists(CONFIG_FILE):
        logger.error(f"配置文件不存在: {CONFIG_FILE}，请先运行初始化脚本生成默认配置")
        return False
    return True

def get_config():
    """获取当前配置；若不存在或读取失败，返回空字典。"""
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return config
    except Exception as e:
        logger.error(f"读取配置文件失败: {str(e)}")
        return {}

def update_config(new_config):
    """更新配置"""
    ensure_config_file()
    try:
        # 读取当前配置
        current_config = get_config()
        
        # 更新配置
        for key, value in new_config.items():
            if key in current_config:
                if isinstance(value, dict) and isinstance(current_config[key], dict):
                    # 如果是嵌套字典，递归更新
                    for sub_key, sub_value in value.items():
                        current_config[key][sub_key] = sub_value
                else:
                    current_config[key] = value
        
        # 更新最后修改时间
        current_config["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 写入文件
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(current_config, f, ensure_ascii=False, indent=4)
        
        logger.info("配置已更新")
        return True, current_config
    except Exception as e:
        logger.error(f"更新配置失败: {str(e)}")
        return False, str(e)

def validate_config(config):
    """验证配置是否有效（支持部分字段更新，缺失字段从现有文件补全）。"""
    # 兼容旧字段名
    if "notification_methods" in config:
        config.setdefault("tenant_notification_methods", config["notification_methods"])
        config.setdefault("landlord_notification_methods", config["notification_methods"])

    current = get_config()

    # 构建合并视图（不写盘，仅用于校验）
    merged = {}
    if isinstance(current, dict):
        merged.update(current)
    for key, value in config.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            d = merged.get(key, {}).copy()
            d.update(value)
            merged[key] = d
        else:
            merged[key] = value

    required_fields = [
        "enabled",
        "advance_days",
        "reminder_count",
        "tenant_notification_methods",
        "landlord_notification_methods",
    ]
    missing = [f for f in required_fields if f not in merged]
    if missing:
        return False, f"缺少必填字段: {', '.join(missing)}"

    # 类型校验
    if not isinstance(merged["enabled"], bool):
        return False, "enabled 字段必须是布尔类型"
    if not isinstance(merged["advance_days"], int) or merged["advance_days"] < 0:
        return False, "advance_days 字段必须是非负整数"
    if not isinstance(merged["reminder_count"], int) or merged["reminder_count"] < 0:
        return False, "reminder_count 字段必须是非负整数"
    if not isinstance(merged["tenant_notification_methods"], list):
        return False, "tenant_notification_methods 字段必须是列表"
    if not isinstance(merged["landlord_notification_methods"], list):
        return False, "landlord_notification_methods 字段必须是列表"

    # SMTP 配置
    if "smtp_config" not in merged or not isinstance(merged["smtp_config"], dict):
        return False, "缺少或不合法的 smtp_config"
    smtp = merged["smtp_config"]
    for field in ["server", "port", "username", "password", "use_tls"]:
        if field not in smtp:
            return False, f"smtp_config.{field} 字段缺失"
    if not isinstance(smtp["port"], int) or smtp["port"] <= 0:
        return False, "smtp_config.port 必须是正整数"
    if not isinstance(smtp["use_tls"], bool):
        return False, "smtp_config.use_tls 必须是布尔类型"

    # 短信配置（可选，若提供需字段完整）
    if "sms_config" in merged:
        sms_config = merged["sms_config"]
        if not isinstance(sms_config, dict):
            return False, "sms_config 字段必须是字典类型"
        for field in [
            "secret_id",
            "secret_key",
            "app_id",
            "sign_name",
            "tenant_template_id",
            "landlord_template_id",
        ]:
            if field not in sms_config:
                return False, f"sms_config.{field} 字段缺失"

    # 邮件配置
    for cfg_key in ["tenant_email_config", "landlord_email_config"]:
        if cfg_key not in merged or not isinstance(merged[cfg_key], dict):
            return False, f"缺少或不合法的 {cfg_key}"
        email_cfg = merged[cfg_key]
        for f in ["sender", "subject", "template"]:
            if f not in email_cfg:
                return False, f"{cfg_key}.{f} 字段缺失"
        if "recipients" in email_cfg and not isinstance(email_cfg["recipients"], list):
            return False, f"{cfg_key}.recipients 必须是列表类型"

    # 房东信息（可选，若提供需字段完整）
    if "landlords" in merged:
        if not isinstance(merged["landlords"], list):
            return False, "landlords 字段必须是列表类型"
        for i, landlord in enumerate(merged["landlords"]):
            if not isinstance(landlord, dict):
                return False, f"landlords[{i}] 必须是字典类型"
            for field in ["name", "phone", "email"]:
                if field not in landlord:
                    return False, f"landlords[{i}].{field} 字段缺失"

    return True, "配置有效"

# 初始化配置文件
ensure_config_file()

if __name__ == "__main__":
    # 测试配置功能
    print("当前配置:", get_config())