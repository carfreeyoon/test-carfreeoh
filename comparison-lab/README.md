# 카프리오 견적 비교 작업실

Vercel 시험용 화면과 `/api/compare` API. 현재 배포 주소: https://carfreeoh-compare-lab.vercel.app/

금융사 견적서에 적힌 월 납입금, 초기 비용, 반환 보증금, 만기 인수금을 직접 입력해 같은 기간의 견적을 비교한다. 반환 합계는 초기 비용 + 월 납입금 × 개월 수, 인수 합계는 반환 합계 + 만기 인수금이다. 반환 보증금은 합계에 넣지 않는다.

현재 계산기는 실제 금융사 견적을 자동 조회하거나 기존 `rent-calculator`의 금융 계산식을 실행하지 않는다. 견적서 판독과 수집 차량·옵션 데이터 연결은 다음 단계다. 운영 `rent-calculator` 저장소는 수정하지 않았다.

GitHub `carfreeyoon/test-carfreeoh`에 `comparison-lab/`으로 올린 뒤 Vercel의 Root Directory를 `comparison-lab`으로 설정하면, 기존 Streamlit 파일과 분리해 이 화면을 Git으로 관리할 수 있다. Vercel 프로젝트 `carfreeoh-compare-lab`은 현재 직접 배포 방식이다.
