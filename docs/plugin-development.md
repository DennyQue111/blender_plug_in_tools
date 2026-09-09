# 插件开发规范

## 最小插件契约

插件目录必须是 Python package，并提供：

```python
CLASSES = (SomeOperator, SomePanel)

def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
```

插件的 `bl_idname` 使用 `bts.<plugin>_<action>` 命名空间，避免与其他 Add-on 冲突。面板优先放进 Tool Shelf 的分类页；跨插件共享的属性和服务才放进 `core/`。

## 推荐拆分

```text
my_tool/
├─ __init__.py
├─ operators.py
├─ panels.py
├─ properties.py
├─ services.py
└─ README.md
```

只有在工具变复杂时才拆文件。这样可以让每个插件独立测试、独立移除，也方便未来打包成单独的 Blender Extension。
