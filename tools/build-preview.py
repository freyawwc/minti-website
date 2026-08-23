#!/usr/bin/env python3
"""Bundle the minti site into a single self-contained preview page.

Every page, the shared stylesheet and the screenshots are inlined into one
HTML file so the site can be browsed and clicked through anywhere -- no web
server, no file:// asset problems. Run this again after editing the site:

    python3 tools/build-preview.py

Requires Pillow (pip install Pillow) to downscale the screenshots.
"""
import base64
import io
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES = ["index", "minti", "about", "terms", "privacy"]
LABELS = {
    "index": "Home",
    "minti": "minti",
    "about": "company",
    "terms": "Terms",
    "privacy": "Privacy",
}
SHOT_WIDTH = 620   # screenshots render at ~300px wide, so 620 covers 2x displays
SHOT_QUALITY = 80


def encode_screens():
    """Downscale each screenshot and return {filename: data URI}."""
    from PIL import Image

    assets = {}
    src = os.path.join(ROOT, "screens")
    for name in sorted(os.listdir(src)):
        if not name.lower().endswith((".png", ".jpg", ".jpeg")):
            continue
        im = Image.open(os.path.join(src, name)).convert("RGB")
        im.thumbnail((SHOT_WIDTH, SHOT_WIDTH * 10), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, "WEBP", quality=SHOT_QUALITY, method=6)
        raw = buf.getvalue()
        assets[name] = "data:image/webp;base64," + base64.b64encode(raw).decode()
        print(f"  {name}: {os.path.getsize(os.path.join(src, name))/1024:>7.0f} KB"
              f" -> {len(raw)/1024:>5.0f} KB")
    return assets


# Injected into every page: resolves screens/* to the inlined data URIs and
# hands link clicks up to the preview shell.
SHIM = """
<script>
(function () {
  // srcdoc frames share the shell's origin, so the screenshots are read from
  // the one copy held there rather than inlined into all six pages.
  var A = (window.parent && window.parent.__MINTI_ASSETS) || {};
  function map(u) {
    if (typeof u !== 'string') return u;
    var m = u.match(/screens\\/([^\\/?#]+)$/);
    return (m && A[m[1]]) ? A[m[1]] : u;
  }
  // index.html swaps the phone screenshot from JS, so map assignments too.
  var d = Object.getOwnPropertyDescriptor(HTMLImageElement.prototype, 'src');
  Object.defineProperty(HTMLImageElement.prototype, 'src', {
    configurable: true,
    get: function () { return d.get.call(this); },
    set: function (v) { d.set.call(this, map(v)); }
  });

  document.addEventListener('click', function (e) {
    var a = e.target.closest && e.target.closest('a[href]');
    if (!a) return;
    var href = a.getAttribute('href');
    if (!href || href.charAt(0) === '#') return;      // in-page anchors work as-is
    if (/^(https?:|mailto:)/i.test(href)) {           // offsite: report, don't leave
      e.preventDefault();
      parent.postMessage({ t: 'ext', href: href }, '*');
      return;
    }
    var m = href.match(/^([\\w-]+)\\.html(#.*)?$/);
    if (m) {
      e.preventDefault();
      parent.postMessage({ t: 'nav', page: m[1], hash: m[2] || '' }, '*');
    }
  });

  parent.postMessage({ t: 'ready', title: document.title }, '*');
})();
</script>
"""


def build_page(name, css, assets):
    html = open(os.path.join(ROOT, name + ".html"), encoding="utf-8").read()

    # Inline the shared stylesheet (index.html carries its own <style> instead).
    html = re.sub(r'<link[^>]+href="styles\.css"[^>]*>',
                  lambda _m: "<style>\n" + css + "\n</style>", html)

    # Static screenshot references.
    html = re.sub(r'(src=")(?:\./)?screens/([^"]+)(")',
                  lambda m: m.group(1) + assets.get(m.group(2), "screens/" + m.group(2)) + m.group(3),
                  html)

    m = re.search(r"<head[^>]*>", html)
    if m:
        html = html[:m.end()] + SHIM + html[m.end():]
    else:
        html = SHIM + html
    return html


def main():
    print("Inlining screenshots...")
    assets = encode_screens()
    css = open(os.path.join(ROOT, "styles.css"), encoding="utf-8").read()

    pages = {n: build_page(n, css, assets) for n in PAGES}
    shell = open(os.path.join(ROOT, "tools", "preview-shell.html"), encoding="utf-8").read()
    shell = shell.replace("/*__PAGES__*/",
                          json.dumps(pages).replace("</", "<\\/"))
    shell = shell.replace("/*__LABELS__*/", json.dumps(LABELS))
    shell = shell.replace("/*__ASSETS__*/",
                          json.dumps(assets).replace("</", "<\\/"))

    out = os.path.join(ROOT, "preview.html")
    open(out, "w", encoding="utf-8").write(shell)
    print(f"\nWrote {out}  ({os.path.getsize(out)/1024:.0f} KB)")


if __name__ == "__main__":
    main()
