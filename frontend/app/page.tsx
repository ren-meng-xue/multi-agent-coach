import { redirect } from "next/navigation";

/** 将根路径转到登录页。 */
export default function Home() {
  redirect("/login");
}
