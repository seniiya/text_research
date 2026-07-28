"""AI 응답(role=Response)을 코딩북 3항에 따라 문장 단위로 분리한다.

분리 로직의 원본이자 검증 도구다. 파일은 만들지 않고 리포트만 찍는다.
코딩 시트(CSV/XLSX)는 make_coding_sheet.py 가 이 모듈을 import 해서 만든다.

전략 라벨(code)은 부여하지 않는다. 4~7항은 적용 대상이 아니다.

코딩북 3항 절차:
  1. 줄바꿈으로 나눈다.
  2. 각 줄 안에 마침표·물음표·느낌표가 2개 이상이면 추가로 나눈다.
  3. 구두점이 없는 줄도 1개 문장으로 센다.
  4. 빈 줄·공백만 있는 줄은 제외한다.
  5. 이모지만 있는 줄은 1개 문장으로 유지한다.

문장 경계로 세지 않는 것 (3항 "분리 시 주의할 문자"):
  소수점(3.5), 시간(1:30), 줄임표(... …), 괄호 안의 문장부호.
  불릿 기호(• - * 1. ①)는 제거하고 본문만 남긴다.

사용: python scripts/split_sentences.py P01
"""

import json
import re
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import markdown_chat  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CHATS = ROOT / "data" / "deid" / "chats"
OUT_DIR = ROOT / "data" / "coding"

# 코딩북 3항은 "괄호 안의 문장부호"만 규정하고 따옴표는 언급하지 않는다.
# 다만 수집 데이터에는 따옴표 안 구두점이 많고, 그대로 두면 인용문이 중간에
# 잘린다(예: '"살쪘다!"고 결론 내릴 필요는 없어.' -> 2문장).
# 오분리 방지라는 3항의 취지에 따라 따옴표를 괄호와 동일하게 취급한다.
# 코딩북 문언대로 따옴표를 무시하려면 False 로 바꾼다.
MASK_QUOTES = True

MASK = "\x00"  # 경계 탐색에서 제외할 위치를 덮어쓰는 문자

SENT_END = ".!?"

PAIRS = [("(", ")"), ("（", "）"), ("[", "]"), ("「", "」"), ("『", "』"), ("<", ">")]
QUOTES = ['"', "'", "“”", "‘’"]

# 선두 불릿. `-` 와 `*` 는 뒤에 공백이 있을 때만 불릿으로 본다
# (연결 기호 `-` 와 마크다운 강조 `**` 를 불릿으로 오인하지 않기 위함).
BULLET_RE = re.compile(r"^\s*(?:[•▪◦·]\s*|[-*]\s+|\d+[.)]\s+|[\u2460-\u2473]\s*)")


def mask_spans(chars):
    """괄호·따옴표로 둘러싸인 구간의 내용을 마스킹한다."""
    text = "".join(chars)

    for open_c, close_c in PAIRS:
        depth, start = 0, None
        for i, c in enumerate(text):
            if c == open_c:
                if depth == 0:
                    start = i
                depth += 1
            elif c == close_c and depth > 0:
                depth -= 1
                if depth == 0:
                    for j in range(start + 1, i):
                        chars[j] = MASK

    if MASK_QUOTES:
        for q in QUOTES:
            if len(q) == 2:  # 여는/닫는 문자가 다른 경우
                depth, start = 0, None
                for i, c in enumerate(text):
                    if c == q[0]:
                        if depth == 0:
                            start = i
                        depth += 1
                    elif c == q[1] and depth > 0:
                        depth -= 1
                        if depth == 0:
                            for j in range(start + 1, i):
                                chars[j] = MASK
            else:  # 같은 문자가 열고 닫음 -> 짝수 번째끼리 묶는다
                pos = [i for i, c in enumerate(text) if c == q]
                for a, b in zip(pos[::2], pos[1::2]):
                    for j in range(a + 1, b):
                        chars[j] = MASK
    return chars


def mask_non_boundaries(line):
    """문장 경계로 세면 안 되는 위치를 마스킹한 사본을 만든다. 길이는 보존한다."""
    chars = list(line)
    chars = mask_spans(chars)

    # 줄임표: 마침표 2개 이상 연속, 그리고 …
    for m in re.finditer(r"\.{2,}|…", line):
        for j in range(m.start(), m.end()):
            chars[j] = MASK

    # 소수점: 숫자.숫자
    for m in re.finditer(r"\d\.\d", line):
        chars[m.start() + 1] = MASK

    return "".join(chars)


def find_boundaries(line):
    """문장 경계로 인정되는 구두점 덩어리의 끝 위치 목록."""
    masked = mask_non_boundaries(line)
    ends, i = [], 0
    while i < len(masked):
        if masked[i] in SENT_END:
            j = i
            while j + 1 < len(masked) and masked[j + 1] in SENT_END:
                j += 1
            ends.append(j)
            i = j + 1
        else:
            i += 1
    return ends


def split_line(line):
    """한 줄을 문장 리스트로. 경계가 2개 이상일 때만 추가 분리한다 (3항 규칙 2)."""
    ends = find_boundaries(line)
    if len(ends) < 2:
        return [line.strip()] if line.strip() else []

    out, prev = [], 0
    for e in ends:
        chunk = line[prev:e + 1].strip()
        if chunk:
            out.append(chunk)
        prev = e + 1
    tail = line[prev:].strip()
    if tail:
        out.append(tail)
    return out


def split_response(text, markdown=False):
    """응답 1건을 문장 리스트로.

    markdown=True 면 리스트·제목·인용 구조를 먼저 읽어 코딩 단위를 만든다.
    GPT가 한 문장을 여러 문단에 걸쳐 쓴 경우를 다시 이어 붙일 수 있다.
    구조 표시가 없는 평문에는 쓸 수 없다. 목록 항목과 끊긴 문단을 구분할
    수 없어 서로 다른 항목까지 이어 붙게 되기 때문이다.
    """
    if markdown:
        return [s for u in markdown_chat.units(text) for s in split_line(u)]

    sents = []
    for raw in text.split("\n"):
        line = BULLET_RE.sub("", raw).strip()
        if not line:  # 규칙 4
            continue
        sents.extend(split_line(line))
    return sents


def build_rows(pid):
    doc = json.loads((CHATS / f"{pid}.json").read_text(encoding="utf-8"))
    is_md = doc.get("metadata", {}).get("format") == "markdown"
    rows, turn = [], 0
    for msg in doc["messages"]:
        if msg["role"] != "Response":
            continue
        turn += 1
        for n, s in enumerate(split_response(msg["say"], markdown=is_md), start=1):
            rows.append({
                "p_id": pid,
                "turn": turn,
                "sent_no": n,
                "text": s,
                "chars": len(s),
                "code": "",
            })
    return rows


# ─────────────────────────── 검증 리포트 ───────────────────────────

def table(headers, rows, widths):
    line = "  ".join(h.ljust(w) for h, w in zip(headers, widths))
    print(line)
    print("  ".join("-" * w for w in widths))
    for r in rows:
        print("  ".join(str(c).ljust(w) for c, w in zip(r, widths)))


def section(title):
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def report(pid, rows):
    lens = [r["chars"] for r in rows]
    turns = len({r["turn"] for r in rows})

    section(f"1. 총계 — {pid}")
    print(f"총 문장 수 : {len(rows)}")
    print(f"turn 수    : {turns}")
    print(f"turn당 평균: {len(rows) / turns:.1f} 문장")
    print()
    table(["turn", "문장 수"], [[r, sum(1 for x in rows if x["turn"] == r)]
                             for r in range(1, turns + 1)], [6, 8])

    section("2. 문장 길이 분포 (글자 수, 공백 포함)")
    print(f"최소   : {min(lens)}")
    print(f"최대   : {max(lens)}")
    print(f"평균   : {statistics.mean(lens):.1f}")
    print(f"중위값 : {statistics.median(lens):.1f}")

    section("3. 5글자 이하 문장 — 과도 분리 확인")
    short = [r for r in rows if r["chars"] <= 5]
    if short:
        table(["turn", "sent", "chars", "text"],
              [[r["turn"], r["sent_no"], r["chars"], r["text"]] for r in short],
              [5, 5, 6, 40])
    else:
        print("없음")
    print(f"\n소계: {len(short)}건 ({len(short) / len(rows) * 100:.1f}%)")

    section("4. 100글자 이상 문장 — 미분리 확인")
    long = [r for r in rows if r["chars"] >= 100]
    if long:
        for r in long:
            print(f"[turn {r['turn']} / sent {r['sent_no']} / {r['chars']}자]")
            print(f"  {r['text']}")
            print()
    else:
        print("없음")
    print(f"소계: {len(long)}건 ({len(long) / len(rows) * 100:.1f}%)")

    section("5. 화살표·줄임표·소수점·시간표기 포함 문장 — 오분리 확인")
    pats = {
        "화살표": r"→|⇒",
        "줄임표": r"\.{2,}|…",
        "소수점": r"\d\.\d",
        "시간": r"\d:\d\d",
    }
    hits = []
    for r in rows:
        tags = [k for k, p in pats.items() if re.search(p, r["text"])]
        if tags:
            hits.append([r["turn"], r["sent_no"], ",".join(tags), r["text"]])
    if hits:
        table(["turn", "sent", "종류", "text"], hits, [5, 5, 8, 46])
    else:
        print("없음")
    print(f"\n소계: {len(hits)}건")

    section("6. 불릿 기호가 text 안에 남아 있는 문장 — 기호 제거 확인")
    leftover = []
    for r in rows:
        found = []
        if re.match(r"^\s*(?:[•▪◦·]|[-*]\s|\d+[.)]\s|[\u2460-\u2473])", r["text"]):
            found.append("선두불릿")
        if re.search(r"[•▪◦]", r["text"]):
            found.append("•")
        if "**" in r["text"]:
            found.append("**(마크다운 강조)")
        if found:
            leftover.append([r["turn"], r["sent_no"], ",".join(found), r["text"]])
    if leftover:
        table(["turn", "sent", "기호", "text"], leftover, [5, 5, 16, 40])
    else:
        print("없음")
    print(f"\n소계: {len(leftover)}건")

    report_quote_effect(pid, rows)


def report_quote_effect(pid, rows):
    """따옴표 처리 가정을 뒤집으면 결과가 어떻게 달라지는지 보여준다."""
    global MASK_QUOTES  # noqa: PLW0603

    section("7. [추가] 따옴표 처리 가정의 영향 — 코딩북 미규정 사항")
    print(f"MASK_QUOTES = {MASK_QUOTES}"
          f"  (따옴표 안 구두점을 문장 경계로 {'세지 않음' if MASK_QUOTES else '셈'})")
    print()

    orig = MASK_QUOTES
    MASK_QUOTES = not orig
    try:
        other = build_rows(pid)
    finally:
        MASK_QUOTES = orig

    print(f"현재 설정  : {len(rows)}문장")
    print(f"뒤집었을 때: {len(other)}문장  (차이 {len(other) - len(rows):+d})")
    print()
    label = "따옴표를 경계로 셀 경우" if orig else "따옴표를 경계에서 뺄 경우"
    print(f"{label} 달라지는 문장 (최대 10개):")
    cur = {r["text"] for r in rows}
    diff = [r["text"] for r in other if r["text"] not in cur]
    for b in diff[:10]:
        print(f"  - {b}")
    if not diff:
        print("  없음")


def main():
    pid = sys.argv[1] if len(sys.argv) > 1 else "P01"
    rows = build_rows(pid)
    report(pid, rows)
    print()
    print("이 스크립트는 검증 전용이다. 코딩 시트는 make_coding_sheet.py 로 만든다.")


if __name__ == "__main__":
    main()
