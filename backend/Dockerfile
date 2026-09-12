# syntax=docker/dockerfile:1

FROM python:3.12-slim AS base

# - PYTHONDONTWRITEBYTECODE: .pyc 안 만듦 (컨테이너에선 불필요)
# - PYTHONUNBUFFERED: 로그 즉시 flush
# - TZ: 배치 스케줄러가 Asia/Seoul 기준으로 동작 (run_batch_scheduler.py)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Seoul \
    APP_ENV=production \
    FLASK_APP=run.py

WORKDIR /app

# tzdata: 시장 세션 판단(거래소 현지시간) / 배치 스케줄러 타임존에 필요
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

# 의존성 레이어 캐시: requirements.txt만 먼저 복사
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드
COPY . .

RUN chmod +x /app/docker-entrypoint.sh \
    && adduser --disabled-password --gecos "" appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 5000

# 컨테이너 헬스체크 (스크립트는 docker-healthcheck.py 참고)
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "/app/docker-healthcheck.py"]

ENTRYPOINT ["/app/docker-entrypoint.sh"]

# 기본 명령: gunicorn 으로 WSGI 서버 구동 (run.py 의 app 객체)
# 스케줄러 컨테이너는 compose 에서 command 를 override 한다.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "3", "--timeout", "120", "--access-logfile", "-", "--error-logfile", "-", "run:app"]
