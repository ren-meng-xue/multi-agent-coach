/** 教练复盘 SSE 事件。 */
export type CoachReviewEvent = 
  | { event: "review_token"; data: { token: string } }
  | { event: "plan_done"; data: CoachPlanData }
  | { event: "final"; data: { plan_id: string } }
  | { event: "error"; data: { detail: string } };

/** 结构化训练计划数据。 */
export interface CoachPlanData {
  summary: string;
  strengths: string[];
  weaknesses: string[];
  next_focus_areas: string[];
  recommended_role: string | null;
  recommended_question_types: string[];
}

/** 教练计划 API 响应。 */
export interface CoachPlanResponse {
  id: string;
  session_id: string | null;
  plan_json: CoachPlanData;
  created_at: string;
  consumed: boolean;
}

/** 用户阶段。 */
export type UserStage = "prepare" | "interview" | "coach";

/** 获取用户当前阶段。 */
export async function fetchUserStage({ token }: { token: string }): Promise<UserStage> {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL || "";
  const cleanBaseUrl = baseUrl.replace(/\/$/, "");
  const resp = await fetch(`${cleanBaseUrl}/api/v1/user/stage`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!resp.ok) throw new Error(`Failed to fetch user stage: ${resp.statusText}`);
  const json = await resp.json();
  return json.data.stage;
}

/** 获取最新教练计划。 */
export async function fetchLatestCoachPlan({ token }: { token: string }): Promise<CoachPlanResponse | null> {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL || "";
  const cleanBaseUrl = baseUrl.replace(/\/$/, "");
  const resp = await fetch(`${cleanBaseUrl}/api/v1/coach/plans/latest`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!resp.ok) throw new Error(`Failed to fetch latest coach plan: ${resp.statusText}`);
  const json = await resp.json();
  // 后端修复后返回的是 null 或 CoachPlanResponse
  return json.data || null;
}
