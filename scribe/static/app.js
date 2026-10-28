"use strict";
// Enregistre le micro en PCM 16 kHz mono dans le navigateur, ou importe un fichier audio existant,
// l'envoie au serveur local, puis affiche la transcription. Aucune autre destination réseau.

const TARGET_RATE = 16000;
const $ = (id) => document.getElementById(id);
const recordBtn = $("record"), message = $("message"), timer = $("timer");

let modelReady = false;
let recorder = null; // { ctx, stream, source, node, chunks, tick, wakeLock }
let transcribing = false;
let importLimits = { max_bytes: 500 * 2 ** 20, max_seconds: 4 * 3600, extensions: [] };
let pickedFile = null;
const dropZone = $("drop"), fileInput = $("file"), importBtn = $("importBtn");

function say(text, isError = false) {
  message.textContent = text;
  message.className = isError ? "error" : "";
}

function fmtDate(iso) {
  return iso ? new Date(iso).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" }) : "—";
}

function fmtDuration(seconds) {
  const s = Math.floor(seconds), h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60);
  const pad = (n) => String(n).padStart(2, "0");
  return (h ? h + ":" : "") + pad(m) + ":" + pad(s % 60);
}

// --- Rééchantillonnage au fil de l'eau (fréquence du micro -> 16 kHz), sortie Int16 -------
function makeResampler(inputRate) {
  const step = inputRate / TARGET_RATE;
  let pos = 0;  // position du prochain échantillon de sortie, relative au bloc courant
  let prev = 0; // dernier échantillon du bloc précédent (indice -1)
  return (input) => {
    const n = input.length, out = [];
    while (pos <= n - 1) {
      const i = Math.floor(pos), frac = pos - i;
      const a = i < 0 ? prev : input[i];
      const b = i + 1 < n ? input[i + 1] : a;
      const v = Math.max(-1, Math.min(1, a + (b - a) * frac));
      out.push(v < 0 ? v * 0x8000 : v * 0x7fff);
      pos += step;
    }
    pos -= n;
    prev = input[n - 1];
    return Int16Array.from(out);
  };
}

function encodeWav(chunks) {
  const samples = chunks.reduce((n, c) => n + c.length, 0);
  const buffer = new ArrayBuffer(44 + samples * 2), v = new DataView(buffer);
  const str = (o, s) => [...s].forEach((ch, i) => v.setUint8(o + i, ch.charCodeAt(0)));
  str(0, "RIFF"); v.setUint32(4, 36 + samples * 2, true); str(8, "WAVE"); str(12, "fmt ");
  v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true);
  v.setUint32(24, TARGET_RATE, true); v.setUint32(28, TARGET_RATE * 2, true);
  v.setUint16(32, 2, true); v.setUint16(34, 16, true); str(36, "data"); v.setUint32(40, samples * 2, true);
  let offset = 44;
  for (const c of chunks) { new Int16Array(buffer, offset, c.length).set(c); offset += c.length * 2; }
  return new Blob([buffer], { type: "audio/wav" });
}

// --- Enregistrement -----------------------------------------------------------------------
async function startRecording() {
  if (!window.isSecureContext || !navigator.mediaDevices) {
    say("Micro indisponible : la page doit être ouverte en HTTPS (ou sur localhost). " +
        "Pour un téléphone, lancez le PC avec « python run.py --lan ».", true);
    return;
  }
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: false, noiseSuppression: false, autoGainControl: true },
    });
  } catch (err) {
    const reasons = {
      NotAllowedError: "Accès au micro refusé. Autorisez le micro pour ce site dans le navigateur.",
      NotFoundError: "Aucun micro détecté.",
      NotReadableError: "Le micro est utilisé par une autre application.",
    };
    say(reasons[err.name] || "Impossible d'ouvrir le micro : " + err.message, true);
    return;
  }
  const ctx = new AudioContext();
  await ctx.audioWorklet.addModule("/static/capture-worklet.js");
  const source = ctx.createMediaStreamSource(stream);
  const node = new AudioWorkletNode(ctx, "capture-processor");
  const chunks = [], resample = makeResampler(ctx.sampleRate);
  node.port.onmessage = (e) => chunks.push(resample(e.data));
  source.connect(node);
  const started = Date.now();
  const tick = setInterval(() => { timer.textContent = fmtDuration((Date.now() - started) / 1000); }, 500);
  let wakeLock = null;
  try { wakeLock = await navigator.wakeLock?.request("screen"); } catch { /* facultatif */ }
  recorder = { ctx, stream, source, node, chunks, tick, wakeLock };
  recordBtn.textContent = "Arrêter";
  recordBtn.classList.add("recording");
  timer.textContent = "00:00";
  say("Enregistrement en cours… Gardez cette page ouverte (écran allumé sur téléphone).");
}

async function stopRecording() {
  const r = recorder;
  recorder = null;
  clearInterval(r.tick);
  r.source.disconnect(); r.node.disconnect();
  r.stream.getTracks().forEach((t) => t.stop());
  await r.ctx.close();
  try { await r.wakeLock?.release(); } catch { /* déjà relâché */ }
  recordBtn.classList.remove("recording");
  recordBtn.textContent = "Enregistrer";
  await sendForTranscription(encodeWav(r.chunks));
}

async function sendForTranscription(wav) {
  await runTranscription(async () => {
    say("Envoi de l'audio au serveur local…");
    const form = new FormData();
    form.append("file", wav, "audio.wav");
    const res = await fetch("/api/transcribe", { method: "POST", body: form });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(body.detail || "Erreur serveur " + res.status);
    return body;
  });
}

// Envoie le fichier brut (sans le charger en mémoire) avec une progression d'envoi.
function uploadFile(file) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/import");
    xhr.setRequestHeader("Content-Type", "application/octet-stream");
    xhr.setRequestHeader("X-Filename", encodeURIComponent(file.name));
    const bar = $("jobProgress");
    bar.classList.remove("hidden"); bar.max = file.size; bar.value = 0;
    xhr.upload.onprogress = (e) => {
      if (!e.lengthComputable) return;
      bar.value = e.loaded;
      say(`Envoi du fichier au serveur local… ${Math.round((100 * e.loaded) / e.total)} %`);
    };
    xhr.onerror = () => reject(new Error("Failed to fetch"));
    xhr.onload = () => {
      let body = {};
      try { body = JSON.parse(xhr.responseText); } catch { /* corps non JSON */ }
      if (xhr.status >= 200 && xhr.status < 300) resolve(body);
      else reject(new Error(body.detail || xhr.responseText || "Erreur serveur " + xhr.status));
    };
    xhr.send(file);
  });
}

// `start` envoie l'audio et renvoie { job_id, audio_seconds } ; on suit ensuite la tâche.
async function runTranscription(start) {
  transcribing = true;
  refreshButton();
  const bar = $("jobProgress");
  try {
    const body = await start();
    bar.classList.remove("hidden"); bar.value = 0; bar.removeAttribute("max");
    while (true) {
      await new Promise((ok) => setTimeout(ok, 1000));
      const res = await fetch("/api/jobs/" + body.job_id);
      if (!res.ok) throw new Error("Suivi de la transcription impossible (erreur " + res.status + ").");
      const job = await res.json();
      if (job.status === "error") throw new Error(job.error);
      if (job.status === "done") { showResult(job); break; }
      if (job.status === "decoding") {
        say("Décodage du fichier audio…" + (job.decoded_seconds ? ` (${fmtDuration(job.decoded_seconds)})` : ""));
        continue;
      }
      if (job.total) { bar.max = job.total; bar.value = job.done; }
      const secs = job.audio_seconds || body.audio_seconds;
      say(`Transcription en cours${secs ? ` (${fmtDuration(secs)} d'audio)` : ""}` +
          (job.total ? ` — segment ${job.done}/${job.total}` : "…"));
    }
  } catch (err) {
    say(err.message === "Failed to fetch"
      ? "Serveur injoignable : le PC est-il allumé et l'appli lancée ?" : err.message, true);
  } finally {
    bar.classList.add("hidden");
    transcribing = false;
    refreshButton();
  }
}

function showResult(job) {
  $("resultCard").classList.remove("hidden");
  $("transcript").value = job.text || "(aucune parole reconnue)";
  const m = job.meta;
  $("resultMeta").textContent = `${fmtDuration(m.audio_seconds)} d'audio transcrites en ` +
    `${m.processing_seconds.toFixed(1)} s · enregistré dans data/${job.folder}/`;
  say("Transcription terminée.");
}

recordBtn.addEventListener("click", () => (recorder ? stopRecording() : startRecording()));
$("copy").addEventListener("click", async () => {
  try { await navigator.clipboard.writeText($("transcript").value); say("Texte copié."); }
  catch { $("transcript").select(); say("Sélectionnez le texte puis copiez-le."); }
});

// --- Import d'un fichier ------------------------------------------------------------------
function fmtSize(bytes) {
  return bytes >= 2 ** 30 ? (bytes / 2 ** 30).toFixed(2) + " Go"
    : bytes >= 2 ** 20 ? (bytes / 2 ** 20).toFixed(1) + " Mo" : Math.max(1, Math.round(bytes / 1024)) + " Ko";
}

function clearPicked() {
  pickedFile = null;
  fileInput.value = "";
  $("fileInfo").classList.add("hidden");
  importBtn.classList.add("hidden");
  $("clearFile").classList.add("hidden");
}

// Durée lue par le navigateur (facultative : certains formats ne sont pas lisibles côté page).
function readDuration(file) {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(file), media = document.createElement("audio");
    const done = (d) => { URL.revokeObjectURL(url); resolve(Number.isFinite(d) ? d : null); };
    media.preload = "metadata";
    media.onloadedmetadata = () => done(media.duration);
    media.onerror = () => done(null);
    setTimeout(() => done(null), 4000);
    media.src = url;
  });
}

async function pickFile(file) {
  if (!file || recorder || transcribing) return;
  clearPicked();
  const ext = "." + (file.name.split(".").pop() || "").toLowerCase();
  if (importLimits.extensions.length && !importLimits.extensions.includes(ext)) {
    say("Format non pris en charge (" + ext + "). Formats acceptés : " +
        importLimits.extensions.join(", ") + ".", true);
    return;
  }
  if (file.size === 0) { say("Le fichier est vide.", true); return; }
  if (file.size > importLimits.max_bytes) {
    say(`Fichier trop volumineux (${fmtSize(file.size)}) : maximum ${fmtSize(importLimits.max_bytes)}.`, true);
    return;
  }
  pickedFile = file;
  const info = $("fileInfo");
  info.textContent = `${file.name} — ${fmtSize(file.size)}`;
  info.classList.remove("hidden");
  importBtn.classList.remove("hidden");
  $("clearFile").classList.remove("hidden");
  say("Fichier prêt. Appuyez sur « Transcrire ce fichier ».");
  const duration = await readDuration(file);
  if (pickedFile !== file) return;
  if (duration) {
    info.textContent += ` — ${fmtDuration(duration)}`;
    if (duration > importLimits.max_seconds) {
      say(`Fichier trop long (${fmtDuration(duration)}) : maximum ${importLimits.max_seconds / 3600} h.`, true);
      clearPicked();
    }
  }
}

fileInput.addEventListener("change", () => pickFile(fileInput.files[0]));
importBtn.addEventListener("click", () => {
  const file = pickedFile;
  if (file) runTranscription(() => uploadFile(file)).then(clearPicked);
});
$("clearFile").addEventListener("click", () => { clearPicked(); say("Prêt."); });
for (const type of ["dragenter", "dragover"]) {
  dropZone.addEventListener(type, () => { if (!fileInput.disabled) dropZone.classList.add("over"); });
}
for (const type of ["dragleave", "drop"]) {
  dropZone.addEventListener(type, () => dropZone.classList.remove("over"));
}
dropZone.addEventListener("drop", (e) => { if (!fileInput.disabled) pickFile(e.dataTransfer.files[0]); });
// Évite que le navigateur ouvre le fichier s'il est lâché à côté de la zone.
for (const type of ["dragover", "drop"]) window.addEventListener(type, (e) => e.preventDefault());

// --- État du modèle -----------------------------------------------------------------------
function refreshButton() {
  recordBtn.disabled = !recorder && (!modelReady || transcribing);
  const busy = !!recorder || transcribing;
  importBtn.disabled = !modelReady || busy;
  $("clearFile").disabled = transcribing;
  fileInput.disabled = busy;
  dropZone.classList.toggle("disabled", busy);
}

async function refreshStatus() {
  let s;
  try { s = await (await fetch("/api/status")).json(); }
  catch { if (!recorder) say("Serveur local injoignable.", true); return; }
  const m = s.model;
  if (s.import) importLimits = s.import;
  $("dropHint").textContent = "mp3, wav, m4a, ogg, flac, mp4… " +
    `(max ${Math.round(importLimits.max_bytes / 2 ** 20)} Mo, ${importLimits.max_seconds / 3600} h)`;
  const wasReady = modelReady;
  modelReady = s.phase === "ready";
  $("mName").textContent = m.repo_id;
  $("mRev").textContent = m.revision
    ? `${m.revision.slice(0, 10)} (publiée le ${fmtDate(m.revision_date)})` : "aucune";
  $("mDownloaded").textContent = fmtDate(m.downloaded_at);
  let check = "jamais";
  if (m.last_check) {
    check = fmtDate(m.last_check) + (!m.last_check_ok ? " — échec (hors ligne ?)"
      : m.update_available ? " — mise à jour disponible" : " — à jour");
  }
  $("mCheck").textContent = check;
  $("mAuto").textContent = { off: "désactivée", check: "au démarrage (signaler)",
                             download: "au démarrage (installer)" }[s.auto_update];
  $("notice").textContent = s.notice || "";
  const p = s.progress, bar = $("dlProgress"), txt = $("dlText");
  if (p && p.total) {
    bar.classList.remove("hidden"); txt.classList.remove("hidden");
    bar.max = p.total; bar.value = p.done;
    txt.textContent = `Téléchargement : ${(p.done / 1e9).toFixed(2)} / ${(p.total / 1e9).toFixed(2)} Go`;
  } else { bar.classList.add("hidden"); txt.classList.add("hidden"); }
  const upd = $("update");
  upd.disabled = s.busy;
  upd.textContent = m.revision ? "Mettre à jour le modèle" : "Télécharger le modèle";
  if (!recorder && !transcribing) {
    if (!modelReady) say(s.message, s.phase === "error" || s.phase === "absent");
    else if (!wasReady) say("Prêt. Appuyez sur Enregistrer ou importez un fichier audio.");
  }
  refreshButton();
}

$("update").addEventListener("click", async () => {
  $("update").disabled = true;
  try {
    const r = await (await fetch("/api/model/update", { method: "POST" })).json();
    if (!r.started) $("notice").textContent = r.message;
  } catch { $("notice").textContent = "Serveur local injoignable."; }
  refreshStatus();
});

refreshStatus();
setInterval(refreshStatus, 2000);
