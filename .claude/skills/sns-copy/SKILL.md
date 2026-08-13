---
name: sns-copy
description: SNS 카피 작성 — 플랫폼(인스타/스레드/블로그)에 맞는 본문 4블록 구조·감정 단어·캐러셀 설계. 예) /sns-copy 단백질 섭취량 인스타
---

`_context/sns_copy_guide.md`를 읽고 그대로 적용한다.

인자에서 주제와 플랫폼을 파악한다. 플랫폼이 없으면 먼저 확인한다.

- 훅은 `_context/first_line_hooks.md`로 뽑는다
- 본문은 4블록(훅→맥락→핵심→CTA 질문), 블록마다 줄 비움
- 감정 단어는 블록당 1~2개, 신뢰·긴급 계열은 실제 근거·마감 있을 때만
- 카드뉴스(캐러셀)면 PART 3 설계 규칙 적용
- 완성 후 `_context/human_tone_guide.md`로 최종 점검
- 스레드면 `_threads/draft_prompt.txt`의 첫 줄·가독성(20자/15자)·신뢰 검증 규칙이 우선
