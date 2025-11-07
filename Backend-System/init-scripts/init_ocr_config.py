import os
import json
import argparse


def get_config_file_path() -> str:
    """Return absolute path to config/ocr_config.json under Backend System."""
    base_dir = os.path.dirname(os.path.dirname(__file__))
    return os.path.join(base_dir, "config", "ocr_config.json")


DEFAULT_CONFIG = {
    "preferred_engine": "paddleocr",
    "paddleocr": {
        "lang": "ch",
        "use_angle_cls": True,
        "ocr": {
            "det": True,
            "rec": True,
            "cls": True
        }
    }
}


def write_default_config(force: bool = False) -> str:
    """Create or overwrite ocr_config.json with DEFAULT_CONFIG.

    Returns the path to the config file.
    """
    config_path = get_config_file_path()
    os.makedirs(os.path.dirname(config_path), exist_ok=True)

    if not force and os.path.exists(config_path):
        return config_path

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(DEFAULT_CONFIG, f, ensure_ascii=False, indent=2)
    return config_path


def read_config() -> dict:
    path = get_config_file_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def main():
    parser = argparse.ArgumentParser(
        description="初始化/重置 OCR 配置文件 ocr_config.json"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="若存在则覆盖为默认配置",
    )
    parser.add_argument(
        "--print",
        action="store_true",
        help="仅打印当前配置，不写入",
    )

    args = parser.parse_args()

    # migrate old root-level file if present and new file missing
    base_dir = os.path.dirname(os.path.dirname(__file__))
    old_path = os.path.join(base_dir, "ocr_config.json")
    new_path = get_config_file_path()
    if not args.print:
        os.makedirs(os.path.dirname(new_path), exist_ok=True)
        if os.path.exists(old_path) and not os.path.exists(new_path):
            try:
                import shutil
                shutil.move(old_path, new_path)
                print(f"已迁移旧配置文件到: {new_path}")
            except Exception as e:
                print(f"迁移旧配置文件失败: {e}")

    if args.print:
        cfg = read_config()
        print(json.dumps({"path": get_config_file_path(), "config": cfg}, ensure_ascii=False, indent=2))
        return

    path = write_default_config(force=args.force)
    existed = os.path.exists(path)
    action = "覆盖" if args.force else ("保持已存在" if existed else "创建")
    print(f"{action}OCR配置文件: {path}")


if __name__ == "__main__":
    main()