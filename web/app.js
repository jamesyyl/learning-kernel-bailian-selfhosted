const LK_LOCAL_LEARNER = "local-learner-001";
const LK_LOCAL_ENVIRONMENT = "home";
const LK_MATH_U1_PACK = "org.learning-kernel.tw-math-g6-u1";
const LK_SURFACE_URL = `/api/learners/${encodeURIComponent(LK_LOCAL_LEARNER)}/environments/${encodeURIComponent(LK_LOCAL_ENVIRONMENT)}/packs/${encodeURIComponent(LK_MATH_U1_PACK)}/surface`;
const LK_OBSERVATIONS_URL = `/api/learners/${encodeURIComponent(LK_LOCAL_LEARNER)}/environments/${encodeURIComponent(LK_LOCAL_ENVIRONMENT)}/packs/${encodeURIComponent(LK_MATH_U1_PACK)}/observations`;
const LK_SURFACE_REQUEST = {
  currentContext: {
    currentPlaceLocalId: "u1-1/composite-number",
    todayPractice: true,
    learnerSelectedCandidateId: "navigation/fluency-practice/u1-1/family/direct-prime-composite-classification",
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
      ? "練習質數、合數與整除關係。每一步作答都會交給本機 Runtime 保存。"
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
  const learnButton = document.querySelector("#learnAtPlace");
  const practiceButton = document.querySelector("#practiceAtPlace");
  if (!list) return;

  list.replaceChildren();
  const item = document.createElement("li");
  const button = document.createElement("button");
  button.type = "button";
  button.className = `journey-stop ${isMath ? "is-active" : "local-disabled"}`;
  if (isMath) button.dataset.startSubject = "math";
  button.disabled = !isMath;
  button.setAttribute("aria-disabled", String(!isMath));
  const icon = document.createElement("span");
  icon.className = "stop-icon";
  icon.textContent = isMath ? "U1" : "…";
  const copy = document.createElement("span");
  const strong = document.createElement("strong");
  strong.textContent = isMath ? "數學 U1" : `${subjects[selected].name}尚未開放`;
  const small = document.createElement("small");
  small.textContent = isMath
    ? "質數、合數與整除關係；依 Runtime 活動逐步作答。"
    : "此科目尚未接通 Learning Kernel。";
  copy.append(strong, small);
  const state = document.createElement("span");
  state.className = "stop-state";
  state.textContent = isMath ? "已開放" : "準備中";
  button.append(icon, copy, state);
  item.append(button);
  list.append(item);

  if (placeSubject) placeSubject.textContent = subjects[selected].name;
  if (placeTitle) placeTitle.textContent = isMath ? "數學 U1・質數與合數" : "尚未開放";
  if (placeDescription) {
    placeDescription.textContent = isMath
      ? "從 Runtime 載入一個真實活動，完成兩個觀察步驟，並保存原始作答。"
      : `${subjects[selected].name}尚未接通 Learning Kernel 活動。`;
  }
  if (detailNote) {
    detailNote.textContent = isMath
      ? "數學 U1 可再次進入；其他科目尚未接通。"
      : "目前 Runtime 尚未接通這個科目。";
  }
  for (const control of [learnButton, practiceButton]) {
    if (control) {
      control.disabled = !isMath;
      control.classList.toggle("local-disabled", !isMath);
      control.setAttribute("aria-disabled", String(!isMath));
    }
  }
};

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
  document.querySelector("#backFromActivity").disabled = false;
  document.querySelector("#activityCounter").hidden = true;
  document.querySelector("#activityProgress").hidden = true;
  const submitButton = document.querySelector("#submitAnswer");
  submitButton.hidden = false;
  submitButton.disabled = false;
  submitButton.textContent = "送出作答";
  document.querySelector("#nextActivity").hidden = true;
  document.querySelector("#dailySummary").hidden = true;
  document.querySelector("#questionLayout").hidden = false;
  lkSetActivityState("");
}

async function lkStartU1() {
  if (selected !== "math") {
    lkToast(`${subjects[selected].name}尚未接通 Learning Kernel，目前不能開始活動。`);
    return;
  }
  lkClearActivity();
  document.querySelector("#activityModeLabel").textContent = "數學 U1・本機練習";
  document.querySelector("#activityTitle").textContent = "數學 U1｜質數與合數";
  document.querySelector("#activitySubject").textContent = "數學 U1";
  document.querySelector("#activitySubtopic").textContent = "質數、合數與整除關係";
  document.querySelector("#activityQuestion").textContent = "正在向 Learning Kernel 載入活動…";
  document.querySelector("#answerHost").replaceChildren();
  document.querySelector("#hintText").textContent = "活動載入後，可以先自己想想，也可以查看 Runtime 提供的提示。";
  document.querySelector("#hintButtonAside").hidden = true;
  document.querySelector(".activity-unjudged").textContent = "作答由 Learning Kernel 判斷；百煉只呈現結果";
  goPage("activity");

  try {
    const response = await fetch(LK_SURFACE_URL, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(LK_SURFACE_REQUEST),
      cache: "no-store",
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.error || "runtime_unavailable");
    if (body.schemaVersion !== "learning-kernel.surface-ir@1") {
      throw new Error("unexpected_surface_schema");
    }
    lkSurface = body;
    lkPoints = body.lineage?.reportableObservationPoints
      ?.filter((point) => Number.isInteger(point.stepIndex))
      .sort((a, b) => a.stepIndex - b.stepIndex) || [];
    const firstStepIndex = body.execution?.stepIndex;
    if (!Number.isInteger(firstStepIndex) || !lkPoints.some((point) => point.stepIndex === firstStepIndex)) {
      throw new Error("surface_step_unavailable");
    }
    lkRenderStep(firstStepIndex);
  } catch (error) {
    const code = error instanceof Error ? error.message : "runtime_unavailable";
    document.querySelector("#activityQuestion").textContent = "目前無法載入數學 U1 活動";
    document.querySelector("#answerHost").replaceChildren();
    document.querySelector("#submitAnswer").hidden = true;
    lkSetActivityState(lkErrorMessage(code), true);
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
    ["response.single-choice@1", "response.multi-choice@1"].includes(block.capability),
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
    lkRenderChoices(lkResponseBlock);
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
    block.capability === "response.multi-choice@1" ? "選擇可整除的數" : "選擇一個答案",
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
  const value = lkResponseValue;
  if (multi && (!Array.isArray(value) || value.length < Number(lkResponseBlock.props?.minSelections || 1))) {
    throw new Error("請先選擇題目要求數量的答案。");
  }
  if (!multi && (typeof value !== "string" || value.length === 0)) {
    throw new Error("請先選一個答案。");
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
    lkClearActivity();
    goPage("today");
  }
}

function lkHandleClick(event) {
  const target = event.target instanceof Element ? event.target : null;
  if (!target) return;

  const answer = target.closest(".runtime-answer-choice");
  const start = target.closest("[data-start-subject]");
  const modeButton = target.closest("[data-mode]");
  const submitButton = target.closest("#submitAnswer");
  const nextButton = target.closest("#nextActivity");
  const hintButton = target.closest("#hintButtonAside");
  const placeButton = target.closest("#learnAtPlace, #practiceAtPlace");
  const recommendedButton = target.closest("#startRecommended");

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
renderParent();
lkShowUnavailableGrowth();
lkUpdateShell();
void lkCheckReadiness();

if (lkHomeHeroTitle) lkHomeHeroTitle.textContent = "數學 U1";
