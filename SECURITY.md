# 安全策略 (Security Policy)

本项目高度重视安全性，特别是涉及智能体（Agent）自动化调度、子进程通信与本地文件 I/O 写入的场景。

---

## 1. 支持的版本

| 版本 | 是否接收安全更新 |
| :--- | :--- |
| 1.0.x | :white_check_mark: 当前支持 |
| < 1.0.0 | :x: 已废弃 |

---

## 2. 内置安全机制 (Security Safeguards)

本项目在架构设计上内置了多项防御性安全策略：

1. **路径沙箱边界限定 (Path Confinement)**：
   调度引擎严格校验模型输出路径是否位于当前工作目录或系统临时工作区内（`is_path_inside`），严防路径穿越（Path Traversal）与外部敏感文件污染。
2. **位图魔数核验 (Magic Number Validation)**：
   严格核验生成文件的二进制魔数头（PNG: `\x89PNG\r\n\x1a\n`，JPEG: `\xff\xd8\xff`，WEBP: `RIFF...WEBP`），杜绝恶意文本或伪造扩展名注入。
3. **参数注入防御 (Command Injection Defense)**：
   外部命令行适配器使用参数数组（而非字符串拼接）传递给 Python 子进程，严禁通过不受信任的 shell 解释器执行动态指令。
4. **单例互斥锁安全 (Kernel File Lock)**：
   采用操作系统内核句柄锁（`msvcrt` / `fcntl`），避免多进程竞争条件（Race Condition）导致文件写入损毁。

---

## 3. 报告安全漏洞 (Reporting a Vulnerability)

如果你在本项目中发现了任何潜在的安全漏洞，请**不要**公开发布 GitHub Issue。

请通过私密渠道向维护者报告：
* **邮箱**：`shirolin.com@gmail.com`
* **邮件主题**：`[SECURITY] agy-imagegen-skill Vulnerability Report`

### 报告时请包含以下信息：
1. 漏洞类型与影响范围；
2. 详细的复现步骤或最小复现代码（PoC）；
3. 你的建议修复方案（若有）。

维护者将在 48 小时内确认并回复你的报告，并在修复完成后给予安全致谢。
