/** 用户个人资料的 API 封装。 */

export type UserProfile = {
  id: string;
  email: string;
  target_role: string | null;
  resume_filename: string | null;
  resume_text: string | null;
  evaluation: string | null;
  total_sessions: number;
};

export type UserProfileResponse = {
  code: number;
  msg: string;
  data: UserProfile;
};

/** Dashboard 看板数据。 */
export type DashboardData = {
  session_count: number;
  total_duration_hours: number;
  average_score: number;
  weaknesses_improved_count: number;
  radar: {
    technical_depth: number;
    quantified_results: number;
    failure_tradeoffs: number;
    structure: number;
  };
  growth_trajectory: {
    session_index: number;
    score: number;
  }[];
  weaknesses: {
    tag: string;
    severity: "severe" | "warn" | "info";
  }[];
};

const getBaseUrl = () => {
  return "";
};

/** 统一处理响应。 */
async function handleResponse<T>(
  response: Response,
  errorMsg: string,
): Promise<T> {
  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw new Error(`${errorMsg}: ${response.status} ${errorBody.msg || ""}`);
  }
  const res = await response.json();
  return res.data;
}

/** 获取用户 Dashboard 看板数据。 */
export async function fetchDashboardData({
  token,
}: {
  token: string;
}): Promise<DashboardData> {
  const response = await fetch(`${getBaseUrl()}/api/v1/user/dashboard`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return handleResponse<DashboardData>(response, "获取 Dashboard 数据失败");
}

/** 获取用户个人配置。 */
export async function fetchUserProfile({
  token,
}: {
  token: string;
}): Promise<UserProfile> {
  const response = await fetch(`${getBaseUrl()}/api/v1/user/profile`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return handleResponse<UserProfile>(response, "获取用户资料失败");
}

/** 上传简历。 */
export async function uploadResume({
  token,
  file,
}: {
  token: string;
  file: File;
}): Promise<UserProfile> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${getBaseUrl()}/api/v1/user/resume`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  });
  return handleResponse<UserProfile>(response, "上传简历失败");
}
