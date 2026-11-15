#!/usr/bin/env python3
"""Symbolon 웹사이트 빌드: src/ -> dist/ (표준 라이브러리만 쓴다).

    python3 build.py           # 빌드 + 내부 링크 점검
    python3 build.py --serve   # 빌드 뒤 http://127.0.0.1:8000 에서 미리 보기
    SITE_URL=https://example.github.io/symbolon python3 build.py
                               # 공개 주소. 주면 canonical·Open Graph 태그를 넣고, 404.html에 <base>를 넣는다
                               # (GitHub Pages는 하위 경로 어디서나 404.html을 보여 주므로 상대 링크가 깨지지 않게).
                               # 페이지 사이 링크는 언제나 상대 경로라 어떤 하위 경로에 올려도 된다.

언어: 한국어 페이지는 src/pages/*.html → dist/, 영어 페이지는 src/pages/en/*.html → dist/en/.
두 언어의 파일 이름은 1:1로 같아야 한다(언어 전환 링크와 hreflang이 같은 이름의 페이지를 가리킨다).
레이아웃 문구는 src/i18n/<언어>.json, 언어별 조각은 src/partials/<언어>/<이름>.html(없으면 src/partials/<이름>.html).

페이지(src/pages/*.html)의 첫 줄은 메타 주석이다.
    <!--meta {"title": "...", "description": "...", "nav": "gateway"} -->
본문에서 쓸 수 있는 치환:
    {{include name="contact"}}          src/partials/<name>.html
    {{img name="console-policy" alt="..." [eager] [link] [variant="dark|light"] [class="..."]}}
        src/assets/img/ 의 AVIF + JPEG로 <picture>를 만든다. <name>-light/-dark 또는 <name>/<name>-dark
        짝이 있으면 테마별 그림 두 개를 만들고 CSS가 현재 테마의 것만 보인다.
    {{pdf file="제품소개서_일반.pdf"}}   PDF 크기 표기(파일이 없으면 "준비 중")
    {{root}}                            사이트 뿌리까지의 상대 경로("" 또는 "../")
    {{t key="nav.gateway"}}             src/i18n/<언어>.json 의 문구(레이아웃용)

src/docs/ 가 있으면(공개용 문서를 미리 빌드해 커밋한 정적 파일) dist/docs/ 로 그대로 복사한다.
"""
from __future__ import annotations

import html
import json
import os
import re
import shutil
import struct
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
DIST = ROOT / "dist"
IMG_DIR = SRC / "assets" / "img"
PDF_DIR = SRC / "assets" / "pdf"

LOCALES = {
    # 언어: (출력 하위 경로, 사이트 뿌리까지의 상대 경로, og:locale)
    "ko": ("", "", "ko_KR"),
    "en": ("en/", "../", "en_US"),
}
CTX = {"lang": "ko", "root": ""}  # 지금 만드는 페이지의 언어(매크로가 읽는다)
STRINGS: dict[str, dict[str, str]] = {}

META_RE = re.compile(r"\A\s*<!--meta\s+(\{.*?\})\s*-->\s*", re.S)
MACRO_RE = re.compile(r"\{\{(\w+)((?:\s+[^}]*)?)\}\}")
ATTR_RE = re.compile(r'(\w[\w-]*)(?:="([^"]*)")?')


def jpeg_size(path: Path) -> tuple[int, int]:
    """JPEG의 SOF 마커에서 (너비, 높이)를 읽는다."""
    with path.open("rb") as f:
        if f.read(2) != b"\xff\xd8":
            raise ValueError(f"JPEG 아님: {path}")
        while True:
            byte = f.read(1)
            while byte and byte != b"\xff":
                byte = f.read(1)
            while byte == b"\xff":
                byte = f.read(1)
            if not byte:
                raise ValueError(f"크기를 찾지 못함: {path}")
            marker = byte[0]
            (length,) = struct.unpack(">H", f.read(2))
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                f.read(1)
                h, w = struct.unpack(">HH", f.read(4))
                return w, h
            f.seek(length - 2, 1)


def parse_attrs(raw: str) -> dict[str, str]:
    return {k: (v if v is not None else "") for k, v in ATTR_RE.findall(raw)}


def picture(stem: str, alt: str, extra_class: str, eager: bool) -> str:
    jpg = IMG_DIR / f"{stem}.jpg"
    if not jpg.exists():
        raise SystemExit(f"그림 없음: {jpg} (scripts/sync-assets.sh 를 먼저 실행)")
    w, h = jpeg_size(jpg)
    loading = 'fetchpriority="high"' if eager else 'loading="lazy"'
    avif = IMG_DIR / f"{stem}.avif"
    r = CTX["root"]
    source = f'<source srcset="{r}assets/img/{stem}.avif" type="image/avif">' if avif.exists() else ""
    cls = f' class="{extra_class}"' if extra_class else ""
    return (
        f"<picture{cls}>{source}"
        f'<img src="{r}assets/img/{stem}.jpg" alt="{html.escape(alt)}" width="{w}" height="{h}" '
        f'{loading} decoding="async"></picture>'
    )


def img_macro(a: dict[str, str]) -> str:
    name = a["name"]
    alt = a.get("alt", "")
    eager = "eager" in a
    cls = a.get("class", "")
    link = "link" in a  # 그림을 원본 JPEG 링크로 감싼다(작은 화면에서 확대해 보기)

    def one(stem: str, theme_cls: str) -> str:
        if not link:
            return picture(stem, alt, f"{theme_cls} {cls}".strip(), eager)
        inner = picture(stem, alt, cls, eager)
        acls = f' class="zoom {theme_cls}"'.replace(" \"", "\"")
        title = html.escape(STRINGS[CTX["lang"]]["img.zoom"])
        return f'<a{acls} href="{CTX["root"]}assets/img/{stem}.jpg" title="{title}">{inner}</a>'

    variant = a.get("variant")  # "dark" | "light": 테마와 상관없이 한쪽만(언제나 어두운 구역 등)
    if variant in ("dark", "light"):
        for stem in (f"{name}-{variant}", name if variant == "light" else f"{name}-dark"):
            if (IMG_DIR / f"{stem}.jpg").exists():
                return one(stem, "")
    for light, dark in ((f"{name}-light", f"{name}-dark"), (name, f"{name}-dark")):
        if (IMG_DIR / f"{light}.jpg").exists() and (IMG_DIR / f"{dark}.jpg").exists():
            return one(light, "themed themed--light") + one(dark, "themed themed--dark")
    return one(name, "")


def pdf_macro(a: dict[str, str]) -> str:
    p = PDF_DIR / a["file"]
    if not p.exists():
        print(f"경고: PDF 없음 {p.name} (scripts/sync-assets.sh)", file=sys.stderr)
        return STRINGS[CTX["lang"]]["pdf.missing"]
    mb = p.stat().st_size / 1_000_000
    return STRINGS[CTX["lang"]]["pdf.size"].format(mb=f"{mb:.1f}")


def expand(text: str, depth: int = 0) -> str:
    def repl(m: re.Match[str]) -> str:
        kind, a = m.group(1), parse_attrs(m.group(2) or "")
        if kind == "include":
            if depth > 3:
                raise SystemExit("include가 너무 깊다")
            local = SRC / "partials" / CTX["lang"] / f"{a['name']}.html"
            path = local if local.exists() else SRC / "partials" / f"{a['name']}.html"
            return expand(path.read_text("utf-8"), depth + 1)
        if kind == "root":
            return CTX["root"]
        if kind == "t":
            table = STRINGS[CTX["lang"]]
            if a["key"] not in table:
                raise SystemExit(f"문구 없음: {CTX['lang']} {a['key']}")
            return html.escape(table[a["key"]])
        if kind == "img":
            return img_macro(a)
        if kind == "pdf":
            return pdf_macro(a)
        if kind in ("title", "description", "content", "canonical", "lang_switch"):
            return m.group(0)  # 레이아웃 자리표시는 그대로 둔다
        raise SystemExit(f"모르는 치환: {m.group(0)}")

    return MACRO_RE.sub(repl, text)


def page_names(lang: str) -> list[str]:
    d = SRC / "pages" / LOCALES[lang][0]
    return sorted(p.name for p in d.glob("*.html"))


def build() -> list[Path]:
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()
    site_url = os.environ.get("SITE_URL", "").strip().rstrip("/")
    if site_url and not (site_url.startswith("https://") or site_url.startswith(("http://127.0.0.1", "http://localhost"))):
        raise SystemExit("SITE_URL은 https:// 로 시작해야 한다(로컬 시험만 http://127.0.0.1·localhost 허용)")
    for lang in LOCALES:
        STRINGS[lang] = json.loads((SRC / "i18n" / f"{lang}.json").read_text("utf-8"))
    names = {lang: page_names(lang) for lang in LOCALES}
    if names["ko"] != names["en"]:
        raise SystemExit(f"언어별 페이지가 1:1이 아니다: ko만 {set(names['ko']) - set(names['en'])}, en만 {set(names['en']) - set(names['ko'])}")
    layout_src = (SRC / "layout.html").read_text("utf-8")

    def url_of(lang: str, name: str, absolute: bool, from_lang: str) -> str:
        sub = LOCALES[lang][0]
        tail = "" if name == "index.html" else name
        if absolute:
            return f"{site_url}/{sub}{tail}"
        return f"{LOCALES[from_lang][1]}{sub}{name}"

    pages = []
    for lang, (sub, root, og_locale) in LOCALES.items():
        CTX["lang"], CTX["root"] = lang, root
        layout = expand(layout_src)
        (DIST / sub).mkdir(parents=True, exist_ok=True)
        for name in names[lang]:
            page = SRC / "pages" / sub / name
            raw = page.read_text("utf-8")
            m = META_RE.match(raw)
            if not m:
                raise SystemExit(f"메타 주석 없음: {page}")
            meta = json.loads(m.group(1))
            body = expand(raw[m.end():])
            other = "en" if lang == "ko" else "ko"
            switch = (
                f'<a class="lang-switch" href="{url_of(other, name, False, lang)}" hreflang="{other}" lang="{other}">'
                f'<span class="visually-hidden">{html.escape(STRINGS[lang]["lang.switch"])}</span>'
                f'<span aria-hidden="true">{"EN" if other == "en" else "KO"}</span></a>'
            )
            out = layout.replace("{{content}}", body).replace("{{lang_switch}}", switch)
            out = out.replace("{{title}}", html.escape(meta["title"]))
            out = out.replace("{{description}}", html.escape(meta["description"]))
            nav = meta.get("nav", "")
            if nav:
                out = out.replace(f'data-nav="{nav}"', f'data-nav="{nav}" aria-current="page"')
            head_extra = ""
            absolute = bool(site_url)
            if name == "404.html":
                if site_url:
                    head_extra += f'<base href="{html.escape(site_url)}/{sub}">\n'
            else:
                if site_url:
                    head_extra += f'<link rel="canonical" href="{html.escape(url_of(lang, name, True, lang))}">\n'
                for alt in LOCALES:
                    head_extra += f'<link rel="alternate" hreflang="{alt}" href="{html.escape(url_of(alt, name, absolute, lang))}">\n'
                head_extra += f'<link rel="alternate" hreflang="x-default" href="{html.escape(url_of("ko", name, absolute, lang))}">\n'
            if site_url:
                t = html.escape(meta["title"]); d = html.escape(meta["description"])
                og_img = "og-en.jpg" if lang == "en" else "og.jpg"
                head_extra += (
                    f'<meta property="og:type" content="website">\n'
                    f'<meta property="og:site_name" content="Symbolon">\n'
                    f'<meta property="og:locale" content="{og_locale}">\n'
                    f'<meta property="og:locale:alternate" content="{LOCALES[other][2]}">\n'
                    f'<meta property="og:title" content="{t}">\n'
                    f'<meta property="og:description" content="{d}">\n'
                    f'<meta property="og:url" content="{html.escape(url_of(lang, name, True, lang))}">\n'
                    f'<meta property="og:image" content="{html.escape(site_url)}/{og_img}">\n'
                    f'<meta name="twitter:card" content="summary_large_image">\n'
                )
            out = out.replace("<!--head-extra-->", head_extra)
            if "{{" in out:
                raise SystemExit(f"처리되지 않은 치환이 남음: {sub}{name}")
            dest = DIST / sub / name
            dest.write_text(out, "utf-8")
            pages.append(dest)
    CTX["lang"], CTX["root"] = "ko", ""
    shutil.copytree(SRC / "static", DIST, dirs_exist_ok=True)
    assets = SRC / "assets"
    if assets.exists():
        shutil.copytree(assets, DIST / "assets", dirs_exist_ok=True)
    docs = SRC / "docs"  # 공개용 문서(빌드된 정적 파일)를 그대로 /docs/ 로 싣는다. 없으면 건너뛴다
    if docs.is_dir():
        shutil.copytree(docs, DIST / "docs", dirs_exist_ok=True)
    (DIST / ".nojekyll").write_text("", "utf-8")  # GitHub Pages가 Jekyll로 다시 처리하지 않게
    return pages


class LinkCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.ids: set[str] = set()
        self.base = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        d = dict(attrs)
        if tag == "base":
            self.base = d.get("href") or ""
            return
        if d.get("id"):
            self.ids.add(d["id"] or "")
        for key in ("href", "src"):
            if d.get(key):
                self.links.append(d[key] or "")
        if d.get("srcset"):
            for part in (d["srcset"] or "").split(","):
                self.links.append(part.strip().split(" ")[0])


def check_links(pages: list[Path]) -> int:
    site_url = os.environ.get("SITE_URL", "").strip().rstrip("/")
    parsed: dict[Path, LinkCollector] = {}
    for p in pages:
        c = LinkCollector()
        c.feed(p.read_text("utf-8"))
        parsed[p] = c
    errors = 0
    for p, c in parsed.items():
        for link in c.links:
            if site_url and link.startswith(site_url + "/"):
                # 공개 주소(canonical·hreflang)는 dist의 파일로 바꿔 점검한다
                rel = link[len(site_url) + 1:]
                link = os.path.relpath(DIST / (rel if rel and not rel.endswith("/") else rel + "index.html"), p.parent)
            elif c.base and not link.startswith("#") and not urlsplit(link).scheme and site_url and c.base.startswith(site_url):
                rel = c.base[len(site_url) + 1:]
                link = os.path.relpath(DIST / rel / link, p.parent) if link else link
            u = urlsplit(link)
            if u.scheme or link.startswith("//"):
                if u.scheme == "https" and u.netloc == "github.com" and u.path.startswith("/spro1"):
                    continue  # 허용한 외부 링크: 만든 사람의 GitHub
                if u.scheme not in ("mailto", "tel"):
                    print(f"외부 링크(허용 안 함): {p.relative_to(DIST)}: {link}")
                    errors += 1
                continue
            target = p if not u.path else (p.parent / unquote(u.path)).resolve()
            if not target.exists():
                print(f"깨진 링크: {p.relative_to(DIST)}: {link}")
                errors += 1
                continue
            if u.fragment and target.suffix == ".html":
                ids = parsed[target].ids if target in parsed else set()
                if u.fragment not in ids:
                    print(f"없는 앵커: {p.relative_to(DIST)}: {link}")
                    errors += 1
    return errors


def main() -> None:
    pages = build()
    errors = check_links(pages)
    print(f"{len(pages)}쪽 빌드 → {DIST.relative_to(ROOT)}/ · 링크 오류 {errors}건")
    if errors:
        sys.exit(1)
    if "--serve" in sys.argv:
        import functools
        import http.server

        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(DIST))
        with http.server.ThreadingHTTPServer(("127.0.0.1", 8000), handler) as srv:
            print("http://127.0.0.1:8000/ (Ctrl+C로 종료)")
            try:
                srv.serve_forever()
            except KeyboardInterrupt:
                pass


if __name__ == "__main__":
    main()
