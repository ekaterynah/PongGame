import math
import random
from dataclasses import dataclass

import pygame


@dataclass(frozen=True)
class Config:
    width: int = 900
    height: int = 540
    fps: int = 60

    bg_color: tuple = (14, 16, 20)
    fg_color: tuple = (230, 235, 245)
    accent: tuple = (120, 200, 255)
    warning: tuple = (255, 180, 100)

    paddle_w: int = 14
    paddle_h: int = 110
    paddle_speed: float = 420.0  # px/sec

    ball_radius: int = 10
    ball_speed: float = 360.0    # px/sec (стартова)
    ball_speed_max: float = 860.0

    score_to_win: int = 7

    # Пауерап "boost"
    powerup_radius: int = 12
    powerup_spawn_every_sec: float = 7.0
    boost_duration_sec: float = 1.2
    boost_multiplier: float = 1.35

    # AI
    ai_reaction: float = 0.10      # менше = швидше реагує
    ai_max_speed_factor: float = 0.92  # AI трохи слабший за гравця


class GameState:
    MENU = "menu"
    PLAYING = "playing"
    PAUSED = "paused"
    GAMEOVER = "gameover"


@dataclass
class Paddle:
    x: float
    y: float
    w: int
    h: int
    speed: float

    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x), int(self.y), self.w, self.h)

    def center_y(self) -> float:
        return self.y + self.h / 2


@dataclass
class Ball:
    x: float
    y: float
    r: int
    vx: float
    vy: float
    speed: float

    def pos(self) -> pygame.Vector2:
        return pygame.Vector2(self.x, self.y)


@dataclass
class PowerUp:
    x: float
    y: float
    r: int
    active: bool = True


class HUD:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.font_big = pygame.font.SysFont("consolas", 44, bold=True)
        self.font = pygame.font.SysFont("consolas", 22)
        self.font_small = pygame.font.SysFont("consolas", 18)

    def draw_center_text(self, screen, text, y, color=None):
        color = color or self.cfg.fg_color
        surf = self.font_big.render(text, True, color)
        rect = surf.get_rect(center=(self.cfg.width // 2, y))
        screen.blit(surf, rect)

    def draw_hint(self, screen, text, y, color=None):
        color = color or self.cfg.fg_color
        surf = self.font.render(text, True, color)
        rect = surf.get_rect(center=(self.cfg.width // 2, y))
        screen.blit(surf, rect)

    def draw_score(self, screen, left_score, right_score):
        s = f"{left_score}  :  {right_score}"
        surf = self.font_big.render(s, True, self.cfg.fg_color)
        rect = surf.get_rect(center=(self.cfg.width // 2, 40))
        screen.blit(surf, rect)

    def draw_status(self, screen, text):
        surf = self.font_small.render(text, True, self.cfg.fg_color)
        screen.blit(surf, (16, self.cfg.height - 28))


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def random_ball_direction():
    angle = random.uniform(-0.35, 0.35)
    dir_x = random.choice([-1, 1])
    return dir_x, angle


def reset_round(cfg: Config, ball: Ball, serve_to_left: bool):
    ball.x = cfg.width / 2
    ball.y = cfg.height / 2
    ball.speed = cfg.ball_speed

    dir_x, angle = random_ball_direction()
    dir_x = -1 if serve_to_left else 1

    # Нормалізований напрям
    vx = dir_x * math.cos(angle)
    vy = math.sin(angle)
    v = pygame.Vector2(vx, vy)
    if v.length() == 0:
        v = pygame.Vector2(dir_x, 0.1)
    v = v.normalize()

    ball.vx = v.x
    ball.vy = v.y


def circle_rect_collision(cx, cy, cr, rect: pygame.Rect) -> bool:
    nearest_x = clamp(cx, rect.left, rect.right)
    nearest_y = clamp(cy, rect.top, rect.bottom)
    dx = cx - nearest_x
    dy = cy - nearest_y
    return (dx * dx + dy * dy) <= (cr * cr)


def apply_paddle_bounce(cfg: Config, ball: Ball, paddle: Paddle, is_left: bool):
    # Відскок по X
    ball.vx = abs(ball.vx) if is_left else -abs(ball.vx)

    offset = (ball.y - paddle.center_y()) / (paddle.h / 2)
    offset = clamp(offset, -1.0, 1.0)
    ball.vy = offset * 0.95

    # Нормалізуємо напрям
    v = pygame.Vector2(ball.vx, ball.vy)
    if v.length() == 0:
        v = pygame.Vector2(1 if is_left else -1, 0.1)
    v = v.normalize()
    ball.vx, ball.vy = v.x, v.y

    # Гра трохи пришвидшується з кожним ударом
    ball.speed = min(cfg.ball_speed_max, ball.speed * 1.03)


def ai_move(cfg: Config, ai: Paddle, ball: Ball, dt: float):
    # AI стежить за м’ячем, але з реакцією і обмеженням швидкості
    target = ball.y
    desired = ai.center_y() + (target - ai.center_y()) * (1.0 - cfg.ai_reaction)
    if desired > ai.center_y() + 2:
        ai.y += ai.speed * cfg.ai_max_speed_factor * dt
    elif desired < ai.center_y() - 2:
        ai.y -= ai.speed * cfg.ai_max_speed_factor * dt

    ai.y = clamp(ai.y, 0, cfg.height - ai.h)


class PongGame:
    def __init__(self):
        pygame.init()
        self.cfg = Config()
        self.screen = pygame.display.set_mode((self.cfg.width, self.cfg.height))
        pygame.display.set_caption("Pong + Boost (mini project)")
        self.clock = pygame.time.Clock()
        self.hud = HUD(self.cfg)

        self.state = GameState.MENU

        self.left = Paddle(
            x=28,
            y=self.cfg.height / 2 - self.cfg.paddle_h / 2,
            w=self.cfg.paddle_w,
            h=self.cfg.paddle_h,
            speed=self.cfg.paddle_speed,
        )
        self.right = Paddle(
            x=self.cfg.width - 28 - self.cfg.paddle_w,
            y=self.cfg.height / 2 - self.cfg.paddle_h / 2,
            w=self.cfg.paddle_w,
            h=self.cfg.paddle_h,
            speed=self.cfg.paddle_speed,
        )

        self.ball = Ball(
            x=self.cfg.width / 2,
            y=self.cfg.height / 2,
            r=self.cfg.ball_radius,
            vx=1.0,
            vy=0.0,
            speed=self.cfg.ball_speed,
        )

        self.left_score = 0
        self.right_score = 0

        self.powerup: PowerUp | None = None
        self.powerup_timer = 0.0

        self.boost_timer = 0.0  # якщо >0 — м’яч у бусті

        reset_round(self.cfg, self.ball, serve_to_left=False)

    def spawn_powerup(self):
        margin = 120
        x = random.randint(margin, self.cfg.width - margin)
        y = random.randint(80, self.cfg.height - 80)
        self.powerup = PowerUp(x=x, y=y, r=self.cfg.powerup_radius, active=True)

    def handle_input(self, dt: float):
        keys = pygame.key.get_pressed()

        # Ліва ракетка (гравець): W/S
        if keys[pygame.K_w]:
            self.left.y -= self.left.speed * dt
        if keys[pygame.K_s]:
            self.left.y += self.left.speed * dt
        self.left.y = clamp(self.left.y, 0, self.cfg.height - self.left.h)

        # Права ракетка: AI (за замовчуванням), але можна увімкнути ручне керування стрілками
        manual_right = keys[pygame.K_RSHIFT] or keys[pygame.K_LSHIFT]
        if manual_right:
            if keys[pygame.K_UP]:
                self.right.y -= self.right.speed * dt
            if keys[pygame.K_DOWN]:
                self.right.y += self.right.speed * dt
            self.right.y = clamp(self.right.y, 0, self.cfg.height - self.right.h)
        else:
            ai_move(self.cfg, self.right, self.ball, dt)

    def update_playing(self, dt: float):
        # Пауерап-таймер
        self.powerup_timer += dt
        if self.powerup is None and self.powerup_timer >= self.cfg.powerup_spawn_every_sec:
            self.powerup_timer = 0.0
            self.spawn_powerup()

        # Буст-таймер
        if self.boost_timer > 0:
            self.boost_timer -= dt
            if self.boost_timer <= 0:
                self.boost_timer = 0.0  

        # Рух м’яча
        speed = self.ball.speed * (self.cfg.boost_multiplier if self.boost_timer > 0 else 1.0)
        self.ball.x += self.ball.vx * speed * dt
        self.ball.y += self.ball.vy * speed * dt

        # Зіткнення зі стінами (верх/низ)
        if self.ball.y - self.ball.r <= 0:
            self.ball.y = self.ball.r
            self.ball.vy = -self.ball.vy
        if self.ball.y + self.ball.r >= self.cfg.height:
            self.ball.y = self.cfg.height - self.ball.r
            self.ball.vy = -self.ball.vy

        # Зіткнення з ракетками
        b_rect = pygame.Rect(int(self.ball.x - self.ball.r), int(self.ball.y - self.ball.r), self.ball.r * 2, self.ball.r * 2)

        if b_rect.colliderect(self.left.rect()) and self.ball.vx < 0:
            self.ball.x = self.left.x + self.left.w + self.ball.r
            apply_paddle_bounce(self.cfg, self.ball, self.left, is_left=True)

        if b_rect.colliderect(self.right.rect()) and self.ball.vx > 0:
            self.ball.x = self.right.x - self.ball.r
            apply_paddle_bounce(self.cfg, self.ball, self.right, is_left=False)

        # Пауерап: якщо м’яч торкнувся — активуємо буст
        if self.powerup and self.powerup.active:
            if (self.ball.pos() - pygame.Vector2(self.powerup.x, self.powerup.y)).length() <= (self.ball.r + self.powerup.r):
                self.powerup.active = False
                self.powerup = None
                self.boost_timer = self.cfg.boost_duration_sec

        # Гол
        if self.ball.x + self.ball.r < 0:
            self.right_score += 1
            reset_round(self.cfg, self.ball, serve_to_left=True)
            self.boost_timer = 0.0

        if self.ball.x - self.ball.r > self.cfg.width:
            self.left_score += 1
            reset_round(self.cfg, self.ball, serve_to_left=False)
            self.boost_timer = 0.0

        # Перемога
        if self.left_score >= self.cfg.score_to_win or self.right_score >= self.cfg.score_to_win:
            self.state = GameState.GAMEOVER

    def draw(self):
        self.screen.fill(self.cfg.bg_color)

        # Центральна лінія
        for y in range(0, self.cfg.height, 24):
            pygame.draw.rect(self.screen, (45, 50, 65), (self.cfg.width // 2 - 2, y, 4, 14))

        # Ракетки
        pygame.draw.rect(self.screen, self.cfg.fg_color, self.left.rect(), border_radius=8)
        pygame.draw.rect(self.screen, self.cfg.fg_color, self.right.rect(), border_radius=8)

        # М’яч
        ball_color = self.cfg.warning if self.boost_timer > 0 else self.cfg.accent
        pygame.draw.circle(self.screen, ball_color, (int(self.ball.x), int(self.ball.y)), self.ball.r)

        # Пауерап
        if self.powerup and self.powerup.active:
            pygame.draw.circle(self.screen, self.cfg.warning, (int(self.powerup.x), int(self.powerup.y)), self.powerup.r, width=3)
            pygame.draw.circle(self.screen, self.cfg.warning, (int(self.powerup.x), int(self.powerup.y)), 3)

        # HUD
        self.hud.draw_score(self.screen, self.left_score, self.right_score)

        if self.state == GameState.MENU:
            self.hud.draw_center_text(self.screen, "PONG + BOOST", self.cfg.height // 2 - 40, self.cfg.fg_color)
            self.hud.draw_hint(self.screen, "ENTER — start | ESC — quit", self.cfg.height // 2 + 20, (200, 205, 220))
            self.hud.draw_hint(self.screen, "W/S — move | hold SHIFT — manual right paddle", self.cfg.height // 2 + 58, (160, 170, 190))

        if self.state == GameState.PAUSED:
            self.hud.draw_center_text(self.screen, "PAUSED", self.cfg.height // 2, self.cfg.fg_color)
            self.hud.draw_hint(self.screen, "P — resume", self.cfg.height // 2 + 48, (200, 205, 220))

        if self.state == GameState.GAMEOVER:
            winner = "LEFT" if self.left_score > self.right_score else "RIGHT"
            self.hud.draw_center_text(self.screen, f"{winner} WINS!", self.cfg.height // 2 - 40, self.cfg.fg_color)
            self.hud.draw_hint(self.screen, "R — restart | ESC — quit", self.cfg.height // 2 + 20, (200, 205, 220))

        status = "Boost: ON" if self.boost_timer > 0 else "Boost: off"
        self.hud.draw_status(self.screen, f"{status} | P — pause | ESC — quit")

        pygame.display.flip()

    def restart(self):
        self.left_score = 0
        self.right_score = 0
        self.left.y = self.cfg.height / 2 - self.left.h / 2
        self.right.y = self.cfg.height / 2 - self.right.h / 2
        self.powerup = None
        self.powerup_timer = 0.0
        self.boost_timer = 0.0
        reset_round(self.cfg, self.ball, serve_to_left=False)
        self.state = GameState.PLAYING

    def run(self):
        while True:
            dt = self.clock.tick(self.cfg.fps) / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    return

                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        pygame.quit()
                        return

                    if self.state == GameState.MENU:
                        if event.key == pygame.K_RETURN:
                            self.state = GameState.PLAYING

                    elif self.state == GameState.PLAYING:
                        if event.key == pygame.K_p:
                            self.state = GameState.PAUSED

                    elif self.state == GameState.PAUSED:
                        if event.key == pygame.K_p:
                            self.state = GameState.PLAYING

                    elif self.state == GameState.GAMEOVER:
                        if event.key == pygame.K_r:
                            self.restart()

            if self.state == GameState.PLAYING:
                self.handle_input(dt)
                self.update_playing(dt)

            self.draw()


if __name__ == "__main__":
    try:
        PongGame().run()
    except Exception as e:
        print("Error:", e)
        raise
