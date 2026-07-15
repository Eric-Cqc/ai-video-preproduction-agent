# 本地设置

当前 skeleton 可在没有 Docker、数据库或云凭据的本机运行。需要 Node 24.18.0、npm 11、Python 3.13、uv 和 `make`；完整命令由根 README 与 Makefile 提供。

## 冻结决定

依赖只通过 npm lockfile 与 `uv.lock` 安装；JavaScript 命令必须经过 Node 包装脚本，Python 使用仓库内 `.venv`。不得初始化数据库、Supabase 或任何外部 Provider。

## 复审触发条件

当 skeleton 工具链无法满足两个连续发布周期的维护目标，或需要数据库/生产队列/部署时，以新 ADR 复审；不得在本文件中预先启用这些能力。
