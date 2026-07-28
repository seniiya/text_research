"""ChatGPT Exporter 마크다운(.md)을 읽고, 구조를 살려 코딩 단위로 편다.

왜 마크다운인가
---------------
같은 대화의 JSON 내보내기는 문단 구분만 남기고 마크다운 구조를 버린다.
그런데 GPT는 한 문장을 여러 문단에 걸쳐 쓰는 일이 잦아서, 구조 없이
문단마다 끊으면 문장이 조각난다.

    '여기서는' / 'LLM을' / '"잘 만드는 것"' / '보다' / '"잘 사용하는 것"' / '이 중요하다.'

마크다운에는 리스트(`- `), 제목(`## `), 인용(`> `), 표(`| `) 표시가 남아 있어
'진짜 목록 항목'과 '끊긴 문단'을 구분할 수 있다. 일반 문단이 문장부호 없이
끝나면 다음 일반 문단과 이어 붙이고, 리스트 항목은 코딩북 규칙 3대로 각각
1개 문장으로 센다. 위 예는 다시 한 문장이 된다.

    '여기서는 LLM을 "잘 만드는 것"보다 "잘 사용하는 것"이 중요하다.'

파일 형식 (ChatGPT Exporter 마크다운)
-------------------------------------
    # <제목>

    **User:** <이름>
    **Created:** ... / **Updated:** ... / **Exported:** ...
    **Link:** [공유 URL](공유 URL)

    ## Prompt:
    <타임스탬프>

    <본문>

    ## Response:
    ...
"""

import re

HEADING = re.compile(r"^#{1,6}\s+")
LISTITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
QUOTE = re.compile(r"^>\s?")
HR = re.compile(r"^\s*(?:-{3,}|\*{3,}|_{3,})\s*$")
TABLE = re.compile(r"^\s*\|")
TABLE_SEP = re.compile(r"^[-: ]*$")

IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")
BOLD = re.compile(r"\*\*(.+?)\*\*")
ITALIC = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")
CODE = re.compile(r"`([^`]*)`")

MSG_HEAD = re.compile(r"^## (Prompt|Response):\s*$")
TIMESTAMP = re.compile(r"^\d{4}\.\s*\d+\.\s*\d+\.")
ENDS = re.compile(r"[.!?]\s*$")

# 이어 붙일 때 앞말에 바로 붙는 조사·어미. 공백을 넣지 않는다.
PARTICLE = re.compile(
    r"^(?:를|을|이|가|은|는|의|도|만|보다|라고|이라고|하고|와|과|처럼|같은|부터|까지|에게|에서|에)\b"
)

META_PATTERNS = {
    "title": re.compile(r"^#\s+(.+?)\s*$", re.M),
    "user": re.compile(r"^\*\*User:\*\*\s*(.+?)\s*$", re.M),
    "created": re.compile(r"^\*\*Created:\*\*\s*(.+?)\s*$", re.M),
    "updated": re.compile(r"^\*\*Updated:\*\*\s*(.+?)\s*$", re.M),
    "exported": re.compile(r"^\*\*Exported:\*\*\s*(.+?)\s*$", re.M),
}


def parse(text):
    """마크다운 전체를 (메타데이터, 메시지 목록)으로 나눈다."""
    meta = {}
    head = text.split("## Prompt:", 1)[0]
    for key, pat in META_PATTERNS.items():
        m = pat.search(head)
        if m:
            meta[key] = m.group(1).strip()

    msgs, role, buf = [], None, []
    for line in text.split("\n"):
        m = MSG_HEAD.match(line)
        if m:
            if role:
                msgs.append(_finish(role, buf))
            role, buf = m.group(1), []
            continue
        if role:
            buf.append(line)
    if role:
        msgs.append(_finish(role, buf))

    return meta, msgs


def _finish(role, lines):
    """메시지 본문 첫 줄의 타임스탬프를 분리한다."""
    body = "\n".join(lines).strip("\n")
    parts = body.split("\n")
    time = ""
    while parts and not parts[0].strip():
        parts.pop(0)
    if parts and TIMESTAMP.match(parts[0].strip()):
        time = parts.pop(0).strip()
    return {"role": role, "say": "\n".join(parts).strip(), "time": time}


def sanitize(text):
    """구조 표시(- ## > |)는 그대로 두고 URL만 걷어낸다.

    내보내기 마크다운에는 서명이 붙은 이미지 URL이 들어 있다. 공유용
    데이터에 남기지 않는다.
    """
    text = IMAGE.sub("[이미지]", text)
    text = LINK.sub(r"\1", text)
    return re.sub(r"https?://\S+", "[링크]", text)


def strip_inline(s):
    """서식 기호를 걷어내고 본문만 남긴다. 이미지는 자리표시자로 바꾼다."""
    s = IMAGE.sub("[이미지]", s)
    s = LINK.sub(r"\1", s)      # 링크 URL 제거, 표시 문자열만
    s = BOLD.sub(r"\1", s)
    s = ITALIC.sub(r"\1", s)
    s = CODE.sub(r"\1", s)
    return re.sub(r"\s+", " ", s).strip()


def blocks(text):
    """빈 줄로 문단을 끊고 종류를 붙인다. 코드펜스 안은 통째로 하나로 둔다."""
    groups, buf, fence = [], [], False
    for line in text.split("\n"):
        if line.strip().startswith("```"):
            # 펜스가 열릴 때도 앞 문단을 먼저 끊는다. 그러지 않으면 직전
            # 일반 문단이 코드 블록에 딸려 들어간다.
            if buf:
                groups.append(("code" if fence else None, buf))
                buf = []
            fence = not fence
            continue
        if fence:
            buf.append(line)
            continue
        if not line.strip():
            if buf:
                groups.append((None, buf))
                buf = []
            continue
        buf.append(line)
    if buf:
        groups.append((None, buf))

    out = []
    for kind, lines in groups:
        if kind == "code":
            out.append(("code", lines))
            continue
        first = lines[0]
        if HR.match(first):
            continue
        if TABLE.match(first):
            out.append(("table", lines))
        elif HEADING.match(first):
            out.append(("heading", lines))
        elif LISTITEM.match(first):
            out.append(("list", lines))
        elif QUOTE.match(first):
            out.append(("quote", lines))
        else:
            out.append(("plain", lines))
    return out


def _join(parts):
    """조각들을 이어 붙인다. 조사로 시작하면 공백 없이 붙인다."""
    out = parts[0]
    for p in parts[1:]:
        out += ("" if PARTICLE.match(p) else " ") + p
    return out


def units(text):
    """마크다운 본문을 코딩 단위 후보 목록으로 편다.

    - 리스트 항목·제목·표의 각 행 : 각각 1개
    - 일반 문단·인용 : 문장부호로 끝나지 않으면 다음 것과 이어 붙임
    - 코드 블록 : 통째로 1개
    """
    out, pend = [], []

    def flush():
        if pend:
            out.append(_join(pend))
            pend.clear()

    for kind, lines in blocks(text):
        if kind in ("list", "heading", "table", "code"):
            flush()
            if kind == "list":
                for ln in lines:
                    s = strip_inline(LISTITEM.sub("", ln))
                    if s:
                        out.append(s)
            elif kind == "heading":
                s = strip_inline(HEADING.sub("", lines[0]))
                if s:
                    out.append(s)
            elif kind == "table":
                for ln in lines:
                    cells = [strip_inline(c) for c in ln.strip().strip("|").split("|")]
                    if all(TABLE_SEP.fullmatch(c or "") for c in cells):
                        continue    # |---|---| 구분선
                    s = " / ".join(c for c in cells if c)
                    if s:
                        out.append(s)
            else:
                s = strip_inline(" ".join(lines))
                if s:
                    out.append(s)
            continue

        raw = " ".join(QUOTE.sub("", ln) for ln in lines) if kind == "quote" \
            else " ".join(lines)
        s = strip_inline(raw)
        if not s:
            continue
        pend.append(s)
        if ENDS.search(s):
            flush()

    flush()
    return out
