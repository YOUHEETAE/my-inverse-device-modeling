package com.semiscopeai.service.support;

import com.semiscopeai.service.casestudy.LearningRepository;
import com.semiscopeai.service.chat.ChatRepository;
import com.semiscopeai.service.internal.DailyQuotaRepository;
import com.semiscopeai.service.internal.JpaAuditingConfig;
import org.springframework.boot.SpringBootConfiguration;
import org.springframework.boot.autoconfigure.EnableAutoConfiguration;
import org.springframework.boot.persistence.autoconfigure.EntityScan;
import org.springframework.context.annotation.Import;
import org.springframework.data.jpa.repository.config.EnableJpaRepositories;

// 저장 계층 테스트용 최소 애플리케이션. 전체 앱 대신 저장소만 띄운다 —
// 웹 계층이나 OAuth 설정은 이 테스트와 무관하고, 올리면 구글 자격증명이
// 필요해진다.
//
// 테스트 패키지가 아니라 여기 따로 두는 이유: @SpringBootConfiguration은
// 같은 패키지의 다른 슬라이스 테스트(@WebMvcTest)가 앱 클래스로 오인해서
// 집어간다.
@SpringBootConfiguration
@EnableAutoConfiguration
@Import({
    ChatRepository.class,
    LearningRepository.class,
    DailyQuotaRepository.class,
    JpaAuditingConfig.class
})
@EntityScan("com.semiscopeai.service.user")
@EnableJpaRepositories("com.semiscopeai.service.user")
public class PersistenceTestApp {
}
