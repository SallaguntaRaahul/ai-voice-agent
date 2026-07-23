const TOKEN_KEY = "voice-agent-token";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

async function request(path, options = {}) {
  const headers = options.headers ? { ...options.headers } : {};
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(path, { ...options, headers });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail || detail;
    } catch {}
    throw new Error(detail);
  }
  return res;
}

async function requestJson(path, options = {}) {
  const res = await request(path, options);
  return res.status === 204 ? null : res.json();
}

export const api = {
  signup: (email, password, name) =>
    requestJson("/api/auth/signup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, name }),
    }),

  login: (email, password) =>
    requestJson("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    }),

  me: () => requestJson("/api/auth/me"),

  listChats: () => requestJson("/api/chats"),
  createChat: () => requestJson("/api/chats", { method: "POST" }),
  deleteChat: (chatId) => requestJson(`/api/chats/${chatId}`, { method: "DELETE" }),
  getMessages: (chatId) => requestJson(`/api/chats/${chatId}/messages`),

  uploadFile: (chatId, file) => {
    const form = new FormData();
    form.append("file", file);
    return requestJson(`/api/chats/${chatId}/upload`, { method: "POST", body: form });
  },

  voiceTurn: (chatId, blob) => {
    const form = new FormData();
    form.append("audio", blob, "turn.webm");
    return requestJson(`/api/chats/${chatId}/voice`, { method: "POST", body: form });
  },

  async *streamMessage(chatId, content) {
    const res = await request(`/api/chats/${chatId}/messages/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content }),
    });

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const parts = buffer.split("\n\n");
      buffer = parts.pop();
      for (const part of parts) {
        const line = part.trim();
        if (!line.startsWith("data: ")) continue;
        yield JSON.parse(line.slice(6));
      }
    }
  },
};
