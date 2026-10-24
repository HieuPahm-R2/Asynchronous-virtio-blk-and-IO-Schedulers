# Nguồn sơ đồ submit và complete

Bản chính để chỉnh sửa là [virtio-submit-complete.drawio](virtio-submit-complete.drawio),
đồng bộ từ bản người dùng sửa trên [ProjectTerm - ET4290](https://app.diagrams.net/#G1lpHCZ3cDq0vzGF7y1B910eJgA_-NZf_m).
File trong repo chứa đúng hai trang 01 Stock xv6 và 02 Async đề xuất.
Bản export đầy đủ của tài liệu chung được lưu ngoài repo, không đưa các trang
khác của nhóm vào phần đóng góp cá nhân.

- Trang stock: 20 bước. Trang async đề xuất: 21 bước.
- Đã giữ nguyên vị trí nhãn, mũi tên, header và nội dung người dùng chỉnh sửa.
- SVG được xuất trực tiếp bằng draw.io Desktop 32.5.5, không dựng lại bố cục.
- Mermaid mô tả thứ tự và ý nghĩa tương đương; không phải nguồn bố cục draw.io.
- drawio-source.json ghi nguồn, page IDs, thời điểm đồng bộ và checksum.
- Không có thay đổi nội dung 20/21 bước so với bản trước; thay đổi nằm ở bố cục
  và bỏ phần tiêu đề/chú thích thừa. Async vẫn chỉ là thiết kế.

Sau khi sửa trên web lần nữa, xuất lại XML để đồng bộ bản trong repo.
Bản web và file local không tự đồng bộ. Để xuất lại SVG từ file local:

```bash
drawio --export --format svg --page-index 1 --theme light \
  --embed-svg-fonts false --output stock-submit-complete.svg \
  virtio-submit-complete.drawio
drawio --export --format svg --page-index 2 --theme light \
  --embed-svg-fonts false --output async-submit-complete.svg \
  virtio-submit-complete.drawio
```

Chạy các lệnh trên từ thư mục docs/week01/diagrams.
