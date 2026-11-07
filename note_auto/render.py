"""Markdown を note のエディタに貼り付けられる HTML に変換する（依存ライブラリなし）。

note のエディタが扱える要素だけを出す: h2 / h3 / p / ul / ol / blockquote / pre / hr / strong / a / code。
"""
from __future__ import annotations

import html
import re

_INLINE = [
    (re.compile(r"`([^`]+)`"), r"<code>\1</code>"),
    (re.compile(r"\*\*(.+?)\*\*"), r"<strong>\1</strong>"),
    (re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)"), r'<a href="\2">\1</a>'),
]


def inline(text: str) -> str:
    s = html.escape(text, quote=False)
    for pat, rep in _INLINE:
        s = pat.sub(rep, s)
    return s


def blocks(md: str) -> list[str]:
    """Markdown をトップレベルのブロック（HTML 文字列）のリストにする。"""
    out: list[str] = []
    lines = md.replace("\r\n", "\n").split("\n")
    i = 0
    para: list[str] = []

    def flush_para() -> None:
        if para:
            out.append("<p>" + "<br>".join(inline(x) for x in para) + "</p>")
            para.clear()

    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if not s:
            flush_para()
            i += 1
            continue
        if s.startswith("```"):
            flush_para()
            code: list[str] = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            i += 1
            out.append("<pre><code>" + html.escape("\n".join(code), quote=False) + "</code></pre>")
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", s)
        if m:
            flush_para()
            # note の見出しは大（h2）と小（h3）の2種類
            tag = "h2" if len(m.group(1)) <= 2 else "h3"
            out.append(f"<{tag}>{inline(m.group(2).strip())}</{tag}>")
            i += 1
            continue
        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", s):
            flush_para()
            out.append("<hr>")
            i += 1
            continue
        if s.startswith(">"):
            flush_para()
            q: list[str] = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                q.append(lines[i].strip()[1:].strip())
                i += 1
            out.append("<blockquote><p>" + "<br>".join(inline(x) for x in q if x) + "</p></blockquote>")
            continue
        ul = re.match(r"^[-*+]\s+(.*)$", s)
        ol = re.match(r"^\d+[.)]\s+(.*)$", s)
        if ul or ol:
            flush_para()
            tag = "ul" if ul else "ol"
            pat = r"^[-*+]\s+(.*)$" if ul else r"^\d+[.)]\s+(.*)$"
            items: list[str] = []
            while i < len(lines):
                mm = re.match(pat, lines[i].strip())
                if not mm:
                    break
                items.append(f"<li>{inline(mm.group(1))}</li>")
                i += 1
            out.append(f"<{tag}>" + "".join(items) + f"</{tag}>")
            continue
        para.append(s)
        i += 1
    flush_para()
    return out


def to_html(md: str) -> str:
    return "".join(blocks(md))


def article_html(free_md: str, paid_md: str) -> tuple[str, int]:
    """本文全体の HTML と、無料部分のブロック数（有料ラインを置く位置）を返す。"""
    free = blocks(free_md)
    paid = blocks(paid_md)
    return "".join(free + paid), len(free)


def article_markdown(title: str, free_md: str, paid_md: str, price: int, tags: list[str]) -> str:
    """手で貼り付けるとき用のプレビュー。"""
    return (
        f"# {title}\n\n{free_md}\n\n"
        f"<!-- ===== ここから有料（{price}円） ===== -->\n\n{paid_md}\n\n"
        + " ".join(f"#{t}" for t in tags)
        + "\n"
    )
