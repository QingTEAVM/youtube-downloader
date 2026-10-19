// YouTube 下载助手 - popup 逻辑
// 读取当前标签页的 YouTube 视频链接，点击按钮后通过 ytdl:// 协议唤起本地下载器

let currentUrl = "";

function showVideo(title, url) {
  document.getElementById("bad").style.display = "none";
  const body = document.getElementById("content");
  body.innerHTML =
    '<p class="title">' + escapeHtml(title) + "</p>" +
    '<button class="btn btn-main" id="btn-video">▶ 下载视频</button>' +
    '<button class="btn btn-open" id="btn-open">打开下载器（手动设置）</button>' +
    '<p class="hint">点击后会打开电脑上的「YouTube 下载器」并自动开始下载。<br>' +
    '如果没反应，请确认下载器已安装，且首次使用允许打开 ytdl:// 协议。</p>';
  document.getElementById("btn-video").addEventListener("click", () => launch("1"));
  document.getElementById("btn-open").addEventListener("click", () => launch("0"));
  currentUrl = url;
}

function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s || "";
  return d.innerHTML;
}

// auto=1 自动开始下载；auto=0 只填入链接。优先走本地服务，失败回退 ytdl://
function launch(auto) {
  const settings = { auto: auto };
  const fallback = () => {
    const qs = new URLSearchParams({ url: currentUrl, auto: auto });
    window.location.href = "ytdl://download?" + qs.toString();
  };
  try {
    chrome.runtime.sendMessage(
      { type: "RELAY_DOWNLOAD", url: currentUrl, settings: settings },
      (resp) => { if (!(resp && resp.relayed)) fallback(); }
    );
  } catch (e) {
    fallback();
  }
}

chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
  const tab = tabs && tabs[0];
  const url = tab ? tab.url : "";
  if (/youtube\.com\/watch\?v=/.test(url)) {
    showVideo(tab.title ? tab.title.replace(/ - YouTube$/, "") : "YouTube 视频", url);
  } else {
    document.getElementById("bad").style.display = "block";
  }
});
