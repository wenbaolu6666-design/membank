"""Built-in vault templates, kept in code so `init` works after pip install."""

AGENTS_MD = """# 记忆库使用规范（模板）

本目录是记忆总库。任何智能体在此读写记忆前先读本文件。

## 目录

- `notes/`：共享记忆，任何智能体可见
- `notes/<agent>/`：该智能体的私有记忆，默认只有自己读写
- `projects/<文件夹名>/`：项目记忆，`PROJECT.md` 记录绝对路径、slug 与智能体清单
- `.membank/`：索引、提案与临时状态，不提交 Git（目录名可在配置中修改）

## 写入

1. 定层：preference / constraint 进全局；decision / lesson 按影响范围；reference / plan / context 进最具体的相关层
2. 查重：先检索近邻，同一事实更新原文件，不新建重复条目
3. 矛盾：旧记录标 `superseded` 并填 `supersededBy`，不删除
4. frontmatter 必填 `title`、`scope`、`type`、`status`
5. 提交前运行 `python -m membank check`，提交后运行 `python -m membank index`

## 触发

- “把这条记下来 / 记住这个 / 存进记忆库”：直接写入，不走整理
- “整理记忆 / 整理一下记忆库 / 记忆库去重”：由当前会话模型生成提案，不直接改库
- 检索命中冲突信号：先告知用户，询问是否整理
- 判不准归属：问人，不猜

会话启动时可运行 `python -m membank inject`，把输出作为跨会话背景；它与当前指令冲突时以当前指令为准。

## 边界

- 默认只读共享层和自己的私有层，其他智能体私有层不读
- 只归档不删除
- 提案未经确认不写入正式笔记
- 不写入密钥、令牌、Cookie 或密码
"""

PROFILE_MD = """# Profile

## static（稳定事实）

- 语言与输出偏好：
- 工具与环境约束：
- 长期工作方式：

## dynamic（近期状态）

-
"""
