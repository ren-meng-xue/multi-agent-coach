"""联调脚本：模拟前端启动一次完整的备课流。"""
import asyncio
import json
import httpx

async def main():
    # 模拟 JD
    jd_text = "字节跳动-国际化团队-后端开发工程师。要求：3年以上后端经验，精通 Python/Go，熟悉分布式系统、高并发设计。加分项：有 AI Agent 或 LangChain 经验。"
    
    url = "http://localhost:8000/api/v1/prepare/launch"
    data = {
        "user_direction": "AI Agent 工程师",
        "jd_text": jd_text,
    }
    
    # 获取 dev bypass token (假设 dev_auth_bypass=True 已经配置)
    headers = {"Authorization": "Bearer dev-auth-bypass-token"}
    
    print(f"--- 启动备课流 ---")
    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream("POST", url, data=data, headers=headers) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    event = data.get("event")
                    node = data.get("data", {}).get("node")
                    label = data.get("data", {}).get("label")
                    
                    if event == "node_start":
                        print(f"▶️  节点开始: {label or node}")
                    elif event == "node_done":
                        print(f"✅ 节点完成: {node}")
                        summary = data.get("data", {}).get("summary")
                        if summary:
                            print(f"   摘要: {summary}")
                    elif event == "phase_change":
                        print(f"🔄 阶段切换: {data.get('data', {}).get('turn_id')}")
                    elif event == "done":
                        print(f"🏁 备课完成")
                        # print(json.dumps(data.get("data"), indent=2, ensure_ascii=False))
                    elif event == "turn_delta":
                        pass # 忽略 token 流

if __name__ == "__main__":
    asyncio.run(main())
