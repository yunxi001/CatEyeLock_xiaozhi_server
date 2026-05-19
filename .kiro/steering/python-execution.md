---
inclusion: always
---

# Python 代码执行规范

## 核心规则

执行任何 Python 命令前，必须激活 conda 环境或使用完整路径。

**环境信息**：

- 环境名：`xiaozhi-esp32-server`
- Python 路径：`D:\Electronic_soft\anaconda\envs\xiaozhi-esp32-server\python.exe`
- Python 版本：3.10.19

## 执行方案

### 方案 1：激活环境（推荐）

**PowerShell**（使用 `;` 连接）：

```powershell
conda activate xiaozhi-esp32-server; python app.py
```

**CMD**（分步执行，不能用 `&`）：

```cmd
conda activate xiaozhi-esp32-server
python app.py
```

### 方案 2：完整路径（备选）

```cmd
D:\Electronic_soft\anaconda\envs\xiaozhi-esp32-server\python.exe app.py
```

## 常见错误

| 错误                       | 原因         | 解决                     |
| -------------------------- | ------------ | ------------------------ |
| `ModuleNotFoundError`      | 环境未激活   | 使用方案 1               |
| `conda: command not found` | conda 不可用 | 使用方案 2               |
| Python 版本不对            | CMD 用了 `&` | 改用 PowerShell 或方案 2 |

## 注意事项

- 每次新会话需重新激活环境
- 长时间运行进程使用 `control_pwsh_process`
- 确保在 `main/xiaozhi-server/` 目录下执行
