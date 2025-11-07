# 初始化脚本使用说明

本目录用于后端数据库的初始化与示例数据脚本。核心脚本为 `init_hotel_db.py`，它负责统一创建缺失表、确保管理员找回字段、可选创建默认管理员账号，并输出数据库概览。

## 环境与数据库/配置路径
- 依赖：Python 3.x（无需额外第三方库）
- 统一数据库路径：`Backend System/sql/hotel.db`（脚本通过 `common.connect()` 使用该路径）
- 通知配置路径：`Backend System/config/notification_config.json`
- 运行目录建议：在 `Backend System` 目录下运行，或在仓库根目录下通过带路径的方式运行（见下例）。

## 快速开始（常用命令）
- 在仓库根目录运行：
  - 概览（紧凑）：`python "Backend System\init-scripts\init_hotel_db.py" --summarize --compact`
  - 初始化表结构：`python "Backend System\init-scripts\init_hotel_db.py" --init`
  - 创建默认管理员：`python "Backend System\init-scripts\init_hotel_db.py" --create-default-admin`
  - 组合执行：`python "Backend System\init-scripts\init_hotel_db.py" --init --create-default-admin --summarize`

- 在 `Backend System` 目录运行：
  - 概览（紧凑）：`python "init-scripts\init_hotel_db.py" --summarize --compact`
  - 初始化表结构：`python "init-scripts\init_hotel_db.py" --init`
  - 创建默认管理员：`python "init-scripts\init_hotel_db.py" --create-default-admin`
  - 组合执行：`python "init-scripts\init_hotel_db.py" --init --create-default-admin --summarize`

## 参数说明
- `--init`
  - 创建缺失的核心表并补齐必要列：`rooms`、`tenants`、`tenant_moves`、`admins`（追加找回密码字段）、`repair_records`。
  - 幂等：仅在缺失时创建/追加，不会清空或覆盖已有数据。

- `--create-default-admin`
  - 若不存在则创建默认管理员：`admin/123456`，`full_name` 为“管理员”。
  - 已存在同名账号时跳过，不覆盖现有密码。

- `--summarize`
  - 输出详细 JSON 概览（数据库路径、各表字段定义与行数）。

- `--compact`
  - 与 `--summarize` 搭配，输出紧凑计数摘要（适合在终端快速查看）。

## 典型使用场景
- 新环境/报错提示缺表：先执行 `--init`，如需开发账号再执行 `--create-default-admin`，最后用 `--summarize --compact` 检查状态。
- 已有数据但需要确认状态：仅执行 `--summarize --compact`。
- 本地开发需要快速登录：执行 `--create-default-admin`。

## 与其他脚本的关系
- `hotel_setup.py`：示例数据脚本，生成房间与租户样例数据（不属于 `init_hotel_db.py` 的默认行为）。
- `repair_records_setup.py`：示例报修记录数据脚本，依赖房间表已存在并有房间数据。
- 合同模板表 `contract_templates`：由后端服务启动时在 `contract_templates_api.ensure_contract_templates_schema()` 中创建；如需在本脚本中一并创建，可扩展支持。

## 注意事项与安全性
- 所有操作指向统一路径 `Backend System/sql/hotel.db`，避免出现多个重复数据库文件。
- 初始化与创建管理员均为幂等，不清空、不覆盖、不自动生成样例数据。
- 如果你在根目录运行并遇到 `ModuleNotFoundError: common`，请切换到 `Backend System` 目录运行或使用带路径的命令（如上示例）。

## 示例输出（紧凑）
```
DB:C:\Users\<你的用户>\Desktop\homes\Backend System\sql\hotel.db
rooms:21 | tenants:36 | tenant_moves:7 | admins:1 | repair_records:5 | contracts:0 | contract_templates:1
```

## 进一步扩展
- 如需一键“清空并重置”或“按配置生成样例数据”（房间/租户），可在本脚本中新增参数（例如 `--reset`、`--seed`），并合并 `hotel_setup.py` 的逻辑。

## init_notification_config.py 使用方法
- 作用：初始化或重置通知配置文件 `Backend-System/config/notification_config.json`；若根目录存在旧版 `notification_config.json` 且新路径不存在，会自动迁移到新路径；支持仅打印配置。

- 可用参数：
  - `--force`：强制覆盖为默认配置（即使文件已存在）。
  - `--print`：仅打印当前配置和文件路径，不进行写入或迁移。

- 在仓库根目录运行：
  - 仅打印配置：`python "Backend-System\init-scripts\init_notification_config.py" --print`
  - 初始化（如不存在则创建；存在则保持原样）：`python "Backend-System\init-scripts\init_notification_config.py"`
  - 强制覆盖为默认配置：`python "Backend-System\init-scripts\init_notification_config.py" --force`

- 在 `Backend-System` 目录运行：
  - 仅打印配置：`python "init-scripts\init_notification_config.py" --print`
  - 初始化（创建或保持）：`python "init-scripts\init_notification_config.py"`
  - 强制覆盖为默认配置：`python "init-scripts\init_notification_config.py" --force`

- 执行结果示例：
  - 打印模式输出：`{"path": "<绝对路径>", "config": { ... } }`
  - 初始化/覆盖模式提示：`创建通知配置文件: <path>`、`保持已存在通知配置文件: <path>` 或 `覆盖通知配置文件: <path>`
  - 若检测到旧文件并成功迁移：`已迁移旧配置文件到: <new_path>`

- 默认配置包含：
  - 开关：`enabled`
  - 提前提醒天数：`advance_days`
  - 提醒次数：`reminder_count`
  - 通知方式：`tenant_notification_methods`、`landlord_notification_methods`
  - 邮件配置：`smtp_config`、`tenant_email_config`、`landlord_email_config`
  - 短信配置：`sms_config`
  - 房东列表：`landlords`
  - 最后更新时间：`last_updated`

提示：首次迁移路径后，建议先执行打印模式确认配置路径与内容，再选择是否使用 `--force` 重置为默认值。

## init_ocr_config.py 使用方法
- 作用：初始化或重置 OCR 配置文件 `Backend-System/config/ocr_config.json`；若根目录存在旧版 `ocr_config.json` 且新路径不存在，会自动迁移到新路径；支持仅打印配置。

- 可用参数：
  - `--force`：强制覆盖为默认配置（即使文件已存在）。
  - `--print`：仅打印当前配置和文件路径，不进行写入或迁移。

- 在仓库根目录运行：
  - 仅打印配置：`python "Backend-System\init-scripts\init_ocr_config.py" --print`
  - 初始化（如不存在则创建；存在则保持原样）：`python "Backend-System\init-scripts\init_ocr_config.py"`
  - 强制覆盖为默认配置：`python "Backend-System\init-scripts\init_ocr_config.py" --force`

- 在 `Backend-System` 目录运行：
  - 仅打印配置：`python "init-scripts\init_ocr_config.py" --print`
  - 初始化（创建或保持）：`python "init-scripts\init_ocr_config.py"`
  - 强制覆盖为默认配置：`python "init-scripts\init_ocr_config.py" --force`

- 执行结果示例：
  - 打印模式输出：`{"path": "<绝对路径>", "config": { ... } }`
  - 初始化/覆盖模式提示：`创建OCR配置文件: <path>`、`保持已存在OCR配置文件: <path>` 或 `覆盖OCR配置文件: <path>`

- 默认配置包含：
  - PaddleOCR：`lang`、`use_angle_cls`、`ocr`（包含 `det/rec/cls`，详见 `Backend-System/config/ocr_config_fields.md`）。

提示：单镜像部署中，supervisor 会在首次启动时自动执行该脚本，创建缺失的 `ocr_config.json`；随后由哨兵文件控制，重启不再重复执行。项目已移除 EasyOCR/Tesseract，统一到 PaddleOCR。