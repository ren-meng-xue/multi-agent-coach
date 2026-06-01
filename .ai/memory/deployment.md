# Deployment

> 当前阶段仍以本地开发为主，生产部署细节未冻结。本文件记录已固化的部分，方便 release / hotfix workflow 引用。

## 本地依赖

- `docker-compose.yml` 启 PostgreSQL（pgvector/pg16）+ Redis 7
- PG: `coach / coach / coach`（user / db / pwd），暴露 5432
- Redis: 暴露 6379，无密码（**仅本地**）
- 持久卷：`postgres-data`、`redis-data`

## 一键启动

```bash
./dev.sh
```

- 启动 docker 依赖
- 清理残留 celery / uvicorn 进程
- 启动后端 uvicorn（8000）、Celery worker、前端 Next.js（3000）
- 日志：`backend.log` / `celery.log` / `frontend.log`（已 gitignore）
- **本地代理**：当前脚本默认走 `127.0.0.1:7897`；不用代理时需注释或导出空字符串

## 生产部署（待定）

未来需要落地：

- 镜像化（backend / frontend / worker 分镜像）
- 数据库迁移在部署阶段单独执行（`alembic upgrade head`）
- LangSmith / OpenAI API key 走 secret 管理，不进镜像
- 前端 `NEXT_PUBLIC_*` 与 Clerk 公私钥分环境注入

## Release / Rollback workflow

- 走 `.ai/workflows/release.yaml`：planning → review → release → verification → done
- 回滚走 `.ai/workflows/rollback.yaml`：planning → rollback → verification → done
- 紧急修复走 `.ai/workflows/hotfix.yaml`：planning → implementation → testing → restored → review → done
