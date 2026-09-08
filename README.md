# Key Hint

一个为 Blender 打造的开源插件：在**侧边栏（N 面板）**和 **3D 视口 HUD** 中，展示
**你自己维护的一份「快捷键清单」**——每一行是「左侧=功能名、右侧=按键」。

它不再只读扫描键位，而是给你一份**全局自定义清单**：侧栏里可自由增删；3D 视口的
HUD 显示的是**同一份清单**（按当前模式过滤后、再按修饰键分组），所见即所配。

## 特性

- **我的快捷键**：一行一条「功能名 + 按键」，按修饰键分组显示：
  **无按键 / Ctrl / Shift / Alt / 其他组合**。
- **可编辑清单**：
  - 「添加」在清单**末尾追加**一行（功能名 / 按键 / Ctrl·Shift·Alt / 显示范围）；
  - 「删除」把那一行**整行移除**（不会留下空位）；
  - 允许清单为 **0 条**。
- **全局存储**：清单存在**用户配置目录**的一个 JSON（`key_hint/shortcuts.json`），
  所有 `.blend` 工程共用，不随文件保存。
- **默认清单**：首次使用自动写入一份默认条目，取自 **Kurt 的 Blender 零基础入门教程**
  建模篇里讲到的基本按键（G 移动 / R 旋转 / S 缩放 / Shift+A 新建 / Tab 编辑 /
  E 挤出 / Ctrl+R 环切 / 数字键视图切换 / …），之后随你增删；也提供「恢复 Kurt 默认」。
- **3D 视口 HUD（默认右下角）**：显示**同一份**清单——只显示适合当前模式的条目
  （显示范围=物体/编辑/所有），再按 无按键/Ctrl/Shift/Alt 分组。可拖动、可锁定：
  拖**标题栏**移动，点标题栏右侧 **解锁/锁定** 切换，锁定后不可移动。
- 开源 (GPL-3.0)，纯 Blender Python，无第三方运行期依赖。

## 安装

1. 下载本仓库（或 `Releases` 里的 zip）。
2. Blender 菜单：`Edit > Preferences > Add-ons > Install…`，选中 zip 后启用 **Key Hint**。
   - 若用仓库文件夹安装：把整个 `key_hint` 文件夹放到你的
     `scripts/addons/` 目录下，然后在插件列表里勾选。
   - **覆盖安装旧版本前**：先取消勾选 / Remove 旧版（或重启 Blender），避免旧模块缓存
     造成 `has no attribute` 之类报错。

## 使用

- 默认 **自动开启**（Preferences → Add-ons → Key Hint → “Auto start with Blender”）。
- **侧边栏**：`N` → **Key Hint**。顶部是开启开关与「+ 添加」；下面按修饰键分组列出你的
  清单，每行右侧的 **×** 即删除该行。
- **HUD**（默认开启）：位于 **3D 视口右下角**，与侧栏同一份清单，按当前模式过滤分组。
- 偏好设置（`Preferences → Add-ons → Key Hint`）：
  - 随 Blender 启动自动开启（auto start）
  - 是否显示 HUD（Show HUD in 3D viewport）
  - 锁定 HUD 位置（Lock HUD）
  - 偏移（offset X / offset Y，距右/距下像素）
  - 字号、透明度、颜色

## 数据文件

默认清单存储在：

```
<用户配置目录>/key_hint/shortcuts.json
```

（Windows 通常是 `C:\Users\<你>\AppData\Roaming\Blender Foundation\Blender\<版本>\...`，
由 `bpy.utils.user_resource("CONFIG", path="key_hint")` 决定。Blender 侧栏的 Key Hint
面板里也有「恢复 Kurt 默认」，可一键重置。）

## 诊断

在 Blender Python Console（或 Text Editor）运行：

```python
import sys
sys.path.insert(0, r"D:/blender")        # key_hint 文件夹的上一级
import key_hint.tests.diagnose as d
d.run()
```

会打印模式、keyconfig、HUD 句柄等，方便定位“不显示”的问题。

> **想确认它到底有没有在跑？** 在 Python Console 输入
> `import key_hint; key_hint.core.is_running()`。返回 `True` 说明 HUD 在运行。

## 工作原理 / 技术说明

- **数据**：`store.py` 维护一份全局 JSON 清单，纯函数负责规范化、按修饰键分组、按模式
  过滤——可无头单测，HUD 与侧栏共用。
- **显示层**：在 `SpaceView3D` 上注册一个 `POST_PIXEL` draw handler，用模块级
  `bpy.app.timers` 循环定时 `tag_redraw()` 驱动刷新。中文通过 `blf.load()` 加载系统
  中文字体显示。
- **捕获**：一个 `PASS_THROUGH` modal（`key_hint.watch`）读取鼠标做拖动/锁定，
  `modal()` 一律返回 `{'PASS_THROUGH'}`，绝不拦截 Blender 的快捷键。
- **坐标**：HUD 命中矩形在 draw 回调里以**窗口坐标**导出，与 `event.mouse_x/y`
  直接比对，避免 modal 的 region 上下文不一致导致点不中。

## 目录结构

```
key_hint/
  __init__.py   注册入口 (bl_info / register / unregister)
  prefs.py      插件偏好设置
  store.py      全局 JSON 存储 + Kurt 默认清单 + 分组/过滤/序列化纯函数
  panels.py     侧边栏 N 面板：可编辑的“我的快捷键”清单（添加/删除/恢复默认）
  core.py       HUD 生命周期、watch modal（拖动/锁定）、payload 组装（读 store）
  draw.py       3D 视口 HUD 绘制（POST_PIXEL，中文字体，分组标题）
  hints.py      遗留的 keymap 扫描辅助（模式推断仍被 core 使用）
  constants.py  遗留的键位/上下文数据（暂保留）
  tests/        无头逻辑测试与诊断脚本
```

## 版权与致谢

- 本项目采用 **GPL-3.0-only**（见仓库顶部 [LICENSE](LICENSE)）。
- 捕获/绘制架构思路参考 **Screencast Keys**（[nutti/Screencast-Keys](https://github.com/nutti/Screencast-Keys)，
  GPL-2.0-or-later）、**Shortcut VUr**（GPL-3.0）与 Blender 官方
  `space_view3d_math_vis`（GPL-2.0-or-later）。本项目代码为原创编写，未复制其代码。
- 默认快捷键清单取自 **Kurt 的 Blender 零基础入门教程**公开讲解的建模基本按键。
- 界面与文档为中文。

## 开发

单元/逻辑测试（可在无 GUI 的 `--background` 下运行）：

```bash
blender --background --factory-startup --python tests/test_logic.py
```

> 说明：HUD 的可视层（绘制、拖动、锁定、命中）依赖真实 GPU/窗口会话，`--background`
> 只能验证注册与纯逻辑。可视行为请在正常图形界面下验证。
