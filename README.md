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
