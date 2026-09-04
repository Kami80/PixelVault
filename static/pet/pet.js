(() => {
  "use strict";

  const config = window.PIXEL_PET_CONFIG || {};
  const form = document.querySelector("#pet-chat-form");
  const input = document.querySelector("#pet-message");
  const send = document.querySelector("#pet-send");
  const log = document.querySelector("#pet-chat");
  const stage = document.querySelector("#pet-stage");
  const speech = document.querySelector("#pet-speech");
  const stateLabel = document.querySelector("#pet-state");
  const status = document.querySelector("#pet-chat-status");
  const counter = document.querySelector("#pet-char-count");
  const memoryList = document.querySelector("#pet-memory-list");
  const providerBadge = document.querySelector("#pet-provider-badge");
  const chatTitle = document.querySelector("#pet-chat-title");
  const csrfToken = form?.querySelector("[name=csrfmiddlewaretoken]")?.value || "";

  if (!form || !input || !send || !log) return;

  function setEmotion(emotion, message) {
    const normalized = String(emotion || "idle").toLowerCase().replace(/[^a-z0-9_-]/g, "") || "idle";
    if (stage) stage.dataset.emotion = normalized;
    if (stateLabel) stateLabel.textContent = normalized.toUpperCase();
    if (speech && message) speech.textContent = message;
  }

  function setProviderState(ai) {
    if (!providerBadge || !ai) return;
    const state = String(ai.status || "");
    providerBadge.classList.toggle("safe", ["online", "local_action"].includes(state));
    if (state === "online") providerBadge.textContent = "NEMOTRON ONLINE";
    else if (state === "fallback") providerBadge.textContent = "LOCAL FALLBACK";
    else if (state === "local_action") providerBadge.textContent = "LOCAL ACTION";
    else if (state === "not_configured") providerBadge.textContent = "LOCAL MODE";
    providerBadge.title = ai.message || ai.model || "";
  }

  function updateActiveChat(data) {
    if (data.chatId) config.chatId = String(data.chatId);
    if (chatTitle && data.chatTitle) chatTitle.textContent = data.chatTitle;
    if (!data.chatId) return;
    const activeLink = [...document.querySelectorAll("[data-chat-id]")].find(
      (link) => link.dataset.chatId === String(data.chatId),
    );
    const label = activeLink?.querySelector("b");
    if (label && data.chatTitle) label.textContent = data.chatTitle;
    const meta = activeLink?.querySelector(".pet-chat-meta");
    if (meta && Number.isInteger(data.chatMessageCount)) {
      meta.textContent = `${data.chatMessageCount} message${data.chatMessageCount === 1 ? "" : "s"} · just now`;
    }
  }

  const objectTokenPattern = /\[(project|idea|task|skill):([A-Za-z0-9_-]{1,128})\]/gi;
  const objectTypes = new Set(["project", "idea", "task", "skill"]);

  function parseObjectReferences(text, objects = []) {
    const references = new Map();
    if (Array.isArray(objects)) {
      objects.forEach((object) => {
        const type = String(object?.type || "").toLowerCase();
        const id = String(object?.id || "");
        if (objectTypes.has(type) && /^[A-Za-z0-9_-]{1,128}$/.test(id)) {
          references.set(`${type}:${id}`, {...object, type, id});
        }
      });
    }
    const cleaned = String(text || "").replace(objectTokenPattern, (_token, rawType, id) => {
      const type = rawType.toLowerCase();
      const key = `${type}:${id}`;
      if (!references.has(key)) references.set(key, {type, id, title: id});
      return "";
    }).replace(/\s+([.,!?;:])/g, "$1").replace(/[ \t]{2,}/g, " ").trim();
    return {text: cleaned || "I’m ready for the next move.", objects: [...references.values()]};
  }

  function workspaceObjectUrl(object) {
    const url = new URL(config.workspaceUrl || "/", window.location.origin);
    url.searchParams.set("open", `${object.type}:${object.id}`);
    return `${url.pathname}${url.search}${url.hash}`;
  }

  function buildObjectCard(object) {
    const card = document.createElement("div");
    const type = String(object?.type || "item").toLowerCase();
    const id = String(object?.id || "");
    const title = String(object?.title || id || "Untitled");
    card.className = "pet-object-card";
    card.dataset.objectType = type;
    card.dataset.objectId = id;

    const link = document.createElement("a");
    link.className = "pet-object-main";
    link.href = workspaceObjectUrl({type, id});
    link.setAttribute("aria-label", `Open ${type} ${title} in PixelVault`);
    const kind = document.createElement("span");
    kind.textContent = type.toUpperCase();
    const copy = document.createElement("span");
    copy.className = "pet-object-copy";
    const label = document.createElement("strong");
    label.textContent = title;
    const meta = document.createElement("small");
    meta.textContent = String(object?.meta || object?.status || "").toUpperCase();
    copy.append(label, meta);
    const open = document.createElement("i");
    open.textContent = "OPEN ↗";
    link.append(kind, copy, open);
    card.append(link);

    if (Array.isArray(object?.actions) && object.actions.length) {
      const actions = document.createElement("div");
      actions.className = "pet-object-actions";
      object.actions.slice(0, 4).forEach((objectAction) => {
        const button = document.createElement("button");
        button.type = "button";
        button.dataset.objectAction = String(objectAction?.id || "");
        button.dataset.objectValue = String(objectAction?.value || "");
        button.textContent = String(objectAction?.label || objectAction?.id || "ACTION");
        if (objectAction?.tone) button.classList.add(String(objectAction.tone));
        actions.append(button);
      });
      card.append(actions);
    }
    return card;
  }

  function addObjectLinks(body, objects) {
    if (!objects.length) return;
    const links = document.createElement("div");
    links.className = "pet-object-links";
    objects.slice(0, 8).forEach((object) => links.append(buildObjectCard(object)));
    body.append(links);
  }

  function updateObjectCards(objects, fallbackContainer) {
    if (!Array.isArray(objects)) return;
    objects.forEach((object) => {
      const type = String(object?.type || "");
      const id = String(object?.id || "");
      const matches = [...document.querySelectorAll(".pet-object-card")].filter(
        (card) => card.dataset.objectType === type && card.dataset.objectId === id,
      );
      if (matches.length) {
        matches.forEach((card) => card.replaceWith(buildObjectCard(object)));
      } else if (fallbackContainer) {
        fallbackContainer.append(buildObjectCard(object));
      }
    });
  }

  async function runObjectAction(button) {
    const card = button.closest(".pet-object-card");
    if (!card) return;
    const container = card.closest(".pet-object-links");
    const cardButtons = card.querySelectorAll("button");
    cardButtons.forEach((item) => { item.disabled = true; });
    status.textContent = `${config.petName || "Companion"} is updating the workspace…`;
    try {
      const response = await fetch(config.objectActionUrl || "/pet/object-action/", {
        method: "POST",
        credentials: "same-origin",
        headers: {"Content-Type": "application/json", "X-CSRFToken": csrfToken, "Accept": "application/json"},
        body: JSON.stringify({
          type: card.dataset.objectType,
          id: card.dataset.objectId,
          action: button.dataset.objectAction,
          value: button.dataset.objectValue || "",
        }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
      const parsed = parseObjectReferences(data.message || "Workspace updated.", data.objects);
      updateObjectCards(data.objects, container);
      setEmotion(data.emotion || "happy", parsed.text);
      status.textContent = parsed.text;
    } catch (error) {
      cardButtons.forEach((item) => { item.disabled = false; });
      setEmotion("concerned", error.message || "I couldn’t update that item.");
      status.textContent = error.message || "I couldn’t update that item.";
    }
  }

  function addMessage(role, text, emotion = "", objects = []) {
    const article = document.createElement("article");
    article.className = `pet-message pet-message-${role}`;
    if (role === "agent") {
      const image = document.createElement("img");
      image.src = config.avatarUrl || "";
      image.alt = "";
      article.append(image);
    }
    const body = document.createElement("div");
    const meta = document.createElement("small");
    meta.textContent = role === "user" ? "YOU" : role === "error" ? "CONNECTION NOTE" : `${String(config.petName || "COMPANION").toUpperCase()} · ${String(emotion || "READY").toUpperCase()}`;
    const paragraph = document.createElement("p");
    const parsed = role === "agent" ? parseObjectReferences(text, objects) : {text: String(text || ""), objects: []};
    paragraph.textContent = parsed.text;
    body.append(meta, paragraph);
    addObjectLinks(body, parsed.objects);
    article.append(body);
    log.append(article);
    log.scrollTop = log.scrollHeight;
  }

  async function sendMessage(message) {
    addMessage("user", message);
    input.value = "";
    updateCounter();
    send.disabled = true;
    status.textContent = config.remoteConfigured
      ? `${config.petName || "Companion"} is thinking with Nemotron…`
      : `${config.petName || "Companion"} is checking your workspace locally…`;
    setEmotion("thinking", "Thinking through your workspace…");
    try {
      const response = await fetch(config.chatUrl || "/pet/chat/", {
        method: "POST",
        credentials: "same-origin",
        headers: {"Content-Type": "application/json", "X-CSRFToken": csrfToken, "Accept": "application/json"},
        body: JSON.stringify({message, chatId: config.chatId || ""}),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
      addMessage("agent", data.message || "I am ready.", data.emotion, data.objects);
      setEmotion(data.emotion || "happy", data.message || "Ready for the next move.");
      setProviderState(data.ai);
      updateActiveChat(data);
      if (["created", "updated", "deleted"].includes(data.action?.status)) {
        const objectType = String(data.action.objectType || "item").toUpperCase();
        const actionText = data.action.status === "created"
          ? "added to"
          : data.action.status === "deleted"
            ? "deleted from"
            : "updated in";
        status.textContent = `${objectType} ${actionText} your workspace.`;
      } else if (data.action?.status === "confirmation_required") {
        status.textContent = "Deletion is waiting for your explicit confirmation.";
      } else {
        status.textContent = "Reply saved to your private companion history.";
      }
    } catch (error) {
      addMessage("error", error.message || "The companion could not reply. Please try again.");
      setEmotion("concerned", "I couldn’t connect just now. Your workspace is still safe.");
      status.textContent = "Message was not saved. Try again.";
    } finally {
      send.disabled = false;
      input.focus();
    }
  }

  async function refreshMemories() {
    const button = document.querySelector("#pet-memory-refresh");
    if (button) button.disabled = true;
    try {
      const response = await fetch(config.memoryUrl || "/pet/memory/", {credentials: "same-origin", headers: {"Accept": "application/json"}});
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.error || "Could not load memories.");
      memoryList.replaceChildren();
      if (!data.memories?.length) {
        const empty = document.createElement("div");
        empty.className = "pet-memory-empty";
        const icon = document.createElement("span");
        icon.textContent = "◇";
        const title = document.createElement("b");
        title.textContent = "NO MEMORIES YET";
        const copy = document.createElement("p");
        copy.textContent = "Your companion’s durable context will appear here.";
        empty.append(icon, title, copy);
        memoryList.append(empty);
        return;
      }
      data.memories.forEach((memory) => {
        const article = document.createElement("article");
        const type = document.createElement("span");
        type.textContent = String(memory.memoryType || "experience").toUpperCase();
        const content = document.createElement("p");
        content.textContent = memory.content || "";
        const importance = document.createElement("small");
        importance.textContent = `IMPORTANCE ${memory.importance ?? 50}`;
        article.append(type, content, importance);
        memoryList.append(article);
      });
    } catch (error) {
      status.textContent = error.message || "Could not refresh memories.";
    } finally {
      if (button) button.disabled = false;
    }
  }

  function updateCounter() {
    counter.textContent = `${input.value.length} / 1000`;
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const message = input.value.trim();
    if (!message) {
      status.textContent = "Write a message first.";
      input.focus();
      return;
    }
    sendMessage(message);
  });
  input.addEventListener("input", updateCounter);
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      form.requestSubmit();
    }
  });
  document.querySelectorAll("[data-pet-prompt]").forEach((button) => button.addEventListener("click", () => {
    input.value = button.dataset.petPrompt || "";
    updateCounter();
    input.focus();
  }));
  log.addEventListener("click", (event) => {
    const button = event.target.closest("[data-object-action]");
    if (button) runObjectAction(button);
  });
  document.querySelector("#pet-memory-refresh")?.addEventListener("click", refreshMemories);
  updateCounter();
  log.scrollTop = log.scrollHeight;
})();
