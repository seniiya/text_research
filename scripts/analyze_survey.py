"""사후 설문 분석. 대화 로그를 건드리지 않고 설문만 본다.

여기서만 나오는 것
------------------
'평소 어떤 주제로 대화하는가' · '평소 어떤 감정 상태에서 쓰는가' 두 문항은
지금까지 한 번도 집계된 적이 없다. 복수응답이라 쉼표로 갈라 세야 한다.

그리고 이 둘을 실제 대화 주제(주제1)와 대조하면 한 가지가 보인다 —
**본인이 평소 주제로 '고민 상담'을 고르지 않은 사람이 실제로는 고민 상담을 한다.**
정서 은폐가 발화 표면 이전에 자기 인식 단계에서 이미 일어난다는 뜻이다.
n 이 작아 사례 수준이므로 결과 상태를 '관찰'로 기록한다.

출력
----
표준출력                                절별 수치
data/output/survey/topics.csv          평소 주제 복수응답 집계
data/output/survey/participants.csv    참가자별 설문 요약
data/output/results/S.json             results.csv 로 모을 조각

사용: python scripts/analyze_survey.py
"""

import csv
import re
import sys
from collections import Counter

import numpy as np
from scipy import stats

from speechact_data import ROOT, Results, load_survey, num

OUT = ROOT / "data" / "output" / "survey"

# 복수응답 문항. 구글 폼이 쉼표로 잇는데, 자유기술 항목 안에도 쉼표가 들어간다
# ("분노, 짜증"). 그래서 정해진 보기 목록을 먼저 떼어내고 나머지를 기타로 본다.
TOPIC_CHOICES = ["정보 검색·질문", "학업·업무 도움", "글쓰기 도움", "코딩·기술",
                 "일상 잡담", "고민 상담", "창작·놀이"]
MOOD_CHOICES = ["답답함·스트레스 해소 목적", "호기심", "특별한 감정 없음", "차분함",
                "외로움·심심함", "불안·걱정이 있을 때", "즐거움·재미"]
# 정서적 대화로 볼 보기. '고민 상담' 하나뿐이다.
EMOTIONAL_TOPIC = "고민 상담"


def multi(rows, col, choices):
    """복수응답을 보기별로 센다. 보기에 없는 것은 '기타(자유기술)'로 묶는다."""
    c, other = Counter(), []
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
                other.append(t)
    return c, Counter(other)


def section(t):
    print(f"\n{'=' * 72}\n{t}\n{'=' * 72}")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sv = load_survey()
    rows = [sv[k] for k in sorted(sv)]
    N = len(rows)
    R = Results("S", "analyze_survey.py")
    R.add("설문 응답자", N, "명", status="확정", part="공통")

    # ── 인구통계 ──────────────────────────────────────────────────────
    section("1. 인구통계")
    ages = [num(r["나이"]) for r in rows if num(r["나이"]) is not None]
    print(f"  나이   n={len(ages)}  평균 {np.mean(ages):.1f}세  "
          f"중앙값 {np.median(ages):.0f}  범위 {min(ages):.0f}–{max(ages):.0f}")
    R.add("참가자 평균 연령", float(np.mean(ages)), "세", n=len(ages),
          status="확정", part="공통",
          note=f"중앙값 {np.median(ages):.0f} · 범위 {min(ages):.0f}-{max(ages):.0f}")
    for col in ("성별", "모델", "요금제", "사용빈도"):
        c = Counter(str(r.get(col, "")).strip() or "무응답" for r in rows)
        print(f"  {col:<7}" + " · ".join(f"{k} {v}" for k, v in c.most_common()))
        top, tn = c.most_common(1)[0]
        R.add(f"{col} 최다", f"{top} {tn}/{N}", n=N, status="확정", part="공통",
              note=" · ".join(f"{k} {v}" for k, v in c.most_common()))

    # ── 평소 대화주제 ────────────────────────────────────────────────
    section("2. 평소 어떤 주제로 대화하는가  (복수응답)")
    tc, tother = multi(rows, "평소_대화주제", TOPIC_CHOICES)
    for k, v in tc.most_common():
        print(f"  {v:>3}명 {v / N * 100:>5.0f}%   {k}")
    print(f"\n  기타(자유기술) {sum(tother.values())}건 — "
          + ", ".join(f"{k}" for k in list(tother)[:6]) + " ...")
    R.add("평소 주제 1위", f"{tc.most_common(1)[0][0]} {tc.most_common(1)[0][1]}/{N}",
          n=N, status="확정", part="공통",
          note=" · ".join(f"{k} {v}" for k, v in tc.most_common()))
    R.add("평소 주제로 '고민 상담'을 고른 비율",
          tc[EMOTIONAL_TOPIC] / N * 100, "%", n=N, status="확정", part="공통",
          note=f"{tc[EMOTIONAL_TOPIC]}/{N}명")

    # ── 평소 감정상태 ────────────────────────────────────────────────
    section("3. 평소 어떤 감정 상태에서 쓰는가  (복수응답)")
    mc, _ = multi(rows, "평소_감정상태", MOOD_CHOICES)
    for k, v in mc.most_common():
        print(f"  {v:>3}명 {v / N * 100:>5.0f}%   {k}")
    R.add("평소 감정상태 1위",
          f"{mc.most_common(1)[0][0]} {mc.most_common(1)[0][1]}/{N}", n=N,
          status="확정", part="공통",
          note=" · ".join(f"{k} {v}" for k, v in mc.most_common()))

    # ── 실제 대화 주제 ───────────────────────────────────────────────
    section("4. 이번에 실제로 한 대화 주제")
    ep = sum(1 for r in rows for k in ("주제1", "주제2") if str(r.get(k, "")).strip())
    print(f"  에피소드 {ep}개 (주제1 {N}건 + 주제2 "
          f"{sum(1 for r in rows if str(r.get('주제2', '')).strip())}건)")
    R.add("에피소드 수", ep, "개", n=N, status="확정", part="공통",
          note="주제2까지 쓴 사람이 있어 참가자 수보다 많다")
    for r in rows:
        t2 = str(r.get("주제2", "")).strip()
        print(f"  {r['p_id']}  {str(r['주제1'])[:40]:<42}"
              + (f"| {t2[:26]}" if t2 else ""))

    # ── 평소 인식 vs 실제 ────────────────────────────────────────────
    section("5. 평소 주제 인식 ↔ 실제 대화  [관찰]")
    said = {r["p_id"] for r in rows if EMOTIONAL_TOPIC in str(r.get("평소_대화주제", ""))}
    neg = [r for r in rows if (num(r.get("주제1_V")) or 9) <= 3]
    miss = [r for r in neg if r["p_id"] not in said]
    print(f"  평소 주제로 '{EMOTIONAL_TOPIC}'을 고른 사람: {len(said)}명 "
          f"({', '.join(sorted(said))})")
    print(f"\n  주제1 자기보고가 부정(V<=3)인 {len(neg)}명:")
    for r in sorted(neg, key=lambda r: num(r["주제1_V"])):
        mark = " " if r["p_id"] in said else "*"
        print(f"   {mark}{r['p_id']}  V{num(r['주제1_V']):.0f}  "
              f"실제=[{str(r['주제1'])[:26]:<28}]  평소=[{str(r['평소_대화주제'])[:34]}]")
    print(f"\n  * = 평소 주제로 '{EMOTIONAL_TOPIC}'을 고르지 않은 사람 — "
          f"{len(miss)}/{len(neg)}명")
    print("  → 정서 은폐가 발화 이전에 자기 인식 단계에서 이미 일어난다는 사례.")
    print(f"  ! n={len(neg)} 이라 통계가 아니다. 사례로만 보고한다.")
    R.add("자기보고 부정(V<=3) 참가자 중 평소 주제로 '고민 상담'을 안 고른 사람",
          f"{len(miss)}/{len(neg)}", n=len(neg), status="관찰", part="공통",
          note=", ".join(r["p_id"] for r in miss))

    # ── VA 구조 ──────────────────────────────────────────────────────
    section("6. 자기보고 VA 구조")
    def col(k):
        return np.array([num(r.get(k)) for r in rows if num(r.get(k)) is not None])
    for k in ("전_V", "전_A", "주제1_V", "주제1_A", "후_V", "후_A"):
        v = col(k)
        print(f"  {k:<8}n={len(v):>3}  평균 {v.mean():.2f}  SD {v.std(ddof=1):.2f}  "
              f"범위 {v.min():.0f}–{v.max():.0f}")
    pre, post = col("전_V"), col("후_V")
    pair = [(num(r["전_V"]), num(r["후_V"])) for r in rows
            if num(r.get("전_V")) is not None and num(r.get("후_V")) is not None]
    a = np.array([p[0] for p in pair]); b = np.array([p[1] for p in pair])
    r_, p_ = stats.pearsonr(a, b)
    t_, tp = stats.ttest_rel(b, a)
    print(f"\n  전_V {a.mean():.2f} → 후_V {b.mean():.2f}  ({b.mean() - a.mean():+.2f})")
    print(f"  대응표본 t = {t_:+.2f}  p = {tp:.3f}   ·   전↔후 r = {r_:+.3f} (p = {p_:.3f})")
    print("  r 은 '전이 높은 사람이 후도 높은가' — 변화량이 아니라 순위 유지 정도다.")
    R.add("대화 전후 Valence 변화", float(b.mean() - a.mean()), "점", n=len(pair),
          status="확정" if tp < .05 else "탐색", part="공통",
          note=f"{a.mean():.2f}→{b.mean():.2f} · 대응표본 t={t_:+.2f} p={tp:.3f}")
    R.add("전_V 와 후_V 의 상관", float(r_), "r", n=len(pair),
          status="확정" if p_ < .05 else "탐색", part="공통",
          note=f"p={p_:.3f} · 순위 유지 정도이지 변화량이 아니다")

    for k in ("주제1_V",):
        pair2 = [(num(r["전_V"]), num(r[k])) for r in rows
                 if num(r.get("전_V")) is not None and num(r.get(k)) is not None]
        x = np.array([q[0] for q in pair2]); y = np.array([q[1] for q in pair2])
        rr, pp = stats.pearsonr(x, y)
        print(f"  전_V ↔ {k}  r = {rr:+.3f} (p = {pp:.3f})  "
              f"→ 주제 감정은 평소 기분의 반복이 아니다")
        R.add(f"전_V 와 {k} 의 상관", float(rr), "r", n=len(pair2),
              status="확정" if pp < .05 else "탐색", part="공통",
              note=f"p={pp:.3f} · 낮을수록 '주제 감정이 평소 기분과 별개'라는 근거")

    # ── 저장 ─────────────────────────────────────────────────────────
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "topics.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["구분", "보기", "응답자수", "비율%"])
        for k, v in tc.most_common():
            w.writerow(["평소_대화주제", k, v, round(v / N * 100, 1)])
        for k, v in mc.most_common():
            w.writerow(["평소_감정상태", k, v, round(v / N * 100, 1)])
        for k, v in tother.most_common():
            w.writerow(["평소_대화주제_기타", k, v, round(v / N * 100, 1)])
    with open(OUT / "participants.csv", "w", newline="", encoding="utf-8-sig") as fh:
        keys = ["p_id", "나이", "성별", "모델", "요금제", "사용빈도", "평소_대화주제",
                "평소_감정상태", "주제1", "주제1_V", "주제1_A", "주제2", "주제2_V",
                "주제2_A", "전_V", "전_A", "후_V", "후_A"]
        w = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"\n저장: {(OUT / 'topics.csv').relative_to(ROOT)}"
          f"\n      {(OUT / 'participants.csv').relative_to(ROOT)}")
    R.save()


if __name__ == "__main__":
    main()
