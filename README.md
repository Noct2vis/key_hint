# Key Hint

一个为 Blender 打造的开源插件（Flowkeys 风格）：在**侧边栏（N 面板）**和
**3D 视口 HUD** 中以分类列表展示**当前模式下的快捷键**。

它读的是你**正在使用的真实键位配置**（`keyconfigs.active` / `user`），所以你自己
改过的快捷键会如实显示，并用 **✱** 标记为“自定义键位”。

## 特性

- **侧边栏参考面板**（`N → Key Hint`）：按分类（Transform / View / Mesh / Sculpt…）
  展示当前模式的快捷键，切换模式自动跟随。
- **即时搜索**：在面板顶部搜索框按名称或按键过滤。
- **自定义键位标记 ✱**：读 `keyconfigs` 解析真实键位，与内置默认键不同时打 ✱。
- **个人笔记**：可为每条快捷键加备注，保存在当前 `.blend` 文件（随文件持久化）。
- **3D 视口 HUD**：可选，在 3D 视口角落常驻显示同一份参考列表。
- 开源 (GPL-3.0)，纯 Blender Python，无第三方运行期依赖。

## 安装

1. 下载本仓库（或 `Releases` 里的 zip）。
2. Blender 菜单：`Edit > Preferences > Add-ons > Install…`，选中 zip 后启用 **Key Hint**。
   - 若用仓库文件夹安装：把整个 `key_hint` 文件夹放到你的
     `scripts/addons/` 目录下，然后在插件列表里勾选。

## 使用

- 默认 **自动开启**（Preferences → Add-ons → Key Hint → “Auto start with Blender”）。
- **侧边栏**：`N` → **Key Hint** 面板，顶部搜索框即时过滤，下面按分类列出快捷键；
  每条快捷键右侧的铅笔图标可添加/编辑个人笔记。
- **HUD**：可选（偏好里的 “Show HUD in 3D viewport”），在 3D 视口左上角常驻显示。
- 若没有自动开启，可在面板勾选 “Enabled”，或 `Space` 搜索运行 `key_hint.capture`。

## 诊断

在 Blender Python Console（或 Text Editor）运行：

```python
import sys
sys.path.insert(0, r"D:/blender")        # key_hint 文件夹的上一级
import key_hint.tests.diagnose as d
d.run()
```

会打印模式、keyconfig、快捷键解析数量、HUD 句柄等，方便定位“不显示”的问题。
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
