# 环境假设

当前仓库处于 tenant persistence foundation 阶段。支持环境固定为 Node 24.18.0、npm 11、Python 3.13、uv lock 与 PostgreSQL 17。Next.js、FastAPI、同步 SQLAlchemy、Alembic 和 psycopg 是可替换工具链假设（ADR-011、ADR-012）。

本地必须能访问一个显式 PostgreSQL database；可以使用原生 PostgreSQL，也可以使用仓库提供的可选 Docker Compose service。Docker 不是唯一工作流，应用不容器化。测试使用独立、名称以 `_test` 结尾的 database。

## 冻结决定

依赖只来自官方 registry、由 lockfile 固定并安装到仓库工作区。持久化测试不得使用 SQLite 隐藏 PostgreSQL 约束、事务、JSONB 或索引语义。不得修改全局 Python 环境或连接云数据库。

## 可替换假设与复审触发

PostgreSQL major、driver packaging、pool 参数和本地数据库载体可替换。同步数据库访问连续两个周期造成量化阻塞、生产镜像不允许 binary driver，或 PostgreSQL 17 生命周期结束时，以新 ADR 复审。
