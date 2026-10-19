// YouTube 下载助手 - 页面内下载按钮 + 选项面板
// 在 YouTube 视频页右下角显示红色「⬇ 下载」按钮
// 点击后弹出选择面板（下载内容/画质/字幕/音频），确认后通过 ytdl:// 协议唤起本地下载器

(function () {
  'use strict';

  var PANEL_ID = 'qingtea-ytdl-panel';

  function isWatchPage() {
    return /youtube\.com\/watch/.test(location.href);
  }

  // ---------- 构建右下角下载按钮 ----------
  function buildBtn() {
    if (document.getElementById('qingtea-ytdl-btn')) return;
    var btn = document.createElement('button');
    btn.id = 'qingtea-ytdl-btn';
    btn.textContent = '⬇ 下载';
    btn.title = '选择下载选项并交给本地 YouTube 下载器';
    btn.style.cssText =
      'position:fixed;right:24px;bottom:120px;z-index:99999;' +
      'background:#ff0000;color:#fff;border:none;border-radius:20px;' +
      'padding:10px 18px;font-size:14px;font-family:"Microsoft YaHei",sans-serif;' +
      'cursor:pointer;box-shadow:0 2px 8px rgba(0,0,0,.35);' +
      'transition:transform .1s ease;';
    btn.addEventListener('mouseover', function () { btn.style.transform = 'scale(1.06)'; });
    btn.addEventListener('mouseout', function () { btn.style.transform = 'scale(1)'; });
    btn.addEventListener('click', openPanel);
    document.body.appendChild(btn);
  }

  // ---------- 选项面板 ----------
  function openPanel() {
    if (document.getElementById(PANEL_ID)) return;

    var ov = document.createElement('div');
    ov.id = PANEL_ID;
    ov.style.cssText =
      'position:fixed;right:24px;bottom:170px;z-index:99999;width:300px;' +
      'background:#fff;color:#222;border-radius:14px;box-shadow:0 8px 32px rgba(0,0,0,.35);' +
      'font-family:"Microsoft YaHei",sans-serif;font-size:13px;overflow:hidden;';

    var head = document.createElement('div');
    head.textContent = 'YouTube 下载助手';
    head.style.cssText =
      'background:#ff0000;color:#fff;padding:10px 14px;font-size:14px;font-weight:bold;';

    var body = document.createElement('div');
    body.style.cssText = 'padding:12px 14px;';

    function label(t) {
      var l = document.createElement('div');
      l.textContent = t;
      l.style.cssText = 'margin:8px 0 4px;color:#555;font-size:12px;';
      return l;
    }

    // 下载内容
    var modeWrap = document.createElement('div');
    var mode = { v: 'video' };
    var modeRow = document.createElement('div');
    modeRow.style.cssText = 'display:flex;gap:10px;';
    [['video', '视频'], ['audio', '音频'], ['sub', '字幕']].forEach(function (m) {
      var radio = document.createElement('label');
      radio.style.cssText = 'display:flex;align-items:center;gap:4px;cursor:pointer;';
      var inp = document.createElement('input');
      inp.type = 'radio'; inp.name = 'ytdl-mode'; inp.value = m[0];
      if (m[0] === 'video') inp.checked = true;
      inp.addEventListener('change', function () { mode.v = m[0]; refresh(); });
      radio.appendChild(inp);
      radio.appendChild(document.createTextNode(m[1]));
      modeRow.appendChild(radio);
    });
    modeWrap.appendChild(label('下载内容'));
    modeWrap.appendChild(modeRow);

    // 画质
    var qualityWrap = document.createElement('div');
    var qualitySel = document.createElement('select');
    qualitySel.style.cssText = 'width:100%;padding:5px;border:1px solid #ccc;border-radius:6px;background:#fff;';
    [['auto', '最高画质（自动）'], ['2160p', '2160p 4K'], ['1440p', '1440p 2K'],
     ['1080p', '1080p'], ['720p', '720p'], ['480p', '480p'], ['360p', '360p']
    ].forEach(function (o) {
      var op = document.createElement('option');
      op.value = o[0]; op.textContent = o[1];
      qualitySel.appendChild(op);
    });
    qualityWrap.appendChild(label('画质'));
    qualityWrap.appendChild(qualitySel);

    // 附带字幕（视频模式）
    var subCheckWrap = document.createElement('div');
    var subCheck = document.createElement('input');
    subCheck.type = 'checkbox'; subCheck.id = 'ytdl-sub-check';
    var subLbl = document.createElement('label');
    subLbl.style.cssText = 'display:flex;align-items:center;gap:5px;cursor:pointer;margin-top:8px;';
    subLbl.appendChild(subCheck);
    subLbl.appendChild(document.createTextNode('附带下载字幕'));
    subCheckWrap.appendChild(subLbl);

    // 字幕设置
    var subOpts = document.createElement('div');
    var langSel = document.createElement('select');
    langSel.style.cssText = 'width:100%;padding:5px;border:1px solid #ccc;border-radius:6px;background:#fff;';
    [['auto', '自动（默认）'], ['zh-Hans', '简体中文'], ['zh-Hant', '繁体中文'], ['en', '英文'],
     ['ja', '日语'], ['ko', '韩语'], ['es', '西班牙语'], ['fr', '法语'], ['de', '德语'],
     ['ru', '俄语'], ['vi', '越南语'], ['th', '泰语']
    ].forEach(function (o) {
      var op = document.createElement('option');
      op.value = o[0]; op.textContent = o[1];
      langSel.appendChild(op);
    });
    var fmtSel = document.createElement('select');
    fmtSel.style.cssText = 'width:100%;padding:5px;border:1px solid #ccc;border-radius:6px;background:#fff;';
    [['SRT', 'SRT'], ['TXT', 'TXT'], ['LRC', 'LRC']].forEach(function (o) {
      var op = document.createElement('option');
      op.value = o[0]; op.textContent = o[1];
      fmtSel.appendChild(op);
    });
    var subLblRow = document.createElement('div'); subLblRow.textContent = '字幕语言';
    subLblRow.style.cssText = 'margin:8px 0 4px;color:#555;font-size:12px;';
    var subFmtRow = document.createElement('div'); subFmtRow.textContent = '字幕格式';
    subFmtRow.style.cssText = 'margin:8px 0 4px;color:#555;font-size:12px;';
    subOpts.appendChild(subLblRow); subOpts.appendChild(langSel);
    subOpts.appendChild(subFmtRow); subOpts.appendChild(fmtSel);

    // 音频格式
    var audioWrap = document.createElement('div');
    var audioSel = document.createElement('select');
    audioSel.style.cssText = 'width:100%;padding:5px;border:1px solid #ccc;border-radius:6px;background:#fff;';
    [['MP3', 'MP3'], ['M4A', 'M4A'], ['WAV', 'WAV']].forEach(function (o) {
      var op = document.createElement('option');
      op.value = o[0]; op.textContent = o[1];
      audioSel.appendChild(op);
    });
    audioWrap.appendChild(label('音频格式'));
    audioWrap.appendChild(audioSel);

    // 刷新可见性
    function refresh() {
      qualityWrap.style.display = (mode.v === 'video') ? '' : 'none';
      subCheckWrap.style.display = (mode.v === 'video') ? '' : 'none';
      subOpts.style.display = (mode.v === 'sub' || (mode.v === 'video' && subCheck.checked)) ? '' : 'none';
      audioWrap.style.display = (mode.v === 'audio') ? '' : 'none';
    }
    subCheck.addEventListener('change', refresh);

    // 按钮行
    var btnRow = document.createElement('div');
    btnRow.style.cssText = 'display:flex;gap:8px;margin-top:14px;';
    var go = document.createElement('button');
    go.textContent = '开始下载';
    go.style.cssText =
      'flex:1;background:#ff0000;color:#fff;border:none;border-radius:8px;padding:9px 0;' +
      'font-size:14px;cursor:pointer;';
    var cancel = document.createElement('button');
    cancel.textContent = '取消';
    cancel.style.cssText =
      'flex:1;background:#eee;color:#555;border:none;border-radius:8px;padding:9px 0;' +
      'font-size:14px;cursor:pointer;';
    btnRow.appendChild(go); btnRow.appendChild(cancel);

    body.appendChild(modeWrap);
    body.appendChild(qualityWrap);
    body.appendChild(subCheckWrap);
    body.appendChild(subOpts);
    body.appendChild(audioWrap);
    body.appendChild(btnRow);

    ov.appendChild(head);
    ov.appendChild(body);
    document.body.appendChild(ov);
    refresh();

    // 关闭
    function close() {
      var el = document.getElementById(PANEL_ID);
      if (el) el.parentNode.removeChild(el);
    }
    cancel.addEventListener('click', close);

    // 开始下载：优先经本地服务把 Cookie+任务送给已开着的下载器；失败再回退 ytdl:// 冷启动
    go.addEventListener('click', function () {
      var url = location.href.split('&')[0];
      var settings = { auto: '1', mode: mode.v };
      if (mode.v === 'video') {
        settings.quality = qualitySel.value;
        if (subCheck.checked) {
          settings.sub = '1';
          if (langSel.value !== 'auto') settings.sub_lang = langSel.value;
          settings.sub_fmt = fmtSel.value;
        }
      } else if (mode.v === 'sub') {
        if (langSel.value !== 'auto') settings.sub_lang = langSel.value;
        settings.sub_fmt = fmtSel.value;
      } else if (mode.v === 'audio') {
        settings.audio_fmt = audioSel.value;
      }
      var fallback = function () {
        var q = new URLSearchParams(Object.assign({ url: url }, settings));
        location.href = 'ytdl://download?' + q.toString();
      };
      try {
        chrome.runtime.sendMessage({ type: 'RELAY_DOWNLOAD', url: url, settings: settings }, function (resp) {
          if (!(resp && resp.relayed)) fallback();
        });
      } catch (e) {
        fallback();
      }
    });
  }

  // 监听 SPA 路由变化
  var lastHref = location.href;
  function tick() {
    if (location.href !== lastHref) {
      lastHref = location.href;
      if (isWatchPage()) buildBtn();
    }
  }
  setInterval(tick, 1000);

  if (isWatchPage()) buildBtn();
})();
