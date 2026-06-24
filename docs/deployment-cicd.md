# CI/CD 部署说明

本文档描述当前服务器架构下的自动部署流程：

```text
GitHub push
  -> Jenkins Pipeline
  -> /www/wwwroot/multi-agent-coach git pull
  -> docker compose up -d --build
```

## 1. 服务器项目配置

在服务器项目目录准备生产环境变量：

```bash
cd /www/wwwroot/multi-agent-coach
cp .env.deploy.example .env.deploy
vim .env.deploy
```

必须把 `.env.deploy` 中的占位值替换成真实值，至少包括：

```text
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY
CLERK_SECRET_KEY
OPENAI_API_KEY
FIRECRAWL_API_KEY
CLERK_JWT_KEY
CLERK_ISSUER
CLERK_JWT_AUDIENCE 或 CLERK_AUTHORIZED_PARTY
```

本地数据库和 Redis 在 Compose 网络内访问，已由 `docker-compose.yml` 固定为：

```text
DATABASE_URL=postgresql+asyncpg://coach:coach@postgres:5432/coach
REDIS_URL=redis://redis:6379/0
```

## 2. 首次手动部署验证

在接入 Jenkins 前，先在服务器手动验证 Compose：

```bash
cd /www/wwwroot/multi-agent-coach
docker compose config
docker compose up -d --build
docker compose ps
curl -fsS http://localhost:8000/api/v1/health
curl -fsS http://localhost:3000 >/dev/null
```

预期容器：

```text
coach-frontend
coach-backend
coach-worker
coach-postgres
coach-redis
```

## 3. Jenkins 接入 Docker

当前 Jenkins 容器内 `docker: not found`，需要同时满足：

```text
1. Jenkins 镜像内有 Docker CLI / Compose plugin
2. Jenkins 容器挂载宿主机 /var/run/docker.sock
```

先确认 Jenkins home 的持久化方式，避免丢失 Jenkins 配置：

```bash
docker inspect jenkins --format '{{json .Mounts}}'
```

如果现有 Jenkins 使用名为 `jenkins_home` 的 volume，可以按下面方式重建 Jenkins 容器。重建前确认 `docker inspect` 结果中的 Jenkins home volume 名称确实是 `jenkins_home`。

```bash
cd /www/wwwroot/multi-agent-coach
docker build -t coach-jenkins-docker -f infra/jenkins/Dockerfile infra/jenkins

docker stop jenkins
docker rm jenkins

docker run -d \
  --name jenkins \
  --restart unless-stopped \
  -p 8080:8080 \
  -p 50000:50000 \
  -v jenkins_home:/var/jenkins_home \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v /www/wwwroot/multi-agent-coach:/www/wwwroot/multi-agent-coach \
  coach-jenkins-docker
```

验证 Jenkins 容器内可以调用 Docker：

```bash
docker exec jenkins docker --version
docker exec jenkins docker compose version
docker exec jenkins docker ps
```

如果 `docker ps` 报 socket 权限错误，临时验证可执行：

```bash
docker exec -u root jenkins chmod 666 /var/run/docker.sock
```

更稳妥的长期做法是让容器内 `jenkins` 用户加入与宿主机 Docker socket 相同的 group id。

## 4. Jenkins Pipeline

仓库根目录已提供 `Jenkinsfile`，部署目录固定为：

```text
/www/wwwroot/multi-agent-coach
```

Pipeline 阶段：

```text
Preflight
Update Source
Build And Deploy
Verify
```

Jenkins Job 可选择：

```text
Pipeline script from SCM
Repository URL: https://github.com/ren-meng-xue/multi-agent-coach
Branch: main
Script Path: Jenkinsfile
```

## 5. GitHub Webhook

在 GitHub 仓库配置：

```text
Settings -> Webhooks -> Add webhook
Payload URL: http://服务器IP:8080/github-webhook/
Content type: application/json
Events: Just the push event
Active: checked
```

Jenkins Job 中勾选：

```text
GitHub hook trigger for GITScm polling
```

完成后推送到 `main` 分支会触发自动部署。

## 6. 常用排查命令

```bash
cd /www/wwwroot/multi-agent-coach
docker compose ps
docker compose logs -f frontend
docker compose logs -f backend
docker compose logs -f worker
docker compose logs -f postgres
docker compose logs -f redis
```
