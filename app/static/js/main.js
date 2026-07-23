const micBtn = document.getElementById("mic");
const statusEl = document.getElementById("status");
const ringsEl = document.getElementById("rings");
const logEl = document.getElementById("log");
const resetBtn = document.getElementById("reset");
const player = document.getElementById("player");

let sessionId = localStorage.getItem("voice-agent-session");
let mediaRecorder = null;
let chunks = [];
let recording = false;
let busy = false;

async function ensureSession() {
  if (sessionId) return sessionId;
  const res = await fetch("/api/session", { method: "POST" });
  const data = await res.json();
  sessionId = data.session_id;
  localStorage.setItem("voice-agent-session", sessionId);
  return sessionId;
}

function setStatus(text) {
  statusEl.textContent = text;
}

function appendLog(role, text) {
  logEl.querySelector(".log__hint")?.remove();
  const entry = document.createElement("div");
  entry.className = `log__entry log__entry--${role}`;
  const label = document.createElement("span");
  label.className = "log__role";
  label.textContent = role === "user" ? "you" : role === "agent" ? "agent" : "error";
  const text_ = document.createElement("div");
  text_.className = "log__text";
  text_.textContent = text;
  entry.appendChild(label);
  entry.appendChild(text_);
  logEl.appendChild(entry);
  logEl.scrollTop = logEl.scrollHeight;
}

async function startRecording() {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const mimeType = MediaRecorder.isTypeSupported("audio/webm")
    ? "audio/webm"
    : "";
  mediaRecorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
  chunks = [];
  mediaRecorder.ondataavailable = (e) => { if (e.data.size > 0) chunks.push(e.data); };
  mediaRecorder.onstop = () => {
    stream.getTracks().forEach((t) => t.stop());
    handleRecordingStopped();
  };
  mediaRecorder.start();
  recording = true;
  micBtn.classList.add("recording");
  ringsEl.hidden = false;
  setStatus("listening… click to stop");
}

function stopRecording() {
  if (mediaRecorder && recording) {
    mediaRecorder.stop();
    recording = false;
    micBtn.classList.remove("recording");
    ringsEl.hidden = true;
  }
}

async function handleRecordingStopped() {
  if (chunks.length === 0) {
    setStatus("click to talk");
    return;
  }
  const blob = new Blob(chunks, { type: chunks[0].type || "audio/webm" });
  await sendAudio(blob);
}

async function sendAudio(blob) {
  busy = true;
  micBtn.classList.add("busy");
  setStatus("thinking…");

  const form = new FormData();
  form.append("session_id", await ensureSession());
  form.append("audio", blob, "turn.webm");

  try {
    const res = await fetch("/api/voice", { method: "POST", body: form });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "request failed");
    }
    const data = await res.json();
    appendLog("user", data.transcript);
    appendLog("agent", data.reply_text);

    const audioBytes = Uint8Array.from(atob(data.audio_base64), (c) => c.charCodeAt(0));
    const audioBlob = new Blob([audioBytes], { type: "audio/wav" });
    player.src = URL.createObjectURL(audioBlob);
    setStatus("speaking…");
    await player.play();
    player.onended = () => setStatus("click to talk");
  } catch (e) {
    appendLog("error", e.message || "something went wrong");
    setStatus("click to talk");
  } finally {
    busy = false;
    micBtn.classList.remove("busy");
  }
}

micBtn.addEventListener("click", async () => {
  if (busy) return;
  if (recording) {
    stopRecording();
  } else {
    try {
      await startRecording();
    } catch (e) {
      appendLog("error", "microphone access denied or unavailable");
    }
  }
});

resetBtn.addEventListener("click", async () => {
  if (!sessionId) return;
  const form = new FormData();
  form.append("session_id", sessionId);
  await fetch("/api/reset", { method: "POST", body: form });
  logEl.innerHTML = '<div class="log__hint">&gt; conversation history will appear here</div>';
  setStatus("session reset — click to talk");
});
