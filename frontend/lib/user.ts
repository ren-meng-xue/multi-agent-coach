/** 用户个人资料与故事库的 API 封装。 */

export type UserProfile = {
  id: string;
  email: string;
  target_role: string | null;
  work_years: string | null;
};

export type UserStory = {
  id: string;
  user_id: string;
  title: string;
  role: string | null;
  tags: string[] | null;
  content_json: {
    situation?: string;
    task?: string;
    action?: string;
    result?: string;
    [key: string]: any;
  };
  created_at: string;
  updated_at: string;
};

export type UserProfileResponse = {
  code: number;
  msg: string;
  data: UserProfile;
};

export type UserStoryResponse = {
  code: number;
  msg: string;
  data: UserStory;
};

export type UserStoryListResponse = {
  code: number;
  msg: string;
  data: {
    stories: UserStory[];
  };
};

const getBaseUrl = () => {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL;
  if (!baseUrl) throw new Error("缺少后端接口配置");
  return baseUrl.replace(/\/$/, "");
};

/** 统一处理响应。 */
async function handleResponse<T>(response: Response, errorMsg: string): Promise<T> {
  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw new Error(`${errorMsg}: ${response.status} ${errorBody.msg || ""}`);
  }
  const res = await response.json();
  return res.data;
}

/** 获取用户个人配置。 */
export async function fetchUserProfile({ token }: { token: string }): Promise<UserProfile> {
  const response = await fetch(`${getBaseUrl()}/api/v1/user/profile`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return handleResponse<UserProfile>(response, "获取用户资料失败");
}

/** 更新用户个人配置。 */
export async function updateUserProfile({
  token,
  profile,
}: {
  token: string;
  profile: Partial<Pick<UserProfile, "target_role" | "work_years">>;
}): Promise<UserProfile> {
  const response = await fetch(`${getBaseUrl()}/api/v1/user/profile`, {
    method: "PATCH",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(profile),
  });
  return handleResponse<UserProfile>(response, "更新用户资料失败");
}

/** 获取故事列表。 */
export async function fetchUserStories({ token }: { token: string }): Promise<UserStory[]> {
  const response = await fetch(`${getBaseUrl()}/api/v1/user/stories`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const data = await handleResponse<{ stories: UserStory[] }>(response, "获取故事库失败");
  return data.stories;
}

/** 创建新故事。 */
export async function createUserStory({
  token,
  story,
}: {
  token: string;
  story: Omit<UserStory, "id" | "user_id" | "created_at" | "updated_at">;
}): Promise<UserStory> {
  const response = await fetch(`${getBaseUrl()}/api/v1/user/stories`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(story),
  });
  return handleResponse<UserStory>(response, "创建故事失败");
}

/** 更新故事内容。 */
export async function updateUserStory({
  token,
  storyId,
  story,
}: {
  token: string;
  storyId: string;
  story: Partial<Omit<UserStory, "id" | "user_id" | "created_at" | "updated_at">>;
}): Promise<UserStory> {
  const response = await fetch(`${getBaseUrl()}/api/v1/user/stories/${storyId}`, {
    method: "PATCH",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(story),
  });
  return handleResponse<UserStory>(response, "更新故事失败");
}

/** 删除故事。 */
export async function deleteUserStory({
  token,
  storyId,
}: {
  token: string;
  storyId: string;
}): Promise<void> {
  const response = await fetch(`${getBaseUrl()}/api/v1/user/stories/${storyId}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw new Error(`删除故事失败: ${response.status} ${errorBody.msg || ""}`);
  }
}
