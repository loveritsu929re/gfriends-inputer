# 仓库贡献指南

## 项目结构与模块组织

- `Gfriends Inputer.py` 是程序入口，包含命令行流程、图片处理、下载及导入调度逻辑。
- `jellyfin_api.py` 封装 Jellyfin HTTP 客户端，负责认证、人物查询、元数据更新和图片操作。
- `Lib/` 存放 OpenCV 模型文件及本地人脸检测辅助代码。
- `tests/` 存放 Jellyfin 客户端单元测试。新增测试应尽量靠近其覆盖的行为。
- `README.md` 记录面向用户的配置与使用方法。不要提交运行时生成的 `config.ini`、`Getter/`、日志或下载图片。

## 构建、测试与开发命令

本仓库没有单独的构建系统。安装依赖并运行程序：

```powershell
python -m pip install -r requirements.txt
python "Gfriends Inputer.py"
```

提交修改前应运行：

```powershell
python -m py_compile "Gfriends Inputer.py" jellyfin_api.py
python -m unittest discover -s tests -v
```

仅在需要诊断或无人值守运行时使用 `--debug` 或 `-q`；普通运行可能要求填写配置并进行交互确认。

## 编码风格与命名约定

使用 Python 3 语法，每级缩进四个空格，并保持函数职责单一。函数和变量采用 `snake_case`，类采用 `PascalCase`，常量名称应清晰明确。保留 UTF-8 编码及现有中文用户提示。调用 Jellyfin 时应复用 `requests.Session` 和统一的 `JellyfinApi` 封装，禁止手动拼接带认证信息的 URL。

## 测试指南

测试使用 Python 标准库 `unittest`，统一放在 `tests/`。测试文件命名为 `test_*.py`，测试方法命名为 `test_<行为>`。应模拟 HTTP 响应，不要依赖真实 Jellyfin 服务器。修改 API 行为时，需要覆盖状态码处理、分页、认证头和请求载荷。

## 提交与拉取请求规范

提交标题应简短并使用祈使语气，例如 `Fix Jellyfin image upload`；发布提交沿用仓库现有的 `Release vX.YY` 格式。拉取请求应说明用户可见的变化、列出已执行的验证命令，并明确配置或兼容性影响。不得包含 API 密钥、私人服务器地址、生成图片、日志或本地配置文件。

## 安全与配置提示

将 `config.ini` 和 `Host_API` 视为敏感信息。API 密钥必须通过 `JellyfinApi` 放入请求头，不得写入日志或粘贴到 Issue。验证元数据删除或图片替换时，应使用可随时恢复的测试媒体库。
