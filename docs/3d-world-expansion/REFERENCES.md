# 시각 자료 조사와 적용

조사일: 2026-11-20 KST. 새 장면 구현 전에 웹·이미지 검색 및 운영사/장비사 자료 확인. 사진·도면은 배치와 조명 분석용이며 제품 번들에 복제하지 않습니다.

| 검색어 | 확인한 출처 | 분석과 적용 |
| --- | --- | --- |
| `global submarine cable map`, `Asia Pacific submarine cable network`, `해저 케이블 아시아 태평양 지도` | [TeleGeography 지도](https://www.submarinecablemap.com/), [2026 지도 설명](https://resources.telegeography.com/2026-submarine-cable-map?hs_amp=true) | 거점과 경로 색을 분리, 중심 허브에서 상태 추적. 실제 케이블 데이터/경로는 복사하지 않고 가상 연결로 표시 |
| `dark futuristic strategy world map UI`, `어두운 전략 게임 세계지도 UI` | 검색 결과의 전략 지도 UI·산업 관제 자료 비교 | 남색 바다·청록 거점·소수 경로·읽기 쉬운 2D 요청 카드. 타 게임 스크린샷/브랜드/아이콘 복제 없음 |
| `data center NOC control room`, `데이터센터 관제실 사진` | [NOC 사진](https://a.storyblok.com/f/302173/3812x2551/76152bf639/184140_unlimited_master_27444_l.jpg/m/900x0), [Switch 운영실 사진](https://cdn.baxtel.com/data-center/switch-supernap-thailand-bangkok-i/photos/Switch-Supernap-Thailand-Bangkok-I-Technicians-monitor-the-facility-environment.jpg) | 모니터 월·여러 운영석의 방향 정렬, 낮은 주변광·화면광, 정보 계층 분리. 기존 NOC 지오메트리와 청록/차콜 톤을 유지하고 필수 조작은 2D HUD에 둠 |
| `hyperscale data center campus isometric`, `데이터센터 단지 항공 사진` | [Google 공식 사진 갤러리](https://www.datacenters.google/discover-more/photo-gallery/)의 Kansas City / New Albany / Storey County 항공 사진 | 낮고 긴 서버동, 외부 설비 yard, 연결 도로·서비스 통로, 관제동과 서버동 구분. 단지는 직접 모델링하며 실제 울산 시설 도면으로 주장하지 않음 |
| `data center UPS electrical room`, `데이터센터 UPS 전기실` | [Vertiv Power Module 공식 브로슈어](https://www.vertiv.com/48ebd8/globalassets/products/facilities-enclosures-and-racks/integrated-solutions/vertiv-power-module-100012002/vertiv-brochure-power-module-1000-1200_emea_updated.pdf) | 캐비닛 반복·정비 통로·전력 설비 구역 구분. 전력동과 UPS 구역을 같은 설비 yard 내 별도 선택 대상으로 표시 |
| `data center cooling plant chillers`, `데이터센터 냉각 칠러 사진` | Google 갤러리의 Douglas County 배관·Kansas City 냉각탑·Storey County fan platform | 반복 팬/열교환 장치·굵은 공급/반환 배관을 가시화. 네트워크와 냉각을 서로 다른 색·구조로 표현 |
| `GPU server rack data center`, `GPU 서버 랙 사진` | [NVIDIA DGX SuperPOD](https://www.nvidia.com/en-us/data-center/dgx-superpod/), Google 서버 통로 사진 | 적층 모듈·케이블 트레이·좁은 서비스 통로. 기존 24랙 시제품 지오메트리·LED·텍스처를 재사용 |

## 권리와 데이터 출처

- 사진·기술 자료는 해당 소유자 권리로 유지되며 본문 링크만 기록. 제품 텍스처/배경/모델로 재배포하지 않습니다. 이미지 검색의 저작권 표시나 검색 가능성을 사용 허락으로 간주하지 않습니다.
- 세계 육지 윤곽만 [Natural Earth 1:110m land](https://github.com/nvkelso/natural-earth-vector/blob/master/geojson/ne_110m_land.geojson)를 사용. [공식 Terms of Use](https://www.naturalearthdata.com/about/terms-of-use/)에서 Public Domain 확인. 자체 투영·재질·경로·거점·UI로 변환하며 출처를 표시합니다. 국가 경계나 실시간 케이블 데이터가 아닙니다.
- 신규 건물·팬·배관·도로·라벨은 직접 만든 지오메트리·Canvas 텍스처. 공급사 로고/제품명·사진 자산은 포함하지 않습니다.
