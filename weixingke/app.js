(function () {
  "use strict";

  var lessons = window.LESSONS || [];
  var storageKey = "weixingke-audio-v1";
  var saved = {};
  try { saved = JSON.parse(localStorage.getItem(storageKey) || "{}"); } catch (_error) { saved = {}; }

  var state = {
    lessonIndex: Math.max(0, Math.min(lessons.length - 1, Number(saved.lessonIndex) || 0)),
    part: saved.part === "reflection" ? "reflection" : "script",
    loop: Boolean(saved.loop),
    continuous: saved.continuous !== false,
    speed: [0.8, 1, 1.2].indexOf(Number(saved.speed)) >= 0 ? Number(saved.speed) : 1,
    positions: saved.positions || {},
    trackIndices: saved.trackIndices || {}
  };

  function byId(id) { return document.getElementById(id); }
  var el = {
    picker: byId("lessonPicker"), cards: byId("lessonCards"), count: byId("lessonCount"), openPicker: byId("openPickerButton"),
    field: byId("fieldBadge"), title: byId("lessonTitle"), previous: byId("previousLesson"), next: byId("nextLesson"),
    scriptTab: byId("scriptTab"), reflectionTab: byId("reflectionTab"), playSection: byId("playSectionButton"), continuous: byId("continuousButton"),
    content: byId("articleContent"), audio: byId("lessonAudio"), nowTitle: byId("nowPlayingTitle"), nowPart: byId("nowPlayingPart"),
    loop: byId("loopButton"), current: byId("currentTime"), duration: byId("durationTime"), range: byId("progressRange"),
    back: byId("backButton"), playPause: byId("playPauseButton"), forward: byId("forwardButton"), speed: byId("speedSelect"), toast: byId("toast")
  };
  var activeBlockIndex = -1;
  var resumeAfterLoad = false;

  function currentLesson() { return lessons[state.lessonIndex]; }
  function currentTrackKey() { return currentLesson().id + "-" + state.part; }
  function currentTrackIndex() {
    var paths = currentAudioPaths();
    var index = Number(state.trackIndices[currentTrackKey()]) || 0;
    return Math.max(0, Math.min(paths.length - 1, index));
  }
  function currentPositionKey() { return currentTrackKey() + "-" + currentTrackIndex(); }
  function currentAudioPaths() {
    var value = currentLesson().audio[state.part];
    return Array.isArray(value) ? value : [value];
  }
  function saveState() {
    try { localStorage.setItem(storageKey, JSON.stringify(state)); } catch (_error) { /* Storage can be disabled. */ }
  }
  function escapeHtml(text) {
    return String(text).replace(/[&<>"']/g, function (char) { return ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"})[char]; });
  }
  function formatText(text) {
    return escapeHtml(text).replace(/\[([^\]]+)\]/g, '<span class="placeholder">[$1]</span>');
  }
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
    showToast.timer = setTimeout(function () { el.toast.hidden = true; }, 2600);
  }

  function buildLessonCards() {
    el.cards.innerHTML = lessons.map(function (lesson, index) {
      return '<button class="lesson-card' + (index === state.lessonIndex ? ' selected' : '') + '" type="button" data-index="' + index + '">' +
        '<span>小班' + escapeHtml(lesson.field) + ' · 第' + (index + 1) + '篇</span><strong>' + escapeHtml(lesson.title) + '</strong></button>';
    }).join("");
  }

  function blocksForPart(lesson) {
    if (state.part === "reflection") {
      return lesson.reflection.map(function (paragraph, index) {
        var title = ["领域定位", "基本环节", "教学策略", "不足与改进"][index] || ("反思" + (index + 1));
        return { heading: (index + 1) + " " + title, meta: "完整成稿", paragraphs: [paragraph], length: paragraph.length };
      });
    }
    var blocks = [];
    lesson.steps.forEach(function (step, index) {
      var paragraphs = index === 0 ? lesson.scriptIntro.concat(step.paragraphs) : step.paragraphs;
      blocks.push({ heading: step.number + " " + step.title, meta: step.duration, paragraphs: paragraphs, length: step.title.length + paragraphs.join("").length });
    });
    return blocks;
  }

  function renderContent() {
    var lesson = currentLesson();
    var blocks = blocksForPart(lesson);
    var total = blocks.reduce(function (sum, block) { return sum + Math.max(1, block.length); }, 0);
    var running = 0;
    el.content.innerHTML = blocks.map(function (block, index) {
      var start = running / total;
      running += Math.max(1, block.length);
      var end = running / total;
      var className = state.part === "reflection" ? "reflection-block" : "step-block";
      return '<section class="reading-block ' + className + '" data-start="' + start + '" data-end="' + end + '">' +
        '<h3 class="block-heading"><span>' + escapeHtml(block.heading) + '</span><small>' + escapeHtml(block.meta) + '</small></h3>' +
        block.paragraphs.map(function (paragraph) { return '<p>' + formatText(paragraph) + '</p>'; }).join("") + '</section>';
    }).join("");
    activeBlockIndex = -1;
  }

  function setAudioSource(restorePosition) {
    var lesson = currentLesson();
    var paths = currentAudioPaths();
    var trackIndex = currentTrackIndex();
    el.audio.pause();
    el.audio.src = paths[trackIndex] + "?v=2";
    el.audio.playbackRate = state.speed;
    el.audio.load();
    el.playPause.textContent = "播放";
    el.playPause.setAttribute("aria-label", "播放");
    el.nowTitle.textContent = lesson.title;
    el.nowPart.textContent = state.part === "script" ? "完整展示脚本 · 环节 " + (trackIndex + 1) + "/" + paths.length : "完整反思成稿";
    if (restorePosition) {
      el.audio.addEventListener("loadedmetadata", function restore() {
        var position = Number(state.positions[currentPositionKey()]) || 0;
        if (position > 0 && position < el.audio.duration - 3) el.audio.currentTime = position;
      }, { once: true });
    }
    updateMediaSession();
  }

  function render() {
    var lesson = currentLesson();
    buildLessonCards();
    el.count.textContent = (state.lessonIndex + 1) + " / " + lessons.length;
    el.field.textContent = "小班" + lesson.field;
    el.title.textContent = lesson.title;
    el.scriptTab.setAttribute("aria-selected", String(state.part === "script"));
    el.reflectionTab.setAttribute("aria-selected", String(state.part === "reflection"));
    el.continuous.textContent = "整篇连续播放：" + (state.continuous ? "开" : "关");
    el.continuous.setAttribute("aria-pressed", String(state.continuous));
    el.loop.textContent = "循环：" + (state.loop ? "开" : "关");
    el.loop.setAttribute("aria-pressed", String(state.loop));
    el.speed.value = String(state.speed);
    renderContent();
    setAudioSource(true);
    saveState();
  }

  function selectLesson(index) {
    state.positions[currentPositionKey()] = el.audio.currentTime || 0;
    state.lessonIndex = (index + lessons.length) % lessons.length;
    state.part = "script";
    render();
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function selectPart(part, autoplay) {
    if (part === state.part) {
      if (autoplay) playAudio();
      return;
    }
    state.positions[currentPositionKey()] = el.audio.currentTime || 0;
    state.part = part;
    state.trackIndices[currentTrackKey()] = 0;
    renderContent();
    el.scriptTab.setAttribute("aria-selected", String(part === "script"));
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
    if (playback && typeof playback.catch === "function") {
      playback.catch(function () { showToast("请再点一次播放，允许浏览器开启声音"); });
    }
  }

  function updateMediaSession() {
    if (!("mediaSession" in navigator) || !("MediaMetadata" in window)) return;
    var lesson = currentLesson();
    navigator.mediaSession.metadata = new MediaMetadata({
      title: lesson.title + " · " + (state.part === "script" ? "展示脚本" : "完整反思"),
      artist: "小班微型课展示练习",
      album: "温和女声朗读"
    });
  }

  function updateActiveBlock() {
    var blocks = Array.prototype.slice.call(el.content.querySelectorAll(".reading-block"));
    var nextIndex = state.part === "script" ? currentTrackIndex() : 0;
    if (state.part === "reflection" && el.audio.duration) {
      var ratio = el.audio.currentTime / el.audio.duration;
      nextIndex = -1;
      blocks.some(function (block, index) {
        if (ratio >= Number(block.getAttribute("data-start")) && ratio < Number(block.getAttribute("data-end"))) { nextIndex = index; return true; }
        return false;
      });
      if (nextIndex < 0) nextIndex = blocks.length - 1;
    }
    if (nextIndex === activeBlockIndex) return;
    blocks.forEach(function (block, index) { block.classList.toggle("active", index === nextIndex); });
    activeBlockIndex = nextIndex;
    if (blocks[nextIndex] && !document.hidden) blocks[nextIndex].scrollIntoView({ behavior: "smooth", block: "center" });
  }

  el.cards.addEventListener("click", function (event) {
    var card = event.target;
    while (card && card !== el.cards && !card.getAttribute("data-index")) card = card.parentNode;
    if (card) selectLesson(Number(card.dataset.index));
  });
  el.openPicker.addEventListener("click", function () { el.picker.scrollIntoView({ behavior: "smooth", block: "start" }); });
  el.previous.addEventListener("click", function () { selectLesson(state.lessonIndex - 1); });
  el.next.addEventListener("click", function () { selectLesson(state.lessonIndex + 1); });
  el.scriptTab.addEventListener("click", function () { selectPart("script", false); });
  el.reflectionTab.addEventListener("click", function () { selectPart("reflection", false); });
  el.playSection.addEventListener("click", playAudio);
  el.playPause.addEventListener("click", function () { if (el.audio.paused) playAudio(); else el.audio.pause(); });
  el.back.addEventListener("click", function () { el.audio.currentTime = Math.max(0, el.audio.currentTime - 10); });
  el.forward.addEventListener("click", function () { el.audio.currentTime = Math.min(el.audio.duration || 0, el.audio.currentTime + 10); });
  el.loop.addEventListener("click", function () { state.loop = !state.loop; el.loop.textContent = "循环：" + (state.loop ? "开" : "关"); el.loop.setAttribute("aria-pressed", String(state.loop)); saveState(); });
  el.continuous.addEventListener("click", function () { state.continuous = !state.continuous; el.continuous.textContent = "整篇连续播放：" + (state.continuous ? "开" : "关"); el.continuous.setAttribute("aria-pressed", String(state.continuous)); saveState(); });
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
    if (state.continuous && state.part === "script") { selectPart("reflection", true); return; }
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

  if (!lessons.length) {
    el.content.innerHTML = "<p>内容加载失败，请刷新页面。</p>";
    return;
  }
  render();
}());
