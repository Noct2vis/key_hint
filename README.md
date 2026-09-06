# Key Hint

一个为 Blender 打造的开源插件（Flowkeys 风格）：在**侧边栏（N 面板）**和
**3D 视口 HUD** 中展示**当前模式下的快捷键参考**。

它读的是你**正在使用的真实键位配置**（`keyconfigs.active` / `user`），所以你自己
改过的快捷键会如实显示，并用 **✱** 标记为“自定义键位”。界面文字为**中文**。

## 特性

- **侧边栏参考面板**（`N → Key Hint`）：按中文分类展示当前模式的快捷键，切换模式
  自动跟随；顶部搜索框即时过滤；每条可加**个人笔记**（随 `.blend` 保存）。
- **覆盖左侧工具栏**：数据库中包含 Blender 3D 视口**左侧工具栏（Toolbar）**的
  全部工具及其快捷键（框选 `W`、挤出 `E`、内插 `I`、倒角 `Ctrl+B`、环切 `Ctrl+R`、
  切割 `K`、撕裂 `V` 等；无默认键的工具如实标注，不编造按键）。
- **3D 视口 HUD（默认右下角）**：常驻显示，且是**可拖动的小窗口**：
  - 按住**标题栏**左键拖动即可移动窗口；
  - 标题栏右侧 **「解锁/锁定」按钮**可点击切换；锁定后位置不可再变动，直到解锁。
- **按键驱动的上下文提示**（三层状态机，按下即切换、松开即恢复）：
  - **基础**：初始显示当前模式的无修饰快捷键（移动/旋转/缩放…）；
  - **按住 `Ctrl`/`Shift`/`Alt`**：立即切换成以该修饰键开头的快捷键组，松开立即
    回到基础（不是“再按一个键才触发”，也不会锁定）；
  - **按 `G`/`R`/`S`/`E`/`K`/`I`，或按住 Ctrl 时按 `R`/`B`**：进入该操作后显示
    **后续提示**（如环切 `Ctrl+R` 的滚轮调段数、翻转、确认/取消；倒角 `Ctrl+B` 的
    滚轮段数、轮廓切换等），确认（左键/回车）或取消（右键/ESC）后回到基础。
- **自定义键位标记 ✱**、**即时搜索**、**个人笔记**。
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
- **侧边栏**：`N` → **Key Hint** 面板，顶部搜索框即时过滤；分类下每条快捷键右侧的
  铅笔图标可添加/编辑个人笔记。
- **HUD**（默认开启）：位于 **3D 视口右下角**，是一个可拖动、可锁定的小窗口。
- 偏好设置（`Preferences → Add-ons → Key Hint`）：
  - 随 Blender 启动自动开启（auto start）
  - 是否显示 HUD（Show HUD in 3D viewport）
  - 锁定 HUD 位置（Lock HUD）
  - 偏移（offset X / offset Y，距右/距下像素）
  - 显示开关：基础快捷键（show fundamentals）、修饰键组（show hints）
  - 每组显示上限、字号、透明度、颜色

## 诊断

在 Blender Python Console（或 Text Editor）运行：

```python
import sys
sys.path.insert(0, r"D:/blender")        # key_hint 文件夹的上一级
import key_hint.tests.diagnose as d
d.run()
```

会打印模式、keyconfig、快捷键解析数量、HUD 句柄等，方便定位“不显示”的问题。

> **想确认它到底有没有在跑？** 在 Python Console 输入
> `import key_hint; key_hint.core.is_running()`。返回 `True` 说明 HUD 在运行。

## 工作原理 / 技术说明

- **显示层**：在 `SpaceView3D` 上注册一个 `POST_PIXEL` draw handler，用模块级
  `bpy.app.timers` 循环定时 `tag_redraw()` 驱动刷新——不依赖 modal 收到事件，所以
  HUD 能稳定重绘。中文通过 `blf.load()` 加载系统中文字体显示。
- **捕获**：一个 `PASS_THROUGH` modal（`key_hint.watch`）读取按键与鼠标，`modal()`
  一律返回 `{'PASS_THROUGH'}`，绝不拦截 Blender 的快捷键。
- **按键解析**：根据当前 `context`（编辑器 + 对象模式）推断相关的 `KeyMap`，扫描
  `keyconfigs.active`/`user` 的真实绑定并显示；模式推断是**尽力而为**的启发式。
- **坐标**：HUD 命中矩形在 draw 回调里以**窗口坐标**导出，与 `event.mouse_x/y`
  直接比对，避免 modal 的 region 上下文不一致导致点不中。

## 目录结构

```
key_hint/
  __init__.py   注册入口 (bl_info / register / unregister)
  prefs.py      插件偏好设置
  constants.py  快捷键数据库 + 键位解析 + 上下文提示表（含工具栏工具）
  hints.py      keymap 扫描 / 模式推断辅助
  core.py       HUD 生命周期、watch modal（按键/拖动/锁定）、payload 组装
  draw.py       3D 视口 HUD 绘制（POST_PIXEL，中文字体）
  panels.py     侧边栏 N 面板 + 笔记存储（.blend）
  tests/        无头逻辑测试与诊断脚本
```

## 版权与致谢

- 本项目采用 **GPL-3.0-only**（见仓库顶部 [LICENSE](LICENSE)）。
- 捕获/绘制架构思路参考 **Screencast Keys**（[nutti/Screencast-Keys](https://github.com/nutti/Screencast-Keys)，
  GPL-2.0-or-later）、**Shortcut VUr**（GPL-3.0）与 Blender 官方
  `space_view3d_math_vis`（GPL-2.0-or-later）。本项目代码为原创编写，未复制其代码。
- 界面与文档为中文。

## 开发

单元/逻辑测试（可在无 GUI 的 `--background` 下运行）：

```bash
blender --background --factory-startup --python tests/test_logic.py
```

> 说明：HUD 的可视层（绘制、拖动、锁定、命中）依赖真实 GPU/窗口会话，`--background`
> 只能验证注册与纯逻辑。可视行为请在正常图形界面下验证。
