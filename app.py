import os
import json
import time
from flask import Flask, render_template, request, Response, stream_with_context, jsonify
from dotenv import load_dotenv

# Import các modules
from backend.query_generator import QueryGenerator
from backend.search_engine import SearchEngine
from backend.content_processor import ContentProcessor

load_dotenv()

app = Flask(__name__)

# --- CẤU HÌNH LƯU TRỮ ---
HISTORY_FILE = 'chat_history.json'

def load_history():
    """Đọc lịch sử từ file JSON"""
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []

def save_history(data):
    """Ghi lịch sử vào file JSON"""
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[STORAGE ERROR] Could not save history: {e}")

def get_chat_by_id(chat_id, history):
    for chat in history:
        if chat['id'] == chat_id:
            return chat
    return None

# --- KHỞI TẠO AI MODULES ---
q_gen = None
searchor = None
processor = None

def init_system():
    global q_gen, searchor, processor
    try:
        print("[SYSTEM] Loading modules...")
        q_gen = QueryGenerator(prompt_path=os.path.join('backend', 'PROMPT', 'SYSTEM_PROMPT.txt'))
        searchor = SearchEngine()
        processor = ContentProcessor()
        print("[SYSTEM] Modules ready.")
    except Exception as e:
        print(f"[SYSTEM ERROR] {e}")

init_system()

# --- ROUTES ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/history', methods=['GET'])
def get_all_history():
    """API lấy toàn bộ lịch sử"""
    return jsonify(load_history())

@app.route('/api/history/<chat_id>', methods=['DELETE'])
def delete_chat(chat_id):
    """API xóa một cuộc trò chuyện"""
    history = load_history()
    new_history = [c for c in history if c['id'] != chat_id]
    save_history(new_history)
    return jsonify({"success": True})

@app.route('/api/chat-stream', methods=['POST'])
def chat_stream():
    data = request.json
    user_input = data.get('message', '')
    chat_id = data.get('chat_id', '') # Frontend gửi ID lên
    
    # --- NHẬN CẤU HÌNH TỪ FRONTEND ---
    config = data.get('config', {})
    # Mặc định là 3 query, 3 kết quả mỗi query nếu không có config
    setting_max_queries = int(config.get('max_queries', 3))
    setting_res_per_query = int(config.get('results_per_query', 3))
    
    # Tạo tiêu đề nếu là chat mới (lấy 30 ký tự đầu)
    chat_title = user_input[:30] + "..." if len(user_input) > 30 else user_input

    if not user_input or not chat_id:
        return Response("Missing data", status=400)

    # 1. Lưu tin nhắn User vào file ngay lập tức
    history = load_history()
    current_chat = get_chat_by_id(chat_id, history)
    
    if not current_chat:
        # Nếu chưa có chat này, tạo mới
        current_chat = {"id": chat_id, "title": chat_title, "messages": []}
        history.append(current_chat)
    
    # Thêm msg của user
    current_chat['messages'].append({"role": "user", "content": user_input})
    save_history(history)

    def generate():
        # Biến tạm để gom nội dung Bot trả về
        full_bot_response = ""
        collected_logs = []

        try:
            # --- BƯỚC 1: SUY NGHĨ ---
            log_1 = "Đang phân tích ý định người dùng..."
            collected_logs.append(log_1)
            yield json.dumps({"type": "log", "content": log_1}) + "\n"
            
            search_plan = q_gen.generate(user_input)
            
            if not search_plan:
                err_msg = "Không thể phân tích yêu cầu."
                yield json.dumps({"type": "error", "content": err_msg}) + "\n"
                return

            analysis = search_plan.get("analysis", {})
            topic_en = analysis.get("topic_en", "General")
            difficulty = analysis.get("difficulty", "Standard")
            
            log_2 = f"Chủ đề: {topic_en} | Độ khó: {difficulty}"
            collected_logs.append(log_2)
            yield json.dumps({"type": "log", "content": log_2}) + "\n"

            # --- BƯỚC 2: TẠO TỪ KHÓA ---
            # Chỉ mang tính chất log, việc cắt giảm số lượng query thật sự nằm ở bước 3
            all_queries = search_plan.get('tier_1_topic_focused', []) + search_plan.get('tier_2_context_specific', []) + search_plan.get('tier_3_descriptive_chaining', [])
            log_3 = f"Đã sinh {len(all_queries)} từ khóa tiềm năng."
            yield json.dumps({"type": "log", "content": log_3}) + "\n"

            # --- BƯỚC 3: SEARCH (CÓ CẤU HÌNH) ---
            log_4 = f"Đang tìm kiếm Google (Queries: {setting_max_queries}, Links/Query: {setting_res_per_query})..."
            collected_logs.append(log_4)
            yield json.dumps({"type": "log", "content": log_4}) + "\n"
            
            links = searchor.execute_search_plan(
                search_plan, 
                max_queries=setting_max_queries, 
                results_per_query=setting_res_per_query,
                max_workers=5
            )
            
            if not links:
                yield json.dumps({"type": "error", "content": "Không tìm thấy tài liệu."}) + "\n"
                return

            log_5 = f"Tìm thấy {len(links)} liên kết duy nhất. Đang đọc và thẩm định..."
            collected_logs.append(log_5)
            yield json.dumps({"type": "log", "content": log_5}) + "\n"

            # --- BƯỚC 4: PROCESS ---
            valid_results = processor.process_links(links, topic_en, difficulty)
            
            log_6 = f"Hoàn tất. Lọc được {len(valid_results)} tài liệu phù hợp."
            collected_logs.append(log_6)
            yield json.dumps({"type": "log", "content": log_6}) + "\n"

            # --- BƯỚC 5: RESULT ---
            if not valid_results:
                final_response = f"### Phân tích: {topic_en}\n> Không tìm thấy bài tập phù hợp độ khó {difficulty} trong số các liên kết đã quét."
            else:
                final_response = f"### Kết quả phân tích\n"
                final_response += f"* **Chủ đề:** {topic_en}\n"
                final_response += f"* **Độ khó:** {difficulty}\n\n"
                final_response += f"### Tìm thấy {len(valid_results)} tài liệu:\n___\n"
                
                for idx, res in enumerate(valid_results, 1):
                    icon = "📄 PDF" if res['type'] == 'PDF' else "🌐 WEB"
                    final_response += f"#### {idx}. [{icon}] {res['url']}\n"
                    final_response += f"- **Score:** {res['score']}/10 ({res['reason']})\n"
                    final_response += f"- **Page:** {res['page']}\n"
                    if res['sample']:
                        # Đóng gói sample vào block math để frontend dễ xử lý
                        final_response += f"\n**Bài tập mẫu:**\n$${res['sample']}$$\n"
                    final_response += "\n___\n"
            
            full_bot_response = final_response
            yield json.dumps({"type": "result", "content": final_response}) + "\n"

        except Exception as e:
            print(f"Error: {e}")
            yield json.dumps({"type": "error", "content": "Lỗi hệ thống trong quá trình xử lý."}) + "\n"
        
        finally:
            # --- BƯỚC CUỐI: LƯU TIN NHẮN BOT VÀO FILE ---
            # Phải load lại history mới nhất vì có thể có thay đổi song song (dù hiếm)
            fresh_history = load_history()
            chat_to_update = get_chat_by_id(chat_id, fresh_history)
            
            if chat_to_update:
                bot_msg = {
                    "role": "bot",
                    "content": full_bot_response if full_bot_response else "Lỗi xử lý hoặc không có phản hồi.",
                    "logs": collected_logs
                }
                chat_to_update['messages'].append(bot_msg)
                save_history(fresh_history)
                print(f"[SYSTEM] Saved bot response to chat {chat_id}")

    return Response(stream_with_context(generate()), mimetype='application/x-ndjson')

if __name__ == '__main__':
    app.run(debug=True, port=5000)