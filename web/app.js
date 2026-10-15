const LK_LOCAL_LEARNER = "local-learner-001";
const LK_LOCAL_ENVIRONMENT = "home";
const LK_MATH_U1_PACK = "org.learning-kernel.tw-math-g6-u1";
const LK_LEARNING_MAP_URL = "/api/learning-map";
const LK_SELECTED_PLACE_KEY = `bailian:${LK_MATH_U1_PACK}:current-place`;
const LK_PENDING_SURFACES_KEY = `bailian:${LK_MATH_U1_PACK}:pending-surfaces`;
const LK_PENDING_SURFACE_LIMIT = 12;
const LK_SURFACE_REFILL_RETRY_COUNT = 8;
const LK_SURFACE_REFILL_RETRY_DELAY_MS = 500;
const LK_SURFACE_URL = `/api/learners/${encodeURIComponent(LK_LOCAL_LEARNER)}/environments/${encodeURIComponent(LK_LOCAL_ENVIRONMENT)}/packs/${encodeURIComponent(LK_MATH_U1_PACK)}/surface`;
const LK_OBSERVATIONS_URL = `/api/learners/${encodeURIComponent(LK_LOCAL_LEARNER)}/environments/${encodeURIComponent(LK_LOCAL_ENVIRONMENT)}/packs/${encodeURIComponent(LK_MATH_U1_PACK)}/observations`;
const LK_SURFACE_REQUEST = {
  currentContext: {
    currentPlaceLocalId: "",
    todayPractice: true,
  },
};

let lkSurface = null;
let lkPoints = [];
let lkActiveStep = null;
let lkResponseBlock = null;
let lkResponseValue = null;
let lkUsedHintIds = [];
let lkStepStartedAt = 0;
let lkAttemptOrdinal = 1;
let lkLastCapturedAtMs = 0;
let lkPendingCapture = null;
let lkAnswersLocked = false;
let lkNextStepIndex = null;
let lkFinished = false;
let lkPendingNextSurface = null;
let lkLearningMap = null;
let lkPendingExplorationFamilyId = null;
let lkCurrentSurfaceCacheKey = null;
let lkJourneyReturnState = null;
let lkSuggestedPlaceId = null;

function lkSurfaceCacheKey(placeId, familyId = null) {
  return JSON.stringify([placeId, familyId || null]);
}

function lkReadPendingSurfaceCache() {
  try {
    const value = JSON.parse(window.sessionStorage.getItem(LK_PENDING_SURFACES_KEY) || "{}");
    return value && typeof value === "object" && !Array.isArray(value) ? value : {};
  } catch {
    return {};
  }
}

function lkCanResumeSurface(surface, familyId = null) {
  const pack = surface?.lineage?.pack;
  const points = surface?.lineage?.reportableObservationPoints;
  return surface?.schemaVersion === "learning-kernel.surface-ir@1"
    && surface?.surface?.payload?.activityId
    && pack?.version === lkLearningMap?.pack?.version
    && pack?.contentDigest === lkLearningMap?.pack?.contentDigest
    && (!familyId || surface?.lineage?.taskFamilyRef?.localId === familyId)
    && Array.isArray(points)
    && points.length === 1;
}

function lkReadPendingSurface(key, placeId, familyId = null) {
  const cache = lkReadPendingSurfaceCache();
  const record = cache[key];
  if (
    !record
    || record.placeId !== placeId
    || (record.familyId || null) !== (familyId || null)
    || !lkCanResumeSurface(record.surface, familyId)
  ) {
    if (record) lkClearPendingSurface(key);
    return null;
  }
  return {
    surface: record.surface,
    attemptOrdinal: Number.isInteger(record.attemptOrdinal) && record.attemptOrdinal > 0
      ? record.attemptOrdinal
      : 1,
  };
}

function lkStorePendingSurface(
  key,
  surface,
  placeId,
  familyId = null,
  attemptOrdinal = 1,
) {
  if (!key || !lkCanResumeSurface(surface, familyId)) {
    return;
  }
  try {
    const cache = lkReadPendingSurfaceCache();
    cache[key] = { surface, placeId, familyId, attemptOrdinal, savedAt: Date.now() };
    const oldestFirst = Object.entries(cache).sort(
      ([, first], [, second]) => (first?.savedAt || 0) - (second?.savedAt || 0),
    );
    while (oldestFirst.length > LK_PENDING_SURFACE_LIMIT) {
      const [expiredKey] = oldestFirst.shift();
      delete cache[expiredKey];
    }
    window.sessionStorage.setItem(LK_PENDING_SURFACES_KEY, JSON.stringify(cache));
  } catch {
    // The Runtime-issued Surface still works in this tab when session storage is unavailable.
  }
}

function lkUpdatePendingSurfaceAttempt(key, attemptOrdinal) {
  if (!key) return;
  try {
    const cache = lkReadPendingSurfaceCache();
    const record = cache[key];
    if (!record) return;
    record.attemptOrdinal = attemptOrdinal;
    record.savedAt = Date.now();
    window.sessionStorage.setItem(LK_PENDING_SURFACES_KEY, JSON.stringify(cache));
  } catch {
    // Runtime remains authoritative if the browser cannot keep retry position locally.
  }
}

function lkClearPendingSurface(key) {
  if (!key) return;
  try {
    const cache = lkReadPendingSurfaceCache();
    delete cache[key];
    window.sessionStorage.setItem(LK_PENDING_SURFACES_KEY, JSON.stringify(cache));
  } catch {
    // Storage is only used to resume an already Runtime-issued Surface.
  }
}

const lkBaseRenderHome = renderHome;

renderHome = function renderHomeWithRuntimeAvailability() {
  lkBaseRenderHome();
  const isMath = selected === "math";
  const card = document.querySelector(`[data-home-hero="${selected}"]`);
  if (!card) return;

  const eyebrow = card.querySelector(".hero-copy > .eyebrow");
  const title = card.querySelector(".hero-title");
  const prompt = card.querySelector(".hero-prompt");
  const reason = card.querySelector(".hero-reason");
  const startButton = card.querySelector("[data-start-subject], #startRecommended");

  if (eyebrow) eyebrow.textContent = isMath ? "數學 U1 練習" : "尚未開放";
  if (title) title.textContent = isMath ? "數學 U1" : "尚未開放";
  if (prompt) {
    prompt.textContent = isMath
      ? "從 U1-1 到 U1-5，一起探索數量關係；每一步都會留在你的學習紀錄裡。"
      : `${subjects[selected].name}練習目前尚未開放。`;
  }
  if (reason) {
    reason.hidden = !isMath;
    if (isMath) {
      const label = reason.querySelector("span:first-child");
      const detail = reason.querySelector(".hero-reason-copy");
      if (label) label.textContent = "學習紀錄";
      if (detail) detail.textContent = "完成的練習會留下紀錄，陪你一步步往前。";
    }
  }
  if (startButton) {
    const label = startButton.querySelector("span");
    if (label) label.textContent = isMath ? "開始數學 U1" : "尚未開放";
    startButton.disabled = !isMath;
    startButton.classList.toggle("local-disabled", !isMath);
    startButton.setAttribute("aria-disabled", String(!isMath));
  }
};

function lkRenderJourneySubjects() {
  const heading = document.querySelector("#journey .page-heading");
  if (!heading) return;
  let controls = document.querySelector("#journeySubjectChooser");
  if (!controls) {
    controls = document.createElement("nav");
    controls.id = "journeySubjectChooser";
    controls.className = "journey-subject-chooser";
    controls.setAttribute("aria-label", "選擇科目");
    heading.append(controls);
  }
  controls.replaceChildren();
  const subjectInputs = document.querySelectorAll("#homeSubjects .subject-radio");
  for (const input of subjectInputs) {
    const key = input.value;
    if (!subjects[key]) continue;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "journey-subject" + (key === selected ? " is-active" : "");
    button.dataset.journeySubject = key;
    button.setAttribute("aria-pressed", String(key === selected));
    button.textContent = subjects[key].name;
    controls.append(button);
  }
}

renderJourney = function renderRuntimeJourney() {
  const isMath = selected === "math";
  const list = document.querySelector("#journeyList");
  const placeSubject = document.querySelector("#placeSubject");
  const placeTitle = document.querySelector("#placeTitle");
  const placeDescription = document.querySelector("#placeDescription");
  const detailNote = document.querySelector("#journey .detail-note");
  const roadsList = document.querySelector("#placeRoads");
  const taskFamiliesList = document.querySelector("#placeTaskFamilies");
  const learnButton = document.querySelector("#learnAtPlace");
  const practiceButton = document.querySelector("#practiceAtPlace");
  if (!list) return;
  lkRenderJourneySubjects();

  const previousScrollTop = list.scrollTop;
  list.replaceChildren();
  if (!isMath) {
    const item = document.createElement("li");
    item.className = "journey-region-item";
    const message = document.createElement("p");
    message.className = "journey-map-loading";
    message.textContent = `${subjects[selected].name}練習目前尚未開放。`;
    item.append(message);
    list.append(item);
    if (placeSubject) placeSubject.textContent = subjects[selected].name;
    if (placeTitle) placeTitle.textContent = "尚未開放";
    if (placeDescription) placeDescription.textContent = `${subjects[selected].name}練習目前尚未開放。`;
    if (detailNote) detailNote.textContent = "你可以先從數學 U1 的學習旅程開始。";
    roadsList?.replaceChildren();
    taskFamiliesList?.replaceChildren();
  } else if (!lkLearningMap) {
    const item = document.createElement("li");
    item.className = "journey-region-item";
    const message = document.createElement("p");
    message.className = "journey-map-loading";
    message.textContent = "正在準備學習旅程…";
    item.append(message);
    list.append(item);
    if (placeSubject) placeSubject.textContent = "數學 U1";
    if (placeTitle) placeTitle.textContent = "正在準備學習旅程";
    if (placeDescription) placeDescription.textContent = "準備好後，就可以選擇想探索的地方。";
    if (detailNote) detailNote.textContent = "你可以從任何學習地點開始，也可以沿著學習路線前進。";
    roadsList?.replaceChildren();
    taskFamiliesList?.replaceChildren();
  } else {
    const placeById = new Map(lkLearningMap.places.map((place) => [place.id, place]));
    const currentPlaceId = LK_SURFACE_REQUEST.currentContext.currentPlaceLocalId;

    for (const region of lkLearningMap.regions) {
      const item = document.createElement("li");
      item.className = "journey-region-item";
      const heading = document.createElement("div");
      heading.className = "journey-region-heading";
      const regionId = document.createElement("span");
      regionId.className = "journey-region-id";
      regionId.textContent = region.id.toUpperCase();
      const regionTitle = document.createElement("h3");
      regionTitle.textContent = region.title;
      heading.append(regionId, regionTitle);
      const places = document.createElement("div");
      places.className = "journey-region-places";

      for (const placeId of region.placeIds) {
        const place = placeById.get(placeId);
        if (!place) continue;
        const button = document.createElement("button");
        button.type = "button";
        button.className = `journey-map-place ${placeId === currentPlaceId ? "is-current" : ""}`;
        button.dataset.packPlaceId = place.id;
        button.setAttribute("aria-pressed", String(placeId === currentPlaceId));
        button.textContent = place.title;
        places.append(button);
      }
      item.append(heading, places);
      list.append(item);
    }

    const selectedPlace = placeById.get(currentPlaceId) || placeById.get(lkLearningMap.entryPoints[0]?.placeId);
    if (selectedPlace) {
      const region = lkLearningMap.regions.find((item) => item.id === selectedPlace.regionId);
      if (placeSubject) placeSubject.textContent = region?.title || "數學 U1";
      if (placeTitle) placeTitle.textContent = selectedPlace.title;
      if (placeDescription) {
        placeDescription.textContent = selectedPlace.realWorldMeaning
          ? `${selectedPlace.description} ${selectedPlace.realWorldMeaning}`
          : selectedPlace.description;
      }
      if (roadsList) {
        roadsList.replaceChildren();
        const connected = lkLearningMap.roads.filter(
          (road) => road.fromPlaceId === selectedPlace.id || road.toPlaceId === selectedPlace.id,
        );
        for (const road of connected) {
          const forward = road.fromPlaceId === selectedPlace.id;
          const destinationId = forward ? road.toPlaceId : road.fromPlaceId;
          const destination = placeById.get(destinationId);
          const item = document.createElement("li");
          item.className = `journey-road journey-road-${road.kind}`;
          const button = document.createElement("button");
          button.type = "button";
          button.className = "journey-road-link";
          button.dataset.packPlaceId = destinationId;
          const direction = document.createElement("span");
          direction.className = "journey-road-direction";
          direction.textContent = forward ? "→" : "←";
          const copy = document.createElement("span");
          copy.className = "journey-road-copy";
          const title = document.createElement("strong");
          title.textContent = road.title;
          const destinationLabel = document.createElement("small");
          destinationLabel.textContent = `${forward ? "往" : "回到"} ${destination?.title || destinationId}`;
          copy.append(title, destinationLabel);
          const kind = document.createElement("span");
          kind.className = "journey-road-kind";
          kind.textContent = road.kind === "remediation" ? "補強" : road.kind === "return" ? "返回" : "學習";
          button.append(direction, copy, kind);
          item.append(button);
          roadsList.append(item);
        }
      }
      if (taskFamiliesList) {
        taskFamiliesList.replaceChildren();
        const familyById = new Map(
          lkLearningMap.taskFamilies.map((family) => [family.id, family]),
        );
        const focused = new Set(selectedPlace.focusedTaskFamilyIds || []);
        const choices = [...(selectedPlace.taskFamilyIds || [])].sort(
          (a, b) => Number(focused.has(b)) - Number(focused.has(a)),
        );
        for (const familyId of choices) {
          const family = familyById.get(familyId);
          if (!family) continue;
          const item = document.createElement("li");
          const button = document.createElement("button");
          button.type = "button";
          button.className = "journey-family-choice";
          button.dataset.packTaskFamilyId = family.id;
          const title = document.createElement("strong");
          title.textContent = family.title;
          const purpose = document.createElement("small");
          purpose.textContent = family.observationPurpose;
          const action = document.createElement("span");
          action.className = "journey-family-action";
          action.textContent = focused.has(familyId) ? "練這個知識點" : "延伸探索（相鄰道路）";
          button.append(title, purpose, action);
          item.append(button);
          taskFamiliesList.append(item);
        }
      }
    }
    if (detailNote) {
      detailNote.textContent = `這裡有 ${lkLearningMap.places.length} 個學習地點和 ${lkLearningMap.roads.length} 條學習路線。你可以跟著建議前進，也可以選擇想練習的內容。`;
    }
  }
  for (const control of [learnButton, practiceButton]) {
    if (control) {
      const disabled = !isMath || !lkLearningMap;
      control.disabled = disabled;
      control.classList.toggle("local-disabled", disabled);
      control.setAttribute("aria-disabled", String(disabled));
    }
  }
  if (isMath && lkLearningMap) list.scrollTop = previousScrollTop;
};

function lkSelectPackPlace(placeId) {
  if (!lkLearningMap?.places.some((place) => place.id === placeId)) return;
  lkRememberPackPlace(placeId);
  renderJourney();
}

function lkRememberPackPlace(placeId) {
  LK_SURFACE_REQUEST.currentContext.currentPlaceLocalId = placeId;
  try {
    window.localStorage.setItem(LK_SELECTED_PLACE_KEY, placeId);
  } catch {
    // The current selection still works for this tab when browser storage is unavailable.
  }
}

function lkCaptureJourneyReturnState(placeId) {
  const list = document.querySelector("#journeyList");
  lkJourneyReturnState = {
    subject: selected,
    placeId,
    scrollTop: Number.isFinite(list?.scrollTop) ? list.scrollTop : 0,
  };
}

function lkReturnToJourney() {
  const returnState = lkJourneyReturnState;
  lkClearActivity();
  if (returnState) {
    selected = returnState.subject;
    if (returnState.placeId) lkRememberPackPlace(returnState.placeId);
  }
  goPage("journey");
  const list = document.querySelector("#journeyList");
  if (list && Number.isFinite(returnState?.scrollTop)) list.scrollTop = returnState.scrollTop;
  lkJourneyReturnState = null;
}

function lkAdoptSurfaceRoute(surface) {
  const refs = surface?.lineage?.semanticContentRefs;
  const target = Array.isArray(refs) ? refs.at(-1)?.localId : null;
  // The learner's chosen Place is navigation state, not the Runtime destination.
  // Retain it for return/resume; show the LK-selected destination separately.
  lkSuggestedPlaceId = typeof target === "string"
    && lkLearningMap?.places.some((place) => place.id === target) ? target : null;
}

async function lkLoadLearningMap() {
  if (lkLearningMap) return true;
  try {
    const response = await fetch(LK_LEARNING_MAP_URL, { cache: "no-store" });
    if (!response.ok) throw new Error("learning_map_unavailable");
    const body = await response.json();
    if (
      body.schemaVersion !== "learning-kernel.learning-map@1" ||
      body.pack?.id !== LK_MATH_U1_PACK ||
      !Array.isArray(body.entryPoints) ||
      !Array.isArray(body.regions) ||
      !Array.isArray(body.places) ||
      !Array.isArray(body.roads) ||
      !Array.isArray(body.taskFamilies) ||
      body.places.length === 0
    ) {
      throw new Error("unexpected_learning_map_schema");
    }
    lkLearningMap = body;
    let savedPlaceId = "";
    try {
      savedPlaceId = window.localStorage.getItem(LK_SELECTED_PLACE_KEY) || "";
    } catch {
      savedPlaceId = "";
    }
    const entryPlaceId = body.entryPoints[0]?.placeId || body.places[0].id;
    const selectedPlaceId = body.places.some((place) => place.id === savedPlaceId)
      ? savedPlaceId
      : entryPlaceId;
    LK_SURFACE_REQUEST.currentContext.currentPlaceLocalId = selectedPlaceId;
    renderJourney();
    return true;
  } catch {
    lkLearningMap = null;
    renderJourney();
    return false;
  }
}

renderParent = function renderUnavailableParent() {
  const page = document.querySelector("#parent");
  if (!page) return;
  const heading = page.querySelector(".page-heading");
  page.querySelectorAll(".parent-closeout, .parent-subjects, .parent-tools").forEach((node) => {
    node.hidden = true;
  });
  let message = page.querySelector(".local-unavailable");
  if (!message) {
    message = document.createElement("div");
    message.className = "local-unavailable";
    message.innerHTML = "<strong>家長摘要尚未開放</strong><p>目前只接通數學 U1 的活動與 raw observation 儲存，這裡不顯示示範進度。</p>";
    heading?.after(message);
  }
};

function lkShowUnavailableGrowth() {
  const page = document.querySelector("#growth");
  if (!page) return;
  const heading = page.querySelector(".page-heading");
  const layout = page.querySelector(".growth-layout");
  if (layout) layout.hidden = true;
  let message = page.querySelector(".local-unavailable");
  if (!message) {
    message = document.createElement("div");
    message.className = "local-unavailable";
     message.innerHTML = "<strong>成長紀錄尚未開放</strong><p>練習紀錄會先好好保存；成長故事準備好後再來看看。</p>";
    heading?.after(message);
  }
}

function lkShowHomeStatus(ready, detail) {
  const status = document.querySelector(".home-status");
  if (!status) return;
  status.replaceChildren();
  const mark = document.createElement("span");
  mark.className = "status-check";
  mark.textContent = ready ? "✓" : "!";
  mark.style.background = ready ? "var(--lime)" : "var(--coral)";
  const title = document.createElement("span");
  title.textContent = ready ? "數學 U1 已準備好" : "目前還無法開始練習";
  const description = document.createElement("span");
  description.className = "status-detail";
  description.textContent = detail;
  status.append(mark, title, description);
}

async function lkCheckReadiness() {
  try {
    const response = await fetch("/api/ready", { cache: "no-store" });
    const body = await response.json();
    const ready = response.ok && body.ready === true && body.persistence?.status === "ready";
    lkShowHomeStatus(
      ready,
      ready ? "現在可以開始練習，完成的作答會留在學習紀錄裡。" : "請再試一次；如果一直無法開始，請告訴家長。",
    );
  } catch {
    lkShowHomeStatus(false, "目前還無法開始練習，請再試一次。");
  }
}

function lkUpdateShell() {
  const note = document.querySelector(".prototype-note");
  if (note) note.textContent = "數學 U1 練習已準備好；今天想從哪個地方開始？";

  document.querySelectorAll("#today .quick-mode").forEach((button, index) => {
    const title = button.querySelector("span");
    const detail = button.querySelector("small");
    if (index === 0) {
      if (title) title.textContent = "數學 U1 練習";
      if (detail) detail.textContent = "跟著學習旅程，一步一步完成練習";
      button.dataset.mode = "daily";
    } else {
      if (title) title.textContent = index === 1 ? "專項練習" : "自訂練習";
      if (detail) detail.textContent = "這項練習目前尚未開放";
      button.disabled = true;
      button.classList.add("local-disabled");
      button.setAttribute("aria-disabled", "true");
    }
  });

  document.querySelectorAll("#practice .practice-card").forEach((card, index) => {
    const title = card.querySelector("h2");
    const description = card.querySelector("p:not(.mode-label)");
    const button = card.querySelector("[data-mode]");
    if (index === 0) {
      if (title) title.textContent = "數學 U1 練習";
      if (description) description.textContent = "從數學 U1 的學習旅程選擇一個地方開始。";
      if (button) button.textContent = "開始 U1 練習";
    } else {
      if (title) title.textContent = `${index === 1 ? "專項" : "自訂"}練習尚未開放`;
      if (description) description.textContent = "這項練習目前尚未開放。";
      if (button) {
        button.disabled = true;
        button.textContent = "尚未開放";
        button.classList.add("local-disabled");
        button.setAttribute("aria-disabled", "true");
      }
    }
  });

  const practiceNote = document.querySelector("#practice .practice-note p");
  if (practiceNote) practiceNote.textContent = "目前可以練習數學 U1；從學習旅程選擇想探索的地方。";
  const journeyIntro = document.querySelector("#journey .page-heading p:not(.eyebrow)");
  if (journeyIntro) journeyIntro.textContent = "沿著學習地圖探索數量關係，或選擇想練習的地方。";
  const practiceIntro = document.querySelector("#practice .page-heading p:not(.eyebrow)");
  if (practiceIntro) practiceIntro.textContent = "選擇一個學習地點開始練習。";
  const journeyNote = document.querySelector("#journey .detail-note");
  if (journeyNote) journeyNote.textContent = "你可以從任何學習地點開始，也可以沿著學習路線前進。";
  const statusDetail = document.querySelector(".home-status .status-detail");
  if (statusDetail) statusDetail.textContent = "選擇一個學習地點，開始今天的練習。";
}

function lkToast(message) {
  if (typeof toast === "function") toast(message);
}

function lkIsNoSupplyError(errorCode) {
  return [
    "activity_supply_unavailable",
    "activity_supply_completed",
    "no_legal_route_candidates",
    "requested_family_exhausted",
  ].includes(errorCode);
}

function lkErrorMessage(errorCode, context = "activity") {
  const messages = {
    activity_supply_unavailable: "這裡目前沒有新的練習了。你可以回到學習旅程，看看其他想練習的地方。",
    activity_supply_completed: "這裡目前沒有新的練習了。你可以回到學習旅程，看看其他想練習的地方。",
    no_legal_route_candidates: "這裡目前沒有新的練習了。你可以回到學習旅程，看看其他想練習的地方。",
    requested_family_exhausted: "這裡目前沒有新的練習了。你可以回到學習旅程，看看其他想練習的地方。",
    runtime_http_400: "題目載入出了點問題，請再試一次。",
    runtime_http_500: "題目載入出了點問題，請再試一次。",
    runtime_http_502: "題目載入出了點問題，請再試一次。",
    runtime_http_503: "題目載入出了點問題，請再試一次。",
    runtime_http_504: "題目載入出了點問題，請再試一次。",
    runtime_response_invalid: "題目載入出了點問題，請再試一次。",
    vnext_d1_persistence_failed: context === "surface"
      ? "題目載入出了點問題，請再試一次。"
      : "作答沒有送出，請再試一次。",
    trusted_evaluation_lineage_mismatch: "作答沒有送出，請再試一次。",
    trusted_evaluation_response_mismatch: "作答沒有送出，請再試一次。",
    invalid_request: "作答沒有送出，請再試一次。",
    unsupported_response_capability: "這種作答方式還沒準備好。請回到學習旅程，換一個地方練習。",
    requested_family_mismatch: "練習內容和你選的題型不同，已停止載入，沒有送出作答。",
  };
  return messages[errorCode] || (context === "surface" ? "題目載入出了點問題，請再試一次。" : "作答沒有送出，請再試一次。");
}

async function lkReadRuntimeJson(response) {
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.toLowerCase().includes("json")) {
    throw new Error(`runtime_http_${response.status}`);
  }
  let body;
  try {
    body = await response.json();
  } catch {
    throw new Error(`runtime_http_${response.status}`);
  }
  if (!body || typeof body !== "object" || Array.isArray(body)) {
    throw new Error("runtime_response_invalid");
  }
  return body;
}

function lkRuntimeRequestError(code, response, body = null) {
  const error = new Error(code);
  error.httpStatus = response?.status ?? null;
  error.runtimeErrorCode = typeof body?.error === "string" ? body.error : null;
  return error;
}

function lkLogRuntimeIssue(context, error) {
  const errorCode = error instanceof Error ? error.message : "unknown_error";
  const statusFromCode = /^runtime_http_(\d+)$/.exec(errorCode)?.[1];
  const httpStatus = error?.httpStatus ?? (statusFromCode ? Number(statusFromCode) : "unknown");
  const runtimeErrorCode = error?.runtimeErrorCode ?? "none";
  console.error(
    `[Math U1] ${context} request failed: errorCode=${errorCode}; httpStatus=${httpStatus}; runtimeErrorCode=${runtimeErrorCode}`,
  );
}

async function lkFetchSurfaceWithRefillRetry(currentContext) {
  for (let attempt = 0; attempt < LK_SURFACE_REFILL_RETRY_COUNT; attempt += 1) {
    const response = await fetch(LK_SURFACE_URL, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ currentContext }),
      cache: "no-store",
    });
    const body = await lkReadRuntimeJson(response);
    if (response.ok) return body;
    if (
      body.error === "activity_supply_unavailable"
      && body.supply_state === "all_legal_routes_exhausted"
    ) {
      throw lkRuntimeRequestError("activity_supply_completed", response, body);
    }
    if (body.error !== "activity_supply_unavailable" || attempt + 1 === LK_SURFACE_REFILL_RETRY_COUNT) {
      throw lkRuntimeRequestError(body.error || `runtime_http_${response.status}`, response, body);
    }
    lkSetActivityState("正在準備題目…", false, "waiting");
    await new Promise((resolve) => setTimeout(resolve, LK_SURFACE_REFILL_RETRY_DELAY_MS));
  }
  throw new Error("activity_supply_unavailable");
}

function lkSetActivityState(message, isError = false, visualState = null) {
  const state = document.querySelector("#submitState");
  if (!state) return;
  state.hidden = !message;
  state.textContent = message || "";
  state.dataset.state = isError ? "error" : visualState || "saved";
}

function lkClearActivity() {
  lkSurface = null;
  lkPoints = [];
  lkActiveStep = null;
  lkResponseBlock = null;
  lkResponseValue = null;
  lkUsedHintIds = [];
  lkAttemptOrdinal = 1;
  lkLastCapturedAtMs = 0;
  lkPendingCapture = null;
  lkAnswersLocked = false;
  lkNextStepIndex = null;
  lkFinished = false;
  lkPendingNextSurface = null;
  lkCurrentSurfaceCacheKey = null;
  document.querySelector("#backFromActivity").disabled = false;
  document.querySelector("#activity")?.classList.remove("has-guided-factor-tree");
  document.querySelector("#activityCounter").hidden = true;
  document.querySelector("#activityProgress").hidden = true;
  const submitButton = document.querySelector("#submitAnswer");
  submitButton.hidden = false;
  submitButton.disabled = false;
  submitButton.textContent = "送出作答";
  document.querySelector("#nextActivity").hidden = true;
  document.querySelector("#dailySummary").hidden = true;
  document.querySelector("#lkNextDecision").hidden = true;
  document.querySelector("#questionLayout").hidden = false;
  lkSetActivityState("");
}

function lkStartFocusedPlace() {
  const place = lkLearningMap?.places.find(
    (item) => item.id === LK_SURFACE_REQUEST.currentContext.currentPlaceLocalId,
  );
  const ownedFamilies = place?.focusedTaskFamilyIds || [];
  if (ownedFamilies.length === 0) {
    lkToast("這個地點目前沒有專屬練習，請先探索相連的學習道路。");
    return;
  }
  const familyId = ownedFamilies[0];
  const family = lkLearningMap.taskFamilies.find((item) => item.id === familyId);
  if (ownedFamilies.length > 1) {
    lkToast(`這裡有多種練習，先從「${family?.title || "基礎練習"}」開始，也能點下方其他題型。`);
  }
  lkPendingExplorationFamilyId = familyId;
  void lkStartU1();
}

async function lkStartU1() {
  if (selected !== "math") {
    lkToast(`${subjects[selected].name}練習目前尚未開放。`);
    return;
  }
  if (!(await lkLoadLearningMap())) {
    lkToast("學習旅程載入出了點問題，請再試一次。");
    return;
  }
  const currentPlace = lkLearningMap.places.find(
    (place) => place.id === LK_SURFACE_REQUEST.currentContext.currentPlaceLocalId,
  );
  if (!currentPlace) {
    lkToast("請重新選擇一個學習地點。");
    return;
  }
  lkCaptureJourneyReturnState(currentPlace.id);
  const requestedFamilyId = lkPendingExplorationFamilyId;
  lkPendingExplorationFamilyId = null;
  const cacheKey = lkSurfaceCacheKey(currentPlace.id, requestedFamilyId);
  lkClearActivity();
  document.querySelector("#activityModeLabel").textContent = "數學 U1 練習";
  document.querySelector("#activityTitle").textContent = `數學 U1｜${currentPlace.title}`;
  document.querySelector("#activitySubject").textContent = currentPlace.regionId.toUpperCase();
  document.querySelector("#activitySubtopic").textContent = currentPlace.title;
  document.querySelector("#activityQuestion").textContent = "正在準備題目…";
  document.querySelector("#activityQuestion").hidden = false;
  document.querySelector("#answerHost").replaceChildren();
  document.querySelector("#hintText").textContent = "先想一想，遇到困難時可以看看提示。";
  document.querySelector("#hintButtonAside").hidden = true;
  document.querySelector(".activity-unjudged").textContent = "仔細想一想，再寫下你的答案。";
  const submitButton = document.querySelector("#submitAnswer");
  submitButton.hidden = true;
  submitButton.disabled = true;
  goPage("activity");

  try {
    const pending = lkReadPendingSurface(cacheKey, currentPlace.id, requestedFamilyId);
    if (pending) {
      lkCurrentSurfaceCacheKey = cacheKey;
      lkLoadSurface(
        pending.surface,
        pending.surface.surface?.payload?.presentation?.title || `數學 U1｜${currentPlace.title}`,
      );
      lkAttemptOrdinal = pending.attemptOrdinal;
      return;
    }

    const startRequest = {
      currentContext: { ...LK_SURFACE_REQUEST.currentContext },
    };
    if (requestedFamilyId) {
      startRequest.currentContext.learnerExplorationTaskFamilyIds = [requestedFamilyId];
    }
    const body = await lkFetchSurfaceWithRefillRetry(startRequest.currentContext);
    if (body.schemaVersion !== "learning-kernel.surface-ir@1") {
      throw new Error("unexpected_surface_schema");
    }
    if (requestedFamilyId && body.lineage?.taskFamilyRef?.localId !== requestedFamilyId) {
      throw new Error("requested_family_mismatch");
    }
    lkLoadSurface(body, body.surface?.payload?.presentation?.title || `數學 U1｜${currentPlace.title}`);
    if (lkPoints.length === 1) {
      lkCurrentSurfaceCacheKey = cacheKey;
      lkStorePendingSurface(cacheKey, body, currentPlace.id, requestedFamilyId);
    }
  } catch (error) {
    const code = error instanceof Error ? error.message : "runtime_unavailable";
    lkLogRuntimeIssue("surface", error);
    const noSupply = lkIsNoSupplyError(code);
    document.querySelector("#activityQuestion").hidden = true;
    document.querySelector("#answerHost").replaceChildren();
    submitButton.hidden = true;
    submitButton.disabled = true;
    lkSetActivityState(lkErrorMessage(code, "surface"), !noSupply, noSupply ? "empty" : "error");
  }
}

function lkLoadSurface(body, title) {
  const points = body.lineage?.reportableObservationPoints
    ?.filter((point) => Number.isInteger(point.stepIndex))
    .sort((a, b) => a.stepIndex - b.stepIndex) || [];
  const firstStepIndex = body.execution?.stepIndex;
  if (!Number.isInteger(firstStepIndex) || !points.some((point) => point.stepIndex === firstStepIndex)) {
    throw new Error("surface_step_unavailable");
  }
  lkSurface = body;
  lkPoints = points;
  lkAdoptSurfaceRoute(body);
  const semanticRefs = body.lineage?.semanticContentRefs;
  const selectedPlaceId = Array.isArray(semanticRefs)
    ? semanticRefs.at(-1)?.localId
    : null;
  const selectedPlace = lkLearningMap?.places.find((place) => place.id === selectedPlaceId);
  const originPlace = lkLearningMap?.places.find(
    (item) => item.id === LK_SURFACE_REQUEST.currentContext.currentPlaceLocalId,
  );
  if (selectedPlace) {
    const region = lkLearningMap.regions.find((item) => item.id === selectedPlace.regionId);
    document.querySelector("#activitySubject").textContent = region?.title || "數學 U1";
  }
  const rerouted = selectedPlace && originPlace && selectedPlace.id !== originPlace.id;
  document.querySelector("#activitySubtopic").textContent = rerouted
    ? `你選擇：${originPlace.title}｜LK 建議：${selectedPlace.title}`
    : (originPlace?.title || selectedPlace?.title || "");
  document.querySelector("#activityTitle").textContent = selectedPlace?.title || title;
  document.querySelector("#activityQuestion").hidden = false;
  document.querySelector("#questionLayout").hidden = false;
  document.querySelector("#lkNextDecision").hidden = true;
  lkRenderStep(firstStepIndex);
}

function lkRouteReason(routeKind) {
  const reasons = {
    advance: "接著往前學一小步。",
    transfer_confirmation: "把剛練到的想法，帶到不同題目裡試試看。",
    targeted_confirmation: "再確認一次剛練到的方法。",
    wrong_turn_discrimination: "換個情境，看看怎麼找出真正有用的線索。",
    remediation: "先用一個小練習，把剛才遇到的地方再弄清楚。",
    return_from_remediation: "回到原來的學習路線，再試一次新的題目。",
    alternate_method: "試試另一種解題方法。",
    alternate_representation: "換一種表示方式，再練習看看。",
    delayed_confirmation: "再想一次，確認還記得這個方法。",
    fluency_practice: "再練習一次，讓這個方法更熟悉。",
    learner_exploration: "試試一個可以自由探索的小活動。",
  };
  return reasons[routeKind] || "這是接下來可以試試看的練習。";
}

function lkRecommendationPrompt(surface) {
  const steps = surface?.surface?.payload?.steps;
  const firstStep = Array.isArray(steps) ? steps[surface.execution?.stepIndex] : null;
  const prompt = firstStep?.blocks?.find((block) => block.capability === "content.text@1")?.props?.text;
  return typeof prompt === "string" && prompt.trim()
    ? prompt.trim()
    : "一個新的數學 U1 練習";
}

function lkShowRecommendationMessage(title, detail, canStart = false) {
  const panel = document.querySelector("#lkNextDecision");
  const titleNode = document.querySelector("#lkNextDecisionTitle");
  const promptNode = document.querySelector("#lkNextDecisionPrompt");
  const reasonNode = document.querySelector("#lkNextDecisionReason");
  const startButton = document.querySelector("#startLkRecommended");
  titleNode.textContent = title;
  promptNode.textContent = detail;
  reasonNode.textContent = "";
  startButton.hidden = !canStart;
  panel.hidden = false;
  document.querySelector("#questionLayout").hidden = true;
  document.querySelector("#dailySummary").hidden = true;
}

async function lkRequestNextDecision() {
  lkShowRecommendationMessage("正在找下一個適合的練習…", "正在看看接下來可以練習什麼。", false);

  try {
    const body = await lkFetchSurfaceWithRefillRetry({
      currentPlaceLocalId: LK_SURFACE_REQUEST.currentContext.currentPlaceLocalId,
      todayPractice: true,
    });
    if (
      body.schemaVersion !== "learning-kernel.surface-ir@1" ||
      !body.execution?.observation?.routeKind ||
      !Array.isArray(body.lineage?.reportableObservationPoints) ||
      !Array.isArray(body.surface?.payload?.steps)
    ) {
      throw new Error("unexpected_surface_schema");
    }
    lkPendingNextSurface = body;
    const placeId = LK_SURFACE_REQUEST.currentContext.currentPlaceLocalId;
    const cacheKey = lkSurfaceCacheKey(placeId);
    if (lkCanResumeSurface(body)) {
      lkStorePendingSurface(cacheKey, body, placeId);
    }
    lkShowRecommendationMessage("接下來可以試試這個練習", lkRecommendationPrompt(body), true);
    document.querySelector("#lkNextDecisionReason").textContent = lkRouteReason(body.execution.observation.routeKind);
  } catch (error) {
    lkPendingNextSurface = null;
    const code = error instanceof Error ? error.message : "runtime_unavailable";
    lkLogRuntimeIssue("next-suggestion", error);
    if (
      code === "activity_supply_unavailable"
      || code === "activity_supply_completed"
      || code === "no_legal_route_candidates"
    ) {
      lkShowRecommendationMessage(
        "這次練習完成了",
        "這裡目前沒有新的練習了。你可以回到學習旅程，看看其他想練習的地方。",
      );
      return;
    }
    lkShowRecommendationMessage(
      "這次練習完成了",
      "題目載入出了點問題，請再試一次。",
    );
  }
}

function lkStartRecommendedSurface() {
  if (!lkPendingNextSurface) return;
  const surface = lkPendingNextSurface;
  lkPendingNextSurface = null;
  const placeId = LK_SURFACE_REQUEST.currentContext.currentPlaceLocalId;
  if (!lkJourneyReturnState) lkCaptureJourneyReturnState(placeId);
  const cacheKey = lkSurfaceCacheKey(placeId);
  try {
    lkCurrentSurfaceCacheKey = cacheKey;
    lkLoadSurface(surface, surface.surface?.payload?.presentation?.title || "數學 U1 練習");
    if (lkPoints.length === 1) {
      lkStorePendingSurface(cacheKey, surface, placeId);
    } else {
      lkCurrentSurfaceCacheKey = null;
    }
  } catch {
    lkCurrentSurfaceCacheKey = null;
    lkClearPendingSurface(cacheKey);
    lkShowRecommendationMessage(
      "目前無法開始這個活動",
      "你的學習紀錄已保存。請返回學習旅程，再試一次。",
    );
  }
}

function lkRenderStep(stepIndex) {
  const steps = lkSurface?.surface?.payload?.steps;
  const step = Array.isArray(steps) ? steps[stepIndex] : null;
  const point = lkPoints.find((item) => item.stepIndex === stepIndex);
  if (!step || !point) throw new Error("surface_step_unavailable");

  const blocks = Array.isArray(step.blocks) ? step.blocks : [];
  const contentBlocks = blocks.filter((block) => block.capability === "content.text@1");
  const responseCandidate = blocks.find((block) =>
    [
      "response.single-choice@1",
      "response.multi-choice@1",
      "response.math@1",
      "response.text@1",
    ].includes(block.capability),
  );
  const supportedMathProfile = responseCandidate?.capability !== "response.math@1"
    || ["integer", "factorization"].includes(responseCandidate?.props?.profile);
  lkResponseBlock = supportedMathProfile ? responseCandidate : null;
  lkActiveStep = { step, stepIndex, point };
  lkResponseValue = lkResponseBlock?.capability === "response.multi-choice@1" ? [] : null;
  lkUsedHintIds = [];
  lkAttemptOrdinal = 1;
  lkLastCapturedAtMs = 0;
  lkPendingCapture = null;
  lkAnswersLocked = false;
  lkStepStartedAt = Date.now();
  lkNextStepIndex = null;
  lkFinished = false;

  const position = lkPoints.findIndex((item) => item.stepIndex === stepIndex) + 1;
  document.querySelector(".question-card")?.classList.remove("guided-factor-tree");
  document.querySelector("#activity")?.classList.remove("has-guided-factor-tree");
  const counter = document.querySelector("#activityCounter");
  counter.hidden = lkPoints.length < 2;
  counter.textContent = `第 ${position} / ${lkPoints.length} 題`;
  document.querySelector("#activityQuestion").textContent = contentBlocks[0]?.props?.text || "請依照題目作答。";
  document.querySelector("#activityPassage").hidden = true;
  const answerHost = document.querySelector("#answerHost");
  answerHost.replaceChildren();
  lkSetActivityState("");
  const submitButton = document.querySelector("#submitAnswer");
  submitButton.hidden = false;
  submitButton.disabled = false;
  submitButton.textContent = "送出作答";
  document.querySelector("#nextActivity").hidden = true;
  document.querySelector("#nextActivity").disabled = false;
  lkSetAnswerChoicesDisabled(false);

  if (!lkResponseBlock) {
    console.error("[Math U1] unsupported response capability", {
      activityId: lkSurface?.surface?.payload?.activityId ?? null,
      responseCapability: step.blocks?.find((block) => block.capability?.startsWith("response."))?.capability ?? null,
    });
    lkSetActivityState(lkErrorMessage("unsupported_response_capability"), true);
    document.querySelector("#submitAnswer").hidden = true;
    document.querySelector("#submitAnswer").disabled = true;
  } else {
    if (contentBlocks.length > 1) {
      const context = document.createElement("p");
      context.className = "runtime-choice-note";
      context.textContent = contentBlocks.slice(1).map((block) => block.props?.text || "").filter(Boolean).join(" ");
      answerHost.append(context);
    }
    if (["response.single-choice@1", "response.multi-choice@1"].includes(lkResponseBlock.capability)) {
      lkRenderChoices(lkResponseBlock);
    } else {
      lkRenderFreeResponse(lkResponseBlock);
    }
  }

  lkRenderHint(step.support?.hints || []);
};

function lkRenderChoices(block) {
  const props = block.props || {};
  const choices = Array.isArray(props.options) ? props.options : [];
  const list = document.createElement("div");
  list.className = "runtime-answer-list";
  list.setAttribute("role", block.capability === "response.multi-choice@1" ? "group" : "radiogroup");
  list.setAttribute(
    "aria-label",
    block.capability === "response.multi-choice@1"
      ? "請選出所有符合條件的答案"
      : "請選一個答案",
  );

  choices.forEach((choice, index) => {
    const value = String(choice.value ?? "");
    const button = document.createElement("button");
    button.type = "button";
    button.className = "runtime-answer-choice";
    button.dataset.runtimeAnswer = value;
    button.dataset.selectionType = block.capability;
    button.setAttribute("role", block.capability === "response.multi-choice@1" ? "checkbox" : "radio");
    button.setAttribute("aria-pressed", "false");
    button.setAttribute("aria-checked", "false");
    const marker = document.createElement("span");
    marker.className = "runtime-answer-marker";
    marker.textContent = String.fromCharCode(65 + index);
    const label = document.createElement("span");
    label.textContent = String(choice.label ?? value);
    button.append(marker, label);
    list.append(button);
  });

  const note = document.createElement("p");
  note.className = "runtime-choice-note";
  note.textContent = block.capability === "response.multi-choice@1"
    ? "請選出所有符合條件的答案。"
    : "請選一個答案。";
  document.querySelector("#answerHost").append(list, note);
}

function lkIsFactorTreeSurface() {
  const activityId = lkSurface?.surface?.payload?.activityId || lkSurface?.activity?.activityId;
  return typeof activityId === "string" && (
    /\/family\/factor-tree(?:\/|$)/.test(activityId)
    || /\/activity\/factor-tree(?:-|\/|$)/.test(activityId)
  );
}

function lkFactorTreeExample(question) {
  const examples = [
    [12, "12=3×4；4=2×2"],
    [18, "18=2×9；9=3×3"],
    [20, "20=4×5；4=2×2"],
    [24, "24=3×8；8=2×4；4=2×2"],
    [30, "30=5×6；6=2×3"],
    [42, "42=6×7；6=2×3"],
    [45, "45=5×9；9=3×3"],
    [70, "70=7×10；10=2×5"],
    [75, "75=3×25；25=5×5"],
  ];
  const prompt = typeof question === "string" ? question : "";
  const example = examples.find(([root]) => !new RegExp(`(^|\\D)${root}(\\D|$)`).test(prompt));
  return example
    ? `格式示範：${example[1]}（示範格式，不是這題的答案）`
    : "格式示範：原數=兩個因數；還能分解的因數=兩個因數。";
}

function lkMakeResponseTool(label, className, datasetKey, datasetValue = "") {
  const button = document.createElement("button");
  button.type = "button";
  button.className = `response-tool ${className}`;
  button.textContent = label;
  button.dataset[datasetKey] = datasetValue;
  return button;
}

function lkRenderFreeResponse(block) {
  const props = block.props || {};
  const isText = block.capability === "response.text@1";
  const isInteger = block.capability === "response.math@1" && props.profile === "integer";
  const isFactorization = block.capability === "response.math@1" && props.profile === "factorization";
  const isFactorTree = isText && lkIsFactorTreeSurface();
  const label = document.createElement("label");
  label.className = "runtime-response-label";
  label.textContent = isFactorization
    ? "請輸入質因數分解式"
    : isFactorTree
      ? "請寫下你的因數樹步驟"
      : isText
        ? "請寫下你的想法"
        : isInteger
          ? "請輸入一個整數"
          : "請寫下你的想法";

  const field = document.createElement(isText ? "textarea" : "input");
  field.className = "runtime-free-response";
  field.dataset.runtimeFreeResponse = "true";
  field.name = typeof props.name === "string" ? props.name : "learner-response";
  field.setAttribute("aria-label", label.textContent);
  field.setAttribute("autocomplete", "off");
  if (isText) {
    field.rows = isFactorTree ? 4 : 3;
    field.placeholder = isFactorTree ? "每一步寫在分號後面" : "寫下你的想法";
  } else {
    field.type = "text";
    field.inputMode = isFactorization ? "text" : "numeric";
    field.placeholder = isFactorization ? "用「×」連接每個質數" : "輸入答案";
  }

  const answerHost = document.querySelector("#answerHost");
  if (isFactorTree) {
    document.querySelector(".question-card")?.classList.add("guided-factor-tree");
    document.querySelector("#activity")?.classList.add("has-guided-factor-tree");
    const guidance = document.createElement("p");
    guidance.className = "factor-tree-guidance";
    guidance.textContent = "先把原數拆成兩個相乘的數字；如果拆出的數字還能繼續分解，就用下一步寫出來；直到最後每個數字都是質數。";
    const example = document.createElement("p");
    example.className = "factor-tree-example";
    example.textContent = lkFactorTreeExample(document.querySelector("#activityQuestion").textContent);
    answerHost.append(guidance, example, label, field);
  } else {
    const note = document.createElement("p");
    note.className = "runtime-choice-note";
    note.textContent = isFactorization
      ? "用「×」連接每個質數。"
      : "仔細想一想，再寫下答案。";
    answerHost.append(label, field, note);
  }

  if (isFactorization || isFactorTree) {
    const toolbar = document.createElement("div");
    toolbar.className = "response-toolbar";
    toolbar.setAttribute("role", "group");
    toolbar.setAttribute("aria-label", "作答小工具");
    toolbar.append(lkMakeResponseTool("× 乘號", "response-tool-insert", "responseInsert", "×"));
    if (isFactorTree) {
      toolbar.append(lkMakeResponseTool("； 下一步", "response-tool-insert", "responseInsert", "； "));
    }
    toolbar.append(lkMakeResponseTool(
      isFactorization ? "清除／重寫" : "重寫",
      "response-tool-rewrite",
      "responseRewrite",
    ));
    answerHost.append(toolbar);
  }

  field.addEventListener("input", () => {
    lkResponseValue = field.value;
  });
}

function lkApplyResponseTool(button) {
  if (lkAnswersLocked || lkPendingCapture) return;
  const field = document.querySelector("[data-runtime-free-response]");
  if (!field || field.disabled) return;
  if (button.hasAttribute("data-response-rewrite")) {
    field.value = "";
    field.dispatchEvent(new Event("input", { bubbles: true }));
    field.focus({ preventScroll: true });
    field.setSelectionRange(0, 0);
    return;
  }
  const insertion = button.dataset.responseInsert;
  if (typeof insertion !== "string") return;
  const start = Number.isInteger(field.selectionStart) ? field.selectionStart : field.value.length;
  const end = Number.isInteger(field.selectionEnd) ? field.selectionEnd : start;
  field.setRangeText(insertion, start, end, "end");
  field.dispatchEvent(new Event("input", { bubbles: true }));
  field.focus({ preventScroll: true });
  const cursor = start + insertion.length;
  field.setSelectionRange(cursor, cursor);
}

function lkSelectChoice(button) {
  if (!lkResponseBlock || !lkActiveStep || lkAnswersLocked || lkPendingCapture) return;
  const value = button.dataset.runtimeAnswer;
  const multi = lkResponseBlock.capability === "response.multi-choice@1";
  if (multi) {
    const selectedValues = new Set(Array.isArray(lkResponseValue) ? lkResponseValue : []);
    if (selectedValues.has(value)) selectedValues.delete(value);
    else {
      const maximum = Number(lkResponseBlock.props?.maxSelections || Infinity);
      if (selectedValues.size >= maximum) {
        lkToast(`這題最多選 ${maximum} 個答案。`);
        return;
      }
      selectedValues.add(value);
    }
    lkResponseValue = [...selectedValues];
  } else {
    lkResponseValue = value;
  }

  document.querySelectorAll(".runtime-answer-choice").forEach((choice) => {
    const active = multi
      ? lkResponseValue.includes(choice.dataset.runtimeAnswer)
      : choice === button;
    choice.setAttribute("aria-pressed", String(active));
    choice.setAttribute("aria-checked", String(active));
  });
}

function lkRenderHint(hints) {
  const hintButton = document.querySelector("#hintButtonAside");
  const hintText = document.querySelector("#hintText");
  const helperCard = hintButton.closest(".helper-card");
  const hint = hints.find((item) => typeof item.id === "string");
  if (helperCard) helperCard.hidden = !hint;
  hintButton.hidden = !hint;
  hintButton.disabled = !hint;
  hintButton.classList.add("hint-button");
  hintButton.textContent = "查看提示";
  hintText.textContent = hint ? "先想一想，也可以打開提示。" : "先照自己的想法試試看。";
  hintButton.dataset.hintId = hint?.id || "";
}

function lkShowHint() {
  const hintButton = document.querySelector("#hintButtonAside");
  const hintId = hintButton.dataset.hintId;
  const hints = lkActiveStep?.step?.support?.hints || [];
  const hint = hints.find((item) => item.id === hintId);
  if (!hint) return;
  if (!lkUsedHintIds.includes(hint.id)) lkUsedHintIds.push(hint.id);
  document.querySelector("#hintText").textContent = (hint.blocks || [])
    .filter((block) => block.capability === "content.text@1")
    .map((block) => block.props?.text || "")
    .filter(Boolean)
    .join(" ") || "請再讀一次題目，找出可能的線索。";
  hintButton.textContent = "已查看提示";
  hintButton.disabled = true;
}

function lkCapturePayload() {
  const { step, stepIndex, point } = lkActiveStep;
  const multi = lkResponseBlock.capability === "response.multi-choice@1";
  const freeResponse = ["response.math@1", "response.text@1"].includes(lkResponseBlock.capability);
  const responseField = freeResponse ? document.querySelector("[data-runtime-free-response]") : null;
  const value = freeResponse ? responseField?.value ?? "" : lkResponseValue;
  if (multi && (!Array.isArray(value) || value.length < Number(lkResponseBlock.props?.minSelections || 1))) {
    throw new Error("請先選擇題目要求數量的答案。");
  }
  if (!multi && (typeof value !== "string" || value.trim().length === 0)) {
    throw new Error(freeResponse ? "請先輸入作答內容。" : "請先選一個答案。");
  }

  const capturedAtMs = Math.max(Date.now(), lkLastCapturedAtMs + 1);
  lkLastCapturedAtMs = capturedAtMs;

  return {
    schemaVersion: lkSurface.surface.observationCaptureVersion,
    decisionId: lkSurface.lineage.decisionId,
    activityId: lkSurface.surface.payload.activityId,
    stepIndex,
    stepId: step.stepId,
    observationPointId: point.observationPointRef.localId,
    response: {
      capability: lkResponseBlock.capability,
      value,
    },
    attempt: {
      attemptId: `attempt/${crypto.randomUUID()}`,
      attemptOrdinal: lkAttemptOrdinal,
      attemptCount: lkAttemptOrdinal,
      activeWorkDurationMs: Math.max(0, Date.now() - lkStepStartedAt),
    },
    support: {
      hintIdsUsed: [...lkUsedHintIds],
      revealIdsUsed: [],
      retryCount: lkAttemptOrdinal - 1,
      assistanceLevel: lkUsedHintIds.length ? "hint_1" : "independent",
    },
    capturedAt: new Date(capturedAtMs).toISOString(),
    practiceMode: lkSurface.execution.practiceMode,
  };
}

async function lkSubmitAnswer() {
  if (!lkSurface || !lkActiveStep || !lkResponseBlock || lkFinished) return;
  if (!lkPendingCapture) {
    try {
      lkPendingCapture = lkCapturePayload();
    } catch (error) {
      lkToast(error instanceof Error ? error.message : "請先完成這一步。 ");
      return;
    }
  }
  const capture = lkPendingCapture;

  const submitButton = document.querySelector("#submitAnswer");
  submitButton.disabled = true;
  submitButton.textContent = "正在送出作答…";
  lkAnswersLocked = true;
  lkSetAnswerChoicesDisabled(true);
  document.querySelector("#backFromActivity").disabled = true;
  try {
    const response = await fetch(LK_OBSERVATIONS_URL, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(capture),
      cache: "no-store",
    });
    const body = await lkReadRuntimeJson(response);
    if (response.status !== 202) {
      throw lkRuntimeRequestError(body.error || "vnext_d1_persistence_failed", response, body);
    }
    const feedback = body.feedback;
    if (
      !feedback ||
      !["correct", "incorrect", "indeterminate"].includes(feedback.verdict) ||
      typeof feedback.message !== "string" ||
      !["success", "retry", "neutral"].includes(feedback.tone) ||
      !["advance", "complete", "retry"].includes(feedback.action) ||
      !["advance", "complete"].includes(body.directive) ||
      !body.receipt ||
      body.receipt.evaluated !== true ||
      typeof body.receipt.attemptChainId !== "string" ||
      !Array.isArray(body.receipt.evidenceIds) ||
      body.receipt.evidenceIds.length === 0
    ) {
      throw new Error("unexpected_observation_receipt");
    }

    const verdict = feedback.verdict;
    const expectedAction = verdict === "incorrect" ? "retry" : body.directive;
    if (feedback.action !== expectedAction) throw new Error("unexpected_runtime_directive");
    let nextStepIndex = null;
    let finished = false;
    if (feedback.action === "advance") {
      const nextPoint = lkPoints.find((item) => item.stepIndex > lkActiveStep.stepIndex);
      if (!nextPoint) throw new Error("runtime_next_step_missing");
      nextStepIndex = nextPoint.stepIndex;
    } else if (feedback.action === "complete") {
      finished = true;
    }

    lkPendingCapture = null;
    lkSetActivityState(feedback.message, false, feedback.tone);
    document.querySelector("#backFromActivity").disabled = false;
    const nextButton = document.querySelector("#nextActivity");
    if (verdict === "incorrect") {
      lkAttemptOrdinal = capture.attempt.attemptOrdinal + 1;
      lkUpdatePendingSurfaceAttempt(lkCurrentSurfaceCacheKey, lkAttemptOrdinal);
      lkResponseValue = lkResponseBlock.capability === "response.multi-choice@1" ? [] : null;
      const freeResponse = document.querySelector("[data-runtime-free-response]");
      if (freeResponse) freeResponse.value = "";
      lkUsedHintIds = [];
      lkAnswersLocked = false;
      lkStepStartedAt = Date.now();
      lkSetAnswerChoicesDisabled(false);
      lkClearChoiceSelection();
      lkRenderHint(lkActiveStep.step.support?.hints || []);
      submitButton.hidden = false;
      submitButton.disabled = false;
      submitButton.textContent = "再試一次";
      nextButton.hidden = true;
      lkNextStepIndex = null;
      lkFinished = false;
      return;
    }

    lkAnswersLocked = true;
    lkSetAnswerChoicesDisabled(true);
    lkFinished = finished;
    if (finished && lkCurrentSurfaceCacheKey) {
      lkClearPendingSurface(lkCurrentSurfaceCacheKey);
      lkCurrentSurfaceCacheKey = null;
    }
    submitButton.hidden = true;
    nextButton.hidden = false;
    if (nextStepIndex !== null) {
      lkNextStepIndex = nextStepIndex;
      nextButton.textContent = "繼續下一題";
    } else if (finished) {
      lkFinished = true;
      nextButton.textContent = "完成練習";
    }
  } catch (error) {
    const code = error instanceof Error ? error.message : "vnext_d1_persistence_failed";
    lkLogRuntimeIssue("observation", error);
    lkSetActivityState(lkErrorMessage(code, "observation"), true);
    submitButton.disabled = false;
    submitButton.textContent = "重新送出";
    lkAnswersLocked = true;
    lkSetAnswerChoicesDisabled(true);
    document.querySelector("#backFromActivity").disabled = true;
  }
}

function lkSetAnswerChoicesDisabled(disabled) {
  document.querySelectorAll(".runtime-answer-choice").forEach((choice) => {
    choice.disabled = disabled;
    choice.setAttribute("aria-disabled", String(disabled));
  });
  document.querySelectorAll("[data-runtime-free-response]").forEach((field) => {
    field.disabled = disabled;
    field.setAttribute("aria-disabled", String(disabled));
  });
  document.querySelectorAll(".response-tool").forEach((button) => {
    button.disabled = disabled;
  });
}

function lkClearChoiceSelection() {
  document.querySelectorAll(".runtime-answer-choice").forEach((choice) => {
    choice.setAttribute("aria-pressed", "false");
    choice.setAttribute("aria-checked", "false");
  });
}

function lkContinue() {
  if (lkNextStepIndex !== null) {
    lkRenderStep(lkNextStepIndex);
    return;
  }
  if (lkFinished) {
    void lkRequestNextDecision();
  }
}

function lkHandleClick(event) {
  const target = event.target instanceof Element ? event.target : null;
  if (!target) return;

  const answer = target.closest(".runtime-answer-choice");
  const familyChoice = target.closest("[data-pack-task-family-id]");
  const start = target.closest("[data-start-subject]");
  const modeButton = target.closest("[data-mode]");
  const submitButton = target.closest("#submitAnswer");
  const nextButton = target.closest("#nextActivity");
  const hintButton = target.closest("#hintButtonAside");
  const subjectChoice = target.closest("[data-journey-subject]");
  const mapPlace = target.closest("[data-pack-place-id]");
  const placeButton = target.closest("#learnAtPlace, #practiceAtPlace");
  const recommendedButton = target.closest("#startRecommended");
  const startLkRecommended = target.closest("#startLkRecommended");
  const returnToJourney = target.closest("#returnToJourney");
  const responseTool = target.closest("[data-response-insert], [data-response-rewrite]");

  if (responseTool) {
    event.preventDefault();
    event.stopImmediatePropagation();
    lkApplyResponseTool(responseTool);
    return;
  }

  if (subjectChoice) {
    event.preventDefault();
    event.stopImmediatePropagation();
    selected = subjectChoice.dataset.journeySubject || "math";
    renderSubjectTabs();
    renderHome();
    renderJourney();
    return;
  }

  if (familyChoice) {
    event.preventDefault();
    event.stopImmediatePropagation();
    lkPendingExplorationFamilyId = familyChoice.dataset.packTaskFamilyId || null;
    void lkStartU1();
    return;
  }

  if (mapPlace) {
    event.preventDefault();
    event.stopImmediatePropagation();
    lkSelectPackPlace(mapPlace.dataset.packPlaceId || "");
    return;
  }

  if (answer) {
    event.preventDefault();
    event.stopImmediatePropagation();
    lkSelectChoice(answer);
    return;
  }
  if (start) {
    event.preventDefault();
    event.stopImmediatePropagation();
    setSubject(start.dataset.startSubject || "math");
    void lkStartU1();
    return;
  }
  if (modeButton) {
    event.preventDefault();
    event.stopImmediatePropagation();
    if (modeButton.dataset.mode === "daily" && selected === "math") void lkStartU1();
    else lkToast("目前只開放數學 U1 練習。");
    return;
  }
  if (recommendedButton) {
    event.preventDefault();
    event.stopImmediatePropagation();
    void lkStartU1();
    return;
  }
  if (startLkRecommended) {
    event.preventDefault();
    event.stopImmediatePropagation();
    lkStartRecommendedSurface();
    return;
  }
  if (returnToJourney) {
    event.preventDefault();
    event.stopImmediatePropagation();
    lkReturnToJourney();
    return;
  }
  if (placeButton) {
    event.preventDefault();
    event.stopImmediatePropagation();
    if (placeButton.id === "learnAtPlace") lkStartFocusedPlace();
    else void lkStartU1();
    return;
  }
  if (submitButton) {
    event.preventDefault();
    event.stopImmediatePropagation();
    void lkSubmitAnswer();
    return;
  }
  if (nextButton) {
    event.preventDefault();
    event.stopImmediatePropagation();
    lkContinue();
    return;
  }
  if (hintButton) {
    event.preventDefault();
    event.stopImmediatePropagation();
    lkShowHint();
  }
}

document.addEventListener("click", lkHandleClick, true);

document.querySelector("#homeSubjects")?.addEventListener("change", (event) => {
  if (event.target.matches(".subject-radio")) selected = event.target.value;
});

document.querySelectorAll("#growth .imprint-chip, #parent [data-parent-action]").forEach((button) => {
  button.disabled = true;
  button.classList.add("local-disabled");
});

document.querySelector("#backFromActivity")?.addEventListener("click", () => {
  lkReturnToJourney();
});

const lkHomeHeroTitle = document.querySelector("#homeHeroMath .hero-title");
const lkDefaultSubject = document.querySelector('#homeSubjects input[value="math"]');
const lkProfileName = document.querySelector("#profileButton > span:not(.avatar)");
if (lkDefaultSubject) lkDefaultSubject.checked = true;
if (lkProfileName) lkProfileName.textContent = "本機學習者";
selected = "math";
selectedStop = 0;
renderSubjectTabs();
renderHome();
renderJourney();
void lkLoadLearningMap();
renderParent();
lkShowUnavailableGrowth();
lkUpdateShell();
void lkCheckReadiness();

if (lkHomeHeroTitle) lkHomeHeroTitle.textContent = "數學 U1";
