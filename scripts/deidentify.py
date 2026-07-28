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

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
SURVEY = ROOT / "data" / "survey"
DEID = ROOT / "data" / "deid"
PRIVATE = ROOT / "data" / "private"

SURVEY_CSV = "AI 채팅 기록 공유 접수(응답) - 설문지 응답 시트1.csv"

# 표 A는 0행이 헤더, 1행부터 응답. 빈 행을 만나면 끝.
# 표 B는 p_id 를 첫 칸으로 갖는 헤더 행에서 시작.
TABLE_B_HEADER = "p_id"

PII_PATTERNS = {
    "email": r"[\w.+-]+@[\w-]+\.[\w.]+",
    "phone": r"01[016-9][-. ]?\d{3,4}[-. ]?\d{4}",
    "url": r"https?://[^\s\"')\]]+",
    "주민등록번호": r"\d{6}-\d{7}",
}


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


def build_mapping(a_header, a_rows):
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

    pids = [v["pid"] for v in mapping.values()]
    if len(set(pids)) != len(pids):
        sys.exit(f"[중단] 실험자 번호 중복: {sorted(pids)}")

    return mapping


def deid_chats(mapping):
    """raw JSON을 P## 로 치환해 내보낸다. 파일명 앞부분(실명)으로 매칭한다."""
    out_dir = DEID / "chats"
    out_dir.mkdir(parents=True, exist_ok=True)

    index = []
    seen = set()
    warnings = []

    for path in sorted(RAW.glob("*.json")):
        name = path.stem.split("_", 1)[0]
        if name not in mapping:
            sys.exit(f"[중단] '{path.name}' 의 이름 '{name}' 이 설문 표 A에 없음.")

        pid = mapping[name]["pid"]
        if pid in seen:
            sys.exit(f"[중단] {pid} 가 두 번 나옴 ({path.name}).")
        seen.add(pid)

        doc = json.loads(path.read_text(encoding="utf-8"))
        meta = doc.get("metadata", {})

        # 파일명과 JSON 내부 이름이 어긋날 수 있으므로 기록만 남긴다.
        inner = (meta.get("user") or {}).get("name", "").strip()
        if inner and inner != name:
            warnings.append(f"  {path.name}: 파일명 '{name}' vs JSON 내부 '{inner}'")

        meta["user"] = {"name": pid}
        meta.pop("link", None)          # 공개 share URL 제거
        meta.pop("powered_by", None)    # 내보내기 도구 광고, 분석과 무관
        doc["metadata"] = meta

        (out_dir / f"{pid}.json").write_text(
            json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        index.append({
            "p_id": pid,
            "title": meta.get("title", ""),
            "n_messages": len(doc.get("messages", [])),
        })

    missing = sorted({v["pid"] for v in mapping.values()} - seen)
    if missing:
        warnings.append(f"  raw JSON 없는 참여자: {', '.join(missing)}")

    index.sort(key=lambda r: r["p_id"])
    with open(DEID / "index.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["p_id", "title", "n_messages"])
        w.writeheader()
        w.writerows(index)

    return index, warnings


def write_survey_analysis(b_header, b_rows):
    """표 B는 이미 p_id 기준이므로 그대로 내보낸다."""
    DEID.mkdir(parents=True, exist_ok=True)
    with open(DEID / "survey_analysis.csv", "w", encoding="utf-8", newline="") as fh:
        csv.writer(fh).writerows([b_header] + b_rows)
    return len(b_rows)


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
    # JSON 내부 표기가 파일명과 다른 경우까지 잡는다.
    for path in RAW.glob("*.json"):
        doc = json.loads(path.read_text(encoding="utf-8"))
        inner = ((doc.get("metadata") or {}).get("user") or {}).get("name", "").strip()
        if inner:
            names.add(inner)

    problems = []
    for path in sorted(DEID.rglob("*")):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(ROOT)
        for n in sorted(names):
            if n in text:
                problems.append(f"{rel}: 실명 '{n}'")
        for label, pat in PII_PATTERNS.items():
            for m in re.findall(pat, text):
                problems.append(f"{rel}: {label} '{m}'")
    return problems


def main():
    (a_header, a_rows), (b_header, b_rows) = read_survey()
    mapping = build_mapping(a_header, a_rows)
    print(f"설문 표 A: {len(a_rows)}명 접수 / 표 B: {len(b_rows)}행 분석표")

    index, warnings = deid_chats(mapping)
    n_survey = write_survey_analysis(b_header, b_rows)
    write_mapping(mapping)

    print(f"가명화 대화 {len(index)}건 -> data/deid/chats/")
    print(f"분석표 {n_survey}행 -> data/deid/survey_analysis.csv")
    print(f"연결키 {len(mapping)}행 -> data/private/mapping.csv  (커밋 금지)")

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
