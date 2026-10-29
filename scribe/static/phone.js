"use strict";
// Panneau « Connecter le téléphone ». Un clic sur le bouton ouvre l'accès téléphone sans redémarrer
// le serveur (POST /api/phone/enable) puis affiche le QR code, le lien complet avec jeton, l'empreinte
// du certificat, le choix de l'adresse et les boutons Prolonger / Arrêter / Régénérer. Les routes
// /api/phone* ne sont servies qu'au PC lui-même.

(() => {
  const RUN_LAN = ".venv\\Scripts\\python run.py --lan";
  const POLL_MS = 15000;
  const dialog = document.getElementById("phoneDialog");
  const body = document.getElementById("phoneBody");
  let selectedIp = null;
  let current = null;
  let pollTimer = null;

  function el(tag, attrs = {}, ...children) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(attrs)) {
      if (key === "class") node.className = value;
      else if (key === "text") node.textContent = value;
      else if (key in node) node[key] = value;
      else node.setAttribute(key, value);
    }
    node.append(...children.filter((c) => c != null));
    return node;
  }

  function button(text, onClick, cls = "secondary") {
    const b = el("button", { class: cls, type: "button", text });
    b.addEventListener("click", onClick);
    return b;
  }

  async function copyText(text, btn) {
    let copied = false;
    try { await navigator.clipboard.writeText(text); copied = true; } catch { /* repli ci-dessous */ }
    if (!copied) {
      const box = el("textarea", { value: text });
      document.body.append(box);
      box.select();
      try { copied = document.execCommand("copy"); } catch { copied = false; }
      box.remove();
    }
    const label = btn.dataset.label || btn.textContent;
    btn.dataset.label = label;
    btn.textContent = copied ? "Copié" : "Copie impossible";
    setTimeout(() => { btn.textContent = label; }, 1500);
  }

  function copyRow(value, label) {
    const input = el("input", { type: "text", value, readOnly: true, spellcheck: false, "aria-label": label });
    input.addEventListener("focus", () => input.select());
    const btn = el("button", { class: "secondary", type: "button", text: "Copier" });
    btn.addEventListener("click", () => copyText(value, btn));
    return el("div", { class: "copyrow" }, input, btn);
  }

  function section(title, hint, value) {
    return [el("h3", { text: title }), hint ? el("p", { class: "hint", text: hint }) : null,
            value ? copyRow(value, title) : null];
  }

  const hhmm = (epoch) => new Date(epoch * 1000).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });

  // --- Appels au serveur ------------------------------------------------------------------------
  async function call(method, path) {
    const res = await fetch(path, { method, cache: "no-store" });
    let data = {};
    try { data = await res.json(); } catch { /* corps vide ou texte */ }
    if (res.status === 403) throw Object.assign(new Error("Cette fonction n'est disponible que depuis le " +
                                                          "PC qui exécute Scribe."), { local: true });
    if (!res.ok) throw new Error(data.detail || "Erreur " + res.status);
    return data;
  }

  async function action(method, path, busyText) {
    body.querySelectorAll("button, select").forEach((n) => { n.disabled = true; });
    if (busyText) body.prepend(el("p", { class: "hint", text: busyText }));
    try { render(await call(method, path)); }
    catch (err) { if (err.local) showError(err.message); else renderFailure(err.message); }
  }

  const enable = (ip) => action("POST", "/api/phone/enable" + (ip ? "?ip=" + encodeURIComponent(ip) : ""),
                                "Ouverture de l'accès téléphone…");

  // --- Affichage --------------------------------------------------------------------------------
  function showError(message) {
    body.replaceChildren(el("p", { class: "warn", text: message }));
  }

  function renderFailure(message) {
    body.replaceChildren(
      el("p", { class: "warn", text: "L'accès téléphone n'a pas pu être ouvert : " + message }),
      el("div", { class: "actions left" }, button("Réessayer", () => enable(selectedIp), "primary")),
      el("h3", { text: "Solution de repli" }),
      el("p", { text: "1. Fermez la fenêtre du serveur Scribe (ou appuyez sur Ctrl+C dedans)." }),
      el("p", { text: "2. Dans le dossier de Scribe, lancez cette commande :" }),
      copyRow(RUN_LAN, "Commande du mode téléphone"),
      el("p", { text: "3. Ouvrez dans ce navigateur l'adresse « Sur ce PC » affichée dans la console " +
                      "(https://localhost…/?t=…), acceptez l'avertissement de certificat, puis cliquez de " +
                      "nouveau sur « Connecter le téléphone »." }),
    );
  }

  function renderOff(info) {
    const why = info.stopped_reason === "expired"
      ? "L'accès téléphone s'est arrêté automatiquement (délai écoulé)."
      : "L'accès téléphone est fermé : seul ce PC peut utiliser Scribe.";
    body.replaceChildren(
      el("p", { text: why }),
      el("div", { class: "actions left" },
         button("Ouvrir l'accès téléphone", () => enable(selectedIp), "primary")),
      el("p", { class: "hint", text: `Un nouveau lien (nouveau jeton) sera créé, valable ${info.minutes} min.` }),
    );
  }

  function troubleshooting() {
    return el("details", {}, el("summary", { text: "Le téléphone n'arrive pas à se connecter ?" }),
      el("p", { text: "• Le téléphone doit être sur le même réseau que le PC (même Wi-Fi, ou partage de " +
                      "connexion du téléphone vers le PC)." }),
      el("p", { text: "• Pare-feu Windows : au premier raccordement, Windows peut afficher « Autoriser " +
                      "l'accès ? » pour Python. Cochez « Réseaux privés » et cliquez sur Autoriser. Sur un " +
                      "poste d'entreprise, ce choix peut exiger un administrateur : sans lui, le téléphone " +
                      "n'atteint pas le PC (la page ne se charge pas, délai dépassé). La fenêtre peut aussi " +
                      "rester derrière le navigateur : regardez la barre des tâches." }),
      el("p", { text: "• Les Wi-Fi d'entreprise ou « invités » isolent souvent les appareils entre eux : " +
                      "utilisez alors le partage de connexion du téléphone." }),
      el("p", { text: "• Si rien n'y fait : solution de repli « " + RUN_LAN + " » (voir README)." }));
  }

  function renderAccess(info) {
    const hot = info.mode === "hot";
    if (hot) selectedIp = info.active_ip;
    const chosen = info.addresses.find((a) => a.ip === selectedIp)
      || info.addresses.find((a) => a.recommended) || info.addresses[0];
    selectedIp = chosen ? chosen.ip : null;
    const parts = [];

    if (hot) {
      parts.push(el("p", { class: "ok", text: `Accessible sur le réseau local jusqu'à ${hhmm(info.expires_at)}.` }),
        el("div", { class: "actions left" },
           button(`Prolonger de ${info.minutes} min`, () => action("POST", "/api/phone/extend")),
           button("Arrêter l'accès téléphone", () => action("POST", "/api/phone/disable"))));
      if (!info.verified) {
        parts.push(el("p", { class: "warn", text: "Le PC n'a pas pu vérifier qu'il répond à cette adresse : " +
                                                  "si le téléphone n'y arrive pas, choisissez une autre adresse." }));
      }
      if (info.cert_regenerated) {
        parts.push(el("p", { class: "hint", text: "Le certificat a été recréé pour cette adresse : une appli " +
                                                  "déjà raccordée demandera de confirmer la nouvelle empreinte." }));
      }
    } else {
      parts.push(el("p", { class: "ok", text: "Mode --lan : Scribe est accessible sur le réseau local tant que " +
                                              "le serveur tourne." }));
    }

    if (!chosen) {
      parts.push(el("p", { class: "warn", text: "Aucune adresse privée trouvée : ce PC n'est pas relié à " +
                                                "un réseau local (Wi-Fi ou Ethernet)." }));
    } else {
      const qr = chosen.qr
        ? [el("img", { class: "qr", src: chosen.qr, alt: "QR code du lien complet" }),
           el("p", { class: "hint center", text: "Scannez-le avec l'appareil photo du téléphone. Avec l'appli " +
             "Scribe : copiez le lien affiché et collez-le dans l'appli. Sans l'appli : ouvrez-le dans le " +
             "navigateur et acceptez l'avertissement de certificat. QR généré sur ce PC." })]
        : [el("p", { class: "hint", text: "QR code indisponible (bibliothèque « segno » non installée : " +
                                          "pip install -r requirements.txt)." })];
      parts.push(...qr, ...section("Lien complet", "À coller dans le champ « Adresse » de l'appli Scribe : le " +
                                                   "jeton est extrait tout seul.", chosen.url));

      if (info.addresses.length > 1) {
        const select = el("select", { "aria-label": "Adresse du PC sur le réseau" });
        for (const a of info.addresses) {
          const tags = [a.kind, a.recommended ? "recommandée" : null].filter(Boolean).join(", ");
          select.append(el("option", { value: a.ip, selected: a.ip === chosen.ip,
                                       text: `${a.ip} — ${a.interface || "réseau"} (${tags})` }));
        }
        select.addEventListener("change", () => {
          selectedIp = select.value;
          if (hot) enable(select.value); else renderAccess(info);
        });
        parts.push(el("h3", { text: "Adresse du PC sur le réseau" }),
                   el("p", { class: "hint", text: "Choisissez celle du réseau du téléphone (en général le même " +
                                                  "Wi-Fi). Évitez les adaptateurs virtuels et les VPN." }), select);
      }
      if (chosen.virtual) {
        parts.push(el("p", { class: "warn", text: "Cette adresse appartient à un adaptateur virtuel ou à " +
                                                  "un VPN : le téléphone ne l'atteindra probablement pas." }));
      }
      if (!chosen.in_certificate) {
        parts.push(el("p", { class: "warn", text: "Cette adresse n'est pas dans le certificat du PC. L'appli " +
          "fonctionne quand même (elle vérifie l'empreinte), mais un navigateur afficherait un second " +
          "avertissement. Pour l'ajouter : relancer avec --lan --new-cert (l'empreinte change alors)." }));
      }
      parts.push(...section("Empreinte SHA-256 du certificat",
        "Au premier raccordement, l'appli affiche une empreinte : elle doit être identique à celle-ci.",
        info.fingerprint));
      parts.push(el("details", {}, el("summary", { text: "Saisie en deux champs (adresse + jeton)" }),
        ...section("Adresse", null, chosen.address), ...section("Jeton d'accès", null, info.token)));
      parts.push(troubleshooting());
    }

    parts.push(el("h3", { text: "Sécurité" }),
      el("p", { class: "hint", text: hot
        ? "Le lien donne accès à l'enregistrement et à l'import de Scribe, sur ce réseau seulement, jusqu'à " +
          "l'arrêt de l'accès. Ne le partagez pas. Ce panneau reste réservé à ce PC."
        : "Le jeton donne accès à Scribe sur le réseau : ne le partagez pas. Il change à chaque démarrage." }),
      button("Régénérer le jeton", regenerateToken));
    body.replaceChildren(...parts);
  }

  function regenerateToken() {
    const ok = confirm("Régénérer le jeton ?\n\nL'ancien lien cesse de fonctionner tout de suite : tout " +
                       "téléphone déjà connecté devra utiliser le nouveau.");
    if (ok) action("POST", "/api/phone/token");
  }

  function render(info) {
    current = info;
    if (info.mode === "hot" || info.mode === "lan") renderAccess(info); else renderOff(info);
  }

  // Tant que le panneau est ouvert : suit l'arrêt automatique ou une action faite ailleurs.
  async function poll() {
    if (!dialog.open || !current) return;
    try {
      const info = await call("GET", "/api/phone");
      const key = (i) => [i.mode, i.token, i.active_ip, i.expires_at].join("|");
      if (key(info) !== key(current)) render(info);
    } catch { /* erreur passagère : nouvel essai au prochain tour */ }
  }

  function openPanel() {
    body.replaceChildren();
    current = null;
    if (!dialog.open) dialog.showModal();
    enable(null);
    clearInterval(pollTimer);
    pollTimer = setInterval(poll, POLL_MS);
  }

  document.getElementById("phoneBtn").addEventListener("click", openPanel);
  document.getElementById("phoneClose").addEventListener("click", () => dialog.close());
  // Le jeton ne reste pas dans la page une fois le panneau fermé (l'accès, lui, reste ouvert).
  dialog.addEventListener("close", () => { clearInterval(pollTimer); current = null; body.replaceChildren(); });
})();
