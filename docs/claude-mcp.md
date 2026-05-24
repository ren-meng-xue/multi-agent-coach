# Claude Code MCP

本项目把 Claude Code MCP 分成本地和生产两套入口：

- `postgres-local` / `redis-local`：连接 Docker Compose 本地服务。
- `postgres-prod` / `redis-prod`：连接生产服务，通过当前 Claude 会话的环境变量注入。

## 本地

如果已经运行 `./dev.sh`，另开一个终端启动 Claude：

```bash
cd /Users/xuebao/learn/AI项目/multi-agent-coach
claude
```

如果只想启动本地 MCP 依赖并进入 Claude：

```bash
cd /Users/xuebao/learn/AI项目/multi-agent-coach
scripts/claude-mcp-local.sh
```

进入 Claude 后明确指定本地 MCP：

```text
用 postgres-local 看一下有哪些表
用 redis-local 检查 Redis 是否能连上
```

## 生产

生产连接串不写进 `.mcp.json`、README 或 git。`.mcp.json` 会提交项目级 MCP server 定义，但生产连接只引用 `PROD_DATABASE_URL` 和 `PROD_REDIS_URL`。第一次使用前，从模板创建本机私有变量文件：

```bash
cd /Users/xuebao/learn/AI项目/multi-agent-coach
cp .env.claude-mcp-prod.example .env.claude-mcp-prod.local
open -e .env.claude-mcp-prod.local
```

填入只读账号连接串：

```bash
PROD_DATABASE_URL='postgresql://只读用户名:只读密码@生产数据库地址:端口/数据库名'
PROD_REDIS_URL='redis://只读用户名:只读密码@生产Redis地址:端口/0'
```

之后每次需要生产 MCP，用脚本启动 Claude：

```bash
cd /Users/xuebao/learn/AI项目/multi-agent-coach
scripts/claude-mcp-prod.sh
```

脚本会 `source .env.claude-mcp-prod.local`，把 `PROD_DATABASE_URL` 和 `PROD_REDIS_URL` 注入当前 Claude Code 进程，然后在执行 `claude` 前显示生产连接警告。必须输入 `prod` 才会继续。普通新终端直接执行 `claude` 不会自动拥有生产连接。

如果终端里已经显式设置了 `PROD_DATABASE_URL` 或 `PROD_REDIS_URL`，脚本会优先使用终端里的值；否则使用 `.env.claude-mcp-prod.local`。

如果是在明确受控的自动化场景，可以用环境变量跳过交互确认：

```bash
ALLOW_PROD_MCP=1 scripts/claude-mcp-prod.sh
```

进入 Claude 后明确指定生产 MCP：

```text
用 postgres-prod 看一下生产数据库有哪些表
用 redis-prod 检查生产 Redis 是否能连上
```

## 只读账号

生产 MCP 必须优先使用只读账号，避免误删、误改生产数据。

PostgreSQL 只读账号示例，需要用管理员账号执行：

```sql
CREATE USER readonly_user WITH PASSWORD '替换为强密码';

GRANT CONNECT ON DATABASE railway TO readonly_user;
GRANT USAGE ON SCHEMA public TO readonly_user;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO readonly_user;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO readonly_user;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
GRANT SELECT ON TABLES TO readonly_user;
```

Redis 6+ 只读 ACL 用户示例：

```text
ACL SETUSER readonly on >强密码 ~* +@read -@write -@dangerous
```

## 安全边界

`.env.claude-mcp-prod.local` 在 `.gitignore` 中声明忽略，不能提交。`.mcp.json`、`.env.claude-mcp-prod.example`、`scripts/claude-mcp-local.sh` 和 `scripts/claude-mcp-prod.sh` 是可提交的项目文件，不能写入真实密钥。

`.claude/settings.local.json` 配置了读取保护：阻断直接读取 `.env*`、`.env.claude-mcp-prod.local`，也阻断 `env`、`printenv`、`export -p`、`set` 等常见环境变量泄露命令。

这些规则是防误读和防误打印，不是生产密钥的绝对隔离机制。生产变量一旦加载进 Claude Code 进程，子进程和 MCP server 可能继承这些变量；因此生产连接必须使用只读账号。
