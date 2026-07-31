"""자기보고 VA 세 값(전 / 주제1 / 후)이 서로 무엇인지 확인한다.

설문은 세 번 물었지만 세 번 다 같은 것을 물은 게 아니다.

    전    "지금 이 순간(대화 시작 직전)의 감정 상태"   -> 응답 시점의 순간 상태
    후    "지금 이 순간(대화 종료 직후)의 감정 상태"   -> 응답 시점의 순간 상태
    주제1 "그 주제를 이야기할 때의 감정은 어땠나요?"    -> 특정 구간에 대한 회상

전/후를 잇는 것은 시간 축이지만 주제1은 그 축 위에 없다. 그래서 셋을 궤적으로
읽기 전에, 주제1 이 실제로 전·후와 같은 것을 재고 있는지부터 확인해야 한다.

네 가지를 본다.
  1. 세 값이 서로 얼마나 겹치는가            -> 상관
  2. 주제1 은 전과 후 중 어디에 가까운가      -> 상관 비교 + 개인 내 거리
  3. 턴 수가 적으면 셋이 붙는가              -> 턴 수와 거리의 상관
  4. Arousal 도 같은 구조인가                -> 1~3 반복

사용: python scripts/va_structure.py
"""

import csv
import sys
from pathlib import Path

from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
SURVEY = ROOT / "data" / "deid" / "survey_analysis.csv"

# n=20 에서 양측 α=.05 로 유의해지는 대략의 경계. 해석할 때 눈금으로만 쓴다.
R_CRIT_20 = 0.444


def load():
    with open(SURVEY, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def num(x):
    x = (x or "").strip()
    return int(x) if x.isdigit() else None


def series(rows, axis):
    """전·주제1·후 세 값이 모두 있는 사람만 모은다. 셋을 비교해야 하므로
    하나라도 비면 그 사람은 뺀다 (Arousal 은 P12~P14 가 여기서 빠진다)."""
    out = []
    for r in rows:
        a, m, b = num(r[f"전_{axis}"]), num(r[f"주제1_{axis}"]), num(r[f"후_{axis}"])
        t = num(r["총_턴수"])
        if None not in (a, m, b):
            out.append((r["p_id"], a, m, b, t))
    return out


def corr(x, y):
    pr, pp = stats.pearsonr(x, y)
    sr, sp = stats.spearmanr(x, y)
    return pr, pp, sr, sp


def line(label, x, y):
    pr, pp, sr, sp = corr(x, y)
    mark = "*" if pp < 0.05 else " "
    return f"  {label:<22} r={pr:+.3f} (p={pp:.3f}){mark}   rho={sr:+.3f} (p={sp:.3f})"


def analyse(rows, axis):
    d = series(rows, axis)
    pre = [x[1] for x in d]
    mid = [x[2] for x in d]
    post = [x[3] for x in d]
    n = len(d)

    print(f"\n{'=' * 74}")
    print(f"{axis}  (전 / 주제1 / 후 모두 있는 사람 n={n})")
    print("=" * 74)

    print(f"\n[1] 기술통계")
    for name, v in (("전", pre), ("주제1", mid), ("후", post)):
        print(f"  {name:<5} 평균 {sum(v)/n:.2f}  SD {stats.tstd(v):.2f} "
              f" 범위 {min(v)}~{max(v)}")

    print(f"\n[2] 세 값이 서로 얼마나 겹치는가  (n={n}, |r|>{R_CRIT_20:.2f} 면 유의)")
    print(line("전  vs 후", pre, post))
    print(line("주제1 vs 전", mid, pre))
    print(line("주제1 vs 후", mid, post))

    print(f"\n[3] 주제1 은 전과 후 중 어디에 가까운가")
    t_pre = stats.ttest_rel(mid, pre)
    t_post = stats.ttest_rel(mid, post)
    print(f"  평균 차이   주제1-전  {sum(mid)/n - sum(pre)/n:+.2f}"
          f"  t={t_pre.statistic:+.2f} p={t_pre.pvalue:.3f}")
    print(f"              주제1-후  {sum(mid)/n - sum(post)/n:+.2f}"
          f"  t={t_post.statistic:+.2f} p={t_post.pvalue:.3f}")

    # 개인 안에서 어느 쪽에 더 붙어 있는지. 평균 차이는 방향이 상쇄되지만
    # 절대 거리는 상쇄되지 않는다.
    dpre = [abs(m - a) for _, a, m, _, _ in d]
    dpost = [abs(m - b) for _, _, m, b, _ in d]
    t_dist = stats.ttest_rel(dpre, dpost)
    print(f"  절대 거리   |주제1-전| 평균 {sum(dpre)/n:.2f}"
          f"   |주제1-후| 평균 {sum(dpost)/n:.2f}"
          f"   t={t_dist.statistic:+.2f} p={t_dist.pvalue:.3f}")
    closer_pre = sum(1 for a, b in zip(dpre, dpost) if a < b)
    closer_post = sum(1 for a, b in zip(dpre, dpost) if a > b)
    print(f"  개인별      전에 더 가까움 {closer_pre}명 /"
          f" 후에 더 가까움 {closer_post}명 / 같음 {n - closer_pre - closer_post}명")

    print(f"\n[4] 턴 수가 적으면 세 값이 붙는가")
    turns = [x[4] for x in d if x[4] is not None]
    if len(turns) == n:
        spread = [max(a, m, b) - min(a, m, b) for _, a, m, b, _ in d]
        pr, pp, sr, sp = corr(turns, spread)
        print(f"  턴 수 범위 {min(turns)}~{max(turns)}, 평균 {sum(turns)/n:.1f}")
        print(line("턴 수 vs 세 값의 폭", turns, spread))
        print(f"  -> 양(+)이면 '턴이 많을수록 벌어진다'(가설 지지),"
              f" 0 근처면 무관")
    else:
        print("  총_턴수 결측이 있어 생략")

    print(f"\n[5] 개인별 값")
    print(f"  {'pid':<5}{'전':>4}{'주제1':>6}{'후':>4}{'폭':>4}{'턴':>4}   가까운 쪽")
    for pid, a, m, b, t in d:
        near = "전" if abs(m - a) < abs(m - b) else ("후" if abs(m - a) > abs(m - b) else "=")
        print(f"  {pid:<5}{a:>4}{m:>6}{b:>4}{max(a,m,b)-min(a,m,b):>4}"
              f"{(t if t is not None else '-'):>4}   {near}")


def main():
    rows = load()
    print(f"자기보고 VA 구조 분석 — {SURVEY.relative_to(ROOT).as_posix()} ({len(rows)}명)")
    for axis in ("V", "A"):
        analyse(rows, axis)
    print()
    print("* 는 p<.05. n=20 이라 유의성보다 효과 크기와 방향을 본다.")


if __name__ == "__main__":
    main()
