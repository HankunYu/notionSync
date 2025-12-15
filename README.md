# Notion Sync

一个可扩展的命令行工具，用于将 Notion 数据库中的任务同步到多种系统（如 Apple Calendar、Things 等）。

## ✨ 特性

- 🔄 **智能同步**：使用本地缓存追踪变化，只更新修改过的任务
- 📅 **Apple Calendar 集成**：自动创建和更新日历事件（全天事件）
- ☁️ **账号选择**：支持 iCloud、Local、Exchange 等多种日历账号
- 🏗️ **可扩展架构**：轻松添加新的导出器（Things、Todoist 等）
- 🎯 **灵活配置**：支持多种导出选项和过滤规则
- 📊 **详细报告**：清晰显示创建、更新和跳过的项目数量
- 🔧 **工具集成**：提供账号查看、缓存管理等实用工具

## 📦 依赖安装

```bash
pip install -r requirements.txt
```

> **注意**：`pyobjc-framework-EventKit` 会触发 macOS 的日历权限对话框，首次运行需要点击"允许"。

## ⚙️ 配置

### 1. 创建 Notion Integration

1. 访问 [Notion Integrations](https://www.notion.so/my-integrations)
2. 创建一个新的 Internal Integration
3. 复制生成的 token
4. 将目标数据库分享给该集成

### 2. 配置文件设置

复制 `config.example.toml` 到 `config.toml` 并填写：

```toml
# 必需配置
notion_token = "ntn_xxx"           # Notion integration token
database_id = "xxx"                 # 数据库 ID

# 可选：覆盖标题属性名称
title_property = "Task name"       # 默认为 "Name"

# Apple Calendar 导出器配置
[exporters.apple_calendar]
calendar_name = "Notion Task"       # 日历名称
skip_completed = true               # 是否跳过已完成任务
event_prefix = "[Notion] "          # 事件标题前缀
account_name = "iCloud"             # 可选：指定日历账号（iCloud、Local 等）
                                    # 运行 'python list_calendar_accounts.py' 查看可用账号
                                    # 如不指定，优先级：iCloud > Local > 第一个可用账号
```

### 3. 数据库要求

确保你的 Notion 数据库包含以下属性：
- **Task name**（或你配置的标题属性）：任务名称
- **Due**：截止日期
- **Status**：任务状态（可选，用于过滤已完成任务）
- **Assign**：分配人员（可选）

## 🚀 使用方法

### 查看可用的日历账号

在首次配置前，建议先查看系统中有哪些日历账号：

```bash
python list_calendar_accounts.py
```

这会列出所有可用账号（iCloud、Gmail、Exchange 等），帮助你选择合适的账号存储 Notion 任务。

### 查看所有任务

```bash
python notion_sync.py
```

### 查看详细信息

```bash
python notion_sync.py --detailed
```

### 导出到 Apple Calendar

```bash
python notion_sync.py --export apple_calendar
```

首次运行时会显示：
- 创建的日历名称
- 使用的账号（例如：`Created new calendar 'Notion Task' in account: iCloud`）
- 创建的事件数量

### 查看原始 JSON 数据

```bash
python notion_sync.py --raw
```

### 指定配置文件

```bash
python notion_sync.py --config /path/to/config.toml --export apple_calendar
```

## 🔄 缓存和同步机制

### 缓存位置

缓存文件存储在 `~/.cache/notion_sync/apple_calendar_cache.json`

### 工作原理

1. **首次运行**：创建所有符合条件的日历事件，并保存到缓存
2. **后续运行**：
   - 检测任务变化（标题、日期、状态等）
   - **有变化**：更新现有日历事件
   - **无变化**：跳过，不重复创建
   - **新任务**：创建新的日历事件

### 查看缓存状态

```bash
python test_cache_update.py
```

### 测试更新功能

1. 在 Notion 中修改某个任务的标题或日期
2. 再次运行导出命令
3. 系统会自动更新对应的日历事件（而不是创建新的）

```bash
python notion_sync.py --export apple_calendar
# 输出示例：
# Created: 0
# Updated: 1  ← 更新了修改过的任务
# Skipped: 9
```

## 🏗️ 架构设计

### 目录结构

```
notionSync/
├── notion_sync.py              # 主程序
├── list_calendar_accounts.py  # 列出可用日历账号的工具
├── test_cache_update.py       # 缓存查看工具
├── exporters/                  # 导出器模块
│   ├── __init__.py
│   ├── base.py                # 抽象基类
│   ├── cache.py               # 缓存管理
│   └── apple_calendar.py      # Apple Calendar 导出器
├── config.toml                 # 用户配置
├── config.example.toml         # 配置示例
└── requirements.txt            # 依赖列表
```

### 添加新的导出器

创建新的导出器非常简单：

1. 在 `exporters/` 目录创建新文件（如 `things.py`）
2. 继承 `TaskExporter` 基类
3. 实现必需的方法
4. 在 `notion_sync.py` 中注册

示例：

```python
# exporters/things.py
from .base import TaskExporter

class ThingsExporter(TaskExporter):
    def get_exporter_name(self) -> str:
        return "things"

    def validate_config(self) -> bool:
        # 验证配置
        return True

    def export_tasks(self, tasks):
        # 实现导出逻辑
        pass
```

## 📊 导出结果说明

运行导出命令后，会显示详细的结果统计：

```
============================================================
Export Results:
  Success: True
  Created: 5      # 新创建的事件数
  Updated: 2      # 更新的事件数
  Skipped: 3      # 跳过的任务数（无变化、无日期或已完成）
  Errors: 0       # 错误数
============================================================
```

## 🔧 高级功能

### 全天事件

所有导出的任务都会创建为**全天事件**，而不是带具体时间的事件。这意味着：
- 任务会显示在日历顶部的全天事件区域
- 不会占用具体的时间段
- 更适合待办任务的展示方式
- 有结束日期的任务会显示为跨天事件

### 选择日历账号

运行 `python list_calendar_accounts.py` 查看所有可用账号，然后在配置中指定：

```toml
[exporters.apple_calendar]
account_name = "iCloud"  # 推荐使用 iCloud，可跨设备同步
```

可用的账号类型：
- **iCloud** - 推荐，自动同步到所有 Apple 设备
- **Local** - 仅本地存储，不同步
- **Exchange/Gmail** - 第三方邮箱服务

如果不指定，系统会按以下优先级自动选择：
1. iCloud（推荐）
2. Local
3. 第一个可用账号

### 跳过已完成任务

在配置中设置 `skip_completed = true`，状态为 "Done" 的任务将不会导出。

### 自定义事件前缀

使用 `event_prefix` 配置项为所有日历事件添加前缀，便于识别：

```toml
event_prefix = "[Work] "  # 所有事件标题前会加上 "[Work] "
```

## ⏰ 定时同步（可选）

### 使用 launchd（macOS 推荐）

创建 `~/Library/LaunchAgents/com.notion.sync.plist`：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.notion.sync</string>
    <key>ProgramArguments</key>
    <array>
        <string>/path/to/venv/bin/python</string>
        <string>/path/to/notionSync/notion_sync.py</string>
        <string>--export</string>
        <string>apple_calendar</string>
    </array>
    <key>StartInterval</key>
    <integer>900</integer> <!-- 每 15 分钟 -->
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
```

加载定时任务：

```bash
launchctl load ~/Library/LaunchAgents/com.notion.sync.plist
```

### 使用 cron

```bash
# 每 15 分钟同步一次
*/15 * * * * cd /path/to/notionSync && /path/to/venv/bin/python notion_sync.py --export apple_calendar
```

## 🐛 故障排除

### 日历访问被拒绝

确保在 **系统设置 > 隐私与安全性 > 日历** 中授予了权限。

### 日历账号选择问题

如果日历创建在了错误的账号中：

1. 运行 `python list_calendar_accounts.py` 查看所有账号
2. 在 `config.toml` 中指定正确的账号：
   ```toml
   account_name = "iCloud"
   ```
3. 在日历应用中删除旧日历
4. 清除缓存：`rm -rf ~/.cache/notion_sync/`
5. 重新运行导出

### 更改为全天事件

如果之前的事件不是全天事件，需要：

1. 在日历应用中删除旧的 "Notion Task" 日历
2. 清除缓存：`rm -rf ~/.cache/notion_sync/`
3. 重新运行导出，新事件会自动设为全天事件

### 缓存问题

如果遇到缓存相关问题，可以删除缓存重新开始：

```bash
rm -rf ~/.cache/notion_sync/
```

然后重新运行导出命令。

### 查看详细错误

运行时会显示详细的错误信息。检查：
1. Notion token 是否有效
2. Database ID 是否正确
3. 数据库是否已分享给 Integration
4. 是否有日历访问权限

## 📝 路线图

- [ ] 支持 Things 导出器
- [ ] 支持 Todoist 导出器
- [ ] 支持双向同步
- [ ] 支持日历事件删除
- [ ] 支持标签映射到日历颜色
- [ ] 增加 dry-run 模式
- [ ] 添加日志文件配置

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交 Issues 和 Pull Requests！
