# Math Search AI Engine

Hệ thống tìm kiếm tài liệu toán học chuyên sâu sử dụng AI (Gemini) để phân tích ý định, sinh từ khóa tìm kiếm, và thẩm định nội dung (PDF/Web) tự động.

## 1. Tác dụng chính

- **Phân tích ý định**: Chuyển đổi yêu cầu tự nhiên (VD: "Tìm bài tập Đại số mức khó") thành kế hoạch tìm kiếm chi tiết.

- **Deep Search**: Tự động sinh hàng chục từ khóa tìm kiếm tối ưu (Tier 1, 2, 3) để quét Google.

- **Thẩm định nội dung**: Tải và đọc nội dung file (PDF/HTML), sử dụng AI để chấm điểm độ phù hợp theo thang đo 0-10.

- **Trích xuất dữ liệu**: Lọc ra bài tập mẫu và tự động chuẩn hóa công thức toán học sang LaTeX.

## 2. Cấu trúc dự án

```
project/
├── app.py                  # Server Flask chính
├── requirements.txt        # Các thư viện cần thiết
├── .env                    # Biến môi trường (API Keys)
├── chat_history.json       # Lưu trữ lịch sử chat
├── backend/
│   ├── query_generator.py  # Sinh từ khóa tìm kiếm (Gemini)
│   ├── search_engine.py    # Gọi Google Custom Search API
│   ├── content_processor.py# Đọc PDF/Web và thẩm định (Gemini)
│   └── PROMPT/             # Các file prompt hệ thống (.txt)
└── templates/
    └── index.html          # Giao diện người dùng
```

## 3. Cài đặt môi trường

**Yêu cầu**: Python 3.8+

### Bước 1: Clone hoặc tải source code về máy

```bash
git clone <repository-url>
cd "Math Search Engine"
```

### Bước 2: Tạo môi trường ảo (Khuyến nghị)

```bash
python -m venv venv

# Windows:
venv\Scripts\activate

# macOS/Linux:
source venv/bin/activate
```

### Bước 3: Cài đặt thư viện

```bash
pip install -r requirements.txt
```

## 4. Cấu hình file .env và lấy API Key

Tạo file tên `.env` tại thư mục gốc của dự án và điền nội dung theo mẫu sau:

```env
# .env file

# 1. Google Gemini API (Dùng cho AI xử lý)
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_KEYS_GENERATOR_MODEL_ID=gemini-2.0-flash
GEMINI_CONTENT_PROCESSOR_MODEL_ID=gemini-2.0-flash

# 2. Google Custom Search API (Dùng để search Google)
GOOGLE_API_KEY=your_google_cloud_api_key_here
GOOGLE_CSE_ID=your_custom_search_engine_id_here
```

### Chi tiết cách lấy API Key:

#### A. Lấy GEMINI_API_KEY (Miễn phí)

1. Truy cập: [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Nhấn **Create API key**
3. Copy chuỗi ký tự và dán vào dòng `GEMINI_API_KEY` trong file `.env`

#### B. Lấy GOOGLE_API_KEY (Google Cloud Platform)

1. Truy cập: [Google Cloud Console](https://console.cloud.google.com/)
2. Tạo một Project mới
3. Vào mục **APIs & Services** > **Library**
4. Tìm và **Enable** `Custom Search API`
5. Vào **APIs & Services** > **Credentials** > **Create Credentials** > **API key**
6. Copy key này vào dòng `GOOGLE_API_KEY`

#### C. Lấy GOOGLE_CSE_ID (Programmable Search Engine)

1. Truy cập: [Programmable Search Engine](https://programmablesearchengine.google.com/)
2. Nhấn **Add** để tạo công cụ tìm kiếm mới
3. Đặt tên bất kỳ. Tại phần **What to search**, chọn **Search the entire web** (Tìm kiếm toàn bộ web)
4. Sau khi tạo xong, tại trang **Overview**, copy đoạn mã **Search engine ID** (có dạng `0123456789...:abcde`)
5. Dán vào dòng `GOOGLE_CSE_ID`

## 5. Cách sử dụng

### Bước 1: Chạy ứng dụng Flask

```bash
python app.py
```

### Bước 2: Truy cập giao diện

Mở trình duyệt và vào địa chỉ: `http://localhost:5000`

### Bước 3: Thao tác

1. Nhập yêu cầu tìm kiếm vào ô chat (Ví dụ: "Tìm bài tập tích phân đường mức vận dụng cao")
2. Nhấn nút gửi hoặc **Enter**
3. Hệ thống sẽ xử lý qua các bước: **Phân tích** → **Tìm kiếm** → **Đọc tài liệu** → **Trả kết quả**

---

**© 2025 Math Search Engine** - Được phát triển bởi Doan Vinh Nhan