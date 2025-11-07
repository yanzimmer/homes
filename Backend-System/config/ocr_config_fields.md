# OCR 配置字段说明（仅 PaddleOCR）

此文档说明 `Backend-System/config/ocr_config.json` 的字段与取值范围。后端每次识别都会读取该文件并应用，无需重启。

## 生效机制与通用规则
- 配置文件路径：`Backend-System/config/ocr_config.json`
- 保存后立即生效（Flask debug 热重载/每次请求重新读取）。
- 值为 `null` 或未提供：表示使用库默认值或不传该参数。
- 未识别字段将被忽略，不影响运行。

## 结构总览
```
{
  "preferred_engine": "paddleocr",
  "paddleocr": { ... }
}
```

说明：项目已统一到 PaddleOCR，引擎选择项只保留 `paddleocr`。

## preferred_engine（首选引擎）
- 类型：string（固定为 `"paddleocr"`）
- 作用：指定使用 PaddleOCR 进行识别。
- 默认：`"paddleocr"`

## paddleocr 节点

### 1) paddleocr.lang
- 类型：string
- 作用：语言选择。
- 常用：`"ch"`（简体中文）、`"en"`（英文）、`"chinese_cht"`（繁体中文）。

### 2) paddleocr.use_angle_cls
- 类型：boolean
- 作用：启用角度分类，改善旋转文本识别。
- 默认：`true`

### 3) paddleocr.ocr（调用参数）
- 类型：对象
- 字段：
  - `det` (boolean)：是否进行文本检测。
  - `rec` (boolean)：是否进行文本识别。
  - `cls` (boolean)：是否进行方向分类。
- 说明：后端调用 `PaddleOCR(...).ocr(image_path, det, rec, cls)`，结果将提取识别文本并按行拼接返回。

## 注意与建议
- 图片尽量保证清晰、方向正确；`use_angle_cls` 可在一定程度上缓解旋转问题。
- 若识别为身份证等结构化信息，后端会做基本字段提取与日期格式规范化。

## 变更历史（简）
- v2：移除 EasyOCR/Tesseract 相关配置，统一到 PaddleOCR。