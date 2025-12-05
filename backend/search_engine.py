import os
import concurrent.futures
import math
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dotenv import load_dotenv

load_dotenv()

class SearchEngine:
    def __init__(self):
        self.api_key = os.getenv("GOOGLE_API_KEY")
        self.cse_id = os.getenv("GOOGLE_CSE_ID")
        
        if not self.api_key or not self.cse_id:
            raise ValueError("Missing GOOGLE_API_KEY or GOOGLE_CSE_ID in .env file")

        try:
            self.service = build("customsearch", "v1", developerKey=self.api_key)
        except Exception as e:
            print(f"[SEARCH INIT ERROR] Could not build service: {e}")
            self.service = None

    def _search_single_query(self, query, num_results=3):
        """Gọi API cho 1 query duy nhất với số lượng kết quả tùy chỉnh."""
        if not self.service:
            return []
            
        try:
            # Google API giới hạn tối đa 10 kết quả mỗi lần gọi
            safe_num = min(num_results, 10)
            
            res = self.service.cse().list(
                q=query, 
                cx=self.cse_id, 
                num=safe_num
            ).execute()
            
            items = res.get('items', [])
            links = [item['link'] for item in items]
            return links
            
        except HttpError as e:
            print(f"[GOOGLE API ERROR] Query: '{query}' failed. Reason: {e}")
            return []
        except Exception as e:
            print(f"[SEARCH ERROR] Unknown error for '{query}': {e}")
            return []

    def execute_search_plan(self, search_plan_json, max_queries=3, results_per_query=3, max_workers=5):
        """
        Input: JSON từ QueryGenerator, cấu hình số lượng query và link.
        """
        if not search_plan_json:
            return []

        # Lấy danh sách query từ các Tier
        t1 = search_plan_json.get('tier_1_topic_focused', [])
        t2 = search_plan_json.get('tier_2_context_specific', [])
        t3 = search_plan_json.get('tier_3_descriptive_chaining', [])
        
        # Chiến thuật Round-Robin để chọn query cân bằng giữa các Tier
        # Ví dụ: max_queries = 5 -> Lấy T1, T2, T3, T1, T2
        all_potential_queries = []
        max_len = max(len(t1), len(t2), len(t3))
        
        for i in range(max_len):
            if i < len(t1): all_potential_queries.append(t1[i])
            if i < len(t2): all_potential_queries.append(t2[i])
            if i < len(t3): all_potential_queries.append(t3[i])
            
        # Cắt lấy đúng số lượng user yêu cầu
        selected_queries = all_potential_queries[:max_queries]
        
        unique_urls = set()
        
        print(f"[INFO] Executing {len(selected_queries)} queries (Limit: {max_queries})...")
        print(f"[INFO] Fetching {results_per_query} links per query...")

        executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
        try:
            # Submit tasks với tham số num_results động
            future_to_query = {
                executor.submit(self._search_single_query, q, results_per_query): q 
                for q in selected_queries
            }
            
            for future in concurrent.futures.as_completed(future_to_query):
                try:
                    urls = future.result()
                    unique_urls.update(urls)
                except Exception as exc:
                    print(f"[THREAD ERROR] Generated an exception: {exc}")
        finally:
            executor.shutdown(wait=True)
        
        results = list(unique_urls)
        print(f"[INFO] Total unique links found: {len(results)}")
        return results