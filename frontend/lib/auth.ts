import Cookies from "js-cookie";

const COOKIE_OPTS = { expires: 7, secure: process.env.NODE_ENV === "production", sameSite: "strict" as const };

export interface User {
  id: string;
  email: string;
  name: string;
  created_at: string;
}

export function saveAuth(token: string, user: User) {
  Cookies.set("axon_token", token, COOKIE_OPTS);
  Cookies.set("axon_user", JSON.stringify(user), COOKIE_OPTS);
}

export function clearAuth() {
  Cookies.remove("axon_token");
  Cookies.remove("axon_user");
}

export function getToken(): string | undefined {
  return Cookies.get("axon_token");
}

export function getUser(): User | null {
  const raw = Cookies.get("axon_user");
  if (!raw) return null;
  try {
    return JSON.parse(raw) as User;
  } catch {
    return null;
  }
}

export function isAuthenticated(): boolean {
  return !!Cookies.get("axon_token");
}
