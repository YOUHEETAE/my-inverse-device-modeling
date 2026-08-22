package com.semiscopeai.service.user;

import com.semiscopeai.service.internal.BaseEntity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;
import lombok.AccessLevel;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Entity
@Table(name = "users", uniqueConstraints = @UniqueConstraint(name = "users_provider_uk", columnNames = { "provider",
        "provider_id" }))
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class User extends BaseEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    // 어느 소셜 서비스로 로그인했는지 ("google" / "kakao" / "naver").
    @Column(nullable = false, length = 20)
    private String provider;

    // 제공자 쪽 고유 ID. 이메일과 달리 바뀌지 않아서 이 값으로 사용자를 찾는다.
    @Column(name = "provider_id", nullable = false)
    private String providerId;

    // 카카오는 사용자가 동의하지 않으면 이메일을 주지 않으므로 null일 수 있다.
    @Column
    private String email;

    @Column(nullable = false)
    private String name;

    @Builder
    public User(String provider, String providerId, String email, String name) {
        this.provider = provider;
        this.providerId = providerId;
        this.email = email;
        this.name = name;
    }

}
