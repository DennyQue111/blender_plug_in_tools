# Blender Tool Shelf

一个面向内部工具开发的 Blender 工具架骨架。它本身是一个可安装的多文件 Add-on/Extension，未来的建模、绑定、动画、导入导出和流程工具都可以作为独立插件挂到同一个 Tool Shelf 面板上。

## 目录约定

```text
blender_plug_in_tools/
├─ blender_tool_shelf/          # 可直接安装到 Blender 的 add-on 包
│  ├─ __init__.py               # bl_info、生命周期和插件加载入口
│  ├─ blender_manifest.toml     # Blender 4.2+ Extension 元数据
│  ├─ core/                     # 与具体工具无关的框架代码
│  ├─ plugins/                  # 每个工具一个独立包
│  │  ├─ __init__.py            # 插件白名单/发现机制
│  │  └─ hello_tool/            # 参考插件
│  ├─ resources/                # icons、presets、templates 等资源
│  └─ utils/                    # 通用辅助代码
├─ tests/                       # 不依赖 Blender 的单元测试和 Blender 集成测试
├─ docs/                        # 开发规范、发布和迁移文档
├─ scripts/                     # 打包、安装、开发环境辅助脚本
└─ pyproject.toml
```

## 安装与开发

1. 在 Blender 的 Preferences > Add-ons 中选择 `blender_tool_shelf` 目录（或将整个目录压缩成 zip 后安装）。
2. 启用 **Blender Tool Shelf**。
3. 在 3D View 按 `N`，打开 **Tool Shelf** 标签页，点击 **Hello Tool** 验证加载。
4. 开发时修改代码后，在 Blender 的 Python Console 执行 `bpy.ops.script.reload()`，必要时先禁用再启用本 Add-on。

新增插件时，复制 `blender_tool_shelf/plugins/hello_tool`，实现 `register()`/`unregister()`，然后把完整模块名加入 `ENABLED_PLUGINS`。插件不要把状态写回自己的安装目录；用户数据应放在 Blender 的用户配置目录。

## 设计原则

- 插件之间只通过稳定的核心 API 协作，避免互相 import 私有实现。
- 每个插件拥有自己的 `operators.py`、`panels.py`、`properties.py` 等文件后再拆分；小插件可先保留在一个包内。
- 所有 Blender 类都在插件自己的 `CLASSES` 中集中注册，并按反序注销。
- 资源与代码分离，图标放 `resources/icons`，预设放 `resources/presets`。
- `ENABLED_PLUGINS` 是显式白名单，避免开发中的临时目录被 Blender 自动加载。

## 参考依据

结构遵循 Blender 多文件 Add-on/Extension 的 `__init__.py` 入口和 manifest 约定，并吸收 Maya Module 常见的 scripts/plugins/icons/presets 分层方式。

### 开发模式：映射源码目录

开发时不建议反复安装 zip。可以把源码目录通过 Windows Junction 映射到 Blender 5.2 的本地 Extension 仓库。映射后，Blender 读取的就是源码目录，不需要重新压缩。

修改或新增代码后，在 Blender Python Console 执行：

```python
bpy.ops.extensions.repo_refresh_all()
bpy.ops.preferences.addon_refresh()
```

如果新增了 Operator、Panel 或新的插件包，刷新后再禁用并重新启用 **Blender Tool Shelf**；如果模块仍被缓存，直接重启 Blender。`bpy.ops.script.reload()` 适合重新读取普通脚本，但不保证清理已经注册的 Blender 类。

### 新增插件

1. 复制 `blender_tool_shelf/plugins/hello_tool` 为新的插件目录，例如 `my_tool`。
2. 实现插件自己的 `register()`/`unregister()`，并在 `CLASSES` 中集中管理 Blender 类。
3. 在 `blender_tool_shelf/plugins/__init__.py` 中加入目录名：

```python
ENABLED_PLUGINS = (
    "hello_tool",
    "my_tool",
)
```

这里只填写插件目录名，不要写 `blender_tool_shelf.plugins.my_tool`；框架会根据当前 Add-on/Extension 包名自动生成正确的导入路径。

## AI 场景服务（开发中）

scene_ai_service 是与 Blender 隔离的本地 VGGT 服务。它将概念图或参考图交给独立 Python 环境中的 VGGT，输出 COLMAP 相机与点云数据；未来 Shelf 再负责提交任务和导入结果。这样不会把 PyTorch、CUDA 与模型权重装进 Blender 自带 Python。具体安装、启动和测试方法见 [scene_ai_service/README.md](scene_ai_service/README.md)。

启动服务后，在 `N` 面板的 **Tool Shelf > Modeling > Concept Scene** 中选择图片，点击 **Generate VGGT Scene Data**，再用 **Check VGGT Job** 查看状态。第一版只提交任务，不会自动将结果导回 Blender。

### 新电脑配置

首次在新电脑上使用时，在项目根目录运行：

```powershell
.\setup_scene_ai.ps1
```

该脚本创建项目专用 `.venv`、克隆 VGGT、安装固定的 NumPy 与 CUDA 版 PyTorch，并检查显卡是否可用。日常只需运行：

```powershell
.\start_scene_ai.ps1
```

如果 PowerShell 拦截本地脚本，可以仅对这次运行使用：

```powershell
powershell -ExecutionPolicy Bypass -File .\setup_scene_ai.ps1
```