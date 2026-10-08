(function () {
  "use strict";

  function icon() {
    return '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M3 3h7v7H3V3Zm2 2v3h3V5H5Zm9-2h7v7h-7V3Zm2 2v3h3V5h-3ZM3 14h7v7H3v-7Zm2 2v3h3v-3H5Zm9-2h3v3h-3v-3Zm4 0h3v3h-3v-3Zm-4 4h3v3h-3v-3Zm4 0h3v3h-3v-3Z"/></svg>';
  }

  function currentUrl() {
    return window.location.href.replace(/#$/, "");
  }

  function isLocalUrl(value) {
    try { return /^(localhost|127\.0\.0\.1)$/i.test(new URL(value).hostname); }
    catch (_) { return false; }
  }

  function lanPageUrl(baseUrl) {
    return new URL(window.location.pathname + window.location.search + window.location.hash, baseUrl).href;
  }

  function build() {
    if (document.querySelector(".flylink-qr-launcher")) return;

    var launcher = document.createElement("button");
    launcher.className = "flylink-qr-launcher";
    launcher.type = "button";
    launcher.setAttribute("aria-haspopup", "dialog");
    launcher.innerHTML = icon() + "<span>路演二维码</span>";

    var overlay = document.createElement("div");
    overlay.className = "flylink-qr-overlay";
    overlay.hidden = true;
    overlay.innerHTML =
      '<section class="flylink-qr-dialog" role="dialog" aria-modal="true" aria-labelledby="flylink-qr-title">' +
        '<header class="flylink-qr-head"><div><p>ROADSHOW SHARE</p><h2 id="flylink-qr-title">生成网页演示二维码</h2></div><button class="flylink-qr-close" type="button" aria-label="关闭">×</button></header>' +
        '<div class="flylink-qr-body">' +
          '<div class="flylink-qr-preview" aria-live="polite"></div>' +
          '<div class="flylink-qr-form">' +
            '<label for="flylink-demo-url">演示网页地址</label>' +
            '<input id="flylink-demo-url" class="flylink-qr-input" type="url" inputmode="url" autocomplete="url" />' +
            '<p class="flylink-qr-note">部署后会自动使用当前网页地址。也可以在此粘贴最终公网地址，生成的图片可直接放进路演 PPT。</p>' +
            '<p class="flylink-qr-warning">当前是本机地址，手机无法直接打开。现场演示请改为同一 Wi-Fi 下的局域网地址，或填入部署后的 HTTPS 公网地址。</p>' +
            '<div class="flylink-qr-actions"><button class="primary flylink-qr-generate" type="button">重新生成</button><button class="flylink-qr-copy" type="button">复制链接</button><a class="flylink-qr-download" href="#" download="FlyLink-路演二维码.gif">下载二维码</a></div>' +
            '<p class="flylink-qr-status" role="status"></p>' +
          '</div>' +
        '</div>' +
      '</section>';

    document.body.appendChild(launcher);
    document.body.appendChild(overlay);

    var input = overlay.querySelector(".flylink-qr-input");
    var preview = overlay.querySelector(".flylink-qr-preview");
    var warning = overlay.querySelector(".flylink-qr-warning");
    var download = overlay.querySelector(".flylink-qr-download");
    var status = overlay.querySelector(".flylink-qr-status");

    function setStatus(message) {
      status.textContent = message;
      window.clearTimeout(setStatus.timer);
      setStatus.timer = window.setTimeout(function () { status.textContent = ""; }, 2600);
    }

    function render() {
      var url = input.value.trim();
      if (!url) return setStatus("请先输入演示网页地址");
      try { new URL(url); } catch (_) { return setStatus("请输入完整地址，例如 https://demo.example.com"); }
      if (typeof window.qrcode !== "function") return setStatus("二维码组件加载失败，请刷新页面后重试");
      try {
        var code = window.qrcode(0, "M");
        code.addData(url);
        code.make();
        var dataUrl = code.createDataURL(7, 4);
        preview.innerHTML = '<img alt="FlyLink 演示网页二维码" src="' + dataUrl + '">';
        download.href = dataUrl;
        warning.classList.toggle("show", isLocalUrl(url));
        localStorage.setItem("flylink_demo_url", url);
        setStatus("二维码已生成，可下载后放入 PPT");
      } catch (error) {
        setStatus("地址内容过长，请使用更短的演示链接");
      }
    }

    async function open() {
      var saved = localStorage.getItem("flylink_demo_url");
      input.value = saved || currentUrl();
      overlay.hidden = false;
      document.body.style.overflow = "hidden";
      if (isLocalUrl(input.value)) {
        status.textContent = "正在获取手机可访问的局域网地址……";
        try {
          var response = await fetch("/api/common/demo-access/", { headers: { "Accept": "application/json" } });
          if (response.ok) {
            var access = await response.json();
            if (access.is_lan && access.base_url) input.value = lanPageUrl(access.base_url);
          }
        } catch (_) {
          // Keep the local URL so the existing warning explains the manual fallback.
        }
      }
      render();
      input.focus();
      input.select();
    }

    function close() {
      overlay.hidden = true;
      document.body.style.overflow = "";
      launcher.focus();
    }

    launcher.addEventListener("click", open);
    overlay.querySelector(".flylink-qr-close").addEventListener("click", close);
    overlay.querySelector(".flylink-qr-generate").addEventListener("click", render);
    input.addEventListener("keydown", function (event) { if (event.key === "Enter") render(); });
    overlay.addEventListener("click", function (event) { if (event.target === overlay) close(); });
    document.addEventListener("keydown", function (event) { if (event.key === "Escape" && !overlay.hidden) close(); });
    overlay.querySelector(".flylink-qr-copy").addEventListener("click", function () {
      var url = input.value.trim();
      if (!url) return setStatus("请先输入演示网页地址");
      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(url).then(function () { setStatus("演示链接已复制"); }, function () { input.select(); setStatus("已选中链接，请按 Ctrl+C 复制"); });
      } else {
        input.select();
        try { document.execCommand("copy"); setStatus("演示链接已复制"); }
        catch (_) { setStatus("已选中链接，请按 Ctrl+C 复制"); }
      }
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", build);
  else build();
})();

