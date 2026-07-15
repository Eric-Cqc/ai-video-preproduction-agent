# 环境假设

当前仓库处于 engineering skeleton 阶段。支持环境固定为 Node 24.18.0、npm 11、Python 3.13 与已锁定的仓库内虚拟环境；Next.js、FastAPI 与 uv 是本阶段的可替换工具链假设（[ADR-011](../adr/ADR-011-engineering-skeleton-toolchain.md)）。不假设数据库、Docker、云账号或外部 Provider 存在。

## 冻结决定

依赖必须来自官方 npm/Python 注册表、由 lockfile 固定，并只安装到仓库工作区。不得通过环境准备引入外部服务或修改全局 Python 环境。

## 可替换假设与复审触发

框架、数据库、队列和部署环境仍可替换。只有达到 ADR-011 或工程宪法的复审条件时才重新选型；数据库、生产队列和部署不属于当前里程碑。
