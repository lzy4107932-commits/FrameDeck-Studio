# FrameDeck Studio Template Pack T-01

## 安装

复制压缩包内的两个目录到 FrameDeck Studio 根目录：

```text
FrameDeck_Studio/
├── core/
│   └── template_system.py
└── templates/
    ├── ai_character/
    └── film_visual/
```

主窗口文件单独替换到：

```text
gui/main_window.py
```

## 模板内容

AI角色设计：
1. 角色主展示板
2. 角色标准多视图板
3. 角色细节开发板
4. 角色剧情阶段对比板
5. 角色与道具综合板
6. 角色候选快速展示板

电影视觉开发：
1. 电影视觉开发提案板

## T-01 状态

已完成：
- JSON模板规范
- 模板校验
- 内置模板分类菜单
- 模板参数应用
- 模板随工程和配置保存
- 用户模板保存
- 不规则框架 layout.frames 数据

当前中央画布使用 fallback_settings 显示兼容网格。
下一阶段 T-02 会让中央画布、PPT、PDF和图片导出
直接使用 layout.frames 的不规则主图/细节图版式。
