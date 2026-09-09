# Key Hint

一个为 Blender 打造的开源快捷键参考插件。它在**侧边栏（N 面板）**和 **3D 视口 HUD**
里显示快捷键，每一行 =「左侧功能名、右侧按键」，按键尽量与**真实的键位(keyconfig)**
一致。

## 核心思路（两表）

- **默认内容（A）**：一份 curated 清单（`content.py`，取自常用建模操作），是“匹配项”：
  每条定义 功能名、属于哪个模式、是否需要选中。默认就显示这些（不会把整张 keymap 全塞
  进去）。
- **数据库（B）**：你当前 keyconfig 的真实绑定。真正显示的**修饰键 + 按键由 B 回填**：
  内容条目带 `op` 的，运行时会从 keyconfig 读它的真实绑定来显示（改键即随）；没有 `op`
  或读不到的条目显示文档默认键。
- 侧栏可把 **B 里的条目搜出来“加入”**（加入会持久化），也可 × 把某条从“我的快捷键”隐藏。

## 特性

- **我的快捷键**：按修饰键分组显示（无按键 / Ctrl / Shift / Alt / 组合），默认=curated
  内容；每行 功能名 | 按键 + **×** 隐藏。
- **搜索（在“我的快捷键”上方）**：一个输入框 + 下拉（按功能名 / 按按键）。它同时
  1) 过滤“我的快捷键”里显示的条目；2) 把 **B(keyconfig)** 里匹配、且还没显示的条目列成
  「加入」，点一下加入并持久化。
- **同步数据库**：按钮/启动时从 keyconfig 回填真实键，并刷新候选池。
- **恢复默认显示**：把“我的快捷键”重置为默认 curated 内容。
- **3D 视口 HUD（默认右下角）**：基于 key 检测实时显示——没按修饰键=基础组、按住
  Shift/Ctrl/Alt=对应组、按 G/R/S/E/I 等=该操作的后续子键；并受**当前模式**与**是否选中
  物体/点线面**影响（`selected` 条目）。可拖动标题栏、可锁定。
- 不再有“是否显示 Key Hint”开关（启用即常开，关闭去 Preferences）。
- 开源 (GPL-3.0)，纯 Blender Python，无第三方运行期依赖。

## 安装

1. 下载本仓库（或 `Releases` 里的 zip）。
2. Blender：`Edit > Preferences > Add-ons > Install…`，选中 zip 后启用 **Key Hint**。
   - 仓库文件夹安装：把整个 `key_hint` 放进 `scripts/addons/`，在插件列表勾选。
   - **覆盖安装旧版本前**：先 Remove/关闭旧版（或重启），避免旧模块缓存报错。

命令行安装（若用 `blender --command`）：

```bash
blender --command extension install-file --repo user_default key_hint-2.0.1.zip
```

## 使用

- **侧边栏**：3D 视口按 `N` → **Key Hint**。
  - 顶部：`同步数据库` / `恢复默认显示`。
  - 搜索栏：输入即过滤“我的快捷键”，同时给出 **B** 里可“加入”的条目。
  - “我的快捷键”：按修饰键分组，每行右侧 **×** 隐藏。
- **HUD**：默认开启，右下角；拖动标题栏移动、右侧锁定/解锁。物体/编辑切换、是否选中、
  是否按住 Shift/Ctrl/Alt、是否按了 G/R/S/E/I，都会改变显示内容。
- 偏好设置（`Preferences → Add-ons → Key Hint`）：自动开启、显示 HUD、锁定、偏移、字号/
  透明度/颜色等。

## 数据文件（用户配置目录 `.../key_hint/`）

- `shown.json`：“我的快捷键”里当前显示哪些(rid 顺序)——你的增删。
- `extras.json`：你从 B 加入并持久化的条目。
- `b_database.json`：可选，维护脚本同步出的 B 快照（runtime 优先读真实 keyconfig）。

## 诊断

Blender Python Console：

```python
import sys; sys.path.insert(0, r"D:/blender")
import key_hint; print(key_hint.core.is_running())
```

## 工作原理 / 技术说明

- `engine.py`：纯查询/格式化引擎。一条记录 = {tags(模式)、sel(是否需要选中)、mods、
  key、name、op、parent(是否某操作后的子键)}；`active_tags(mode, space)` 解析当前标签；
  `query/match_record` 按 **模式 × 选中 × 父操作 × 按住修饰键** 过滤分组。无 bpy，可单测。
- `content.py`：curated 默认内容（Kurt/常用清单），转成带稳定 rid 的记录。
- `library.py`：两表纯逻辑 —— rid、默认显示、增/删/切换、搜索、分组、A 持久化。
- `builder.py`：数据库 B —— 读活动 keyconfig 全量(键盘+鼠标+特殊键+modal 子键)映射成
  记录；`real_binding_for(op)` 回填某算子的真实键。GUI 才有数据。
- `runtime.py`：运行时状态 —— A(默认内容+从 B 加入)、B(候选池)；惰性加载、同步回填
  真实键、持久化 A/extras。
- `core.py` + `draw.py`：HUD 生命周期、PASS_THROUGH watch modal(按键/修饰键/操作键/
  拖动/锁定)、POST_PIXEL 绘制；payload 用 engine/runtime 的上下文查询。中文用 `blf`
  加载系统中文字体。
- `panels.py`：侧栏（搜索/过滤 + 从 B 加入 + 分组显示 + 隐藏/恢复默认 + 同步）。

## 目录结构

```
key_hint/
  __init__.py   注册入口 (bl_info / register / unregister / reload)
  prefs.py      插件偏好设置
  engine.py     纯查询/格式化引擎（模式×选中×修饰键×操作键，分组）
  content.py    curated 默认内容（A 的默认；Kurt/常用清单）
  library.py    两表纯逻辑（rid、增删、搜索、分组、A 持久化）
  builder.py    数据库 B：读 keyconfig 全量 + real_binding_for 回填真实键
  runtime.py    运行时状态（A 显示集 + B 候选池、同步、持久化）
  panels.py     侧栏 N 面板（搜索/从 B 加入/分组显示）
  core.py       HUD 生命周期、watch modal、payload（engine/runtime）
  draw.py       HUD 绘制（POST_PIXEL，中文字体）
  data/blender_default.json  官方中文键位表（备用种子/参考）
  hints.py / constants.py    旧版遗留（暂保留，界面已不使用核心显示）
  store.py      旧版遗留（暂保留）
  tests/        无头逻辑测试
```

## 版权与致谢

- **GPL-3.0-only**（见仓库顶部 [LICENSE](LICENSE)）。
- 捕获/绘制架构思路参考 **Screencast Keys**（GPL-2.0-or-later）、**Shortcut VUr**（GPL-3.0）
  与 Blender 官方 `space_view3d_math_vis`（GPL-2.0-or-later）。代码为原创编写。
- 默认内容(部分功能名)参考 **Kurt 的 Blender 零基础入门教程**公开讲解的建模基本操作。
- 界面与文档为中文。

## 开发

无头注册 + 纯逻辑测试（真实 keymap 读取仅 GUI 生效）：

```bash
blender --background --factory-startup --python tests/test_logic.py
```

> HUD 可视层(绘制/拖动/锁定/命中)与数据库 B 的真实键读取依赖真实 GPU/窗口会话，
> `--background` 只能验证注册与纯逻辑；请在正常图形界面下验证。
