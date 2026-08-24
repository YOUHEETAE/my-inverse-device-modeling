package com.semiscopeai.service.internal;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

import io.github.bucket4j.Bucket;

import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

@Service
public class RateLimiterService {

    // 요청마다 스레드가 달라서 동시 접근함 — HashMap이면 같은 IP가 동시에
    // 처음 들어올 때 버킷이 두 개 만들어질 수 있음.
    //
    // 키가 IP 하나가 아니라 (IP, 그룹)인 이유: 무거운 호출을 다 써버렸다고
    // 화면 이동까지 막히면 안 되고, 반대로 화면을 여러 번 옮겼다고 분석
    // 호출이 막혀서도 안 됨. 두 몫을 따로 센다.
    private final Map<Key, Bucket> buckets = new ConcurrentHashMap<>();

    private record Key(String ip, RateLimitGroup group) {
    }

    public boolean isAllowed(String ip, RateLimitGroup group) {
        Bucket bucket = buckets.computeIfAbsent(
                new Key(ip, group),
                key -> Bucket.builder().addLimit(key.group().bandwidth()).build());
        return bucket.tryConsume(1);
    }

    // 가득 찬 버킷은 지워도 안전함 — 새로 만든 버킷도 어차피 가득 찬 상태라
    // 제한이 약해지지 않음. 덕분에 마지막 접근 시각을 따로 들고 있을 필요가
    // 없음. (package-private인 이유는 테스트에서 직접 호출하기 위해)
    @Scheduled(fixedDelay = 60000)
    void cleanupExpiredBucket() {
        buckets.entrySet().removeIf(
                entry -> entry.getValue().getAvailableTokens() >= entry.getKey().group().burstCapacity());
    }

    // 테스트에서 정리 결과를 확인하기 위한 접근자.
    int trackedBucketCount() {
        return buckets.size();
    }
}
