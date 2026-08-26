"""배포된 웹 서비스를 한 대의 PC에서 돌리는 로컬 실행판.

배포 구성은 Caddy → java_service → backend(FastAPI) → Postgres 네 겹인데,
여기서는 backend 하나만 남기고 자바가 하던 저장·인증 자리를 파일로 채운다
(standalone/shim.py). 화면은 배포판과 똑같은 web/dist를 그대로 서빙하므로
심사용 실행 파일과 실제 서비스가 같은 것을 보여준다.

빠지는 것: 로그인(구글 OAuth는 인터넷과 실제 client secret이 필요하다),
계정별 하루 한도와 초당 제한(여러 사람이 함께 쓰는 서버의 사정이다),
외부 LLM(키를 실행 파일에 넣을 수 없다 — 없으면 로컬 폴백으로 답한다).

빠지지 않는 것: I-V Curve와 Field Map 예측, 전기적 파라미터 추출, 조건
비교, 이론 시뮬레이터, Case Study 8종의 4단계 전부. 예측 모델은 번들에
들어가고, Case Study 채점은 원래 정답표 대조라 LLM 없이 돈다.
"""
