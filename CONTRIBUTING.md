# 贡献指南 (Contributing Guide)

感谢你关注并愿意为 `agy-imagegen-skill` 做出贡献！本项目致力于为 Google Antigravity、智能体工作流（AI Agents）及游戏/UI 开发者提供最健壮、最优雅的图像生成与透明资产色键后处理方案。

在提交 Issue 或 Pull Request 前，请花几分钟阅读以下准则。

---

## 1. 核心设计原则

贡献代码时，请始终牢记以下架构原则：

- **深度模块原则 (Deep Module)**：让接口尽可能简单（少量参数、直观语义），让实现尽可能强大（内置处理并发互斥、沙箱隔离、魔数核验、防死锁通信）。
- **零外部测试依赖**：所有单元测试必须基于 Python 标准库 `unittest`，严禁引入第三方测试框架依赖。
- **单一事实源 (Single Source of Truth)**：仓库根目录本身即为自包含技能，技术规范与资源严禁跨目录维护冗余副本。
- **跨平台一致性**：确保代码在 Windows、Linux 和 macOS 下行为严格等价，脚本注意换行符（LF）与执行权限位。

---

## 2. 本地开发环境设置

### 环境需求
- Python 3.10+
- Pillow >= 9.5.0

### 克隆与依赖安装
```bash
git clone https://github.com/Shirolin/agy-imagegen-skill.git
cd agy-imagegen-skill

# 创建并激活虚拟环境 (推荐)
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# 安装运行时依赖
pip install Pillow>=9.5.0
```

---

## 3. 运行测试

在提交任何修改前，请确保全量测试套件通过：

```bash
python -m unittest discover tests -v
```

如果添加了新功能或修复了 Bug，请务必在 `tests/` 中添加对应的测试用例（仅写能锁住回归或证明功能的有意义测试，严禁堆砌无意义测试）。

---

## 4. 提交规范 (Commit Convention)

本项目严格采用 [Conventional Commits](https://www.conventionalcommits.org/) 规范。提交信息格式如下：

```text
<type>(<scope>): <subject>

[optional body]
```

### 推荐的 Type
- `feat`: 新增功能特性
- `fix`: 修复 Bug 或异常行为
- `refactor`: 重构代码（无行为变更）
- `docs`: 修改或完善文档
- `test`: 增加或更新测试用例
- `ci`: CI/CD 配置变更
- `chore`: 构建工具、依赖或辅助配置更新

示例：
```bash
git commit -m "fix(engine): 修复并发锁在非标准路径下的释放异常"
```

---

## 5. Pull Request 流程

1. 从 `main` 分支拉出特性分支：`git checkout -b feature/my-awesome-feature`；
2. 编写代码与必要的单测；
3. 本地验证全量测试通过：`python -m unittest discover tests`；
4. 提交修改并推送到你的 Fork 仓库；
5. 向主仓库的 `main` 分支发起 PR，并详细填写 PR 模板描述你的改动意图。

再次感谢你的贡献！
