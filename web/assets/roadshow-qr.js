(function () {
  "use strict";

  function icon() {
    return '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M3 3h7v7H3V3Zm2 2v3h3V5H5Zm9-2h7v7h-7V3Zm2 2v3h3V5h-3ZM3 14h7v7H3v-7Zm2 2v3h3v-3H5Zm9-2h3v3h-3v-3Zm4 0h3v3h-3v-3Zm-4 4h3v3h-3v-3Zm4 0h3v3h-3v-3Z"/></svg>';
  }

  function homeUrl(baseUrl) {
    var url = new URL('/', baseUrl || window.location.origin);
    url.hash = 'home';
    return url.href;
  }

  function isLocalUrl(value) {
    try { return /^(localhost|127\.0\.0\.1)$/i.test(new URL(value).hostname); }
    catch (_) { return false; }
  }

  function build() {
    if (document.querySelector('.flylink-qr-launcher')) return;

    var launcher = document.createElement('button');
    launcher.className = 'flylink-qr-launcher';
    launcher.type = 'button';
    launcher.setAttribute('aria-haspopup', 'dialog');
    launcher.innerHTML = icon() + '<span>路演二维码</span>';

    var overlay = document.createElement('div');
    overlay.className = 'flylink-qr-overlay';
    overlay.hidden = true;
    overlay.innerHTML =
      '<section class="flylink-qr-dialog" role="dialog" aria-modal="true" aria-labelledby="flylink-qr-title">' +
        '<header class="flylink-qr-head"><div><p>ROADSHOW SHARE</p><h2 id="flylink-qr-title">生成首页路演二维码</h2></div><button class="flylink-qr-close" type="button" aria-label="关闭">×</button></header>' +
        '<div class="flylink-qr-body">' +
          '<div class="flylink-qr-preview" aria-live="polite"></div>' +
          '<div class="flylink-qr-form">' +
            '<label for="flylink-demo-url">扫码后展示的首页地址</label>' +
            '<input id="flylink-demo-url" class="flylink-qr-input" type="url" inputmode="url" readonly />' +
            '<p class="flylink-qr-note">二维码固定打开飞链首页。电脑和手机连接同一 Wi-Fi 时，会自动使用手机可访问的局域网地址。</p>' +
            '<p class="flylink-qr-warning">暂未获取到手机可访问的地址。请检查电脑网络，或将平台部署到 HTTPS 公网地址后重试。</p>' +
            '<div class="flylink-qr-actions"><button class="primary flylink-qr-generate" type="button">重新生成</button><button class="flylink-qr-copy" type="button">复制链接</button><a class="flylink-qr-download" href="#" download="FlyLink-首页路演二维码.gif">下载二维码</a></div>' +
            '<p class="flylink-qr-status" role="status"></p>' +
          '</div>' +
        '</div>' +
      '</section>';

    document.body.appendChild(launcher);
    document.body.appendChild(overlay);
    var input = overlay.querySelector('.flylink-qr-input');
    var preview = overlay.querySelector('.flylink-qr-preview');
    var warning = overlay.querySelector('.flylink-qr-warning');
    var download = overlay.querySelector('.flylink-qr-download');
    var status = overlay.querySelector('.flylink-qr-status');

    function setStatus(message) {
      status.textContent = message;
      window.clearTimeout(setStatus.timer);
      setStatus.timer = window.setTimeout(function () { status.textContent = ''; }, 3000);
    }

    function render() {
      var url = input.value.trim();
      if (!url || typeof window.qrcode !== 'function') return setStatus('二维码组件加载失败，请刷新页面后重试');
      try {
        var code = window.qrcode(0, 'M');
        code.addData(url);
        code.make();
        var dataUrl = code.createDataURL(7, 4);
        preview.innerHTML = '<img alt="FlyLink 首页路演二维码" src="' + dataUrl + '">';
        download.href = dataUrl;
        warning.classList.toggle('show', isLocalUrl(url));
        setStatus('首页二维码已生成，可下载后放入路演材料');
      } catch (_) { setStatus('二维码生成失败，请刷新页面后重试'); }
    }

    async function open() {
      input.value = homeUrl();
      overlay.hidden = false;
      document.body.style.overflow = 'hidden';
      if (isLocalUrl(input.value)) {
        status.textContent = '正在获取手机可访问的局域网地址……';
        try {
          var response = await fetch('/api/demo-access', { headers: { Accept: 'application/json' } });
          if (response.ok) {
            var access = await response.json();
            if (access.is_lan && access.base_url) input.value = homeUrl(access.base_url);
          }
        } catch (_) {}
      }
      render();
    }

    function close() {
      overlay.hidden = true;
      document.body.style.overflow = '';
      launcher.focus();
    }

    launcher.addEventListener('click', open);
    overlay.querySelector('.flylink-qr-close').addEventListener('click', close);
    overlay.querySelector('.flylink-qr-generate').addEventListener('click', render);
    overlay.addEventListener('click', function (event) { if (event.target === overlay) close(); });
    document.addEventListener('keydown', function (event) { if (event.key === 'Escape' && !overlay.hidden) close(); });
    overlay.querySelector('.flylink-qr-copy').addEventListener('click', function () {
      var url = input.value.trim();
      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(url).then(function () { setStatus('首页链接已复制'); });
      } else {
        input.select();
        try { document.execCommand('copy'); setStatus('首页链接已复制'); }
        catch (_) { setStatus('已选中链接，请按 Ctrl+C 复制'); }
      }
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', build);
  else build();
})();
