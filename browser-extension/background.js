// YouTube 下载助手 - 后台 Service Worker
// 优先通过本地服务(127.0.0.1:47831)把实时 Cookie 和下载任务直接送给已开着的下载器；
// 服务连不上（下载器未启动）时，由页面回退到 ytdl:// 协议冷启动。

var SERVER = "http://127.0.0.1:47831";

async function postJSON(path, obj) {
  var res = await fetch(SERVER + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(obj)
  });
  if (!res.ok) throw new Error("HTTP " + res.status);
  return res.json();
}

// 上报实时 Cookie（domain 传裸域 youtube.com，Chrome 会匹配它及所有子域，含父域登录 Cookie）
async function pushCookies() {
  var cookies = await chrome.cookies.getAll({ domain: "youtube.com" });
  await postJSON("/cookies", cookies);
  return { ok: true, count: cookies.length };
}

// 先送 Cookie，再把下载任务送进已开着的下载器（单实例，不另起进程）
async function relayDownload(url, settings) {
  await pushCookies();
  await postJSON("/download", Object.assign({ url: url, auto: "1" }, settings || {}));
  return { relayed: true };
}

chrome.runtime.onMessage.addListener(function (msg, sender, sendResponse) {
  if (msg && msg.type === "RELAY_DOWNLOAD") {
    relayDownload(msg.url, msg.settings)
      .then(function (r) { sendResponse(r); })
      .catch(function (e) { sendResponse({ relayed: false, error: String(e) }); });
    return true; // 异步响应
  }
  if (msg && msg.type === "PUSH_COOKIES") {
    pushCookies()
      .then(function (r) { sendResponse({ ok: true, count: r.count }); })
      .catch(function (e) { sendResponse({ ok: false, error: String(e) }); });
    return true;
  }
});
