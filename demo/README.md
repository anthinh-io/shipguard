# Demo ShipGuard

Thư mục này chứa kịch bản, mã quay màn hình và mã lồng tiếng của video Demo. Video và các clip quay ra rất nặng nên không nằm trong Git; bản nộp được đưa lên Google Drive.

- `kich-ban-demo.md`: kịch bản 7 cảnh và lời thuyết minh từng bước.
- `recording/`: kịch bản Playwright quay từng cảnh thành clip .webm không tiếng, ghi vào `demo/clips`.
- `video/`: dự án Remotion lồng tiếng cho các clip và xuất MP4 ra `demo/ShipGuard-Demo.mp4`.

## Quay lại các cảnh

Cần ứng dụng chạy ở http://localhost:3000 trên dữ liệu sạch, và Playwright đã cài (`bun install` ở gốc repo). Thư mục Source phải có `docker-compose.yml`, `.env`, `db/initdb` và `models` (xem mục 5 của README ở gốc). Các lệnh dưới chạy trong Git Bash, từ gốc repo:

```
export SHIPGUARD_SOURCE_DIR=/đường/dẫn/tới/Source
sh demo/recording/dung-lai-du-lieu.sh
node demo/recording/run-all.cjs
```

Lệnh thứ hai dựng lại dữ liệu sạch cho dự án Docker `shipverify` (xóa dữ liệu của chính dự án này, không đụng volume của môi trường phát triển) rồi nạp 12 đơn đối chiếu. Lệnh thứ ba quay cả bảy cảnh; thêm số cảnh phía sau để quay riêng, ví dụ `node demo/recording/run-all.cjs 3 4`.

## Lồng tiếng và xuất video

Trong `demo/video`:

```
npm install
npm run sync
npm run narration
npm run tts
npm run check
npm run render:full
```

`sync` chép các clip từ `demo/clips`, `narration` chép lời thuyết minh từ `kich-ban-demo.md`, `tts` tạo giọng đọc bằng Edge TTS (cần Internet), `check` in bảng thời gian và báo lỗi nếu lời đọc lệch kịch bản, còn `render:full` xuất `demo/ShipGuard-Demo.mp4`. Dùng `npm run studio` để xem trước từng cảnh. Các tham số cắt và tăng tốc video được mô tả ở cuối `kich-ban-demo.md`.
