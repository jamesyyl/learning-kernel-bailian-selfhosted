const LK_LOCAL_LEARNER = "local-learner-001";
const LK_LOCAL_ENVIRONMENT = "home";
const LK_MATH_U1_PACK = "org.learning-kernel.tw-math-g6-u1";
const LK_LEARNING_MAP_URL = "/api/learning-map";
const LK_SELECTED_PLACE_KEY = `bailian:${LK_MATH_U1_PACK}:current-place`;
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

  if (eyebrow) eyebrow.textContent = isMath ? "已接通 Learning Kernel" : "尚未開放";
  if (title) title.textContent = isMath ? "數學 U1" : "尚未開放";
  if (prompt) {
    prompt.textContent = isMath
      ? "從 U1-1 到 U1-5，沿著完整學習地圖探索數量關係；每一步作答都會交給本機 Runtime 保存。"
      : `${subjects[selected].name}目前尚未接通 Learning Kernel 活動。`;
  }
  if (reason) {
    reason.hidden = !isMath;
    if (isMath) {
      const label = reason.querySelector("span:first-child");
      const detail = reason.querySelector(".hero-reason-copy");
      if (label) label.textContent = "本機 Runtime";
      if (detail) detail.textContent = "出題與學習紀錄由 Learning Kernel 提供。";
    }
  }
  if (startButton) {
    const label = startButton.querySelector("span");
    if (label) label.textContent = isMath ? "開始 U1 練習" : "尚未開放";
    startButton.disabled = !isMath;
    startButton.classList.toggle("local-disabled", !isMath);
    startButton.setAttribute("aria-disabled", String(!isMath));
  }
};

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

  const previousScrollTop = list.scrollTop;
  list.replaceChildren();
  if (!isMath) {
    const item = document.createElement("li");
    item.className = "journey-region-item";
    const message = document.createElement("p");
    message.className = "journey-map-loading";
    message.textContent = `${subjects[selected].name}尚未接通 Learning Kernel。`;
    item.append(message);
    list.append(item);
    if (placeSubject) placeSubject.textContent = subjects[selected].name;
    if (placeTitle) placeTitle.textContent = "尚未開放";
    if (placeDescription) placeDescription.textContent = `${subjects[selected].name}尚未接通 Learning Kernel 活動。`;
    if (detailNote) detailNote.textContent = "目前只有數學 U1 可從 Learning Map 載入活動。";
    roadsList?.replaceChildren();
    taskFamiliesList?.replaceChildren();
  } else if (!lkLearningMap) {
    const item = document.createElement("li");
    item.className = "journey-region-item";
    const message = document.createElement("p");
    message.className = "journey-map-loading";
    message.textContent = "正在讀取數學 U1 的完整學習地圖…";
    item.append(message);
    list.append(item);
    if (placeSubject) placeSubject.textContent = "數學 U1";
    if (placeTitle) placeTitle.textContent = "正在載入學習地圖";
    if (placeDescription) placeDescription.textContent = "地點與連線會直接來自已發布的 Knowledge Pack。";
    if (detailNote) detailNote.textContent = "地圖載入後可從任一 Place 開始，或沿 Pack 路線切換地點。";
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
        for (const familyId of selectedPlace.taskFamilyIds || []) {
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
          action.textContent = "探索這個做法";
          button.append(title, purpose, action);
          item.append(button);
          taskFamiliesList.append(item);
        }
      }
    }
    if (detailNote) {
      detailNote.textContent = `地圖列出 Pack 的全部 ${lkLearningMap.places.length} 個 Place 與 ${lkLearningMap.roads.length} 條 Road。可以讓 Learning Kernel 依學習紀錄安排下一步，也可以選擇這裡的學習做法。`;
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

function lkAdoptSurfaceRoute(surface) {
  const refs = surface?.lineage?.semanticContentRefs;
  const target = Array.isArray(refs) ? refs.at(-1)?.localId : null;
  if (typeof target !== "string" || !lkLearningMap?.places.some((place) => place.id === target)) {
    return;
  }
  lkRememberPackPlace(target);
  if (document.querySelector("#journey")?.hidden === false) renderJourney();
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
    message.innerHTML = "<strong>成長紀錄尚未開放</strong><p>Runtime 已接收作答原始紀錄；本機介面目前不讀取或推算學習進度。</p>";
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
  title.textContent = ready ? "本機 Learning Kernel 已就緒" : "本機 Runtime 尚未就緒";
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
      ready ? "數學 U1 可練習・作答保存於本機 SQLite" : "請確認 Runtime 與 SQLite 狀態",
    );
  } catch {
    lkShowHomeStatus(false, "無法連線 Runtime；請稍後重試");
  }
}

function lkUpdateShell() {
  const note = document.querySelector(".prototype-note");
  if (note) note.textContent = "本機數學 U1 已接通 LK Runtime；其他科目與學習摘要尚未開放";

  document.querySelectorAll("#today .quick-mode").forEach((button, index) => {
    const title = button.querySelector("span");
    const detail = button.querySelector("small");
    if (index === 0) {
      if (title) title.textContent = "數學 U1 練習";
      if (detail) detail.textContent = "載入活動並依序提交作答";
      button.dataset.mode = "daily";
    } else {
      if (title) title.textContent = index === 1 ? "專項練習" : "自訂練習";
      if (detail) detail.textContent = "尚未接通 Runtime";
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
      if (description) description.textContent = "載入 Runtime 活動，完成作答後保存 raw observation。";
      if (button) button.textContent = "開始 U1 練習";
    } else {
      if (title) title.textContent = `${index === 1 ? "專項" : "自訂"}練習尚未開放`;
      if (description) description.textContent = "目前 Runtime 只供應數學 U1 活動。";
      if (button) {
        button.disabled = true;
        button.textContent = "尚未開放";
        button.classList.add("local-disabled");
        button.setAttribute("aria-disabled", "true");
      }
    }
  });

  const practiceNote = document.querySelector("#practice .practice-note p");
  if (practiceNote) practiceNote.textContent = "本機目前只開放數學 U1；活動數量與學習狀態由 Runtime 決定。";
  const journeyIntro = document.querySelector("#journey .page-heading p:not(.eyebrow)");
  if (journeyIntro) journeyIntro.textContent = "目前只有數學 U1 已接通；其他科目尚未開放。";
  const practiceIntro = document.querySelector("#practice .page-heading p:not(.eyebrow)");
  if (practiceIntro) practiceIntro.textContent = "目前只有數學 U1 今日練習可以使用。";
  const journeyNote = document.querySelector("#journey .detail-note");
  if (journeyNote) journeyNote.textContent = "數學 U1 可再次進入；其他科目尚未接通。";
  const statusDetail = document.querySelector(".home-status .status-detail");
  if (statusDetail) statusDetail.textContent = "數學 U1 可練習・其他科目尚未開放";
}

function lkToast(message) {
  if (typeof toast === "function") toast(message);
}

function lkErrorMessage(errorCode) {
  const messages = {
    activity_supply_unavailable: "Runtime 暫時沒有可用活動，請稍後再試。",
    vnext_d1_persistence_failed: "本機學習資料未能完成保存，請檢查 Runtime。",
    trusted_evaluation_lineage_mismatch: "Runtime 無法核對這份作答；請重新載入活動。",
    trusted_evaluation_response_mismatch: "Runtime 無法核對這份作答；請重新載入活動。",
    invalid_request: "Runtime 拒絕了不符合契約的作答；請重新載入活動。",
  };
  return messages[errorCode] || "Runtime 暫時無法完成這個步驟，請稍後重試。";
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
  document.querySelector("#backFromActivity").disabled = false;
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

async function lkStartU1() {
  if (selected !== "math") {
    lkToast(`${subjects[selected].name}尚未接通 Learning Kernel，目前不能開始活動。`);
    return;
  }
  if (!(await lkLoadLearningMap())) {
    lkToast("目前無法載入數學 U1 學習地圖，請稍後再試。");
    return;
  }
  const currentPlace = lkLearningMap.places.find(
    (place) => place.id === LK_SURFACE_REQUEST.currentContext.currentPlaceLocalId,
  );
  if (!currentPlace) {
    lkToast("這個學習地點不在目前的 Pack 地圖中。");
    return;
  }
  lkClearActivity();
  document.querySelector("#activityModeLabel").textContent = "數學 U1・本機練習";
  document.querySelector("#activityTitle").textContent = `數學 U1｜${currentPlace.title}`;
  document.querySelector("#activitySubject").textContent = currentPlace.regionId.toUpperCase();
  document.querySelector("#activitySubtopic").textContent = currentPlace.title;
  document.querySelector("#activityQuestion").textContent = "正在向 Learning Kernel 載入活動…";
  document.querySelector("#answerHost").replaceChildren();
  document.querySelector("#hintText").textContent = "活動載入後，可以先自己想想，也可以查看 Runtime 提供的提示。";
  document.querySelector("#hintButtonAside").hidden = true;
  document.querySelector(".activity-unjudged").textContent = "作答由 Learning Kernel 判斷；百煉只呈現結果";
  goPage("activity");

  try {
    const startRequest = {
      currentContext: { ...LK_SURFACE_REQUEST.currentContext },
    };
    const requestedFamilyId = lkPendingExplorationFamilyId;
    lkPendingExplorationFamilyId = null;
    if (requestedFamilyId) {
      startRequest.currentContext.learnerExplorationTaskFamilyIds = [requestedFamilyId];
    }
    const response = await fetch(LK_SURFACE_URL, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(startRequest),
      cache: "no-store",
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.error || "runtime_unavailable");
    if (body.schemaVersion !== "learning-kernel.surface-ir@1") {
      throw new Error("unexpected_surface_schema");
    }
    lkLoadSurface(body, body.surface?.payload?.presentation?.title || `數學 U1｜${currentPlace.title}`);
  } catch (error) {
    const code = error instanceof Error ? error.message : "runtime_unavailable";
    document.querySelector("#activityQuestion").textContent = "目前無法載入數學 U1 活動";
    document.querySelector("#answerHost").replaceChildren();
    document.querySelector("#submitAnswer").hidden = true;
    lkSetActivityState(lkErrorMessage(code), true);
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
  if (selectedPlace) {
    document.querySelector("#activitySubject").textContent = selectedPlace.regionId.toUpperCase();
    document.querySelector("#activitySubtopic").textContent = selectedPlace.title;
  }
  document.querySelector("#activityTitle").textContent = title;
  document.querySelector("#questionLayout").hidden = false;
  document.querySelector("#lkNextDecision").hidden = true;
  lkRenderStep(firstStepIndex);
}

function lkRouteReason(routeKind) {
  const reasons = {
    advance: "依照你剛完成的練習，LK 建議接著往前學一小步。",
    transfer_confirmation: "LK 想讓你把剛練到的想法，帶到不同題目裡試試看。",
    targeted_confirmation: "LK 建議再確認一次剛練到的方法。",
    wrong_turn_discrimination: "換個情境，看看怎麼找出真正有用的線索。",
    remediation: "先用一個小練習，把剛才遇到的地方再弄清楚。",
    return_from_remediation: "回到原來的學習路線，再試一次新的題目。",
    alternate_method: "試試另一種解題方法。",
    alternate_representation: "換一種表示方式，再練習看看。",
    delayed_confirmation: "LK 想請你再想一次，確認還記得這個方法。",
    fluency_practice: "再練習一次，讓這個方法更熟悉。",
    learner_exploration: "LK 找到一個可以自由探索的小活動。",
  };
  return reasons[routeKind] || "這是 LK 根據目前學習紀錄找到的下一個活動。";
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
  lkShowRecommendationMessage("正在找下一個適合的練習…", "Learning Kernel 正在查看這次練習的紀錄。", false);

  try {
    const response = await fetch(LK_SURFACE_URL, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        currentContext: {
          currentPlaceLocalId: LK_SURFACE_REQUEST.currentContext.currentPlaceLocalId,
          todayPractice: true,
        },
      }),
      cache: "no-store",
    });
    const body = await response.json();
    if (!response.ok) {
      if (body.error === "activity_supply_unavailable" || body.error === "no_legal_route_candidates") {
        lkPendingNextSurface = null;
        lkShowRecommendationMessage(
          "這次練習完成了",
          "目前沒有可接續的數學 U1 活動。你的學習紀錄已保存。",
        );
        return;
      }
      throw new Error(body.error || "runtime_unavailable");
    }
    if (
      body.schemaVersion !== "learning-kernel.surface-ir@1" ||
      !body.execution?.observation?.routeKind ||
      !Array.isArray(body.lineage?.reportableObservationPoints) ||
      !Array.isArray(body.surface?.payload?.steps)
    ) {
      throw new Error("unexpected_surface_schema");
    }
    lkPendingNextSurface = body;
    lkShowRecommendationMessage("LK 為你挑了下一個練習", lkRecommendationPrompt(body), true);
    document.querySelector("#lkNextDecisionReason").textContent = lkRouteReason(body.execution.observation.routeKind);
  } catch {
    lkPendingNextSurface = null;
    lkShowRecommendationMessage(
      "這次練習完成了",
      "現在暫時無法取得下一步建議。你的學習紀錄已保存，稍後可以再試。",
    );
  }
}

function lkStartRecommendedSurface() {
  if (!lkPendingNextSurface) return;
  const surface = lkPendingNextSurface;
  lkPendingNextSurface = null;
  try {
    lkLoadSurface(surface, surface.surface?.payload?.presentation?.title || "數學 U1｜LK 推薦練習");
  } catch {
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
  lkResponseBlock = blocks.find((block) =>
    [
      "response.single-choice@1",
      "response.multi-choice@1",
      "response.math@1",
      "response.text@1",
    ].includes(block.capability),
  );
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
    lkSetActivityState("這個步驟使用了目前頁面尚未支援的回答形式。", true);
    document.querySelector("#submitAnswer").hidden = true;
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
      ? "選擇所有符合條件的答案"
      : "選擇一個答案",
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
  note.textContent = block.capability === "response.multi-choice@1" ? "可複選，選好後送出。" : "選一個答案後送出。";
  document.querySelector("#answerHost").append(list, note);
}

function lkRenderFreeResponse(block) {
  const props = block.props || {};
  const isText = block.capability === "response.text@1";
  const label = document.createElement("label");
  label.className = "runtime-response-label";
  label.textContent = props.label || (isText ? "輸入作答" : "輸入數學答案");

  const field = document.createElement(isText ? "textarea" : "input");
  field.className = "runtime-free-response";
  field.dataset.runtimeFreeResponse = "true";
  field.name = typeof props.name === "string" ? props.name : "learner-response";
  field.setAttribute("aria-label", label.textContent);
  field.setAttribute("autocomplete", "off");
  if (isText) {
    field.rows = 3;
    field.placeholder = "輸入你的想法或解題步驟";
  } else {
    field.type = "text";
    field.inputMode = props.profile === "factorization" ? "text" : "numeric";
    field.placeholder = props.profile === "factorization" ? "例如：2×3×3" : "輸入答案";
  }

  const note = document.createElement("p");
  note.className = "runtime-choice-note";
  note.textContent = props.profile === "factorization"
    ? "用乘號連接質因數，不需要指數記號。"
    : "答案會交由 Learning Kernel 判斷並保存。";
  document.querySelector("#answerHost").append(label, field, note);
  field.addEventListener("input", () => {
    lkResponseValue = field.value;
  });
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
  const hint = hints.find((item) => typeof item.id === "string");
  hintButton.hidden = !hint;
  hintButton.disabled = !hint;
  hintButton.classList.add("hint-button");
  hintButton.textContent = "查看提示";
  hintText.textContent = hint ? "先想一想，也可以打開提示。" : "這個步驟沒有附 Runtime 提示。";
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
  submitButton.textContent = "正在判斷並保存…";
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
    const body = await response.json();
    if (response.status !== 202) throw new Error(body.error || "vnext_d1_persistence_failed");
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
    lkSetActivityState(lkErrorMessage(code), true);
    submitButton.disabled = false;
    submitButton.textContent = "重新傳送同一次作答";
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
  const mapPlace = target.closest("[data-pack-place-id]");
  const placeButton = target.closest("#learnAtPlace, #practiceAtPlace");
  const recommendedButton = target.closest("#startRecommended");
  const startLkRecommended = target.closest("#startLkRecommended");
  const returnToJourney = target.closest("#returnToJourney");

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
    lkClearActivity();
    goPage("journey");
    return;
  }
  if (placeButton) {
    event.preventDefault();
    event.stopImmediatePropagation();
    void lkStartU1();
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
  lkClearActivity();
  goPage("today");
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
