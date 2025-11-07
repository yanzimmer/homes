import logging
from flask import Flask
from flask_cors import CORS

from common import SECRET_KEY, JWT_EXPIRATION_DELTA
from contract_templates_api import templates_bp, ensure_contract_templates_schema
from contracts_api import contracts_bp, ensure_contracts_schema
from auth_api import auth_bp
from ocr_api import ocr_bp
from notify_api import notify_bp
from rooms_api import rooms_bp
from tenants_api import tenants_bp
from moves_api import moves_bp
from repair_records_api import repair_bp
import forgot_password as fp


app = Flask(__name__)
# 允许跨域并显式声明方法与请求头，确保带 Authorization 的预检通过
CORS(
    app,
    resources={
        r"/api/*": {
            "origins": "*",
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"],
            # 暴露刷新令牌相关响应头，便于前端读取
            "expose_headers": ["Content-Type", "X-Refreshed-Token", "X-Token-Expires"],
        }
    },
    supports_credentials=True,
)

# 应用基础配置（集中在 common.py）
app.config['SECRET_KEY'] = SECRET_KEY
app.config['JWT_EXPIRATION_DELTA'] = JWT_EXPIRATION_DELTA

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
app.logger.setLevel(logging.INFO)


# 初始化找回密码模块（如存在则进行初始化）
try:
    fp.ensure_schema()
    # 设置一个默认的恢复信息，避免首次使用时没有配置
    fp.set_recovery_info('admin', security_answer='15286304124')
except Exception as e:
    app.logger.warning(f"初始化找回密码模块失败: {e}")


# 注册各功能蓝图
try:
    ensure_contract_templates_schema()
    app.register_blueprint(templates_bp)
except Exception as e:
    app.logger.warning(f"注册合同模板模块失败: {e}")

# 注册合同档案蓝图
try:
    ensure_contracts_schema()
    app.register_blueprint(contracts_bp)
except Exception as e:
    app.logger.warning(f"注册合同档案模块失败: {e}")

app.register_blueprint(auth_bp)
app.register_blueprint(ocr_bp)
app.register_blueprint(notify_bp)
app.register_blueprint(rooms_bp)
app.register_blueprint(tenants_bp)
app.register_blueprint(moves_bp)
app.register_blueprint(repair_bp)


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)