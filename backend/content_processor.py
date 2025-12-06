import io
import json
import re
import time
import random
import requests
import urllib3
import google.generativeai as genai
from bs4 import BeautifulSoup
from pypdf import PdfReader
from dotenv import load_dotenv
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

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
        
        text = text.replace("\\", "\\\\") 
        text = text.replace("\\\\n", "\\n").replace("\\\\t", "\\t").replace("\\\\\"", "\\\"")
        return text.strip()

    def _call_gemini_with_retry(self, prompt, max_retries=5):
        """
        Hàm wrapper gọi API với cơ chế Retry khi gặp lỗi 429.
        Sử dụng Exponential Backoff + Jitter để tránh nghẽn mạng.
        """
        attempt = 0
        base_wait_time = 5 # Bắt đầu chờ 5 giây

        while attempt <= max_retries:
            try:
                # Gọi API
                return verifier_model.generate_content(prompt)
            except Exception as e:
                error_msg = str(e)
                # Chỉ retry nếu là lỗi 429 (Resource Exhausted)
                if "429" in error_msg:
                    attempt += 1
                    if attempt > max_retries:
                        print(f"[ERROR] Quota exhausted after {max_retries} retries. Skipping.")
                        return None
                    
                    # Tính thời gian chờ: (5 * 2^attempt) + random(1-3s)
                    # VD: Lần 1: ~6s, Lần 2: ~11s, Lần 3: ~21s...
                    wait_time = (base_wait_time * (2 ** (attempt - 1))) + random.uniform(1, 3)
                    print(f"[WARN] Quota hit (429). Retrying in {wait_time:.1f}s (Attempt {attempt}/{max_retries})...")
                    time.sleep(wait_time)
                else:
                    # Nếu lỗi khác (400, 500...) thì bỏ qua luôn, không retry
                    print(f"[AI ERROR] Unrecoverable error: {error_msg}")
                    return None
        return None

    def _refine_latex_with_ai(self, raw_sample):
        """Refine LaTeX logic (Có Retry)"""
        if not raw_sample or len(raw_sample) < 5:
            return raw_sample

        base_dir = os.path.dirname(os.path.abspath(__file__))
        prompt_path = os.path.join(base_dir, 'PROMPT', 'FIX_LATEX_PROMPT.txt')

        if not os.path.exists(prompt_path):
            return raw_sample

        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                prompt_template = f.read()

            prompt = prompt_template.replace("{raw_sample_question}", raw_sample)
            
            # Thay thế lệnh gọi trực tiếp bằng hàm có retry
            response = self._call_gemini_with_retry(prompt, max_retries=3)
            
            if not response: return raw_sample

            refined_text = response.text.strip()
            
            if refined_text.startswith("```"):
                parts = refined_text.split("\n", 1)
                if len(parts) > 1:
                    refined_text = parts[1]
                if refined_text.endswith("```"):
                    refined_text = refined_text.rsplit("```", 1)[0]
            
            return refined_text.strip()
        except Exception:
            return raw_sample

    def _extract_relevant_context_with_pages(self, pages_data, topic_keywords, window_size=800):
        # ... (Giữ nguyên code cũ)
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
        # ... (Giữ nguyên code cũ tối ưu timeout 8s)
        if any(x in url for x in ["youtube.com", "reddit.com", "tiktok.com", "giphy.com", "tenor.com", "knowyourmeme.com"]):
            return [], None

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=8, verify=False) 
            content_type = response.headers.get('Content-Type', '').lower()
            final_url = response.url.lower()
            pages_data = []

            is_pdf = 'application/pdf' in content_type or final_url.endswith('.pdf')
            if is_pdf:
                try:
                    f = io.BytesIO(response.content)
                    reader = PdfReader(f)
                    if len(reader.pages) > 0:
                        for i in range(min(10, len(reader.pages))): 
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

        base_dir = os.path.dirname(os.path.abspath(__file__))
        prompt_path = os.path.join(base_dir, 'PROMPT', 'PROMPT.txt')
        if not os.path.exists(prompt_path):
             return None

        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                prompt_template = f.read()

            prompt = prompt_template.replace("{user_topic}", str(user_topic)) \
                                    .replace("{difficulty}", str(difficulty)) \
                                    .replace("{doc_type}", str(doc_type)) \
                                    .replace("{tagged_context}", str(tagged_context))
            
            prompt = prompt.replace("{{", "{").replace("}}", "}")
            
            # --- Thay thế lệnh gọi trực tiếp bằng hàm _call_gemini_with_retry ---
            # Max retries = 5, nếu mạng lag hoặc hết quota sẽ kiên trì thử lại
            res = self._call_gemini_with_retry(prompt, max_retries=5)
            
            if not res: return None # Nếu sau 5 lần vẫn lỗi thì đành chịu

            raw_text = res.text
            
            parsed_result = None
            try:
                clean_text = self._clean_json_text(raw_text)
                parsed_result = json.loads(clean_text)
            except json.JSONDecodeError:
                match = re.search(r'\{.*\}', raw_text, re.DOTALL)
                if match:
                    try:
                        parsed_result = json.loads(match.group(0))
                    except:
                        pass
            
            if parsed_result and parsed_result.get('is_relevant') and parsed_result.get('contains_exercises'):
                sample = parsed_result.get('sample_question')
                if sample:
                    refined_sample = self._refine_latex_with_ai(sample)
                    parsed_result['sample_question'] = refined_sample
            
            return parsed_result
            
        except Exception as e:
            print(f"[ERROR] Logic error in verify: {e}")
            return None

    def _process_single_url(self, link, topic, difficulty):
        try:
            pages_data, doc_type = self.fetch_content(link)
            if not pages_data: return None
            
            evaluation = self.verify_relevance(pages_data, doc_type, topic, difficulty)
            
            if evaluation:
                score = evaluation.get('score', 0)
                has_exercises = evaluation.get('contains_exercises', False)
                reason = evaluation.get('reason', 'N/A')
                
                if score >= 5 and has_exercises:
                    page_loc = evaluation.get('page_location', 'Unknown')
                    return {
                        "url": link, "type": doc_type, "score": score,
                        "page": page_loc, "reason": reason,
                        "sample": evaluation.get('sample_question', '')
                    }
            return None
            
        except Exception as e:
            print(f"[THREAD ERROR] Error processing {link}: {e}")
            return None

    def process_links_stream(self, links, topic, difficulty):
        """
        Generator version: Yields progress updates to the app in real-time.
        """
        results = []
        max_workers = 5
        total_links = len(links)
        completed_count = 0
        
        print(f"[INFO] Verifying {total_links} links using {max_workers} parallel workers...")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_url = {
                executor.submit(self._process_single_url, url, topic, difficulty): url 
                for url in links
            }
            
            for future in as_completed(future_to_url):
                url = future_to_url[future]
                completed_count += 1
                
                try:
                    data = future.result()
                    if data:
                        print(f"[MATCH] Score: {data['score']} | {data['type']} | {url}")
                        results.append(data)
                except Exception as exc:
                    print(f"[ERROR] {url} generated an exception: {exc}")
                
                # YIELD PROGRESS: Return current state
                yield {
                    "type": "progress_update",
                    "current": completed_count,
                    "total": total_links,
                    "found": len(results)
                }
        
        # After processing all links, sort and return final results
        results.sort(key=lambda x: x['score'], reverse=True)
        yield {
            "type": "final_result",
            "data": results
        }
    
    def process_links(self, links, topic, difficulty):
        """Legacy method kept for backward compatibility - delegates to streaming version"""
        results = []
        for update in self.process_links_stream(links, topic, difficulty):
            if update["type"] == "final_result":
                results = update["data"]
        return results