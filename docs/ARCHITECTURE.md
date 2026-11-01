# 통합 워게임 환경 구조

## 배포 단위

제출용 OVA는 OVF, streamOptimized VMDK, SHA-1 매니페스트로 구성됩니다. OVF에서 1 vCPU, RAM 2048MB, 가상 디스크 10GiB, 브리지 네트워크를 확인했습니다. 게스트의 `/usr/lib/os-release`는 Ubuntu 24.04.4 LTS입니다.

OVA가 하나의 VM을 제공한다는 사실과, 각 문제의 권한이 완전히 격리되었다는 주장은 구분해야 합니다. 이 환경은 OS 계정과 디렉터리 권한을 이용한 경계를 포함하지만 문제별 컨테이너나 별도 VM으로 구성된 것은 아닙니다.

## 요청 경로

| 공개 경로 | 백엔드 | 근거 |
| --- | --- | --- |
| `/ch1`, `/ch2` | Flask의 담당 문제 페이지 | Apache ProxyPass와 Flask 라우트 |
| `/api/ch1`, `/api/ch2` | `127.0.0.1:8080` | Apache ProxyPass와 `app.run()` |
| `/hidden-archive/` | `127.0.0.1:8081/` | Apache ProxyPass |
| `/internal-system/`, `/wargame/` | DocumentRoot 아래 PHP 문제 | 워크스루 및 디렉터리 구성 |
| `/progress/` | PHP 완료 검증과 SQLite 진행도 | 담당 앱과 완료 API 소스 |

원본 설정은 [Apache VirtualHost](../reference/apache/000-default.conf)에서 확인할 수 있습니다. 외부 HTTP 요청을 프록시와 PHP 경로로 분기하는 구조이며, 별도의 컨테이너 게이트웨이를 사용했다는 근거는 없습니다.

## 팀 전체 문제 지도

| 문제 | 학습 주제 | 본인 기여 구분 |
| --- | --- | --- |
| 1 | JSON 로그인 / Boolean-based Blind SQL Injection | 본인 담당 |
| 2 | 웹훅 / OS Command Injection / 외부 관측 | 본인 담당 |
| 3-1 | 프로필 ID 변경 / IDOR | 팀 문제 |
| 3-2 | 로그 다운로드 / Path Traversal | 팀 문제 |
| 4 | 메시지 차이를 이용한 Blind SQL Injection | 팀 문제 |
| 5 | JWT 서명 키·백업 노출 / 권한 변경 | 팀 문제 |
| 6 | 방명록의 저장형 XSS / 문자열 필터 한계 | 팀 문제 |
| 7 | 신뢰 헤더와 짧은 키 탐색 | 팀 문제 |
| 8 | robots.txt / 백업 파일 노출 | 팀 문제 |
| 9 | 다운로드 경로 조작 / Path Traversal | 팀 문제 |

문제 번호 1~9 중 3번이 두 개의 목표를 갖습니다. 중앙 완료 API에 저장된 목표 수의 합도 10개입니다. 이 표의 취약점 설명은 워크스루에 근거한 팀 전체 개요이며, 팀 문제의 모든 소스를 감사한 결과는 아닙니다.

## 실행 계정과 데이터 경계

| 구성 | 계정 또는 저장소 | 의미 |
| --- | --- | --- |
| 담당 Flask 앱 | `wargame` | Challenge 1·2가 같은 프로세스·계정 사용 |
| Hidden Archive 앱 | `hiddenarchive` | 별도의 실행 계정 및 디렉터리 |
| Apache/PHP 계열 | `www-data`를 포함한 웹 실행 구성 | PHP 문제별 별도 풀은 확인하지 않음 |
| Challenge 1 | MariaDB의 `wargame_db` | 원본 앱에서 연결 구성 확인; DB 실효 권한은 미조회 |
| 진행도 | `/progress/data/progress.db` | 완료 API 소스에서 SQLite 사용 확인 |
| 완료 요청 서명 | `/etc/wargame-progress/secret.key` | 값은 공개·추출하지 않고 권한만 확인 |

## 완료 기록의 두 경로

Challenge 1은 관리자 행이 조회되면 `mark_progress()`를 호출합니다. 참가자 ID 형식을 확인하고, `participant_id|challenge_id|flag_id`에 HMAC-SHA256 서명을 붙여 로컬 `/progress/complete.php`에 전달합니다. 수신 API는 `hash_equals()`로 서명을 비교하고 준비된 SQL로 진행도를 기록합니다.

Challenge 2에는 별도 `ch2-complete.php`가 있으며 제출한 플래그를 `hash_equals()`로 비교합니다. 따라서 **일반 웹훅 요청의 성공**과 **문제 풀이 완료 증명**을 같은 것으로 취급하지 않습니다.

진행도 관련 구현은 통합 구조를 설명하기 위해 분석했습니다. 별도 확인 없이 해당 공통 기능 전체를 본인 단독 개발 성과로 귀속하지 않았습니다.
