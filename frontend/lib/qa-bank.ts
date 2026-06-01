/** 面试题库 API 封装。 */

export type QABankSummary = {
  technical: number;
  hr: number;
  project: number;
  total: number;
};

export type QABankUploadResult = {
  imported: { technical?: number; hr?: number; project?: number };
  skipped: number;
};

const getBaseUrl = () => {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL;
  if (!baseUrl) throw new Error("缺少后端接口配置");
  return baseUrl.replace(/\/$/, "");
};

/** 获取题库各分类条目数。 */
export async function fetchQABankSummary({
  token,
}: {
  token: string;
}): Promise<QABankSummary> {
  const res = await fetch(`${getBaseUrl()}/api/v1/user/qa-bank/summary`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error("获取题库摘要失败");
  const json = await res.json();
  return json.data as QABankSummary;
}

/** 触发浏览器下载题库 Markdown 模板。 */
export async function downloadQABankTemplate({
  token,
  category,
}: {
  token: string;
  category?: string;
}): Promise<void> {
  const urlParams = category ? `?category=${category}` : "";
  const res = await fetch(
    `${getBaseUrl()}/api/v1/user/qa-bank/template${urlParams}`,
    {
      headers: { Authorization: `Bearer ${token}` },
    }
  );
  if (!res.ok) throw new Error("下载模板失败");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  const filename = category
    ? `面试题库模板_${category}.md`
    : "面试题库模板.md";
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

/** 上传填好的 Markdown 文件，解析并入库。 */
export async function uploadQABank({
  token,
  file,
}: {
  token: string;
  file: File;
}): Promise<QABankUploadResult> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${getBaseUrl()}/api/v1/user/qa-bank/upload`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.msg || "上传失败");
  }
  const json = await res.json();
  return json.data as QABankUploadResult;
}
