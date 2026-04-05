"""One-off: sync all templates to partials/_sidebar_static.html"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent / "templates"
CANONICAL = (ROOT / "partials" / "_sidebar_static.html").read_text(encoding="utf-8").strip() + "\n"
SKIP = {"invoice_print.html", "login.html", "index.html", "_sidebar_static.html"}


def replace_one(content: str) -> tuple[str, bool]:
    marker = '<aside class="sidebar sidebar-modern"'
    if marker not in content:
        return content, False
    start = content.index(marker)
    end_aside = content.index("</aside>", start) + len("</aside>")
    tail = content[end_aside:]
    m = re.match(r'(\s*)<script src="/static/js/sidebar-active\.js" defer></script>\s*', tail)
    end = end_aside + m.end() if m else end_aside
    return content[:start] + CANONICAL + content[end:], True


def main() -> None:
    for path in sorted(ROOT.glob("*.html")):
        if path.name in SKIP:
            continue
        text = path.read_text(encoding="utf-8")
        if '<aside class="sidebar sidebar-modern"' not in text:
            continue
        new_text, ok = replace_one(text)
        if ok:
            path.write_text(new_text, encoding="utf-8")
            print("updated", path.name)
        else:
            print("FAIL", path.name)


if __name__ == "__main__":
    main()
