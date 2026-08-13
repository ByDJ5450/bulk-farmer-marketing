// 벌크농부 클래스 · 초기 시드 데이터
// 실제 데이터는 브라우저 localStorage에 저장되며, 이 파일은 첫 방문 시 한 번만 복사된다.
// 관리자 페이지(admin.html)에서 강의·영상 링크를 수정하면 localStorage에 반영된다.
'use strict';

window.SEED = {
  courses: [
    {
      id: 'starter',
      title: '마른 몸 탈출 스타터 · 벌크업 기초 4강',
      thumbTitle: '마른 몸 탈출\n스타터',
      tagline: '벌크업을 시작하기 전에 반드시 알아야 할 원리만 골라 담은 무료 입문 강의입니다.',
      badge: '무료 공개',
      color: 'green',
      level: '입문',
      weeks: '1주 완성',
      price: 0,
      outcomes: [
        '왜 지금까지 살이 안 쪘는지 원인을 스스로 진단할 수 있습니다',
        '칼로리 잉여를 숫자로 계산하는 법을 배웁니다',
        '마른 체형에게 맞는 첫 루틴 구성 원칙을 이해합니다',
        '55kg에서 88kg까지, 코치의 실제 과정을 그대로 봅니다'
      ],
      sections: [
        {
          id: 'st-s1',
          title: '오리엔테이션',
          lectures: [
            { id: 'st-l1', title: '벌크업이 안 되는 진짜 이유', duration: '7:42', videoUrl: '' },
            { id: 'st-l2', title: '55kg에서 88kg이 되기까지', duration: '9:18', videoUrl: '' }
          ]
        },
        {
          id: 'st-s2',
          title: '벌크업 기초 원리',
          lectures: [
            { id: 'st-l3', title: '칼로리 잉여, 숫자로 계산하는 법', duration: '11:05', videoUrl: '' },
            { id: 'st-l4', title: '마른 체형이 처음 잡아야 할 3분할 루틴', duration: '12:40', videoUrl: '' }
          ]
        }
      ]
    },
    {
      id: 'master',
      title: '벌크업 마스터 클래스 · 12주 완성',
      thumbTitle: '벌크업\n마스터 클래스',
      tagline: '진단부터 훈련 설계, 식단, 기록까지. 트레이너 없이 스스로 벌크업을 설계하는 능력을 만듭니다.',
      badge: 'BEST',
      color: 'dark',
      level: '입문~중급',
      weeks: '12주 과정',
      price: 199000,
      outcomes: [
        '인바디를 읽고 내 몸 상태를 스스로 진단할 수 있습니다',
        '점진적 과부하 원칙으로 무게 올리는 규칙을 세웁니다',
        '하루 3,500kcal 식단을 직접 설계합니다',
        '기록 습관으로 정체기를 스스로 돌파합니다',
        '코치 없이도 다음 12주 계획을 직접 짤 수 있게 됩니다'
      ],
      sections: [
        {
          id: 'ms-s1',
          title: '1단계 · 몸 진단',
          lectures: [
            { id: 'ms-l1', title: '인바디 읽는 법 · 골격근량이 전부다', duration: '10:22', videoUrl: '' },
            { id: 'ms-l2', title: '내 유지 칼로리 찾기 실습', duration: '13:07', videoUrl: '' }
          ]
        },
        {
          id: 'ms-s2',
          title: '2단계 · 훈련 설계',
          lectures: [
            { id: 'ms-l3', title: '점진적 과부하 · 무게 올리는 규칙', duration: '14:51', videoUrl: '' },
            { id: 'ms-l4', title: '가슴·등·하체, 대근육 우선 배치', duration: '12:33', videoUrl: '' },
            { id: 'ms-l5', title: '한계 지점까지 가야 하는 이유', duration: '9:46', videoUrl: '' }
          ]
        },
        {
          id: 'ms-s3',
          title: '3단계 · 식단 설계',
          lectures: [
            { id: 'ms-l6', title: '하루 3,500kcal 식단 짜는 법', duration: '15:12', videoUrl: '' },
            { id: 'ms-l7', title: '단백질은 하루 총량으로 관리한다', duration: '8:58', videoUrl: '' },
            { id: 'ms-l8', title: '외식·편의점 대응 전략', duration: '10:04', videoUrl: '' }
          ]
        },
        {
          id: 'ms-s4',
          title: '4단계 · 기록과 유지',
          lectures: [
            { id: 'ms-l9', title: '기록이 벌크업의 절반인 이유', duration: '11:40', videoUrl: '' },
            { id: 'ms-l10', title: '정체기 돌파 체크리스트', duration: '13:25', videoUrl: '' }
          ]
        }
      ]
    },
    {
      id: 'diet',
      title: '벌크업 식단 설계 · 많이 먹는 기술',
      thumbTitle: '벌크업\n식단 설계',
      tagline: '"입이 짧아서 못 먹어요"를 해결합니다. 칼로리 잉여를 유지하는 현실적인 식사 전략.',
      badge: 'NEW',
      color: 'pink',
      level: '입문',
      weeks: '4주 과정',
      price: 99000,
      outcomes: [
        '운동(자극)과 식단(재료), 둘 다 잡는 기본 구조를 이해합니다',
        '한 끼 700kcal 밥상 공식을 그대로 따라 만들 수 있습니다',
        '간식으로 하루 500kcal를 더 채우는 법을 배웁니다',
        '일주일 장보기 리스트로 식단 준비 시간을 줄입니다'
      ],
      sections: [
        {
          id: 'dt-s1',
          title: '원리 편',
          lectures: [
            { id: 'dt-l1', title: '벌크업 식단의 3원칙 · 잉여·단백질·꾸준함', duration: '9:33', videoUrl: '' },
            { id: 'dt-l2', title: '살 안 찌는 체질? 먹는 양을 기록해보면', duration: '8:17', videoUrl: '' }
          ]
        },
        {
          id: 'dt-s2',
          title: '실전 편',
          lectures: [
            { id: 'dt-l3', title: '한 끼 700kcal 밥상 공식', duration: '12:05', videoUrl: '' },
            { id: 'dt-l4', title: '간식으로 500kcal 더 먹는 법', duration: '7:54', videoUrl: '' },
            { id: 'dt-l5', title: '일주일 장보기 리스트 공개', duration: '10:41', videoUrl: '' }
          ]
        }
      ]
    }
  ],

  // 회원별 수강 목록 { 이메일: [courseId, ...] } · 가입·수강신청 시 채워진다
  enrollments: {},

  // 회원별 진도 { 이메일: { courseId: [lectureId, ...] } }
  progress: {},

  // 강의실 댓글 { 'courseId/lectureId': [{ id, name, text, ts }] }
  comments: {
    'starter/st-l1': [
      {
        id: 'seed-c1',
        name: '벌크업3주차',
        text: '이 강의 보고 제가 왜 안 쪘는지 알았습니다. 먹는 양을 기록해보니 생각보다 훨씬 적게 먹고 있었네요.',
        ts: Date.now() - 1000 * 60 * 60 * 26
      },
      {
        id: 'seed-c2',
        name: '동진 코치',
        coach: true,
        text: '맞습니다. 대부분 "많이 먹는다"는 느낌과 실제 섭취량이 다릅니다. 3일만 기록해보면 바로 보입니다. 다음 강의에서 계산법 알려드립니다.',
        ts: Date.now() - 1000 * 60 * 60 * 22
      }
    ]
  },

  // 커뮤니티 게시글
  posts: [
    {
      id: 'seed-p1',
      cat: 'notice',
      title: '벌크농부 클래스 오픈 안내',
      body: '벌크농부 온라인 클래스를 시작합니다.\n\n- 무료 강의: 마른 몸 탈출 스타터 4강 (지금 바로 수강 가능)\n- 질문은 각 강의 아래 댓글, 또는 커뮤니티 질문 게시판에 남겨주세요. 전부 답합니다.\n- 1:1 코칭 문의는 인스타그램 @bulk_farmer DM으로 주세요.\n\n55kg에서 88kg까지 온 과정을 그대로 나누겠습니다.',
      name: '동진 코치',
      coach: true,
      ts: Date.now() - 1000 * 60 * 60 * 72,
      comments: []
    },
    {
      id: 'seed-p2',
      cat: 'qna',
      title: '완전 처음인데 어떤 강의부터 들어야 하나요?',
      body: '헬스장 등록만 세 번째입니다. 매번 한 달을 못 넘기고 그만뒀는데, 이번엔 제대로 해보고 싶습니다. 어떤 순서로 들으면 될까요?',
      name: '멸치탈출희망',
      ts: Date.now() - 1000 * 60 * 60 * 30,
      comments: [
        {
          id: 'seed-pc1',
          name: '동진 코치',
          coach: true,
          text: '무료 스타터 4강부터 들어주세요. 특히 1강에서 "왜 지금까지 안 됐는지"를 먼저 잡아야 같은 실패를 반복하지 않습니다. 스타터 끝나면 마스터 클래스 1단계(몸 진단)로 넘어오시면 됩니다.',
          ts: Date.now() - 1000 * 60 * 60 * 28
        }
      ]
    },
    {
      id: 'seed-p3',
      cat: 'free',
      title: '한 달 만에 2.5kg 늘었습니다',
      body: '스타터 강의 듣고 식사 기록부터 시작했습니다.\n하루 세 끼 + 간식 두 번, 한 달 유지하니 61.0 → 63.5kg.\n숫자가 움직이니까 헬스장 가는 게 재밌어졌습니다.',
      name: '벌크업3주차',
      ts: Date.now() - 1000 * 60 * 60 * 8,
      comments: [
        {
          id: 'seed-pc2',
          name: '동진 코치',
          coach: true,
          text: '한 달에 2.5kg이면 아주 좋은 속도입니다. 이 페이스 그대로 가되, 다음 달부터는 중량 기록도 같이 남겨보세요.',
          ts: Date.now() - 1000 * 60 * 60 * 5
        }
      ]
    }
  ]
};
