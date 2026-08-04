"""원자료를 가명화해 data/deid/ 로 내보낸다.

입력 (Git 제외):
  data/raw/<이름>_ChatGPT-<제목>.json      원본 대화 로그
  data/survey/...설문지 응답 시트1.csv      표 A(접수, 실명) + 표 B(분석, p_id) 이중 구조

출력:
  data/deid/chats/P01.json ...            metadata.user.name -> P##, share link 제거
  data/deid/survey_analysis.csv           표 B 그대로 (이미 p_id 기준)
  data/deid/index.csv                     P## -> 제목, 턴수  (이름 없음)
  data/private/mapping.csv                P## <-> 실명 연결키. 절대 커밋 금지.

마지막에 검증 단계가 돌며, 출력물에 실명·URL·이메일·전화번호가 하나라도 남아 있으면
비정상 종료한다.

사용: python scripts/deidentify.py
"""

import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import markdown_chat  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
SURVEY = ROOT / "data" / "survey"
DEID = ROOT / "data" / "deid"
PRIVATE = ROOT / "data" / "private"

SURVEY_CSV = "AI 채팅 기록 공유 접수(응답) - 설문지 응답 시트1.csv"
SURVEY_CSV_NEW = "AI 채팅 기록 공유 접수(응답) - 설문지 응답 시트1 (1).csv"

# 2차 모집은 폼을 새로 만들어 열 구성이 다르다. 접수 순서대로 P12 부터 붙인다.
NEW_PID_START = 12

# 번호를 고정한 응답. 접수 시각으로 지목한다 (실명을 스크립트에 남기지 않는다).
#
# 왜 필요한가 — 기본 규칙이 '접수 순서대로 P12 부터'라서, 중간에 응답이 하나
# 끼거나 빠지면 그 뒤 번호가 통째로 밀린다. 그러면 이미 만들어 둔 코딩 시트와
# 분석 결과가 전부 다른 사람을 가리키게 된다. 실제로 2026-07-30 에 로그 미제출
# 1명을 빼면서 한 번 밀렸고, 그때 P20 의 정체가 바뀌었다 (README 참조).
#
# 그래서 규칙을 하나 세운다. **한 번 부여한 p_id 는 바꾸지 않는다.**
# 뒤늦게 합류한 응답은 접수 순서와 무관하게 다음 빈 번호를 받는다.
PINNED = {
    # 로그 미제출로 제외됐다가 2026-08-04 에 제출해 재포함. 접수 시각으로는
    # P20 자리지만, 그 번호는 이미 다른 사람 것이므로 뒤에 붙인다.
    "2026. 7. 30 오전 10:42:28": "P21",
    # 3차 합류.
    "2026. 8. 3 오후 3:56:38": "P22",
}

# 연구에서 아예 뺀 응답. 번호를 받지 않는다. 지금은 없다.
EXCLUDED = {}
NEW_TIMESTAMP_COL = 0

# 새 폼 열 번호 -> 분석표 열 이름.
# 감정 문항은 제목이 두 번씩 같아서 번호로만 구분된다.
#   M(12) P(15) T(19) = Valence,  N(13) Q(16) U(20) = Arousal
NEW_COLS = {
    "나이": 3, "MBTI": 5, "성별": 6,
    "사용빈도": 7, "평소_대화주제": 8, "평소_감정상태": 9,
    "요금제": 10, "모델": 11,
    "전_V": 12, "전_A": 13, "전_감정단어": 14,
    "후_V": 15, "후_A": 16, "후_감정단어": 17,
    "주제1": 18, "주제1_V": 19, "주제1_A": 20, "주제1_감정단어": 21,
    "주제2": 23,
}
NEW_NAME_COL = 2

# 무료 요금제에서 쓸 수 있는 모델은 하나뿐이다.
#
# 이 규칙은 한 방향이다. '무료 -> gpt5.5' 이지, 'gpt5.5 -> 무료' 가 아니다.
# 유료가 gpt5.5 를 쓰는 것은 모순이 아니라 기본 모델을 안 바꾼 것이다
# (P03 'gpt5.5 Instant', P21 'Chat GPT 5.5'). 유료의 모델 응답은 표기가
# 제각각이어도 그대로 둔다. 요금제를 실제 사용 모델의 대리 지표로 쓸 수
# 없다는 것 자체가 자료이므로, 추론해서 덮어쓰지 않는다.
FREE_TIER_MODEL = "gpt5.5"

# 응답 자체에 문제가 있어 연구자가 바로잡은 내역. 설문 원본은 건드리지 않고
# 여기에만 적어, 무엇을 왜 고쳤는지 남긴다.
# 감정단어는 자유기술이라 "감정이 없다"는 뜻을 저마다 다르게 쓴다. 그대로 두면
# 같은 상태가 6가지 낱말로 갈라져 집계가 안 된다. 연구자가 무감정으로 통일한 건.
# 자유기술이라 자동 규칙(NORMALIZE)으로 돌리지 않는다. 새 응답이 들어올 때마다
# 사람이 보고 여기에 적는다.
CORRECTIONS = {
    # 단일 선택 문항인데 두 개를 골랐다. 연구자 판단으로 주1-2 로 확정.
    "P12": {"전_감정단어": "무감정"},                             # '무념무상'
    "P13": {"전_감정단어": "무감정"},                             # '무난'
    "P14": {"전_감정단어": "무감정", "후_감정단어": "무감정"},      # '무'
    "P16": {"사용빈도": "주1-2",
            "전_감정단어": "무감정", "후_감정단어": "무감정"},      # '그냥 그럼'
    "P18": {"전_감정단어": "무감정", "후_감정단어": "무감정"},      # '졸림'
    "P19": {"전_감정단어": "무감정"},                             # '특별한 감정 없음'
    # 유료라 무료 요금제 자동 확정 규칙이 안 걸린다. 같은 모델을 다르게 적은
    # 것뿐이라 표기만 맞춘다. 요금제로 모델을 추론한 것이 아니다.
    "P20": {"모델": "gpt5.5"},                                    # 'Chat GPT 5.5'
}

# 다른 열에 잘못 적힌 응답을 옮긴다. (p_id, 원래 열, 옮길 열)
# P19 는 '두 번째로 오래 다룬 주제' 칸에 주제가 아니라 대화 소감을 적었다.
MOVES = [("P19", "주제2", "첨언")]

# 표기 통일. 같은 선택지가 폼마다 다르게 적혀 있어 그대로 두면 집계에서 갈라진다.
NORMALIZE = {
    "성별": {"여성": "F", "남성": "M"},
    "요금제": {"무료 버전": "무료", "유료(Plus 등)": "유료"},
    "사용빈도": {
        "거의 매일": "거의매일", "거의 사용 안 함": "거의사용안함",
        "월 1~3회": "월1-3", "주 1~2회": "주1-2", "주 3~5회": "주3-5",
    },
}

# 표 A는 0행이 헤더, 1행부터 응답. 빈 행을 만나면 끝.
# 표 B는 p_id 를 첫 칸으로 갖는 헤더 행에서 시작.
TABLE_B_HEADER = "p_id"

PII_PATTERNS = {
    "email": r"[\w.+-]+@[\w-]+\.[\w.]+",
    "phone": r"01[016-9][-. ]?\d{3,4}[-. ]?\d{4}",
    "url": r"https?://[^\s\"')\]]+",
    "주민등록번호": r"\d{6}-\d{7}",
}

# 대화 본문에 남은 실명을 이걸로 바꾼다. sanitize() 의 [이미지]·[링크] 와 같은 표기.
NAME_PLACEHOLDER = "[이름]"

# 이름은 한 글자면 흔한 낱말과 겹친다('이', '수'...). 두 글자부터만 지운다.
MIN_NAME_LEN = 2


def read_survey():
    """설문 CSV를 표 A(접수)와 표 B(분석)로 분리한다."""
    with open(SURVEY / SURVEY_CSV, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.reader(fh))

    a_header = rows[0]
    a_rows = []
    for row in rows[1:]:
        if not any(c.strip() for c in row):
            break
        a_rows.append(row)

    b_start = next(i for i, r in enumerate(rows) if r and r[0].strip() == TABLE_B_HEADER)
    b_header = rows[b_start]
    b_rows = [r for r in rows[b_start + 1:] if any(c.strip() for c in r)]

    return (a_header, a_rows), (b_header, b_rows)


def assign_pids(new_rows):
    """2차 폼 각 행에 p_id 를 붙인다. 이 함수가 배정의 유일한 출처다.

    PINNED 에 적힌 접수 시각은 그 번호를 그대로 쓰고, 나머지는 P12 부터
    순서대로 채우되 고정된 번호는 건너뛴다. 배정을 두 군데서 따로 계산하면
    분석표와 매핑이 어긋나므로 반드시 이 함수를 거친다.
    """
    taken = set(PINNED.values())
    pids, n = [], NEW_PID_START
    for r in new_rows:
        pinned = PINNED.get(r[NEW_TIMESTAMP_COL].strip())
        if pinned:
            pids.append(pinned)
            continue
        while f"P{n:02d}" in taken:
            n += 1
        pids.append(f"P{n:02d}")
        n += 1
    if len(set(pids)) != len(pids):
        sys.exit(f"[중단] p_id 중복: {sorted(pids)}")
    return pids


def read_new_survey():
    """2차 폼. 헤더 1줄 + 응답. 번호는 assign_pids() 가 붙인다.

    EXCLUDED 는 여기서 걸러낸다. 번호를 받지 않고 아예 빠지는 응답이다.
    """
    path = SURVEY / SURVEY_CSV_NEW
    if not path.exists():
        return [], []
    with open(path, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.reader(fh))

    kept, dropped = [], []
    for r in rows[1:]:
        if len(r) <= NEW_NAME_COL or not r[NEW_NAME_COL].strip():
            continue
        stamp = r[NEW_TIMESTAMP_COL].strip()
        if stamp in EXCLUDED:
            dropped.append(f"{stamp} ({EXCLUDED[stamp]})")
        else:
            kept.append(r)
    return kept, dropped


def tidy(field, value):
    """표기 통일. 규칙에 없으면 공백만 정리해 그대로 둔다."""
    v = value.strip()
    if field in NORMALIZE:
        return NORMALIZE[field].get(v, v)
    if field == "MBTI":
        return v.upper()
    if field in ("평소_대화주제", "평소_감정상태"):
        # '정보 검색 · 질문' -> '정보 검색·질문' (1차 폼 표기에 맞춘다)
        return re.sub(r"\s*·\s*", "·", v)
    return v


def new_rows_as_analysis(new_rows, b_header):
    """2차 폼 응답을 1차 분석표(표 B) 열 구성으로 변환한다."""
    out = []
    for pid, r in zip(assign_pids(new_rows), new_rows):
        rec = {"p_id": pid}
        for field, col in NEW_COLS.items():
            rec[field] = tidy(field, r[col] if col < len(r) else "")
        # 2차 폼은 주제2 의 V·A·감정단어와 첨언을 묻지 않는다. 총_턴수는 로그에서 센다.
        for field in ("주제2_V", "주제2_A", "주제2_감정단어", "첨언", "총_턴수"):
            rec.setdefault(field, "")
        out.append([rec.get(h, "") for h in b_header])
    return out


def build_mapping(a_header, a_rows, new_rows=()):
    """실명 -> P## 매핑. 표 A의 '실험자 번호'를 그대로 쓴다."""
    name_i = a_header.index("사용자 이름")
    num_i = a_header.index("실험자 번호")
    link_i = a_header.index("공유된 채팅 링크")

    mapping = {}
    for row in a_rows:
        name = row[name_i].strip()
        num = row[num_i].strip()
        if not name or not num:
            continue
        mapping[name] = {"pid": f"P{int(num):02d}", "link": row[link_i].strip()}

    if len(mapping) != len(a_rows):
        sys.exit(f"[중단] 표 A {len(a_rows)}행 중 {len(mapping)}행만 매핑됨. 빈 이름/번호 확인 필요.")

    for pid, r in zip(assign_pids(new_rows), new_rows):
        name = r[NEW_NAME_COL].strip()
        if name in mapping:
            sys.exit(f"[중단] '{name}' 이 1차와 2차 설문에 모두 있음.")
        link_col = 4        # 2차 폼의 '공유할 ChatGPT 채팅 링크'
        mapping[name] = {
            "pid": pid,
            "link": r[link_col].strip() if link_col < len(r) else "",
        }

    pids = [v["pid"] for v in mapping.values()]
    if len(set(pids)) != len(pids):
        sys.exit(f"[중단] 실험자 번호 중복: {sorted(pids)}")

    return mapping


def collect_sources():
    """참여자별 원본 파일을 고른다. 같은 사람의 .md 와 .json 이 둘 다 있으면
    .md 를 쓴다. 마크다운은 리스트·제목·인용 구조가 남아 있어 문장 분리가
    정확하다 (markdown_chat 모듈 설명 참고)."""
    picked = {}
    for path in sorted(RAW.glob("*.md")) + sorted(RAW.glob("*.json")):
        name = path.stem.split("_", 1)[0]
        if name not in picked:      # .md 를 먼저 순회하므로 .md 가 이긴다
            picked[name] = path
    return picked


def name_tokens(mapping):
    """지워야 할 실명 표기를 모은다. 긴 것부터 지우도록 정렬한다.

    참여자는 대화 중 자기 이름을 말하고, GPT는 그 이름을 그대로 불러 준다.
    이때 성을 뗀 이름만 쓰는 일이 훨씬 잦다("길동이는 22살이지만").
    풀네임만 지우면 이쪽이 그대로 남으므로 둘 다 지운다. '홍길동' 을 먼저
    지워야 '홍[이름]' 이 되지 않는다.
    """
    tokens = set()
    for name in mapping:
        name = name.strip()
        if len(name) >= MIN_NAME_LEN:
            tokens.add(name)
        given = name[1:]            # 성 한 글자를 뗀 이름
        if len(given) >= MIN_NAME_LEN:
            tokens.add(given)
    return sorted(tokens, key=len, reverse=True)


def scrub_names(text, tokens):
    for t in tokens:
        text = text.replace(t, NAME_PLACEHOLDER)
    return text


def scrub_doc(doc, tokens):
    """제목과 발화 본문에서 실명을 지운다.

    모든 참여자의 이름을 모든 파일에서 지운다. 대화에 등장하는 제3자가
    다른 참여자와 동명이인일 수 있고, 그 경우에도 실명인 것은 같다.
    """
    meta = doc.get("metadata", {})
    if meta.get("title"):
        meta["title"] = scrub_names(meta["title"], tokens)
    for m in doc.get("messages", []):
        m["say"] = scrub_names(m.get("say", ""), tokens)
    return doc


def deid_chats(mapping):
    """원본을 P## 로 치환해 내보낸다. 파일명 앞부분(실명)으로 매칭한다."""
    out_dir = DEID / "chats"
    out_dir.mkdir(parents=True, exist_ok=True)

    index = []
    seen = set()
    warnings = []
    tokens = name_tokens(mapping)
    scrubbed = []

    for name, path in sorted(collect_sources().items()):
        if name not in mapping:
            sys.exit(f"[중단] '{path.name}' 의 이름 '{name}' 이 설문 표 A에 없음.")

        pid = mapping[name]["pid"]
        if pid in seen:
            sys.exit(f"[중단] {pid} 가 두 번 나옴 ({path.name}).")
        seen.add(pid)

        if path.suffix == ".md":
            doc, inner = _from_markdown(path)
        else:
            doc, inner = _from_json(path)

        # 파일명과 파일 안의 이름이 어긋날 수 있으므로 기록만 남긴다.
        if inner and inner != name:
            warnings.append(f"  {path.name}: 파일명 '{name}' vs 파일 내부 '{inner}'")

        doc["metadata"]["user"] = {"name": pid}

        before = json.dumps(doc, ensure_ascii=False).count(NAME_PLACEHOLDER)
        doc = scrub_doc(doc, tokens)
        added = json.dumps(doc, ensure_ascii=False).count(NAME_PLACEHOLDER) - before
        if added:
            scrubbed.append(f"{pid} {added}회")

        (out_dir / f"{pid}.json").write_text(
            json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        index.append({
            "p_id": pid,
            "source": doc["metadata"]["format"],
            "title": doc["metadata"].get("title", ""),
            "n_messages": len(doc.get("messages", [])),
        })

    missing = sorted({v["pid"] for v in mapping.values()} - seen)
    if missing:
        warnings.append(f"  원본 없는 참여자: {', '.join(missing)}")

    plain = sorted(r["p_id"] for r in index if r["source"] != "markdown")
    if plain:
        warnings.append(
            f"  마크다운이 없어 문단 단위로만 분리되는 참여자: {', '.join(plain)}\n"
            f"    -> 같은 대화를 .md 로 내보내 data/raw/ 에 넣으면 구조 기반으로 분리된다."
        )

    index.sort(key=lambda r: r["p_id"])
    with open(DEID / "index.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["p_id", "source", "title", "n_messages"])
        w.writeheader()
        w.writerows(index)

    return index, warnings, scrubbed


def _from_json(path):
    """JSON 내보내기. 마크다운 구조가 없어 문단 단위로만 나뉜다."""
    doc = json.loads(path.read_text(encoding="utf-8"))
    meta = doc.get("metadata", {})
    inner = (meta.get("user") or {}).get("name", "").strip()
    meta.pop("link", None)          # 공개 share URL 제거
    meta.pop("powered_by", None)    # 내보내기 도구 광고, 분석과 무관
    meta["format"] = "plain"
    doc["metadata"] = meta
    return doc, inner


def _from_markdown(path):
    """마크다운 내보내기. say 에 구조 표시(- ## > |)를 살려 둔다."""
    meta_raw, msgs = markdown_chat.parse(path.read_text(encoding="utf-8"))
    inner = meta_raw.get("user", "").strip()

    for m in msgs:
        m["say"] = markdown_chat.sanitize(m["say"])

    doc = {
        "metadata": {
            "title": meta_raw.get("title", ""),
            "user": {},
            "dates": {k: meta_raw.get(k, "") for k in ("created", "updated", "exported")},
            "format": "markdown",
        },
        "messages": msgs,
    }
    return doc, inner


def unexplained_edits(b_header, rows, explained):
    """덮어쓰기 직전에, 스크립트가 설명할 수 없는 차이를 찾는다.

    이 스크립트는 분석표를 덧붙이지 않고 매번 통째로 다시 만든다. 그래서
    data/deid/survey_analysis.csv 를 손으로 고치면 다음 실행에서 조용히
    사라진다. 실제로 감정단어 정정 9건을 그렇게 잃은 적이 있다.

    스크립트가 의도적으로 바꾼 셀(explained)은 빼고 보고한다. 남는 것은
    '누군가 손으로 고쳤지만 CORRECTIONS 에 적히지 않은 값'뿐이다.
    """
    path = DEID / "survey_analysis.csv"
    if not path.exists():
        return []
    with open(path, encoding="utf-8", newline="") as fh:
        old = list(csv.reader(fh))
    if not old or old[0] != b_header:
        return []      # 열 구성이 바뀌었으면 비교가 의미 없다

    pid_i = b_header.index("p_id")
    prev = {r[pid_i]: r for r in old[1:] if r}

    lost = []
    for r in rows:
        o = prev.get(r[pid_i])
        if not o or len(o) != len(r):
            continue
        for i, col in enumerate(b_header):
            if (r[pid_i], col) in explained:
                continue
            if o[i].strip() != r[i].strip():
                lost.append(f"{r[pid_i]} {col}: {o[i]!r} -> {r[i]!r}")
    return lost


def write_survey_analysis(b_header, b_rows, new_rows, turns):
    """1차 표 B(이미 p_id 기준) 뒤에 2차 폼 변환분을 붙인다.

    총_턴수는 설문이 아니라 대화 로그에서 센다. 1차 응답 중 비어 있던 값도
    이때 채워진다.
    """
    rows = [list(r) for r in b_rows] + new_rows_as_analysis(new_rows, b_header)

    pid_at = b_header.index("p_id")
    applied = []
    explained = set()       # 스크립트가 일부러 바꾼 (p_id, 열)

    for pid, target, dest in MOVES:
        for r in rows:
            if r[pid_at] != pid:
                continue
            src_i, dst_i = b_header.index(target), b_header.index(dest)
            val = r[src_i].strip()
            if val:
                r[dst_i] = (r[dst_i].strip() + " " + val).strip()
                r[src_i] = ""
                applied.append(f"{pid} {target}->{dest}")
                explained |= {(pid, target), (pid, dest)}

    for pid, fields in CORRECTIONS.items():
        for r in rows:
            if r[pid_at] != pid:
                continue
            for field, value in fields.items():
                i = b_header.index(field)
                explained.add((pid, field))
                if r[i].strip() != value:
                    applied.append(f"{pid} {field} {r[i]!r}->{value!r}")
                    r[i] = value

    # 무료 요금제는 선택할 수 있는 모델이 하나뿐이다. 2차 폼의 모델 문항이
    # 자유입력이라 '.', 'ㅁㄴㅇ', '모름' 같은 값이 들어왔는데, 요금제로부터
    # 확정할 수 있으므로 채운다. 유료는 모델이 여러 개라 추론하지 않는다.
    plan_i = b_header.index("요금제")
    model_i = b_header.index("모델")
    fixed_model = []
    for r in rows:
        if r[plan_i].strip() == "무료" and r[model_i].strip() != FREE_TIER_MODEL:
            fixed_model.append(f"{r[b_header.index('p_id')]} {r[model_i]!r}")
            r[model_i] = FREE_TIER_MODEL
            explained.add((r[pid_at], "모델"))

    pid_i = b_header.index("p_id")
    turn_i = b_header.index("총_턴수")
    filled = []
    for r in rows:
        n = turns.get(r[pid_i])
        if n and str(r[turn_i]).strip() != str(n):
            if str(r[turn_i]).strip():
                filled.append(f"{r[pid_i]} {r[turn_i]}->{n}")
            r[turn_i] = n
            explained.add((r[pid_i], "총_턴수"))

    rows.sort(key=lambda r: r[pid_i])

    # 덮어쓰기 전에 본다. 여기 뭔가 잡히면 손으로 고친 값이 사라진다는 뜻이다.
    lost = unexplained_edits(b_header, rows, explained)

    DEID.mkdir(parents=True, exist_ok=True)
    with open(DEID / "survey_analysis.csv", "w", encoding="utf-8", newline="") as fh:
        csv.writer(fh).writerows([b_header] + rows)
    return len(rows), filled, fixed_model, applied, lost


def write_mapping(mapping):
    """연결키. data/private/ 는 .gitignore 로 통째로 제외된다."""
    PRIVATE.mkdir(parents=True, exist_ok=True)
    with open(PRIVATE / "mapping.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["p_id", "name", "share_link"])
        for name, v in sorted(mapping.items(), key=lambda kv: kv[1]["pid"]):
            w.writerow([v["pid"], name, v["link"]])


def verify(mapping):
    """출력물 전체를 훑어 잔존 식별정보를 찾는다."""
    names = set(mapping)
    # 파일 내부 표기가 파일명과 다른 경우까지 잡는다.
    for path in RAW.glob("*.json"):
        doc = json.loads(path.read_text(encoding="utf-8"))
        inner = ((doc.get("metadata") or {}).get("user") or {}).get("name", "").strip()
        if inner:
            names.add(inner)
    for path in RAW.glob("*.md"):
        meta, _ = markdown_chat.parse(path.read_text(encoding="utf-8"))
        if meta.get("user"):
            names.add(meta["user"].strip())

    # 성을 뗀 이름까지 본다. 대화에서는 이쪽이 훨씬 자주 불린다.
    tokens = name_tokens({n: None for n in names})

    problems = []
    for path in sorted(DEID.rglob("*")):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(ROOT)
        for n in tokens:
            if n in text:
                problems.append(f"{rel}: 실명 '{n}' {text.count(n)}회")
        for label, pat in PII_PATTERNS.items():
            for m in re.findall(pat, text):
                problems.append(f"{rel}: {label} '{m}'")
    return problems


def main():
    (a_header, a_rows), (b_header, b_rows) = read_survey()
    new_rows, dropped = read_new_survey()
    mapping = build_mapping(a_header, a_rows, new_rows)
    print(f"설문 1차: 표 A {len(a_rows)}명 / 표 B {len(b_rows)}행"
          f" | 2차 폼: {len(new_rows)}명")
    if dropped:
        print(f"  연구에서 제외: {', '.join(dropped)}")

    index, warnings, scrubbed = deid_chats(mapping)
    turns = {r["p_id"]: r["n_messages"] // 2 for r in index}
    n_survey, filled, fixed_model, applied, lost = write_survey_analysis(
        b_header, b_rows, new_rows, turns)
    write_mapping(mapping)

    print(f"가명화 대화 {len(index)}건 -> data/deid/chats/")
    if scrubbed:
        print(f"  본문 실명을 {NAME_PLACEHOLDER} 로 치환: {', '.join(scrubbed)}")
    print(f"분석표 {n_survey}행 -> data/deid/survey_analysis.csv")
    if filled:
        print(f"  총_턴수 로그 기준으로 정정: {', '.join(filled)}")
    if fixed_model:
        print(f"  무료 요금제 모델을 {FREE_TIER_MODEL} 로 확정: {', '.join(fixed_model)}")
    if applied:
        print(f"  연구자 정정 적용: {', '.join(applied)}")
    print(f"연결키 {len(mapping)}행 -> data/private/mapping.csv  (커밋 금지)")

    if lost:
        print(f"\n[경고] 분석표를 손으로 고친 값 {len(lost)}건을 덮어썼다."
              f" 유지하려면 CORRECTIONS 에 적어야 한다:")
        for x in lost:
            print("  " + x)

    if warnings:
        print("\n[확인 필요]")
        for w in warnings:
            print(w)

    problems = verify(mapping)
    if problems:
        print(f"\n[검증 실패] 출력물에 식별정보 {len(problems)}건이 남아 있다:")
        for p in problems:
            print("  " + p)
        sys.exit(1)

    print("\n[검증 통과] 출력물에서 실명·URL·이메일·전화번호가 발견되지 않음.")


if __name__ == "__main__":
    main()
