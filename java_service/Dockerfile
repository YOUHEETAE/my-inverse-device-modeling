# 빌드 컨텍스트는 저장소 루트(docker-compose.yml 참고) — 다른 두 이미지와
# 동일하게 맞춤.
FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /build

# pom.xml만 먼저 복사해서 의존성을 받아두면, 소스만 바뀌었을 때 이 레이어가
# 캐시로 재사용돼서 재빌드가 빨라짐.
COPY java_service/pom.xml .
RUN mvn -q -B dependency:go-offline

COPY java_service/src src
# 테스트는 이미지 빌드가 아니라 `mvn test`로 따로 돌림 — 이미지 빌드에
# 묶으면 배포할 때마다 테스트 시간만큼 느려짐.
RUN mvn -q -B clean package -DskipTests

FROM eclipse-temurin:21-jre-alpine
WORKDIR /app
COPY --from=build /build/target/java-service-*.jar app.jar

# 인터넷에 노출되는 경로(Caddy -> 여기)의 첫 자바 프로세스라, 컨테이너가
# 뚫렸을 때의 피해를 줄이려고 root가 아닌 계정으로 실행함. 파일을 쓰거나
# 1024 미만 포트를 열 일이 없어서 권한이 더 필요하지 않음.
RUN addgroup -S app && adduser -S -G app app
USER app

EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]
