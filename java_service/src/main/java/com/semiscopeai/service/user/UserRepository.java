package com.semiscopeai.service.user;

import java.util.Optional;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface UserRepository extends JpaRepository<User, Long> {

    // 소셜 로그인 후 기존 사용자를 찾는 기준. 이메일로 찾지 않는 이유는
    // 이메일이 없을 수도(카카오) 있고, 같은 이메일로 여러 제공자에 가입하면
    // 여러 행이 나올 수도 있기 때문.
    Optional<User> findByProviderAndProviderId(String provider, String providerId);
}
