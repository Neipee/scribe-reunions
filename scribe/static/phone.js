"use strict";
// Panneau « Connecter le téléphone » : affiche, avec un bouton Copier pour chacun, l'adresse du PC,
// le jeton et l'empreinte du certificat à saisir dans l'appli Android Scribe. Les données viennent de
// /api/phone, que le serveur ne sert qu'au PC lui-même.

(() => {
  const RUN_LAN = ".venv\\Scripts\\python run.py --lan";
  const dialog = document.getElementById("phoneDialog");
  const body = document.getElementById("phoneBody");
  let selectedIp = null;

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

  async function copyText(text, button) {
    let copied = false;
    try { await navigator.clipboard.writeText(text); copied = true; } catch { /* repli ci-dessous */ }
    if (!copied) {
      const box = el("textarea", { value: text });
      document.body.append(box);
      box.select();
      try { copied = document.execCommand("copy"); } catch { copied = false; }
      box.remove();
    }
    const label = button.dataset.label || button.textContent;
    button.dataset.label = label;
    button.textContent = copied ? "Copié" : "Copie impossible";
    setTimeout(() => { button.textContent = label; }, 1500);
  }

  function copyRow(value, label) {
    const input = el("input", { type: "text", value, readOnly: true, spellcheck: false, "aria-label": label });
    input.addEventListener("focus", () => input.select());
    const button = el("button", { class: "secondary", type: "button", text: "Copier" });
    button.addEventListener("click", () => copyText(value, button));
    return el("div", { class: "copyrow" }, input, button);
  }

  function section(title, hint, value) {
    return [el("h3", { text: title }), hint ? el("p", { class: "hint", text: hint }) : null,
            value ? copyRow(value, title) : null];
  }

  function showError(message) {
    body.replaceChildren(el("p", { class: "warn", text: message }));
  }

  function renderLocalOnly() {
    body.replaceChildren(
      el("p", { text: "Le serveur tourne en mode local seulement : seul ce PC peut s'y connecter, le " +
                      "téléphone n'a pas accès. C'est voulu, rien n'est exposé sur le réseau." }),
      el("h3", { text: "Pour activer le mode téléphone" }),
      el("p", { text: "1. Fermez la fenêtre du serveur Scribe (ou appuyez sur Ctrl+C dedans)." }),
      el("p", { text: "2. Dans le dossier de Scribe, lancez cette commande :" }),
      copyRow(RUN_LAN, "Commande du mode téléphone"),
      el("p", { text: "3. Ouvrez dans ce navigateur l'adresse « Sur ce PC » affichée dans la console " +
                      "(elle commence par https://localhost, avec ?t=…), acceptez l'avertissement de " +
                      "certificat, puis cliquez de nouveau sur « Connecter le téléphone »." }),
      el("p", { class: "hint", text: "Pas de bouton de redémarrage automatique : un serveur relancé en " +
                                     "arrière-plan n'aurait plus de fenêtre pour l'arrêter, et la " +
                                     "sécurité ne s'en trouverait pas meilleure." }),
    );
  }

  async function regenerateToken() {
    const ok = confirm("Régénérer le jeton ?\n\nL'ancien jeton cesse de fonctionner tout de suite : tout " +
                       "téléphone déjà connecté devra saisir la nouvelle adresse. Cette page, elle, " +
                       "reste connectée.");
    if (!ok) return;
    try {
      const res = await fetch("/api/phone/token", { method: "POST" });
      if (!res.ok) throw new Error((await res.json()).detail || "Erreur " + res.status);
      render(await res.json());
    } catch (err) { showError("Régénération impossible : " + err.message); }
  }

  function renderLan(info) {
    const chosen = info.addresses.find((a) => a.ip === selectedIp)
      || info.addresses.find((a) => a.recommended) || info.addresses[0];
    selectedIp = chosen ? chosen.ip : null;
    const parts = [];

    if (!chosen) {
      parts.push(el("p", { class: "warn", text: "Aucune adresse privée trouvée : ce PC n'est pas relié à " +
                                                  "un réseau local (Wi-Fi ou Ethernet)." }));
    } else {
      if (info.addresses.length > 1) {
        const select = el("select", { "aria-label": "Adresse du PC sur le réseau" });
        for (const a of info.addresses) {
          const tags = [a.kind, a.recommended ? "recommandée" : null].filter(Boolean).join(", ");
          select.append(el("option", { value: a.ip, selected: a.ip === chosen.ip,
                                       text: `${a.ip} — ${a.interface || "réseau"} (${tags})` }));
        }
        select.addEventListener("change", () => { selectedIp = select.value; renderLan(info); });
        parts.push(el("h3", { text: "Adresse du PC sur le réseau" }),
                   el("p", { class: "hint", text: "Choisissez celle du réseau auquel le téléphone est " +
                                                  "connecté (en général le même Wi-Fi). Évitez les " +
                                                  "adaptateurs virtuels et les VPN." }), select);
      }
      if (chosen.virtual) {
        parts.push(el("p", { class: "warn", text: "Cette adresse appartient à un adaptateur virtuel ou à " +
                                                    "un VPN : le téléphone ne l'atteindra probablement pas." }));
      }
      parts.push(...section("1. Adresse complète à coller dans l'appli",
        "Dans l'appli Scribe, collez-la dans le champ « Adresse » : le jeton est extrait tout seul.",
        chosen.url));
      if (!chosen.in_certificate) {
        parts.push(el("p", { class: "warn", text: "Cette adresse n'est pas dans le certificat du PC. L'appli " +
          "fonctionne quand même (elle vérifie l'empreinte), mais un navigateur afficherait un second " +
          "avertissement. Pour l'ajouter : relancer avec --lan --new-cert (l'empreinte change alors)." }));
      }
      parts.push(...section("2. Empreinte SHA-256 du certificat",
        "Au premier raccordement, l'appli affiche une empreinte : elle doit être identique à celle-ci.",
        info.fingerprint));

      const qr = chosen.qr
        ? [el("img", { class: "qr", src: chosen.qr, alt: "QR code de l'adresse complète" }),
           el("p", { class: "hint", text: "Lisez-le avec l'appareil photo du téléphone, copiez le lien " +
             "affiché (ne l'ouvrez pas dans le navigateur), puis collez-le dans l'appli. Généré sur ce " +
             "PC, sans service externe." })]
        : [el("p", { class: "hint", text: "QR code indisponible (bibliothèque « segno » non installée : " +
                                          "pip install -r requirements.txt)." })];
      parts.push(el("details", {}, el("summary", { text: "QR code de l'adresse complète" }), ...qr));

      parts.push(el("details", {}, el("summary", { text: "Saisie en deux champs (adresse + jeton)" }),
        ...section("Adresse", null, chosen.address), ...section("Jeton d'accès", null, info.token)));
    }

    const regenerate = el("button", { class: "secondary", type: "button", text: "Régénérer le jeton" });
    regenerate.addEventListener("click", regenerateToken);
    parts.push(el("h3", { text: "Sécurité" }),
      el("p", { class: "hint", text: "Le jeton donne accès à Scribe sur le réseau : ne le partagez pas. " +
                                     "Il change à chaque démarrage du serveur." }),
      regenerate);
    body.replaceChildren(...parts);
  }

  function render(info) {
    if (info.lan) renderLan(info); else renderLocalOnly();
  }

  async function openPanel() {
    body.replaceChildren(el("p", { class: "hint", text: "Chargement…" }));
    if (!dialog.open) dialog.showModal();
    try {
      const res = await fetch("/api/phone", { cache: "no-store" });
      if (res.status === 403) return showError("Cette fonction n'est disponible que depuis le PC qui " +
                                               "exécute Scribe.");
      if (!res.ok) throw new Error("Erreur " + res.status);
      render(await res.json());
    } catch (err) { showError("Serveur local injoignable : " + err.message); }
  }

  document.getElementById("phoneBtn").addEventListener("click", openPanel);
  document.getElementById("phoneClose").addEventListener("click", () => dialog.close());
  // Le jeton ne reste pas dans la page une fois le panneau fermé.
  dialog.addEventListener("close", () => body.replaceChildren());
})();
