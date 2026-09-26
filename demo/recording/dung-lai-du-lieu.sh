#!/bin/sh
# Dựng lại dữ liệu sạch cho dự án shipverify rồi nạp 12 đơn đối chiếu. Chạy trước khi quay lại toàn bộ Demo.
# Không đụng volume shipguard_pg_data của môi trường phát triển.
# SHIPGUARD_SOURCE_DIR: thư mục Source (có docker-compose.yml, .env, db/initdb, models).
SEED="$(cd "$(dirname "$0")" && pwd)/seed.cjs"
cd "${SHIPGUARD_SOURCE_DIR:?Chưa đặt SHIPGUARD_SOURCE_DIR}" || exit 1
docker compose -p shipverify down -v && docker compose -p shipverify up -d --build --wait || exit 1
node "$SEED"
