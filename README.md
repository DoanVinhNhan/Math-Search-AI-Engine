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
git clone https://github.com/DoanVinhNhan/Math-Search-AI-Engine
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
GEMINI_KEYS_GENERATOR_MODEL_ID=gemini-2.5-pro
GEMINI_CONTENT_PROCESSOR_MODEL_ID=gemini-2.5-flash

# 2. Google Custom Search API (Dùng để search Google)
GOOGLE_API_KEY=your_google_cloud_api_key_here
GOOGLE_CSE_ID=your_custom_search_engine_id_here
```

### Chi tiết cách lấy API Key:

#### Bước 1: Tạo Project và lấy GEMINI_API_KEY (Google AI Studio)
1. Truy cập: [Google AI Studio - API Key](https://aistudio.google.com/api-keys)
2. Nhấn vào nút Create API key.
3. Chọn Create project.
4. Tạo API key với project vừa tạo.
4. Hệ thống sẽ tạo key, hãy copy chuỗi ký tự này và dán vào dòng GEMINI_API_KEY trong file .env.
#### Bước 2: Tạo GOOGLE_CSE_ID (Programmable Search Engine)
1. Truy cập: [Google Programmable Search Engine](https://programmablesearchengine.google.com/)
2. Nhấn nút Add (Thêm) để tạo công cụ mới.
3. Điền thông tin:
    - Name: Đặt tên bất kỳ (VD: MathSearch).
    - What to search: Chọn Search the entire web (Tìm kiếm toàn bộ web).
5. Nhấn Create, sau đó copy ID.
6. Copy mã này dán vào dòng GOOGLE_CSE_ID trong file .env.
#### Bước 3: Lấy GOOGLE_API_KEY và kích hoạt Custom Search API
1. Truy cập: [Google Cloud Console](https://console.cloud.google.com/)
2. Ở góc trên bên trái, nhấn vào danh sách Project và chọn đúng Project bạn đã tạo ở Bước 1:
3. Kích hoạt thư viện Search:
    - Vào menu bên trái > APIs & Services > Library.
    - Tìm từ khóa Custom Search API.
    - Nhấn vào kết quả và chọn Enable (Kích hoạt).
4. Tạo API Key:
    - Vào menu APIs & Services > Credentials.
    - Nhấn + CREATE CREDENTIALS > Chọn API key.
    - Copy key này dán vào dòng GOOGLE_API_KEY trong file .env.
5. Cấu hình giới hạn (API Restrictions):
    - Tại danh sách API Keys, nhấn vào tên key vừa tạo (hoặc biểu tượng cây bút) để chỉnh sửa.
    - Tại mục API restrictions, chọn Restrict key.
    - Trong menu thả xuống, tích chọn Generative Language API và Custom Search API.
    - Nhấn Save.

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