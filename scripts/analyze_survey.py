"""사후 설문 분석. 대화 로그를 건드리지 않고 설문만 본다.

세 가지를 정리한다.
  1. 평소 AI 와 무슨 주제로 대화하는가 · 어떤 감정 상태에서 쓰는가 (복수응답)
  2. 이번에 실제로 한 대화 주제 (주제1 · 주제2)
  3. 감정 자기보고 VA — 참가자별 전 / 주제1 / 주제2 / 후 와 전→후 변화

VA 네 값은 서로 다른 문항이다. 차이를 계산한 값이 아니다.
  전_V/A    "지금 이 순간(대화 시작 직전)의 감정 상태"
  후_V/A    "지금 이 순간(대화 종료 직후)의 감정 상태"
  주제n_V/A "그 주제를 이야기할 때의 감정은 어땠나요?"
전→후 차이만 여기서 계산한다(후_V - 전_V).

출력
----
표준출력                                절별 수치
data/output/tables/survey_topics.csv        평소 주제·감정 복수응답 집계
data/output/tables/survey_va.csv            참가자별 VA 전체
data/output/tables/survey_participants.csv  참가자별 설문 요약

사용: python scripts/analyze_survey.py
"""

import csv
import re
import sys
from collections import Counter

import numpy as np
from scipy import stats

from speechact_data import ROOT, TABLES, Results, load_survey, num

OUT = TABLES

# 복수응답 문항. 구글 폼이 쉼표로 잇는데 자유기술 항목 안에도 쉼표가 들어간다
# ("분노, 짜증"). 그래서 정해진 보기를 먼저 떼어내고 나머지를 기타로 본다.
TOPIC_CHOICES = ["정보 검색·질문", "학업·업무 도움", "글쓰기 도움", "코딩·기술",
                 "일상 잡담", "고민 상담", "창작·놀이"]
MOOD_CHOICES = ["답답함·스트레스 해소 목적", "호기심", "특별한 감정 없음", "차분함",
                "외로움·심심함", "불안·걱정이 있을 때", "즐거움·재미"]
EMOTIONAL_TOPIC = "고민 상담"   # 보기 중 정서적 대화에 해당하는 것은 이것뿐이다

# 이번에 실제로 한 대화를 묶어 보기 위한 분류. 참가자가 쓴 주제명을 연구자가
# 사후에 묶은 것이므로 판정이 들어간다. 로그가 아니라 주제명만 보고 나눈다.
TOPIC_KIND = [
    ("고민·정서", ["고민", "퇴사", "야근", "대인관계", "진로", "스트레스", "걱정",
                   "방향성", "컨택", "복학"]),
    ("일상·잡담", ["점심", "식사", "카페", "강아지", "영화", "담", "일상", "자유",
                   "민달팽이", "뱃살", "수면", "다이어트", "추천", "학생 이야기"]),
    ("학업·업무", ["과제", "자소서", "공문", "논문", "자격증", "기계", "공부", "관리"]),
    ("정보 검색", ["금리", "검색", "기준"]),
]


def multi(rows, col, choices):
    """복수응답을 보기별로 센다. 보기에 없는 것은 기타로 따로 모은다."""
    c, other = Counter(), Counter()
    for r in rows:
        s = str(r.get(col, "") or "")
        hit = [ch for ch in choices if ch in s]
        c.update(hit)
        rest = s
        for ch in hit:
            rest = rest.replace(ch, "")
        for t in re.split(r"[,·]", rest):
            t = t.strip(" ,·")
            if len(t) > 1:
                other[t] += 1
    return c, other


def kind_of(topic):
    t = str(topic)
    for name, keys in TOPIC_KIND:
        if any(k in t for k in keys):
            return name
    return "기타"


def section(t):
    print(f"\n{'=' * 74}\n{t}\n{'=' * 74}")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sv = load_survey()
    rows = [sv[k] for k in sorted(sv)]
    N = len(rows)
    R = Results("analyze_survey.py")
    S_WHO, S_USUAL = "참가자", "평소 AI와 무슨 대화를 하는가"
    S_THIS, S_VA = "이번에 실제로 한 대화", "감정 자기보고 VA"

    # ── 1. 참가자 ────────────────────────────────────────────────────
    section("1. 참가자")
    ages = [num(r["나이"]) for r in rows if num(r["나이"]) is not None]
    demo = [["인원", f"{N}명"],
            ["나이", f"평균 {np.mean(ages):.1f}세 · 중앙값 {np.median(ages):.0f} · "
                     f"범위 {min(ages):.0f}–{max(ages):.0f}"]]
    for col in ("성별", "모델", "요금제", "사용빈도"):
        c = Counter(str(r.get(col, "")).strip() or "무응답" for r in rows)
        demo.append([col, " · ".join(f"{k} {v}" for k, v in c.most_common())])
    for a, b in demo:
        print(f"  {a:<8}{b}")
    R.table(S_WHO, "인구통계", ["구분", "값"], demo)

    # ── 2. 평소 대화 주제 ────────────────────────────────────────────
    section("2. 평소 AI와 무슨 주제로 대화하는가  (복수응답)")
    tc, tother = multi(rows, "평소_대화주제", TOPIC_CHOICES)
    trows = [[k, v, round(v / N * 100, 1)] for k, v in tc.most_common()]
    for k, v, p in trows:
        print(f"  {v:>3}명 {p:>5.1f}%   {k}")
    R.table(S_USUAL, "평소 대화 주제 (보기 7개)", ["주제", "응답자", "비율(%)"], trows,
            note=f"복수응답. 한 사람이 평균 {sum(tc.values()) / N:.1f}개를 골랐다. "
                 f"보기 밖 자유기술 {len(tother)}종은 topics.csv 에 있다.")
    orows = [[k, v] for k, v in tother.most_common()]
    print(f"\n  기타(자유기술) {len(orows)}종")
    for k, v in orows:
        print(f"       {v}   {k}")
    R.table(S_USUAL, "평소 대화 주제 — 기타 자유기술", ["내용", "응답자"], orows)

    section("3. 평소 어떤 감정 상태에서 쓰는가  (복수응답)")
    mc, _ = multi(rows, "평소_감정상태", MOOD_CHOICES)
    mrows = [[k, v, round(v / N * 100, 1)] for k, v in mc.most_common()]
    for k, v, p in mrows:
        print(f"  {v:>3}명 {p:>5.1f}%   {k}")
    R.table(S_USUAL, "평소 사용 시 감정 상태", ["감정 상태", "응답자", "비율(%)"], mrows)

    # ── 4. 이번에 실제로 한 대화 ─────────────────────────────────────
    section("4. 이번에 실제로 한 대화 주제")
    n2 = sum(1 for r in rows if str(r.get("주제2", "")).strip())
    print(f"  에피소드 {N + n2}개 (주제1 {N}건 + 주제2 {n2}건)\n")
    trows2 = []
    for r in rows:
        t1, t2 = str(r["주제1"]).strip(), str(r.get("주제2", "")).strip()
        trows2.append([r["p_id"], t1, kind_of(t1), t2, kind_of(t2) if t2 else ""])
        print(f"  {r['p_id']}  {t1[:38]:<40}{kind_of(t1):<8}"
              + (f"| {t2[:24]}" if t2 else ""))
    R.table(S_THIS, "참가자별 대화 주제",
            ["참가자", "주제1", "분류", "주제2", "분류"], trows2,
            note="'분류'는 연구자가 주제명만 보고 사후에 묶은 것이다.")

    kinds = Counter([kind_of(r["주제1"]) for r in rows]
                    + [kind_of(r["주제2"]) for r in rows
                       if str(r.get("주제2", "")).strip()])
    krows = [[k, v, round(v / (N + n2) * 100, 1)] for k, v in kinds.most_common()]
    print("\n  주제 분류")
    for k, v, p in krows:
        print(f"    {v:>3}건 {p:>5.1f}%   {k}")
    R.table(S_THIS, "대화 주제 분류", ["분류", "에피소드", "비율(%)"], krows)
    R.num(S_THIS, "에피소드 수", N + n2, "개", n=N,
          note=f"주제1 {N}건 + 주제2 {n2}건")

    # ── 5. 평소 인식 vs 실제 ─────────────────────────────────────────
    section("5. 평소 주제 인식 ↔ 실제 대화")
    said = {r["p_id"] for r in rows if EMOTIONAL_TOPIC in str(r.get("평소_대화주제", ""))}
    neg = [r for r in rows if (num(r.get("주제1_V")) or 9) <= 3]
    miss = [r for r in neg if r["p_id"] not in said]
    print(f"  평소 주제로 '{EMOTIONAL_TOPIC}'을 고른 사람 {len(said)}명 "
          f"({', '.join(sorted(said))})\n")
    nrows = []
    for r in sorted(neg, key=lambda r: num(r["주제1_V"])):
        got = "○" if r["p_id"] in said else "—"
        nrows.append([r["p_id"], f"V{num(r['주제1_V']):.0f}", str(r["주제1"])[:24],
                      got, str(r["평소_대화주제"])[:40]])
        print(f"  {r['p_id']}  V{num(r['주제1_V']):.0f}  {got}  "
              f"실제=[{str(r['주제1'])[:24]:<26}] 평소=[{str(r['평소_대화주제'])[:36]}]")
    print(f"\n  '{EMOTIONAL_TOPIC}'을 고르지 않은 사람 {len(miss)}/{len(neg)}명")
    print(f"  ! n={len(neg)} 이라 통계가 아니다. 사례로만 본다.")
    R.table(S_THIS, "자기보고가 부정(주제1 V≤3)인 참가자",
            ["참가자", "주제1 V", "실제 주제", "평소 주제에 '고민 상담' 포함", "평소 주제"],
            nrows,
            note=f"{len(miss)}/{len(neg)}명이 평소 주제로 '{EMOTIONAL_TOPIC}'을 "
                 f"고르지 않았다. n={len(neg)} 이라 사례다.")

    # ── 6. 감정 자기보고 VA ─────────────────────────────────────────
    section("6. 감정 자기보고 VA — 참가자별")
    hdr = ["참가자", "전 V", "전 A", "주제1 V", "주제1 A", "주제2 V", "주제2 A",
           "후 V", "후 A", "후−전 V", "후−전 A"]
    print("  " + "".join(f"{h:>8}" for h in hdr))
    varows = []
    for r in rows:
        g = lambda k: num(r.get(k))
        dv = None if g("후_V") is None or g("전_V") is None else g("후_V") - g("전_V")
        da = None if g("후_A") is None or g("전_A") is None else g("후_A") - g("전_A")
        row = [r["p_id"]] + [g(k) for k in
                             ("전_V", "전_A", "주제1_V", "주제1_A", "주제2_V",
                              "주제2_A", "후_V", "후_A")] + [dv, da]
        varows.append([c if c is not None else "" for c in row])
        print("  " + f"{r['p_id']:>8}" + "".join(
            f"{('' if v is None else f'{v:.0f}'):>8}" for v in row[1:9])
            + "".join(f"{('' if v is None else f'{v:+.0f}'):>8}" for v in (dv, da)))
    R.table(S_VA, "참가자별 자기보고 VA", hdr, varows,
            note="9점 척도. V 는 유쾌–불쾌, A 는 각성–이완.")

    print("\n  요약")
    def col(k):
        return np.array([num(r.get(k)) for r in rows if num(r.get(k)) is not None])
    srows = []
    for k in ("전_V", "전_A", "주제1_V", "주제1_A", "주제2_V", "주제2_A", "후_V", "후_A"):
        v = col(k)
        srows.append([k.replace("_", " "), len(v), round(float(v.mean()), 2),
                      round(float(v.std(ddof=1)), 2), int(v.min()), int(v.max())])
        print(f"    {k:<9}n={len(v):>3}  평균 {v.mean():.2f}  SD {v.std(ddof=1):.2f}  "
              f"범위 {v.min():.0f}–{v.max():.0f}")
    R.table(S_VA, "VA 요약 통계", ["문항", "n", "평균", "SD", "최소", "최대"], srows)

    pair = [(num(r["전_V"]), num(r["후_V"])) for r in rows
            if num(r.get("전_V")) is not None and num(r.get("후_V")) is not None]
    a = np.array([p[0] for p in pair]); b = np.array([p[1] for p in pair])
    r_, p_ = stats.pearsonr(a, b)
    t_, tp = stats.ttest_rel(b, a)
    print(f"\n  전_V {a.mean():.2f} → 후_V {b.mean():.2f}  ({b.mean() - a.mean():+.2f})"
          f"   대응표본 t = {t_:+.2f}  p = {tp:.3f}")
    print(f"  전↔후 r = {r_:+.3f} (p = {p_:.3f}) — 변화량이 아니라 순위 유지 정도다")
    R.num(S_VA, "대화 전후 Valence 변화", float(b.mean() - a.mean()), "점", n=len(pair),
          note=f"{a.mean():.2f}→{b.mean():.2f} · 대응표본 t={t_:+.2f} p={tp:.3f}"
               f"{' (유의하지 않음)' if tp >= .05 else ''}")
    R.num(S_VA, "전_V 와 후_V 의 상관", float(r_), "r", n=len(pair),
          note=f"p={p_:.3f} · 순위 유지 정도이지 변화량이 아니다")

    pair2 = [(num(r["전_V"]), num(r["주제1_V"])) for r in rows
             if num(r.get("전_V")) is not None and num(r.get("주제1_V")) is not None]
    x = np.array([q[0] for q in pair2]); y = np.array([q[1] for q in pair2])
    rr, pp = stats.pearsonr(x, y)
    print(f"  전_V ↔ 주제1_V  r = {rr:+.3f} (p = {pp:.3f}) — "
          f"주제 감정은 평소 기분의 반복이 아니다")
    R.num(S_VA, "전_V 와 주제1_V 의 상관", float(rr), "r", n=len(pair2),
          note=f"p={pp:.3f} · 낮을수록 주제 감정이 대화 직전 기분과 별개라는 뜻")

    # ── 저장 ─────────────────────────────────────────────────────────
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "survey_topics.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["구분", "보기", "응답자수", "비율%"])
        for k, v in tc.most_common():
            w.writerow(["평소_대화주제", k, v, round(v / N * 100, 1)])
        for k, v in tother.most_common():
            w.writerow(["평소_대화주제_기타", k, v, round(v / N * 100, 1)])
        for k, v in mc.most_common():
            w.writerow(["평소_감정상태", k, v, round(v / N * 100, 1)])
        for k, v in kinds.most_common():
            w.writerow(["이번_대화주제_분류", k, v, round(v / (N + n2) * 100, 1)])
    with open(OUT / "survey_va.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(hdr)
        w.writerows(varows)
    with open(OUT / "survey_participants.csv", "w", newline="", encoding="utf-8-sig") as fh:
        keys = ["p_id", "나이", "성별", "모델", "요금제", "사용빈도", "평소_대화주제",
                "평소_감정상태", "주제1", "주제1_V", "주제1_A", "주제2", "주제2_V",
                "주제2_A", "전_V", "전_A", "후_V", "후_A"]
        w = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    for f in ("survey_topics.csv", "survey_va.csv", "survey_participants.csv"):
        print(f"저장: {(OUT / f).relative_to(ROOT)}")
    R.save("1_설문")


if __name__ == "__main__":
    main()
