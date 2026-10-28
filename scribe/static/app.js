"use strict";
// Enregistre le micro en PCM 16 kHz mono dans le navigateur, envoie un WAV au serveur local,
// puis affiche la transcription. Aucune autre destination réseau.

const TARGET_RATE = 16000;
const $ = (id) => document.getElementById(id);
const recordBtn = $("record"), message = $("message"), timer = $("timer");

let modelReady = false;
let recorder = null; // { ctx, stream, source, node, chunks, tick, wakeLock }
let transcribing = false;

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
  transcribing = true;
  refreshButton();
  const bar = $("jobProgress");
  say("Envoi de l'audio au serveur local…");
  try {
    const form = new FormData();
    form.append("file", wav, "audio.wav");
    const res = await fetch("/api/transcribe", { method: "POST", body: form });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(body.detail || "Erreur serveur " + res.status);
    bar.classList.remove("hidden"); bar.value = 0;
    while (true) {
      await new Promise((ok) => setTimeout(ok, 1000));
      const job = await (await fetch("/api/jobs/" + body.job_id)).json();
      if (job.status === "error") throw new Error(job.error);
      if (job.status === "done") { showResult(job); break; }
      if (job.total) { bar.max = job.total; bar.value = job.done; }
      say(`Transcription en cours (${fmtDuration(body.audio_seconds)} d'audio)` +
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

// --- État du modèle -----------------------------------------------------------------------
function refreshButton() {
  recordBtn.disabled = !recorder && (!modelReady || transcribing);
}

async function refreshStatus() {
  let s;
  try { s = await (await fetch("/api/status")).json(); }
  catch { if (!recorder) say("Serveur local injoignable.", true); return; }
  const m = s.model;
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
    else if (!wasReady) say("Prêt. Appuyez sur Enregistrer.");
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
