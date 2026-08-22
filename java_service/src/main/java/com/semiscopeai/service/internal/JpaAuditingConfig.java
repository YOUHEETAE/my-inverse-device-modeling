package com.semiscopeai.service.internal;

import org.springframework.context.annotation.Configuration;
import org.springframework.data.jpa.repository.config.EnableJpaAuditing;

// BaseEntity의 @CreatedDate/@LastModifiedDate는 이 설정이 있어야 값이 채워진다.
// 없으면 조용히 null로 남아서, NOT NULL인 created_at/updated_at에 INSERT할 때
// 저장 시점에야 실패한다.
@Configuration
@EnableJpaAuditing
public class JpaAuditingConfig {
}
