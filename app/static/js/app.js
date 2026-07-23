import { api, getToken, setToken, clearToken } from "./api.js";
import { renderMarkdown } from "./markdown.js";
import { startMatrixRain } from "./matrix.js";

startMatrixRain(document.getElementById("matrix-bg"));

// ---------- elements ----------
const authView = document.getElementById("auth-view");
const appView = document.getElementById("app-view");
const authError = document.getElementById("auth-error");
const loginForm = document.getElementById("login-form");
const signupForm = document.getElementById("signup-form");
const tabs = document.querySelectorAll(".tab");

const chatListEl = document.getElementById("chat-list");
const newChatBtn = document.getElementById("new-chat");
const userNameEl = document.getElementById("user-name");
const logoutBtn = document.getElementById("logout");

const messagesEl = document.getElementById("messages");
const voiceStatusEl = document.getElementById("voice-status");
const textInput = document.getElementById("text-input");
const sendBtn = document.getElementById("send");
const uploadBtn = document.getElementById("upload-btn");
const fileInput = document.getElementById("file-input");
const micBtn = document.getElementById("mic");
const player = document.getElementById("player");

// ---------- state ----------
let chats = [];
let activeChatId = null;
let mediaRecorder = null;
let audioChunks = [];
let recording = false;
let voiceBusy = false;

// ---------- auth ----------

tabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    tabs.forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    const isLogin = tab.dataset.tab === "login";
    loginForm.hidden = !isLogin;
    signupForm.hidden = isLogin;
    authError.textContent = "";
  });
});

loginForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  authError.textContent = "";
  try {
    const res = await api.login(
      document.getElementById("login-email").value.trim(),
      document.getElementById("login-password").value
    );
    setToken(res.access_token);
    await enterApp(res.user);
  } catch (err) {
    authError.textContent = err.message;
  }
});

signupForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  authError.textContent = "";
  try {
    const res = await api.signup(
      document.getElementById("signup-email").value.trim(),
      document.getElementById("signup-password").value,
      document.getElementById("signup-name").value.trim()
    );
    setToken(res.access_token);
    await enterApp(res.user);
  } catch (err) {
    authError.textContent = err.message;
  }
});

logoutBtn.addEventListener("click", () => {
  clearToken();
  activeChatId = null;
  chats = [];
  authView.hidden = false;
  appView.hidden = true;
});

async function enterApp(user) {
  userNameEl.textContent = user.name;
  authView.hidden = true;
  appView.hidden = false;
  await refreshChats();
  if (chats.length === 0) {
    await createChat();
  } else {
    await selectChat(chats[0].id);
  }
}

(async function tryResume() {
  if (!getToken()) return;
  try {
    const user = await api.me();
    await enterApp(user);
  } catch {
    clearToken();
  }
})();

// ---------- chats ----------

async function refreshChats() {
  chats = await api.listChats();
  renderChatList();
}

function renderChatList() {
  chatListEl.innerHTML = "";
  for (const chat of chats) {
    const item = document.createElement("div");
    item.className = "chat-item" + (chat.id === activeChatId ? " active" : "");
    const title = document.createElement("span");
    title.className = "chat-item__title";
    title.textContent = chat.title;
    const del = document.createElement("button");
    del.className = "chat-item__delete";
    del.textContent = "×";
    del.title = "delete chat";
    del.addEventListener("click", async (e) => {
      e.stopPropagation();
      await api.deleteChat(chat.id);
      await refreshChats();
      if (activeChatId === chat.id) {
        chats.length ? await selectChat(chats[0].id) : await createChat();
      }
    });
    item.appendChild(title);
    item.appendChild(del);
    item.addEventListener("click", () => selectChat(chat.id));
    chatListEl.appendChild(item);
  }
}

newChatBtn.addEventListener("click", createChat);

async function createChat() {
  const chat = await api.createChat();
  await refreshChats();
  await selectChat(chat.id);
}

async function selectChat(chatId) {
  activeChatId = chatId;
  renderChatList();
  const messages = await api.getMessages(chatId);
  messagesEl.innerHTML = "";
  if (messages.length === 0) {
    messagesEl.innerHTML = '<div class="messages__hint">&gt; start a conversation — type, talk, or drop in a file</div>';
  }
  for (const m of messages) renderMessage(m.role, m.content);
  scrollToBottom();
}

// ---------- message rendering ----------

function clearHint() {
  messagesEl.querySelector(".messages__hint")?.remove();
}

function renderMessage(role, content) {
  clearHint();
  const bubble = document.createElement("div");
  bubble.className = `msg msg--${role}`;

  if (role === "user" && content.startsWith("Uploaded file: ")) {
    const [firstLine] = content.split("\n");
    bubble.innerHTML = `<p>📎 ${firstLine.replace("Uploaded file: ", "")}</p>`;
  } else if (role === "assistant") {
    const { html, editedFile } = renderMarkdown(content);
    bubble.innerHTML = html;
    if (editedFile) bubble.appendChild(makeDownloadButton(editedFile));
  } else {
    bubble.innerHTML = renderMarkdown(content).html;
  }

  messagesEl.appendChild(bubble);
  return bubble;
}

function makeDownloadButton(content) {
  const wrap = document.createElement("div");
  wrap.className = "msg__meta";
  const btn = document.createElement("button");
  btn.className = "download-btn";
  btn.textContent = "download revised file";
  btn.addEventListener("click", () => {
    const blob = new Blob([content], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "revised-file.txt";
    a.click();
    URL.revokeObjectURL(url);
  });
  wrap.appendChild(btn);
  return wrap;
}

function scrollToBottom() {
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

// ---------- text chat (streaming) ----------

textInput.addEventListener("input", () => {
  textInput.style.height = "auto";
  textInput.style.height = Math.min(textInput.scrollHeight, 160) + "px";
});

textInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendText();
  }
});
sendBtn.addEventListener("click", sendText);

async function sendText() {
  const content = textInput.value.trim();
  if (!content || !activeChatId) return;
  textInput.value = "";
  textInput.style.height = "auto";

  renderMessage("user", content);
  const wasNewChat = chats.find((c) => c.id === activeChatId)?.title === "New chat";

  const assistantBubble = document.createElement("div");
  assistantBubble.className = "msg msg--assistant msg--streaming";
  clearHint();
  messagesEl.appendChild(assistantBubble);
  scrollToBottom();

  let full = "";
  try {
    for await (const event of api.streamMessage(activeChatId, content)) {
      if (event.error) throw new Error(event.error);
      if (event.delta) {
        full += event.delta;
        assistantBubble.innerHTML = renderMarkdown(full).html;
        scrollToBottom();
      }
      if (event.done) break;
    }
    assistantBubble.classList.remove("msg--streaming");
    const { editedFile } = renderMarkdown(full);
    if (editedFile) assistantBubble.appendChild(makeDownloadButton(editedFile));
  } catch (err) {
    assistantBubble.classList.remove("msg--streaming");
    assistantBubble.classList.add("msg--error");
    assistantBubble.textContent = `error: ${err.message}`;
  }

  if (wasNewChat) await refreshChats();
}

// ---------- file upload ----------

uploadBtn.addEventListener("click", () => fileInput.click());

fileInput.addEventListener("change", async () => {
  const file = fileInput.files[0];
  fileInput.value = "";
  if (!file || !activeChatId) return;

  voiceStatusEl.textContent = `uploading ${file.name}…`;
  try {
    await api.uploadFile(activeChatId, file);
    await selectChat(activeChatId);
    await refreshChats();
    voiceStatusEl.textContent = "file uploaded — ask a question or request changes";
  } catch (err) {
    voiceStatusEl.textContent = `upload failed: ${err.message}`;
  }
});

// ---------- voice ----------

micBtn.addEventListener("click", async () => {
  if (voiceBusy || !activeChatId) return;

  // Barge-in: stop any agent speech immediately so the user can jump back in.
  if (!player.paused) {
    player.pause();
    player.currentTime = 0;
  }

  if (recording) {
    stopRecording();
  } else {
    try {
      await startRecording();
    } catch {
      voiceStatusEl.textContent = "microphone access denied or unavailable";
    }
  }
});

async function startRecording() {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const mimeType = MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : "";
  mediaRecorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
  audioChunks = [];
  mediaRecorder.ondataavailable = (e) => { if (e.data.size > 0) audioChunks.push(e.data); };
  mediaRecorder.onstop = () => {
    stream.getTracks().forEach((t) => t.stop());
    handleRecordingStopped();
  };
  mediaRecorder.start();
  recording = true;
  micBtn.classList.add("recording");
  voiceStatusEl.textContent = "listening… click mic to stop";
}

function stopRecording() {
  if (mediaRecorder && recording) {
    mediaRecorder.stop();
    recording = false;
    micBtn.classList.remove("recording");
  }
}

async function handleRecordingStopped() {
  if (audioChunks.length === 0) {
    voiceStatusEl.textContent = "";
    return;
  }
  const blob = new Blob(audioChunks, { type: audioChunks[0].type || "audio/webm" });

  voiceBusy = true;
  micBtn.classList.add("busy");
  voiceStatusEl.textContent = "thinking…";

  const wasNewChat = chats.find((c) => c.id === activeChatId)?.title === "New chat";

  try {
    const data = await api.voiceTurn(activeChatId, blob);
    renderMessage("user", data.transcript);
    renderMessage("assistant", data.reply_text);
    scrollToBottom();

    const audioBytes = Uint8Array.from(atob(data.audio_base64), (c) => c.charCodeAt(0));
    player.src = URL.createObjectURL(new Blob([audioBytes], { type: "audio/wav" }));
    voiceStatusEl.textContent = "speaking… click mic to interrupt";
    await player.play();
    player.onended = () => { voiceStatusEl.textContent = ""; };
  } catch (err) {
    voiceStatusEl.textContent = `error: ${err.message}`;
  } finally {
    voiceBusy = false;
    micBtn.classList.remove("busy");
    if (wasNewChat) await refreshChats();
  }
}
