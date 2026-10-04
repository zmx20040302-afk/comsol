(function () {
  "use strict";

  var categories = window.CATEGORIES || [];
  var items = window.LESSONS || [];
  var audioPacks = window.AUDIO_PACKS || {};
  var activeObjectUrl = "";
  var sourceRequestId = 0;
  var itemById = {};
  items.forEach(function (item) { itemById[item.id] = item; });

  var storageKey = "weixingke-audio-v2";
  var saved = {};
  try { saved = JSON.parse(localStorage.getItem(storageKey) || "{}"); } catch (_error) { saved = {}; }

  var initialIndex = Math.max(0, items.findIndex(function (item) { return item.id === saved.itemId; }));
  var state = {
    itemIndex: initialIndex,
    part: saved.part === "reflection" ? "reflection" : "process",
    loop: Boolean(saved.loop),
    continuous: saved.continuous !== false,
    speed: [0.8, 1, 1.2].indexOf(Number(saved.speed)) >= 0 ? Number(saved.speed) : 1,
    positions: saved.positions || {},
    trackIndices: saved.trackIndices || {}
  };

  function byId(id) { return document.getElementById(id); }
  var el = {
    category: byId("categorySelect"), picker: byId("lessonPicker"), cards: byId("lessonCards"), count: byId("lessonCount"), openPicker: byId("openPickerButton"),
    field: byId("fieldBadge"), kind: byId("kindBadge"), title: byId("lessonTitle"), previous: byId("previousLesson"), next: byId("nextLesson"),
    processTab: byId("scriptTab"), reflectionTab: byId("reflectionTab"), playSection: byId("playSectionButton"), continuous: byId("continuousButton"),
    content: byId("articleContent"), audio: byId("lessonAudio"), nowTitle: byId("nowPlayingTitle"), nowPart: byId("nowPlayingPart"),
    loop: byId("loopButton"), current: byId("currentTime"), duration: byId("durationTime"), range: byId("progressRange"),
    back: byId("backButton"), playPause: byId("playPauseButton"), forward: byId("forwardButton"), speed: byId("speedSelect"), toast: byId("toast")
  };
  var activeBlockIndex = -1;
  var resumeAfterLoad = false;

  function currentItem() { return items[state.itemIndex]; }
  function currentCategory() { return categories.find(function (category) { return category.id === currentItem().categoryId; }); }
  function currentTrackKey() { return currentItem().id + "-" + state.part; }
  function currentBlocks() { return state.part === "process" ? currentItem().processBlocks : currentItem().reflectionBlocks; }
  function currentAudioPaths() { return currentItem().audio[state.part] || []; }
  function currentTrackIndex() {
    var paths = currentAudioPaths();
    var index = Number(state.trackIndices[currentTrackKey()]) || 0;
    return Math.max(0, Math.min(Math.max(0, paths.length - 1), index));
  }
  function currentPositionKey() { return currentTrackKey() + "-" + currentTrackIndex(); }
  function saveState() {
    try {
      localStorage.setItem(storageKey, JSON.stringify({
        itemId: currentItem().id, part: state.part, loop: state.loop, continuous: state.continuous,
        speed: state.speed, positions: state.positions, trackIndices: state.trackIndices
      }));
    } catch (_error) { /* Storage can be disabled. */ }
  }
  function escapeHtml(text) {
    return String(text).replace(/[&<>"']/g, function (char) { return ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"})[char]; });
  }
  function formatText(text) { return escapeHtml(text).replace(/\[([^\]]+)\]/g, '<span class="placeholder">[$1]</span>'); }
  function formatTime(seconds) {
    if (!isFinite(seconds) || seconds < 0) return "00:00";
    var minutes = Math.floor(seconds / 60);
    var remain = Math.floor(seconds % 60);
    return (minutes < 10 ? "0" : "") + minutes + ":" + (remain < 10 ? "0" : "") + remain;
  }
  function showToast(message) {
    el.toast.textContent = message;
    el.toast.hidden = false;
    clearTimeout(showToast.timer);
    showToast.timer = setTimeout(function () { el.toast.hidden = true; }, 2800);
  }

  function buildCategoryOptions() {
    el.category.innerHTML = categories.map(function (category) {
      return '<option value="' + category.id + '">' + category.id + ' ' + escapeHtml(category.title) + '（' + category.itemIds.length + '篇）</option>';
    }).join("");
    el.category.value = currentItem().categoryId;
  }

  function buildItemCards() {
    var category = currentCategory();
    var categoryItems = category.itemIds.map(function (id) { return itemById[id]; });
    var lessonNumber = 0;
    el.cards.innerHTML = categoryItems.map(function (item) {
      if (item.kind === "lesson") lessonNumber += 1;
      var flatIndex = items.indexOf(item);
      var label = item.kind === "template" ? "通用模板" : "对应教案 " + lessonNumber;
      return '<button class="lesson-card ' + item.kind + (flatIndex === state.itemIndex ? ' selected' : '') + '" type="button" data-index="' + flatIndex + '">' +
        '<span>' + escapeHtml(label) + '</span><strong>' + escapeHtml(item.title) + '</strong></button>';
    }).join("");
    var currentInCategory = category.itemIds.indexOf(currentItem().id) + 1;
    el.count.textContent = currentInCategory + " / " + category.itemIds.length;
  }

  function renderContent() {
    var blocks = currentBlocks();
    var total = blocks.reduce(function (sum, block) { return sum + Math.max(1, block.paragraphs.join("").length); }, 0) || 1;
    var running = 0;
    el.content.innerHTML = blocks.map(function (block) {
      var start = running / total;
      running += Math.max(1, block.paragraphs.join("").length);
      var end = running / total;
      var className = state.part === "reflection" ? "reflection-block" : "step-block";
      return '<section class="reading-block ' + className + '" data-start="' + start + '" data-end="' + end + '">' +
        '<h3 class="block-heading"><span>' + escapeHtml(block.heading) + '</span><small>' + escapeHtml(block.meta || "") + '</small></h3>' +
        block.paragraphs.map(function (paragraph) { return '<p>' + formatText(paragraph) + '</p>'; }).join("") + '</section>';
    }).join("");
    activeBlockIndex = -1;
  }

  function resolveAudioSource(path) {
    var packed = audioPacks[path];
    if (!packed) return Promise.resolve(path + "?v=4");
    var firstByte = packed.offset;
    var lastByte = packed.offset + packed.length - 1;
    return fetch(packed.pack + "?v=4", {
      headers: { Range: "bytes=" + firstByte + "-" + lastByte }
    }).then(function (response) {
      if (!response.ok) throw new Error("audio download failed");
      return response.arrayBuffer().then(function (buffer) {
        if (response.status === 206) return buffer;
        return buffer.slice(firstByte, firstByte + packed.length);
      });
    }).then(function (buffer) {
      return URL.createObjectURL(new Blob([buffer], { type: "audio/mpeg" }));
    });
  }

  function setAudioSource(restorePosition) {
    var item = currentItem();
    var paths = currentAudioPaths();
    var trackIndex = currentTrackIndex();
    var requestId = ++sourceRequestId;
    el.audio.pause();
    el.audio.playbackRate = state.speed;
    el.playPause.textContent = "播放";
    el.playPause.setAttribute("aria-label", "播放");
    el.nowTitle.textContent = item.title;
    el.nowPart.textContent = item.partLabels[state.part] + (paths.length > 1 ? " · " + (trackIndex + 1) + "/" + paths.length : "");
    updateMediaSession();
    return resolveAudioSource(paths[trackIndex]).then(function (source) {
      if (requestId !== sourceRequestId) {
        if (source.indexOf("blob:") === 0) URL.revokeObjectURL(source);
        return;
      }
      if (activeObjectUrl) URL.revokeObjectURL(activeObjectUrl);
      activeObjectUrl = source.indexOf("blob:") === 0 ? source : "";
      el.audio.src = source;
      el.audio.playbackRate = state.speed;
      el.audio.load();
      if (restorePosition) {
        el.audio.addEventListener("loadedmetadata", function restore() {
          var position = Number(state.positions[currentPositionKey()]) || 0;
          if (position > 0 && position < el.audio.duration - 3) el.audio.currentTime = position;
        }, { once: true });
      }
    }).catch(function () {
      showToast("音频加载失败，请检查网络后重试");
    });
  }

  function render() {
    var item = currentItem();
    buildCategoryOptions();
    buildItemCards();
    el.field.textContent = "小班" + item.field + " · " + currentCategory().title;
    el.kind.textContent = item.kind === "template" ? "模板" : "教案";
    el.kind.className = "kind-badge " + item.kind;
    el.title.textContent = item.title;
    el.processTab.textContent = item.partLabels.process;
    el.reflectionTab.textContent = item.partLabels.reflection;
    el.processTab.setAttribute("aria-selected", String(state.part === "process"));
    el.reflectionTab.setAttribute("aria-selected", String(state.part === "reflection"));
    el.continuous.textContent = "过程后接反思：" + (state.continuous ? "开" : "关");
    el.continuous.setAttribute("aria-pressed", String(state.continuous));
    el.loop.textContent = "循环：" + (state.loop ? "开" : "关");
    el.loop.setAttribute("aria-pressed", String(state.loop));
    el.speed.value = String(state.speed);
    renderContent();
    setAudioSource(true);
    saveState();
  }

  function selectItem(index) {
    state.positions[currentPositionKey()] = el.audio.currentTime || 0;
    state.itemIndex = (index + items.length) % items.length;
    state.part = "process";
    render();
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function selectPart(part, autoplay) {
    if (part === state.part) { if (autoplay) playAudio(); return; }
    state.positions[currentPositionKey()] = el.audio.currentTime || 0;
    state.part = part;
    state.trackIndices[currentTrackKey()] = 0;
    renderContent();
    el.processTab.setAttribute("aria-selected", String(part === "process"));
    el.reflectionTab.setAttribute("aria-selected", String(part === "reflection"));
    setAudioSource(true);
    saveState();
    if (autoplay) {
      resumeAfterLoad = true;
      el.audio.addEventListener("canplay", function resume() { if (resumeAfterLoad) { resumeAfterLoad = false; playAudio(); } }, { once: true });
    }
  }

  function playAudio() {
    var playback = el.audio.play();
    if (playback && typeof playback.catch === "function") playback.catch(function () { showToast("请再点一次播放，允许浏览器开启声音"); });
  }

  function updateMediaSession() {
    if (!("mediaSession" in navigator) || !("MediaMetadata" in window)) return;
    var item = currentItem();
    navigator.mediaSession.metadata = new MediaMetadata({
      title: item.title + " · " + item.partLabels[state.part],
      artist: "小班微型课展示练习",
      album: item.kind === "template" ? "通用模板" : "对应教案"
    });
  }

  function updateActiveBlock() {
    var blocks = Array.prototype.slice.call(el.content.querySelectorAll(".reading-block"));
    var nextIndex = currentAudioPaths().length === blocks.length ? currentTrackIndex() : 0;
    if (currentAudioPaths().length === 1 && blocks.length > 1 && el.audio.duration) {
      var ratio = el.audio.currentTime / el.audio.duration;
      nextIndex = blocks.length - 1;
      blocks.some(function (block, index) {
        if (ratio >= Number(block.dataset.start) && ratio < Number(block.dataset.end)) { nextIndex = index; return true; }
        return false;
      });
    }
    if (nextIndex === activeBlockIndex) return;
    blocks.forEach(function (block, index) { block.classList.toggle("active", index === nextIndex); });
    activeBlockIndex = nextIndex;
    if (blocks[nextIndex] && !document.hidden) blocks[nextIndex].scrollIntoView({ behavior: "smooth", block: "center" });
  }

  el.category.addEventListener("change", function () {
    var category = categories.find(function (entry) { return entry.id === el.category.value; });
    if (category) selectItem(items.findIndex(function (item) { return item.id === category.itemIds[0]; }));
  });
  el.cards.addEventListener("click", function (event) {
    var card = event.target.closest("[data-index]");
    if (card) selectItem(Number(card.dataset.index));
  });
  el.openPicker.addEventListener("click", function () { el.picker.scrollIntoView({ behavior: "smooth", block: "start" }); });
  el.previous.addEventListener("click", function () { selectItem(state.itemIndex - 1); });
  el.next.addEventListener("click", function () { selectItem(state.itemIndex + 1); });
  el.processTab.addEventListener("click", function () { selectPart("process", false); });
  el.reflectionTab.addEventListener("click", function () { selectPart("reflection", false); });
  el.playSection.addEventListener("click", playAudio);
  el.playPause.addEventListener("click", function () { if (el.audio.paused) playAudio(); else el.audio.pause(); });
  el.back.addEventListener("click", function () { el.audio.currentTime = Math.max(0, el.audio.currentTime - 10); });
  el.forward.addEventListener("click", function () { el.audio.currentTime = Math.min(el.audio.duration || 0, el.audio.currentTime + 10); });
  el.loop.addEventListener("click", function () { state.loop = !state.loop; el.loop.textContent = "循环：" + (state.loop ? "开" : "关"); el.loop.setAttribute("aria-pressed", String(state.loop)); saveState(); });
  el.continuous.addEventListener("click", function () { state.continuous = !state.continuous; el.continuous.textContent = "过程后接反思：" + (state.continuous ? "开" : "关"); el.continuous.setAttribute("aria-pressed", String(state.continuous)); saveState(); });
  el.speed.addEventListener("change", function () { state.speed = Number(el.speed.value) || 1; el.audio.playbackRate = state.speed; saveState(); });
  el.range.addEventListener("input", function () { if (el.audio.duration) el.audio.currentTime = (Number(el.range.value) / 1000) * el.audio.duration; });

  el.audio.addEventListener("play", function () { el.playPause.textContent = "暂停"; el.playPause.setAttribute("aria-label", "暂停"); });
  el.audio.addEventListener("pause", function () { el.playPause.textContent = "播放"; el.playPause.setAttribute("aria-label", "播放"); state.positions[currentPositionKey()] = el.audio.currentTime || 0; saveState(); });
  el.audio.addEventListener("loadedmetadata", function () { el.duration.textContent = formatTime(el.audio.duration); });
  el.audio.addEventListener("timeupdate", function () {
    el.current.textContent = formatTime(el.audio.currentTime);
    el.duration.textContent = formatTime(el.audio.duration);
    el.range.value = el.audio.duration ? String(Math.round((el.audio.currentTime / el.audio.duration) * 1000)) : "0";
    state.positions[currentPositionKey()] = el.audio.currentTime || 0;
    if (Math.floor(el.audio.currentTime) % 5 === 0) saveState();
    updateActiveBlock();
  });
  el.audio.addEventListener("ended", function () {
    var paths = currentAudioPaths();
    var trackIndex = currentTrackIndex();
    if (trackIndex < paths.length - 1) {
      state.trackIndices[currentTrackKey()] = trackIndex + 1;
      setAudioSource(false);
      el.audio.addEventListener("canplay", playAudio, { once: true });
      saveState();
      return;
    }
    if (state.loop) {
      state.trackIndices[currentTrackKey()] = 0;
      setAudioSource(false);
      el.audio.addEventListener("canplay", playAudio, { once: true });
      saveState();
      return;
    }
    if (state.continuous && state.part === "process") { selectPart("reflection", true); return; }
    showToast("本篇朗读完成");
  });
  el.audio.addEventListener("error", function () { showToast("音频暂时没有加载成功，请刷新页面后重试"); });

  if ("mediaSession" in navigator) {
    try {
      navigator.mediaSession.setActionHandler("play", playAudio);
      navigator.mediaSession.setActionHandler("pause", function () { el.audio.pause(); });
      navigator.mediaSession.setActionHandler("seekbackward", function () { el.audio.currentTime = Math.max(0, el.audio.currentTime - 10); });
      navigator.mediaSession.setActionHandler("seekforward", function () { el.audio.currentTime = Math.min(el.audio.duration || 0, el.audio.currentTime + 10); });
    } catch (_error) { /* Optional lock-screen controls. */ }
  }

  if (!items.length || !categories.length) {
    el.content.innerHTML = "<p>内容加载失败，请刷新页面。</p>";
    return;
  }
  render();
}());
