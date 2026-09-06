# Key Hint

一个为 Blender 打造的开源插件：像游戏一样，**按住 Ctrl / Shift / Alt**，就能看到当前模式下以该修饰键开头的**真实快捷键**列表。

例如按住 `Ctrl`，画面角落会浮现类似下面的 HUD：

```
Ctrl + A     应用全部变换
Ctrl + C     复制对象
Ctrl + X     剪切
Ctrl + Shift + A  添加物体
...
```

它读的是你**正在使用的真实键位配置**（`keyconfigs.active` / `user`），而不是一份写死的清单——所以连你自己自定义过的快捷键也会被正确列出来。

## 特性

- **常驻基础快捷键参考**：在 3D 视口角落始终显示当前模式的无修饰键快捷键，
  例如 Object 模式下列出 `G  移动`、`R  旋转`、`S  缩放` 等；切换模式会自动跟随。
- **按住修饰键追加显示**：按住 `Ctrl`/`Shift`/`Alt` 时，在下方**追加**以该修饰键
  开头的快捷键（基础表始终保留）。
- **读取你真实的键位配置**：显示内容来自你正在使用的 `keyconfigs.active`/`user`，
  自己改过的快捷键会正确反映；不是写死的清单。
- **完全非侵入**：通过 `PASS_THROUGH` 被动监听，**绝不吞掉任何快捷键**，照常操作。
- 干净的面向 3D 视口的 HUD，多列自动换行，字体/透明度/偏移/强调色可调。
- 开源 (GPL)，纯 Blender Python，无第三方运行期依赖。

## 安装

1. 下载本仓库（或 `Releases` 里的 zip）。
2. Blender 菜单：`Edit > Preferences > Add-ons > Install…`，选中 zip 后启用 **Key Hint**。
   - 若用仓库文件夹安装：把整个 `key_hint` 文件夹放到你的
     `scripts/addons/` 目录下，然后在插件列表里勾选。

## 使用

- 默认 **自动开启**（Preferences → Add-ons → Key Hint → “Auto start with
  Blender”）。启用插件后，若处于 3D 视口，左上角会**始终显示**当前模式的基础
  快捷键表（Object 模式会看到 `G/R/S` 等）。——**看到这张表就说明插件在运行**。
- 内容会**跟随当前模式**：切到 Edit / Sculpt / Pose 等会自动刷新成对应模式的快捷键。
- 按住 `Ctrl`/`Shift`/`Alt` 时，会在这张表下方**追加**以该修饰键开头的快捷键；
  松开即隐藏追加部分（基础表一直在）。
- 若没有自动出现，可在 **3D 视口侧边栏 (`N`) → Key Hint** 面板手动勾选
  “Enabled”，或 `Space` 搜索运行 `key_hint.capture` 手动启动。
- 可调节项（`Preferences → Add-ons → Key Hint`）：
  - 随 Blender 启动自动开启
  - 是否常驻显示基础快捷键表（show fundamentals）
  - 按住修饰键时是否追加对应组（show hints）
  - 每组显示上限（max entries）、字号、透明度、偏移、强调色

> **想确认它到底有没有在跑？** 打开 Blender 的 Python Console 或 Info，输入
> `import key_hint; key_hint.core.is_running()`。返回 `True` 说明捕获在运行；
> 为 `False` 时可手动运行 `bpy.ops.key_hint.capture('INVOKE_DEFAULT')` 启动。
> 若启动时控制台打印 `[Key Hint] ...failed...`，把那行贴给我。

## 工作原理 / 技术说明

- **捕获**：采用与广受欢迎的 [Screencast Keys](https://github.com/nutti/Screencast-Keys)
  (GPL-2.0-or-later) 相同的**被动观察者**思路——把一个 modal 运算符挂到
  `WindowManager`，其 `modal()` 一律返回 `{'PASS_THROUGH'}` 从而不拦截事件；
  用短周期 `Timer` 驱动刷新；用 3D 视口区域的 `POST_PIXEL` draw handler 绘制 HUD。
- **提示引擎**：根据当前 `context`（编辑器类型 + 对象模式，如 Object / Edit Mesh /
  Sculpt / Pose…）推断相关的 `KeyMap`，再在其 `keymap_items` 中筛选出以当前按住
  修饰键为前缀、`map_type=='KEYBOARD'`、`active` 的绑定，并解析出友好操作名。
  由于 Blender 不直接暴露"当前激活的 keymap"，模式推断是**尽力而为**的启发式——
  欢迎反馈偏差较大的模式，以便扩充 `hints.py` 里的映射表。

## 版权与致谢

- 本项目采用 **GPL-3.0-only**（见仓库顶部 [LICENSE](LICENSE)），与 Blender 及其
  插件生态兼容。
- 捕获架构灵感来自 **Screencast Keys**（[nutti/Screencast-Keys](https://github.com/nutti/Screencast-Keys)，
  GPL-2.0-or-later）。本项目代码为原创编写，未复制其代码，并按 GPL-3.0-only
  发布。

## 开发

单元/逻辑测试（可在无 GUI 的 `--background` 下运行）：

```bash
blender --background --factory-startup --python tests/test_logic.py
```

目录结构：

```
key_hint/
  __init__.py   注册入口 (bl_info / register / unregister)
  prefs.py      插件偏好设置
  hints.py      提示引擎：keymap 扫描 + 上下文推断 + 命名
  core.py       被动 modal 捕获器 + draw handler 注册
  draw.py       HUD 渲染（blf 文本 + 尽力而为的 GPU 圆角背景）
  ui.py         3D 视口侧边栏面板
```

> 说明：`core.py` 与 `draw.py` 中的 HUD 绘制依赖真实 GPU 会话，`--background`
> 只能验证注册与纯逻辑（`hints.py`）。可视层建议在正常的图形界面下验证。
