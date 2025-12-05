import io
import json
import re
import time
import requests
import urllib3
import google.generativeai as genai
from bs4 import BeautifulSoup
from pypdf import PdfReader
from dotenv import load_dotenv
import os

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Model Configuration
MODEL_ID = os.getenv("GEMINI_CONTENT_PROCESSOR_MODEL_ID", "gemini-2.0-flash")
print(f"[INFO] Content Processor Model: {MODEL_ID}")

try:
    verifier_model = genai.GenerativeModel(MODEL_ID)
except Exception as e:
    print(f"[ERROR] Failed to initialize model {MODEL_ID}: {e}")
    verifier_model = genai.GenerativeModel("gemini-2.0-flash")

class ContentProcessor:
    def __init__(self):
        self.signal_keywords = [
            "bài tập", "ví dụ", "lời giải", "đáp án", "câu hỏi", "đề thi", 
            "exercise", "problem", "solution", "example", "quiz", "exam", "assignment", 
            "homework", "midterm", "final", "test", "practice"
        ]

    def _clean_json_text(self, text):
        """Làm sạch chuỗi JSON và xử lý lỗi escape LaTeX"""
        text = text.strip()
        if text.startswith("```"):
            first_newline = text.find("\n")
            if first_newline != -1:
                text = text[first_newline+1:]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
        
        # Sửa lỗi phổ biến: LaTeX dùng \ nhưng JSON yêu cầu \\
        text = text.replace("\\", "\\\\") 
        # Hoàn tác cho các ký tự JSON hợp lệ
        text = text.replace("\\\\n", "\\n").replace("\\\\t", "\\t").replace("\\\\\"", "\\\"")
        
        return text.strip()

    def _refine_latex_with_ai(self, raw_sample):
        """
        Gửi sample_question qua AI một lần nữa để chuẩn hóa LaTeX.
        Sử dụng prompt từ file FIX_LATEX_PROMPT.txt
        """
        if not raw_sample or len(raw_sample) < 5:
            return raw_sample

        prompt_path = os.path.join('PROMPT', 'FIX_LATEX_PROMPT.txt')

        # Kiểm tra file tồn tại
        if not os.path.exists(prompt_path):
            print(f"[WARNING] File prompt '{prompt_path}' not found. Skipping LaTeX refinement.")
            return raw_sample

        try:
            # Đọc nội dung file prompt
            with open(prompt_path, "r", encoding="utf-8") as f:
                prompt_template = f.read()

            # Sử dụng replace thay vì f-string để tránh lỗi với dấu {} của LaTeX/JSON trong prompt
            prompt = prompt_template.replace("{raw_sample_question}", raw_sample)
            
            # Gọi AI model (dùng flash model cho nhanh)
            response = verifier_model.generate_content(prompt)
            refined_text = response.text.strip()
            
            # Xóa markdown wrapper nếu AI lỡ thêm vào (VD: ```latex ... ```)
            if refined_text.startswith("```"):
                # Bỏ dòng đầu tiên (chứa ```)
                parts = refined_text.split("\n", 1)
                if len(parts) > 1:
                    refined_text = parts[1]
                
                # Bỏ dòng cuối cùng nếu chứa ```
                if refined_text.endswith("```"):
                    refined_text = refined_text.rsplit("```", 1)[0]
            
            return refined_text.strip()
            
        except Exception as e:
            print(f"[LATEX REFINE ERROR] Could not refine sample: {e}")
            return raw_sample # Fallback về text gốc nếu lỗi
        
    def _extract_relevant_context_with_pages(self, pages_data, topic_keywords, window_size=800):
        if not pages_data: return ""
        
        search_terms = self.signal_keywords + topic_keywords.lower().split()
        final_context = ""
        total_len = 0
        MAX_LEN = 25000 

        for page_item in pages_data:
            page_num = page_item['page']
            text = str(page_item['text'])
            if not text: continue

            lowered_text = text.lower()
            indices = []
            
            for term in search_terms:
                if len(term) < 3: continue
                if term in lowered_text:
                    indices.extend([m.start() for m in re.finditer(re.escape(term), lowered_text)])
            
            if not indices: continue
            
            indices.sort()
            ranges = []
            text_len = len(text)
            for idx in indices:
                start = max(0, idx - 200)
                end = min(text_len, idx + window_size)
                ranges.append((start, end))

            merged_ranges = []
            if ranges:
                curr_start, curr_end = ranges[0]
                for next_start, next_end in ranges[1:]:
                    if next_start < curr_end:
                        curr_end = max(curr_end, next_end)
                    else:
                        merged_ranges.append((curr_start, curr_end))
                        curr_start, curr_end = next_start, next_end
                merged_ranges.append((curr_start, curr_end))

            for start, end in merged_ranges:
                if total_len > MAX_LEN: break
                chunk = text[start:end].replace('\n', ' ')
                final_context += f"\n=== PAGE {page_num} ===\n...{chunk}...\n"
                total_len += len(chunk)

        if not final_context and pages_data:
             p1 = pages_data[0]
             final_context += f"\n=== PAGE {p1['page']} (Intro) ===\n{str(p1['text'])[:3000]}"
             if len(pages_data) > 1:
                 p_last = pages_data[-1]
                 final_context += f"\n=== PAGE {p_last['page']} (End) ===\n{str(p_last['text'])[:2000]}"

        return final_context

    def fetch_content(self, url):
        # BỘ LỌC RÁC CỨNG (Hard Filter)
        if any(x in url for x in ["youtube.com", "reddit.com", "tiktok.com", "giphy.com", "tenor.com", "knowyourmeme.com"]):
            print(f"[INFO] Skipped junk domain: {url}")
            return [], None

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=10, verify=False) 
            content_type = response.headers.get('Content-Type', '').lower()
            final_url = response.url.lower()
            pages_data = []

            is_pdf = 'application/pdf' in content_type or final_url.endswith('.pdf')
            if is_pdf:
                try:
                    f = io.BytesIO(response.content)
                    reader = PdfReader(f)
                    if len(reader.pages) > 0:
                        for i in range(min(15, len(reader.pages))): 
                            txt = reader.pages[i].extract_text()
                            if txt:
                                pages_data.append({"page": i + 1, "text": txt})
                        return pages_data, "PDF"
                except:
                    pass 

            soup = BeautifulSoup(response.content, 'html.parser')
            for tag in soup(["script", "style", "nav", "footer", "header", "iframe", "noscript"]):
                tag.decompose()
            text = soup.get_text(separator=' ', strip=True)
            
            if len(text) > 200: 
                pages_data.append({"page": "Web", "text": text[:30000]})
                return pages_data, "WEB"
            
            return [], None

        except Exception:
            return [], None

    def verify_relevance(self, pages_data, doc_type, user_topic, difficulty):
        if not pages_data: return None

        tagged_context = self._extract_relevant_context_with_pages(pages_data, user_topic)
        if not tagged_context: return None 

        prompt_path = os.path.join('PROMPT', 'PROMPT.txt')
        if not os.path.exists(prompt_path):
             print(f"[ERROR] Prompt file '{prompt_path}' not found.")
             return None

        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                prompt_template = f.read()

            prompt = prompt_template.replace("{user_topic}", str(user_topic)) \
                                    .replace("{difficulty}", str(difficulty)) \
                                    .replace("{doc_type}", str(doc_type)) \
                                    .replace("{tagged_context}", str(tagged_context))
            
            prompt = prompt.replace("{{", "{").replace("}}", "}")
            
            time.sleep(2) 
            
            res = verifier_model.generate_content(prompt)
            raw_text = res.text
            
            parsed_result = None
            
            # Thử parse JSON
            try:
                clean_text = self._clean_json_text(raw_text)
                parsed_result = json.loads(clean_text)
            except json.JSONDecodeError:
                # Fallback: Regex tìm JSON
                match = re.search(r'\{.*\}', raw_text, re.DOTALL)
                if match:
                    try:
                        parsed_result = json.loads(match.group(0))
                    except:
                        pass
            
            # --- BƯỚC QUAN TRỌNG: CHUẨN HOÁ LATEX ---
            if parsed_result and parsed_result.get('is_relevant') and parsed_result.get('contains_exercises'):
                sample = parsed_result.get('sample_question')
                if sample:
                    # Gọi thêm 1 API nữa để sửa Latex cho đẹp
                    refined_sample = self._refine_latex_with_ai(sample)
                    parsed_result['sample_question'] = refined_sample
            
            return parsed_result
            
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg:
                print("[ERROR] Quota exceeded (429). Cooling down for 5s...")
                time.sleep(5) 
            elif "404" in error_msg:
                print(f"[ERROR] Model '{MODEL_ID}' not found.")
            else:
                print(f"[ERROR] AI Inference failed: {error_msg}")
            return None

    def process_links(self, links, topic, difficulty):
        results = []
        print(f"[INFO] Verifying {len(links)} links...")
        
        for link in links:
            pages_data, doc_type = self.fetch_content(link)
            
            if pages_data:
                evaluation = self.verify_relevance(pages_data, doc_type, topic, difficulty)
                
                if evaluation:
                    score = evaluation.get('score', 0)
                    has_exercises = evaluation.get('contains_exercises', False)
                    reason = evaluation.get('reason', 'N/A')
                    
                    if score >= 5 and has_exercises:
                        page_loc = evaluation.get('page_location', 'Unknown')
                        print(f"[MATCH] Score: {score} | Type: {doc_type} | URL: {link}")
                        
                        results.append({
                            "url": link, "type": doc_type, "score": score,
                            "page": page_loc, "reason": reason,
                            "sample": evaluation.get('sample_question', '')
                        })
                    else:
                        print(f"[SKIP]  Score: {score} | Reason: {reason} | URL: {link}")
                else:
                    pass
            else:
                 pass 
                
        return results