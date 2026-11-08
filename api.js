import axios from "axios";

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "/api",
  timeout: 12000,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("foodbridge-token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export function errorMessage(error) {
  if (!error?.response && error?.code === "ERR_NETWORK") {
    return "FoodBridge could not reach the API. Start the backend server and try again.";
  }
  const detail = error?.response?.data?.detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => typeof item === "string" ? item : item?.msg)
      .filter((message) => typeof message === "string" && message.trim());
    if (messages.length) return messages.join(" ");
  }
  if (error?.response?.status >= 500) {
    return "FoodBridge encountered a server error. Please try again shortly. If the problem continues, check that the backend server is running.";
  }
  return error?.message || "Something went wrong. Please try again.";
}
