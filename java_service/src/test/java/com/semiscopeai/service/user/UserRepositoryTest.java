package com.semiscopeai.service.user;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.semiscopeai.service.internal.JpaAuditingConfig;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.data.jpa.test.autoconfigure.DataJpaTest;
import org.springframework.context.annotation.Import;
import org.springframework.test.context.ActiveProfiles;

// @DataJpaTest는 JPA 관련 빈만 띄우고 @Configuration은 제외하기 때문에,
// 감사(auditing) 설정을 명시적으로 가져와야 createdAt/updatedAt이 채워진다.
@DataJpaTest
@Import(JpaAuditingConfig.class)
@ActiveProfiles("test")
class UserRepositoryTest {

    @Autowired
    private UserRepository userRepository;

    // created_at/updated_at은 NOT NULL인데 값을 코드에서 직접 넣지 않는다.
    // @EnableJpaAuditing이 빠지면 조용히 null로 남아 저장할 때 터지므로,
    // 그 배선이 살아있는지 확인한다.
    @Test
    void 저장하면_생성_수정_시각이_자동으로_채워진다() {
        User saved = userRepository.save(User.builder()
                .provider("google")
                .providerId("10482930155")
                .email("a@example.com")
                .name("홍길동")
                .build());

        assertThat(saved.getCreatedAt()).isNotNull();
        assertThat(saved.getUpdatedAt()).isNotNull();
    }

    // 카카오는 사용자가 동의하지 않으면 이메일을 주지 않는다.
    @Test
    void 이메일_없이도_가입할_수_있다() {
        User saved = userRepository.save(User.builder()
                .provider("kakao")
                .providerId("3821094")
                .name("길동")
                .build());

        assertThat(saved.getId()).isNotNull();
        assertThat(saved.getEmail()).isNull();
    }

    // 같은 사람이 구글과 카카오로 각각 로그인하면 같은 이메일로 두 계정이
    // 생긴다. 이메일에 UNIQUE를 걸지 않은 이유가 이것이고, 걸었다면 두 번째
    // 로그인이 실패했을 것이다.
    @Test
    void 제공자가_다르면_같은_이메일로도_가입된다() {
        userRepository.save(User.builder()
                .provider("google").providerId("g-1").email("same@example.com").name("홍길동").build());
        userRepository.save(User.builder()
                .provider("kakao").providerId("k-1").email("same@example.com").name("홍길동").build());

        assertThat(userRepository.count()).isEqualTo(2);
    }

    @Test
    void 같은_제공자의_같은_ID로는_중복_가입되지_않는다() {
        userRepository.save(User.builder()
                .provider("google").providerId("dup").email("a@example.com").name("홍길동").build());

        assertThatThrownBy(() -> userRepository.saveAndFlush(User.builder()
                .provider("google").providerId("dup").email("b@example.com").name("다른사람").build()))
                .isInstanceOf(Exception.class);
    }

    @Test
    void 제공자와_ID로_기존_사용자를_찾는다() {
        userRepository.save(User.builder()
                .provider("naver").providerId("n-77").email("c@example.com").name("홍길동").build());

        assertThat(userRepository.findByProviderAndProviderId("naver", "n-77")).isPresent();
        assertThat(userRepository.findByProviderAndProviderId("naver", "없는ID")).isEmpty();
    }
}
