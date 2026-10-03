(() => {
  const cards = Array.isArray(window.DEFENSE_CARDS) ? window.DEFENSE_CARDS : [];
  const storageKey = "luoyang-defense-cards-v1";
  const modeNames = { all: "全部题目", due: "今日复习", weak: "不会与模糊", favorites: "我的收藏" };
  const intervals = { again: 1, hard: 3, good: 7 };

  const $ = (selector) => document.querySelector(selector);
  const elements = {
    card: $("#studyCard"), modeLabel: $("#modeLabel"), progressText: $("#progressText"), progressBar: $("#progressBar"),
    category: $("#categoryLabel"), number: $("#questionNumber"), question: $("#questionText"), keywords: $("#keywords"),
    favorite: $("#favoriteButton"), reveal: $("#revealButton"), answer: $("#answerContent"), answerText: $("#answerText"),
    focus: $("#focusNote"), rating: $("#ratingPanel"), prev: $("#prevButton"), next: $("#nextButton"), shuffle: $("#shuffleButton"),
    panel: $("#sidePanel"), openPanel: $("#openPanelButton"), closePanel: $("#closePanelButton"), backdrop: $("#panelBackdrop"),
    categorySelect: $("#categorySelect"), modeGrid: $("#modeGrid"), mastered: $("#masteredCount"), due: $("#dueCount"), favorites: $("#favoriteCount"),
    searchInput: $("#searchInput"), searchButton: $("#searchButton"), searchResults: $("#searchResults"),
    timer: $("#timerToast"), timerText: $("#timerText"), startTimer: $("#startTimerButton"), stopTimer: $("#stopTimerButton"),
    loopSingle: $("#loopSingleButton"), loopAll: $("#loopAllButton"), speechDock: $("#speechDock"),
    speechModeText: $("#speechModeText"), speechStatusText: $("#speechStatusText"), speechRate: $("#speechRateSelect"),
    pauseSpeech: $("#pauseSpeechButton"), stopSpeech: $("#stopSpeechButton"), narrationAudio: $("#narrationAudio"),
    toast: $("#toast"), install: $("#installButton"), compatibilityNote: $("#browserCompatibilityNote"),
    export: $("#exportButton"), import: $("#importInput")
  };

  const defaultState = { ratings: {}, favorites: [], mode: "all", category: "all", currentId: 1, speechRate: 1 };
  let state = loadState();
  let queue = [];
  let index = 0;
  let revealed = false;
  let timerId = null;
  let timerRemaining = 90;
  let deferredInstallPrompt = null;
  let touchStartX = null;
  let speechMode = null;
  let speechPaused = false;
  let speechRunId = 0;
  let speechCardIndex = 0;
  let singleSpeechCard = null;
  let wakeLock = null;
  let usingRecordedAudio = false;

  function loadState() {
    try { return { ...defaultState, ...JSON.parse(localStorage.getItem(storageKey) || "{}") }; }
    catch { return { ...defaultState }; }
  }

  function saveState() { localStorage.setItem(storageKey, JSON.stringify(state)); }
  function todayStart() { const d = new Date(); d.setHours(23, 59, 59, 999); return d.getTime(); }

  function rebuildQueue(keepCurrent = true) {
    const currentId = keepCurrent && queue[index] ? queue[index].id : state.currentId;
    queue = cards.filter((card) => {
      if (state.category !== "all" && card.category !== state.category) return false;
      const rating = state.ratings[card.id];
      if (state.mode === "favorites") return state.favorites.includes(card.id);
      if (state.mode === "weak") return rating && rating.level !== "good";
      if (state.mode === "due") return !rating || rating.nextDue <= todayStart();
      return true;
    });
    index = Math.max(0, queue.findIndex((card) => card.id === currentId));
    if (!queue.length) index = 0;
    renderCard();
    updateStats();
  }

  function renderCard() {
    stopTimer();
    revealed = false;
    elements.answer.hidden = true;
    elements.reveal.hidden = false;
    elements.rating.hidden = true;
    if (!queue.length) {
      elements.category.textContent = "本组已完成";
      elements.number.textContent = "暂无题目";
      elements.question.textContent = state.mode === "favorites" ? "还没有收藏题目" : "当前筛选下没有待练习题目";
      elements.keywords.innerHTML = '<span class="keyword">打开练习中心重新选择</span>';
      elements.reveal.hidden = true;
      elements.prev.disabled = true;
      elements.next.disabled = true;
      elements.progressText.textContent = "0 / 0";
      elements.progressBar.style.width = "0%";
      return;
    }

    const card = queue[index];
    state.currentId = card.id;
    saveState();
    elements.category.textContent = card.category;
    elements.number.textContent = `问题 ${card.id}`;
    elements.question.textContent = card.question;
    elements.keywords.innerHTML = card.keywords.map((word) => `<span class="keyword">${escapeHtml(word)}</span>`).join("");
    elements.answerText.textContent = card.answer;
    elements.focus.hidden = !card.focus;
    elements.focus.textContent = card.focus ? `考察点：${card.focus}` : "";
    const favorite = state.favorites.includes(card.id);
    elements.favorite.textContent = favorite ? "★" : "☆";
    elements.favorite.setAttribute("aria-pressed", String(favorite));
    elements.progressText.textContent = `${index + 1} / ${queue.length}`;
    elements.progressBar.style.width = `${((index + 1) / queue.length) * 100}%`;
    elements.modeLabel.textContent = modeNames[state.mode];
    elements.prev.disabled = queue.length < 2;
    elements.next.disabled = queue.length < 2;
  }

  function revealAnswer() {
    if (!queue.length || revealed) return;
    revealed = true;
    elements.reveal.hidden = true;
    elements.answer.hidden = false;
    elements.rating.hidden = false;
    elements.answer.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  function move(direction) {
    if (speechMode) stopNarration();
    if (queue.length < 2) return;
    elements.card.classList.add(direction > 0 ? "slide-left" : "slide-right");
    setTimeout(() => {
      index = (index + direction + queue.length) % queue.length;
      renderCard();
      elements.card.classList.remove("slide-left", "slide-right");
      window.scrollTo({ top: 0, behavior: "smooth" });
    }, 150);
  }

  function rate(level) {
    const card = queue[index];
    if (!card) return;
    const days = intervals[level];
    state.ratings[card.id] = { level, reviewedAt: Date.now(), nextDue: Date.now() + days * 86400000 };
    saveState();
    showToast(level === "good" ? "已记录：会了" : level === "hard" ? "已记录：还需巩固" : "已加入明日复习");
    updateStats();
    setTimeout(() => move(1), 260);
  }

  function toggleFavorite() {
    const card = queue[index];
    if (!card) return;
    const position = state.favorites.indexOf(card.id);
    if (position >= 0) state.favorites.splice(position, 1); else state.favorites.push(card.id);
    saveState();
    if (state.mode === "favorites" && position >= 0) rebuildQueue(false); else renderCard();
    updateStats();
  }

  function updateStats() {
    const ratings = Object.values(state.ratings);
    elements.mastered.textContent = ratings.filter((item) => item.level === "good").length;
    elements.due.textContent = cards.filter((card) => !state.ratings[card.id] || state.ratings[card.id].nextDue <= todayStart()).length;
    elements.favorites.textContent = state.favorites.length;
  }

  function setMode(mode) {
    state.mode = mode;
    saveState();
    elements.modeGrid.querySelectorAll("button").forEach((button) => button.classList.toggle("selected", button.dataset.mode === mode));
    rebuildQueue(false);
    closePanel();
  }

  function openPanel() {
    elements.panel.classList.add("open");
    elements.panel.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
    updateStats();
    setTimeout(() => elements.closePanel.focus(), 50);
  }

  function closePanel() {
    elements.panel.classList.remove("open");
    elements.panel.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
  }

  function runSearch() {
    const term = elements.searchInput.value.trim().toLowerCase();
    elements.searchResults.innerHTML = "";
    if (!term) return;
    const results = cards.filter((card) => `${card.question} ${card.keywords.join(" ")}`.toLowerCase().includes(term)).slice(0, 8);
    if (!results.length) {
      elements.searchResults.innerHTML = '<p class="panel-note">没有找到匹配题目。</p>';
      return;
    }
    results.forEach((card) => {
      const button = document.createElement("button");
      button.className = "search-result";
      button.innerHTML = `<small>问题 ${card.id} · ${escapeHtml(card.category)}</small>${escapeHtml(card.question)}`;
      button.addEventListener("click", () => {
        state.mode = "all";
        state.category = "all";
        elements.categorySelect.value = "all";
        state.currentId = card.id;
        saveState();
        rebuildQueue(false);
        closePanel();
      });
      elements.searchResults.appendChild(button);
    });
  }

  function startTimer() {
    stopTimer();
    timerRemaining = 90;
    elements.timer.hidden = false;
    updateTimerText();
    timerId = setInterval(() => {
      timerRemaining -= 1;
      updateTimerText();
      if (timerRemaining <= 0) {
        stopTimer(false);
        elements.timer.hidden = false;
        elements.timerText.textContent = "时间到";
        if (navigator.vibrate) navigator.vibrate([180, 100, 180]);
        showToast("90秒口述时间到");
        setTimeout(() => { elements.timer.hidden = true; }, 3500);
      }
    }, 1000);
  }

  function stopTimer(hide = true) {
    if (timerId) clearInterval(timerId);
    timerId = null;
    if (hide) elements.timer.hidden = true;
  }

  function updateTimerText() {
    const minutes = String(Math.floor(timerRemaining / 60)).padStart(2, "0");
    const seconds = String(timerRemaining % 60).padStart(2, "0");
    elements.timerText.textContent = `${minutes}:${seconds}`;
  }

  function splitForSpeech(text, maxLength = 70) {
    const sentences = String(text).replace(/\s+/g, " ").match(/[^。！？；]+[。！？；]?/g) || [String(text)];
    const chunks = [];
    sentences.forEach((sentence) => {
      let remaining = sentence.trim();
      while (remaining.length > maxLength) {
        let cut = Math.max(remaining.lastIndexOf("，", maxLength), remaining.lastIndexOf("、", maxLength));
        if (cut < Math.floor(maxLength * .55)) cut = maxLength;
        chunks.push(remaining.slice(0, cut + (cut === maxLength ? 0 : 1)));
        remaining = remaining.slice(cut + (cut === maxLength ? 0 : 1)).trim();
      }
      if (remaining) chunks.push(remaining);
    });
    return chunks;
  }

  function narrationSegments(card) {
    return [
      { label: "正在朗诵题目", text: `第${card.id}题。${card.question}` },
      { label: "正在朗诵关键词", text: `关键词。${card.keywords.join("，")}` },
      ...splitForSpeech(`参考答案。${card.answer}`).map((text) => ({ label: "正在朗诵答案", text })),
      ...(card.focus ? splitForSpeech(`考察点。${card.focus}`).map((text) => ({ label: "正在朗诵考察点", text })) : [])
    ];
  }

  function getChineseVoice() {
    const voices = window.speechSynthesis?.getVoices?.() || [];
    return voices.find((voice) => /^zh-CN$/i.test(voice.lang) && voice.localService)
      || voices.find((voice) => /^zh-CN$/i.test(voice.lang))
      || voices.find((voice) => /^zh/i.test(voice.lang))
      || null;
  }

  async function holdScreenAwake() {
    if (!speechMode || document.visibilityState !== "visible" || !navigator.wakeLock?.request) return;
    try {
      wakeLock = await navigator.wakeLock.request("screen");
      wakeLock.addEventListener("release", () => { wakeLock = null; }, { once: true });
    } catch { /* The browser may deny wake lock in power-saving mode. */ }
  }

  async function releaseWakeLock() {
    if (!wakeLock) return;
    try { await wakeLock.release(); } catch { /* Already released by the browser. */ }
    wakeLock = null;
  }

  function showAnswerWithoutScrolling() {
    revealed = true;
    elements.reveal.hidden = true;
    elements.answer.hidden = false;
    elements.rating.hidden = false;
  }

  function showNarratedCard(card) {
    if (!card) return;
    state.mode = "all";
    state.category = "all";
    queue = cards.slice();
    index = Math.max(0, queue.findIndex((item) => item.id === card.id));
    elements.categorySelect.value = "all";
    elements.modeGrid.querySelectorAll("button").forEach((button) => button.classList.toggle("selected", button.dataset.mode === "all"));
    renderCard();
    showAnswerWithoutScrolling();
  }

  function updateSpeechControls() {
    const active = Boolean(speechMode);
    elements.speechDock.hidden = !active;
    document.body.classList.toggle("speech-active", active);
    elements.speechDock.classList.toggle("paused", speechPaused);
    elements.pauseSpeech.textContent = speechPaused ? "继续" : "暂停";
    elements.loopSingle.classList.toggle("active", speechMode === "single");
    elements.loopAll.classList.toggle("active", speechMode === "all");
    elements.loopSingle.setAttribute("aria-pressed", String(speechMode === "single"));
    elements.loopAll.setAttribute("aria-pressed", String(speechMode === "all"));
  }

  function speakSegment(segments, segmentIndex, card, runId) {
    if (!speechMode || runId !== speechRunId) return;
    if (segmentIndex >= segments.length) {
      elements.speechStatusText.textContent = speechMode === "single" ? `第${card.id}题朗诵完毕，即将重复` : `第${card.id}题朗诵完毕，即将进入下一题`;
      setTimeout(() => {
        if (!speechMode || runId !== speechRunId) return;
        if (speechMode === "all") speechCardIndex = (speechCardIndex + 1) % cards.length;
        speakCurrentNarrationCard(runId);
      }, 900);
      return;
    }

    const segment = segments[segmentIndex];
    elements.speechStatusText.textContent = `${segment.label} · 第${card.id}题`;
    const utterance = new SpeechSynthesisUtterance(segment.text);
    utterance.lang = "zh-CN";
    utterance.rate = Number(state.speechRate) || 1;
    utterance.pitch = 1;
    const voice = getChineseVoice();
    if (voice) utterance.voice = voice;
    utterance.onend = () => speakSegment(segments, segmentIndex + 1, card, runId);
    utterance.onerror = (event) => {
      if (event.error === "canceled" || event.error === "interrupted" || runId !== speechRunId) return;
      elements.speechStatusText.textContent = "朗诵遇到问题，请停止后重试";
    };
    window.speechSynthesis.speak(utterance);
  }

  function speakCurrentNarrationCard(runId) {
    if (!speechMode || runId !== speechRunId) return;
    const card = speechMode === "single" ? singleSpeechCard : cards[speechCardIndex];
    if (!card) return;
    showNarratedCard(card);
    elements.speechModeText.textContent = speechMode === "single" ? `单题循环 · 第${card.id}题` : `全部循环 · ${speechCardIndex + 1}/${cards.length}`;
    if (usingRecordedAudio) {
      playRecordedCard(card, runId);
      return;
    }
    speakSegment(narrationSegments(card), 0, card, runId);
  }

  function recordedAudioPath(card) {
    const filename = `audio/card-${String(card.id).padStart(2, "0")}.mp3?v=12`;
    const bundledHost = /(^localhost$|^127\.0\.0\.1$|\.chatgpt\.site$)/i.test(location.hostname);
    return bundledHost ? filename : `https://luoyang-youshi-dabian-cards.benfeili64.chatgpt.site/${filename}`;
  }

  function updateMediaSession(card) {
    if (!("mediaSession" in navigator) || !("MediaMetadata" in window)) return;
    navigator.mediaSession.metadata = new MediaMetadata({
      title: `第${card.id}题 · ${card.question}`,
      artist: "洛阳幼师答辩题卡",
      album: speechMode === "single" ? "单题循环" : "全部题目循环",
      artwork: [
        { src: "icon-192.png", sizes: "192x192", type: "image/png" },
        { src: "icon-512.png", sizes: "512x512", type: "image/png" }
      ]
    });
  }

  function playRecordedCard(card, runId) {
    const audio = elements.narrationAudio;
    audio.pause();
    audio.onended = () => {
      if (!speechMode || runId !== speechRunId) return;
      if (speechMode === "all") speechCardIndex = (speechCardIndex + 1) % cards.length;
      speakCurrentNarrationCard(runId);
    };
    audio.onerror = () => {
      if (!speechMode || runId !== speechRunId) return;
      stopNarration(false);
      showToast("音频加载失败，请刷新页面后重试", 5200);
    };
    audio.loop = speechMode === "single";
    audio.src = recordedAudioPath(card);
    audio.playbackRate = Number(state.speechRate) || 1;
    audio.setAttribute("playsinline", "true");
    audio.setAttribute("webkit-playsinline", "true");
    audio.setAttribute("x5-playsinline", "true");
    audio.load();
    elements.speechStatusText.textContent = `正在播放固定音频 · 第${card.id}题`;
    updateMediaSession(card);
    const playback = audio.play();
    if (playback && typeof playback.then === "function") {
      playback.then(() => {
        if ("mediaSession" in navigator) navigator.mediaSession.playbackState = "playing";
      }).catch(() => {
        speechPaused = true;
        updateSpeechControls();
        elements.speechStatusText.textContent = "浏览器等待手动授权，请点“继续”";
        showToast("请点下方“继续”按钮开启声音", 4200);
      });
    } else if ("mediaSession" in navigator) {
      navigator.mediaSession.playbackState = "playing";
    }
  }

  function startNarration(mode) {
    // Some Xiaomi/vivo browsers incorrectly reject an MP3 capability hint even
    // though their native media engine plays the file normally. Attempt the actual
    // recorded file instead of blocking playback based on that unreliable hint.
    usingRecordedAudio = Boolean(elements.narrationAudio);
    const currentCard = queue[index];
    if (!currentCard) return;
    window.speechSynthesis?.cancel();
    elements.narrationAudio.pause();
    speechRunId += 1;
    speechMode = mode;
    speechPaused = false;
    singleSpeechCard = mode === "single" ? currentCard : null;
    speechCardIndex = mode === "all" ? 0 : Math.max(0, cards.findIndex((card) => card.id === currentCard.id));
    elements.speechRate.value = String(state.speechRate || 1);
    updateSpeechControls();
    void holdScreenAwake();
    speakCurrentNarrationCard(speechRunId);
  }

  function toggleSpeechPause() {
    if (!speechMode) return;
    if (speechPaused) {
      if (usingRecordedAudio) void elements.narrationAudio.play(); else window.speechSynthesis.resume();
      speechPaused = false;
      void holdScreenAwake();
      if (usingRecordedAudio && "mediaSession" in navigator) navigator.mediaSession.playbackState = "playing";
    } else {
      if (usingRecordedAudio) elements.narrationAudio.pause(); else window.speechSynthesis.pause();
      speechPaused = true;
      if (usingRecordedAudio && "mediaSession" in navigator) navigator.mediaSession.playbackState = "paused";
    }
    updateSpeechControls();
    elements.speechStatusText.textContent = speechPaused ? "已暂停，点“继续”恢复" : "继续朗诵";
  }

  function restartNarrationAtNewRate() {
    state.speechRate = Number(elements.speechRate.value) || 1;
    saveState();
    if (!speechMode) return;
    if (usingRecordedAudio) {
      elements.narrationAudio.playbackRate = state.speechRate;
      showToast(`语速已调整为${elements.speechRate.options[elements.speechRate.selectedIndex].text}`);
      return;
    }
    window.speechSynthesis.cancel();
    speechRunId += 1;
    speechPaused = false;
    updateSpeechControls();
    speakCurrentNarrationCard(speechRunId);
  }

  function stopNarration(showMessage = true) {
    if (!speechMode) return;
    speechRunId += 1;
    window.speechSynthesis?.cancel();
    elements.narrationAudio.pause();
    elements.narrationAudio.removeAttribute("src");
    elements.narrationAudio.load();
    speechMode = null;
    speechPaused = false;
    singleSpeechCard = null;
    usingRecordedAudio = false;
    updateSpeechControls();
    void releaseWakeLock();
    if (showMessage) showToast("已停止循环朗诵");
  }

  function showToast(message, duration = 1800) {
    elements.toast.textContent = message;
    elements.toast.hidden = false;
    clearTimeout(showToast.timer);
    showToast.timer = setTimeout(() => { elements.toast.hidden = true; }, duration);
  }

  function detectAndroidBrowser() {
    const ua = navigator.userAgent || "";
    if (!/Android/i.test(ua)) return null;
    if (/baidubrowser|baiduboxapp|bidubrowser|\bbaidu\b/i.test(ua)) return "百度浏览器";
    if (/MiuiBrowser|MiBrowser|XiaoMi|\bMIUI\b/i.test(ua)) return "小米浏览器";
    if (/VivoBrowser|\bvivo\b/i.test(ua)) return "vivo浏览器";
    if (/HuaweiBrowser/i.test(ua)) return "华为浏览器";
    if (/EdgA/i.test(ua)) return "Edge安卓浏览器";
    if (/Chrome|CriOS/i.test(ua)) return "安卓Chrome";
    return "安卓浏览器";
  }

  function installHint(browserName) {
    if (browserName === "百度浏览器") return "百度浏览器兼容模式：首次朗诵请点击循环按钮；如系统拦截声音，再点一次“继续”。";
    if (browserName === "小米浏览器") return "小米浏览器：点底部或右下角菜单，选择“添加到桌面”或“安装应用”。";
    if (browserName === "vivo浏览器") return "vivo浏览器：点菜单，选择“添加到桌面”或“安装应用”；若没有该项，可用安卓Chrome打开。";
    return `${browserName || "当前浏览器"}：点浏览器菜单，选择“安装应用”或“添加到主屏幕”。`;
  }

  function initializeAndroidCompatibility() {
    const browserName = detectAndroidBrowser();
    if (!browserName) return;
    elements.install.hidden = browserName === "百度浏览器";
    elements.compatibilityNote.hidden = false;
    elements.compatibilityNote.textContent = `${browserName}已适配，朗诵使用固定MP3音频。${installHint(browserName)}`;
    try { window.speechSynthesis?.getVoices?.(); } catch { /* Optional voice warm-up. */ }
  }

  function exportProgress() {
    const blob = new Blob([JSON.stringify({ app: "洛阳幼师答辩题卡", version: 1, exportedAt: new Date().toISOString(), state }, null, 2)], { type: "application/json" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `答辩题卡学习记录-${new Date().toISOString().slice(0, 10)}.json`;
    link.click();
    URL.revokeObjectURL(link.href);
  }

  function importProgress(file) {
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const imported = JSON.parse(reader.result);
        if (!imported.state || !imported.state.ratings) throw new Error("invalid");
        state = { ...defaultState, ...imported.state };
        saveState();
        elements.categorySelect.value = state.category;
        elements.modeGrid.querySelectorAll("button").forEach((button) => button.classList.toggle("selected", button.dataset.mode === state.mode));
        rebuildQueue(true);
        showToast("学习记录已导入");
      } catch { showToast("文件格式不正确"); }
    };
    reader.readAsText(file, "utf-8");
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char]));
  }

  function initializeCategories() {
    [...new Set(cards.map((card) => card.category))].forEach((category) => {
      const option = document.createElement("option");
      option.value = category;
      option.textContent = category;
      elements.categorySelect.appendChild(option);
    });
    elements.categorySelect.value = state.category;
  }

  function registerWebMcpTools() {
    const context = typeof document === "undefined" ? null : document.modelContext;
    if (!context?.registerTool) return;
    const register = (tool) => {
      try { void Promise.resolve(context.registerTool(tool)).catch(() => {}); } catch { /* Unsupported preview runtime. */ }
    };

    register({
      name: "get_study_status",
      title: "查看学习进度",
      description: "读取答辩题卡的总题数、已掌握数量、待复习数量和收藏数量。",
      inputSchema: { type: "object", properties: {}, additionalProperties: false },
      annotations: { readOnlyHint: true, untrustedContentHint: false },
      execute() {
        const ratings = Object.values(state.ratings);
        return {
          total: cards.length,
          mastered: ratings.filter((item) => item.level === "good").length,
          due: cards.filter((card) => !state.ratings[card.id] || state.ratings[card.id].nextDue <= todayStart()).length,
          favorites: state.favorites.length,
          current_card_id: queue[index]?.id ?? null
        };
      }
    });

    register({
      name: "show_flashcard",
      title: "打开指定题卡",
      description: `按1至${cards.length}的题号打开对应答辩题卡，显示问题和关键词但不自动揭晓答案。`,
      inputSchema: {
        type: "object",
        properties: { card_id: { type: "integer", minimum: 1, maximum: cards.length } },
        required: ["card_id"],
        additionalProperties: false
      },
      annotations: { readOnlyHint: false, untrustedContentHint: false },
      execute(input) {
        const cardId = Number(input?.card_id);
        if (!Number.isInteger(cardId) || !cards.some((card) => card.id === cardId)) throw new Error(`card_id必须是1至${cards.length}之间的整数`);
        state.mode = "all";
        state.category = "all";
        state.currentId = cardId;
        saveState();
        elements.categorySelect.value = "all";
        rebuildQueue(false);
        return { card_id: cardId, question: queue[index]?.question ?? "", answer_revealed: false };
      }
    });

    register({
      name: "record_mastery",
      title: "记录题卡掌握程度",
      description: "为指定题卡记录不会、模糊或会了，并安排下一次复习时间。",
      inputSchema: {
        type: "object",
        properties: {
          card_id: { type: "integer", minimum: 1, maximum: cards.length },
          level: { type: "string", enum: ["again", "hard", "good"] }
        },
        required: ["card_id", "level"],
        additionalProperties: false
      },
      annotations: { readOnlyHint: false, untrustedContentHint: false },
      execute(input) {
        const cardId = Number(input?.card_id);
        const level = input?.level;
        if (!Number.isInteger(cardId) || !cards.some((card) => card.id === cardId)) throw new Error(`card_id必须是1至${cards.length}之间的整数`);
        if (!Object.prototype.hasOwnProperty.call(intervals, level)) throw new Error("level必须是again、hard或good");
        const days = intervals[level];
        const nextDue = Date.now() + days * 86400000;
        state.ratings[cardId] = { level, reviewedAt: Date.now(), nextDue };
        saveState();
        updateStats();
        return { card_id: cardId, level, next_due: new Date(nextDue).toISOString() };
      }
    });
  }

  elements.reveal.addEventListener("click", revealAnswer);
  elements.prev.addEventListener("click", () => move(-1));
  elements.next.addEventListener("click", () => move(1));
  elements.shuffle.addEventListener("click", () => {
    if (!queue.length) return;
    index = Math.floor(Math.random() * queue.length);
    renderCard();
    showToast("已随机抽取一题");
  });
  elements.favorite.addEventListener("click", toggleFavorite);
  document.querySelectorAll("[data-rating]").forEach((button) => button.addEventListener("click", () => rate(button.dataset.rating)));
  elements.openPanel.addEventListener("click", openPanel);
  elements.closePanel.addEventListener("click", closePanel);
  elements.backdrop.addEventListener("click", closePanel);
  elements.modeGrid.addEventListener("click", (event) => { const button = event.target.closest("button[data-mode]"); if (button) setMode(button.dataset.mode); });
  elements.categorySelect.addEventListener("change", () => { state.category = elements.categorySelect.value; saveState(); rebuildQueue(false); closePanel(); });
  elements.searchButton.addEventListener("click", runSearch);
  elements.searchInput.addEventListener("keydown", (event) => { if (event.key === "Enter") runSearch(); });
  elements.startTimer.addEventListener("click", startTimer);
  elements.stopTimer.addEventListener("click", () => stopTimer());
  elements.loopSingle.addEventListener("click", () => speechMode === "single" ? stopNarration() : startNarration("single"));
  elements.loopAll.addEventListener("click", () => speechMode === "all" ? stopNarration() : startNarration("all"));
  elements.pauseSpeech.addEventListener("click", toggleSpeechPause);
  elements.stopSpeech.addEventListener("click", () => stopNarration());
  elements.speechRate.addEventListener("change", restartNarrationAtNewRate);
  elements.export.addEventListener("click", exportProgress);
  elements.import.addEventListener("change", () => { if (elements.import.files[0]) importProgress(elements.import.files[0]); elements.import.value = ""; });

  elements.card.addEventListener("pointerdown", (event) => {
    touchStartX = event.target.closest("button, input, select, label") ? null : event.clientX;
  });
  elements.card.addEventListener("pointerup", (event) => {
    if (touchStartX === null || speechMode) { touchStartX = null; return; }
    const delta = event.clientX - touchStartX;
    touchStartX = null;
    if (Math.abs(delta) > 65) move(delta < 0 ? 1 : -1);
  });
  elements.card.addEventListener("pointercancel", () => { touchStartX = null; });
  document.addEventListener("keydown", (event) => {
    if (elements.panel.classList.contains("open")) { if (event.key === "Escape") closePanel(); return; }
    if (event.key === "ArrowRight") move(1);
    if (event.key === "ArrowLeft") move(-1);
    if ((event.key === " " || event.key === "Enter") && document.activeElement === document.body) { event.preventDefault(); revealAnswer(); }
  });

  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    deferredInstallPrompt = event;
    elements.install.hidden = false;
  });
  elements.install.addEventListener("click", async () => {
    if (!deferredInstallPrompt) { showToast(installHint(detectAndroidBrowser()), 5200); return; }
    deferredInstallPrompt.prompt();
    await deferredInstallPrompt.userChoice;
    deferredInstallPrompt = null;
    elements.install.hidden = true;
  });
  window.addEventListener("appinstalled", () => showToast("已安装到手机桌面"));
  document.addEventListener("visibilitychange", () => { if (speechMode && document.visibilityState === "visible") void holdScreenAwake(); });
  window.addEventListener("beforeunload", () => { window.speechSynthesis?.cancel(); elements.narrationAudio.pause(); void releaseWakeLock(); });

  if (!cards.length) {
    elements.question.textContent = "题库加载失败，请刷新页面";
    elements.reveal.hidden = true;
    return;
  }
  initializeCategories();
  initializeAndroidCompatibility();
  if ("mediaSession" in navigator) {
    try {
      navigator.mediaSession.setActionHandler("play", () => { if (speechMode && speechPaused) toggleSpeechPause(); });
      navigator.mediaSession.setActionHandler("pause", () => { if (speechMode && !speechPaused) toggleSpeechPause(); });
      navigator.mediaSession.setActionHandler("nexttrack", () => {
        if (speechMode !== "all") return;
        speechCardIndex = (speechCardIndex + 1) % cards.length;
        elements.narrationAudio.pause();
        speakCurrentNarrationCard(speechRunId);
      });
      navigator.mediaSession.setActionHandler("previoustrack", () => {
        if (speechMode !== "all") return;
        speechCardIndex = (speechCardIndex - 1 + cards.length) % cards.length;
        elements.narrationAudio.pause();
        speakCurrentNarrationCard(speechRunId);
      });
    } catch { /* Some Android browsers expose only part of Media Session. */ }
  }
  elements.speechRate.value = String(state.speechRate || 1);
  registerWebMcpTools();
  elements.modeGrid.querySelectorAll("button").forEach((button) => button.classList.toggle("selected", button.dataset.mode === state.mode));
  rebuildQueue(true);
})();
