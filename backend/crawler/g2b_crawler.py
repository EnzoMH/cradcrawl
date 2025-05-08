"""
나라장터 크롤러 클래스

나라장터(G2B) 크롤링 통합 기능을 제공하는 클래스입니다.
다양한 하위 모듈들을 활용하여 나라장터 웹사이트의 입찰공고를 크롤링합니다.
"""

import os
import sys
import asyncio
import logging
import json
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException

# 현재 스크립트 위치 기반으로 경로 설정
current_dir = Path(__file__).parent
backend_dir = current_dir.parent
project_root = backend_dir.parent

# 리팩토링된 하위 모듈 임포트
from backend.crawler.crawler_base import CrawlerBase
from backend.crawler.g2b_navigation import G2BNavigator
from backend.crawler.g2b_search import G2BSearcher
from backend.crawler.g2b_detail import G2BDetailProcessor
from backend.crawler.g2b_contract import G2BContractExtractor
from backend.crawler.g2b_parser import G2BParser
from backend.crawler.g2b_extractor import G2BExtractor

# 유틸리티 모듈 임포트
from backend.utils.ai_helpers import extract_with_gemini_text, check_relevance_with_ai, ai_model_manager
from backend.utils.parsing_helpers import extract_detail_page_data_from_soup

# 로깅 설정
logger = logging.getLogger("g2b-crawler")

# 환경 변수 확인
DEFAULT_GEMINI_API_KEY = "AIzaSyDLe9f5i3AlKZp4eX-U8Xgop7GiO0y_Qzc"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", DEFAULT_GEMINI_API_KEY)
if not GEMINI_API_KEY or GEMINI_API_KEY == "":
    logger.warning("GEMINI_API_KEY 환경 변수가 설정되지 않았습니다. 기본값을 사용합니다.")
    os.environ["GEMINI_API_KEY"] = DEFAULT_GEMINI_API_KEY
else:
    logger.info(f"크롤러에서 GEMINI_API_KEY를 로드했습니다.")

# 결과 저장 디렉토리 설정
RESULTS_DIR = current_dir / 'results'
RESULTS_DIR.mkdir(exist_ok=True)

class G2BCrawler:
    """나라장터 크롤러 통합 클래스"""
    
    def __init__(self, headless: bool = False):
        """
        초기화
        
        Args:
            headless (bool): 헤드리스 모드 사용 여부
        """
        # 기본 속성 설정
        self.headless = headless
        self.results = []
        self.keyword = "AI"  # 기본 검색어
        
        # 기본 인스턴스 설정
        self.driver = None
        self.wait = None
        
        # 각 모듈별 인스턴스 초기화 (driver 설정 후 초기화)
        self.base = None
        self.navigator = None
        self.searcher = None
        self.detail_processor = None
        self.contract_extractor = None
        self.parser = None
        self.extractor = None
        
        # AI 모델 관리자 확인
        if not ai_model_manager.gemini_model:
            logger.info("AI 모델 관리자 초기화")
            ai_model_manager.setup_models()
    
    # 수정된 initialize 메서드
    async def initialize(self):
        try:
            logger.info("크롤러 초기화 시작")
            
            # 기본 크롤러 초기화
            self.base = CrawlerBase(headless=self.headless)
            await self.base.initialize()  # CrawlerBase의 initialize 메서드 호출
            
            if not self.base:
                logger.error("크롤러 기본 초기화 실패")
                return False
            
            # WebDriver 및 Wait 객체 공유
            self.driver = self.base.driver
            self.wait = self.base.wait
            
            if not self.driver:
                logger.error("웹드라이버 초기화 실패")
                return False
            
            # 각 모듈 인스턴스 초기화 (driver와 wait 객체 전달)
            self.navigator = G2BNavigator(driver=self.driver, wait=self.wait)
            self.searcher = G2BSearcher(driver=self.driver, wait=self.wait, navigator=self.navigator)
            self.extractor = G2BExtractor(driver=self.driver)
            self.detail_processor = G2BDetailProcessor(driver=self.driver, extractor=self.extractor)
            self.contract_extractor = G2BContractExtractor(driver=self.driver)
            self.parser = G2BParser()
            
            logger.info("크롤러 모듈 초기화 성공")
            return True
        except Exception as e:
            logger.error(f"크롤러 초기화 실패: {str(e)}")
            logger.debug(traceback.format_exc())
            return False
    
    async def close(self):
        """
        크롤러 종료 및 리소스 정리
        """
        if self.base:
            await self.base.close()
            self.driver = None
            self.wait = None
    
    async def navigate_to_main(self):
        """
        나라장터 메인 페이지로 이동
        
        Returns:
            bool: 이동 성공 여부
        """
        try:
            logger.info("나라장터 메인 페이지로 이동 시도")
            return await self.navigator.navigate_to_main()
        except Exception as e:
            logger.error(f"메인 페이지 이동 중 오류: {str(e)}")
            logger.debug(traceback.format_exc())
            return False
    
    async def navigate_to_bid_list(self):
        """
        입찰공고 목록 페이지로 이동
        
        Returns:
            bool: 이동 성공 여부
        """
        try:
            logger.info("입찰공고 목록 페이지로 이동 시도")
            return await self.navigator.navigate_to_bid_list()
        except Exception as e:
            logger.error(f"입찰공고 목록 페이지 이동 중 오류: {str(e)}")
            logger.debug(traceback.format_exc())
            return False
            
    async def setup_search_conditions(self):
        """
        검색 조건 설정
        
        Returns:
            bool: 설정 성공 여부
        """
        try:
            logger.info("검색 조건 설정 시도")
            return await self.searcher.setup_search_conditions()
        except Exception as e:
            logger.error(f"검색 조건 설정 중 오류: {str(e)}")
            logger.debug(traceback.format_exc())
            return False
    
    async def process_detail_page(self, item):
        """
        단일 항목의 상세 페이지 처리
        
        Args:
            item: 처리할 항목
            
        Returns:
            Dict: 상세 정보 딕셔너리
        """
        try:
            logger.info(f"항목 상세 페이지 처리: {item['title']}")
            
            # 상세 페이지 처리기를 통해 처리
            detail_data = await self.detail_processor.process_detail_page(item)
            
            if detail_data:
                logger.info("상세 정보 추출 성공")
                return detail_data
            else:
                logger.warning("상세 정보 추출 실패")
                return None
                
        except Exception as e:
            logger.error(f"항목 상세 페이지 처리 중 오류: {str(e)}")
            logger.debug(traceback.format_exc())
            return None

    async def search_keyword(self, keyword=None):
        """
        키워드로 입찰공고 검색 수행
        
        Args:
            keyword: 검색할 키워드 (None이면 self.keyword 사용)
        
        Returns:
            bool: 검색 성공 여부
        """
        # 매개변수로 전달받은 keyword가 있으면 해당 값 사용, 없으면 self.keyword 사용
        search_keyword = keyword if keyword is not None else self.keyword
        self.keyword = search_keyword  # 현재 키워드 업데이트
        
        try:
            logger.info(f"키워드 '{search_keyword}' 검색 시작")
            
            # 입찰공고 목록 페이지로 이동
            if not await self.navigate_to_bid_list():
                logger.error("입찰공고 목록 페이지 이동 실패")
                return False
            
            # 검색 조건 설정 및 키워드 검색 수행
            if not await self.searcher.setup_search_conditions():
                logger.warning("검색 조건 설정 실패 (계속 진행)")
            
            # 키워드 검색 수행
            if not await self.searcher.search_keyword(search_keyword):
                logger.error("키워드 검색 실패")
                return False
            
            return True
        except Exception as e:
            logger.error(f"키워드 검색 중 오류 발생: {str(e)}")
            logger.debug(traceback.format_exc())
            return False
    
    async def extract_search_results(self, max_items=1000):
        """
        검색 결과 목록에서 항목 추출
        
        Args:
            max_items: 처리할 최대 항목 수 (기본값: 1000)

        Returns:
            List: 추출된 항목 리스트
        """
        try:
            logger.info("검색 결과 항목 추출 시작")
            
            # 기본 검색 결과 항목 추출
            all_items = await self.searcher.extract_search_results()
            if not all_items:
                logger.warning("추출된 항목이 없습니다")
                return []
                
            logger.info(f"총 {len(all_items)}개 항목 추출됨")
                
            # 필터링 및 제한
            valid_items = []
            filtered_count = 0
            
            for index, item in enumerate(all_items):
                if max_items > 0 and len(valid_items) >= max_items:
                    logger.info(f"최대 항목 수({max_items})에 도달하여 처리 중단")
                    break
                            
                # 검색어와 공고명 연관성 확인
                try:
                    is_relevant = await check_relevance_with_ai(item['title'], self.keyword)
                    
                    if not is_relevant:
                        logger.info(f"항목 '{item['title']}': 검색어와 연관성 없음 (건너뜀)")
                        filtered_count += 1
                        continue
                            
                    # 마감 일자가 7일 이내인지 확인 (비활성화)
                    # if item.get('is_within_7days', False):
                    #     logger.info(f"항목 '{item['title']}': 마감일 7일 이내 (건너뜀)")
                    #     filtered_count += 1
                    #     continue
                            
                    # 유효한 항목 추가
                    valid_items.append(item)
                    logger.info(f"항목 #{len(valid_items)} 추가: {item['title']}")
                    
                except Exception as e:
                    logger.warning(f"항목 '{item['title']}' 필터링 중 오류: {str(e)}")
                
            logger.info(f"총 {len(all_items)}개 중 {len(valid_items)}개 항목 처리 대상 (필터링: {filtered_count}개)")
            return valid_items
            
        except Exception as e:
            logger.error(f"검색 결과 추출 중 오류: {str(e)}")
            logger.debug(traceback.format_exc())
            return []
    
    async def process_detail_pages(self, items):
        """
        항목들의 상세 페이지 처리
        
        Args:
            items: 처리할 항목 리스트
            
        Returns:
            List: 상세 정보가 추가된 항목 리스트
        """
        try:
            logger.info(f"상세 페이지 처리 시작 ({len(items)}개 항목)")
            
            detailed_results = []
            
            for index, item in enumerate(items):
                try:
                    logger.info(f"항목 {index+1}/{len(items)} 상세 페이지 처리: {item['title']}")
                    
                    # 상세 페이지 처리
                    detail_data = await self.process_detail_page(item)
                    
                    if detail_data:
                        # 상세 정보 병합
                        item.update(detail_data)
                        detailed_results.append(item)
                        logger.info(f"항목 {index+1} 상세 정보 추출 성공")
                    else:
                        logger.warning(f"항목 {index+1} 상세 정보 추출 실패")
                        
                except Exception as e:
                    logger.error(f"항목 {index+1} 상세 페이지 처리 중 오류: {str(e)}")
                    logger.debug(traceback.format_exc())
            
            logger.info(f"상세 페이지 처리 완료: {len(detailed_results)}/{len(items)}개 성공")
            return detailed_results
            
        except Exception as e:
            logger.error(f"상세 페이지 처리 중 오류: {str(e)}")
            logger.debug(traceback.format_exc())
            return []
    
    def _prepare_results_for_save(self, items):
        """
        저장을 위해 결과 데이터 전처리
        
        Args:
            items: 전처리할 항목 리스트
            
        Returns:
            List: 전처리된 항목 리스트
        """
        # JSON 직렬화를 위한 객체 필터링 함수
        def filter_web_elements(obj):
            """JSON 직렬화 불가능한 객체 처리"""
            if hasattr(obj, 'tag_name') or 'selenium.webdriver.remote.webelement' in str(type(obj)):
                return str(obj)  # WebElement 객체를 문자열로 변환
            elif isinstance(obj, datetime):
                return obj.isoformat()  # 날짜/시간 객체를 ISO 형식으로 변환
            elif isinstance(obj, (set, frozenset)):
                return list(obj)  # 집합을 리스트로 변환
            return str(obj)  # 그 외 직렬화 불가능 객체를 문자열로 변환
            
        # 결과 데이터 전처리
        cleaned_results = []
        for item in items:
            # WebElement 객체 및 직렬화 불가능 객체 필터링
            cleaned_item = {}
            for key, value in item.items():
                if hasattr(value, 'tag_name') or 'selenium.webdriver.remote.webelement' in str(type(value)):
                    cleaned_item[key] = str(value)
                elif isinstance(value, datetime):
                    cleaned_item[key] = value.isoformat()
                elif isinstance(value, (set, frozenset)):
                    cleaned_item[key] = list(value)
                else:
                    cleaned_item[key] = value
                
            # prompt_result가 있으면 구조화 시도
            if 'prompt_result' in cleaned_item:
                try:
                    # Gemini 응답이 이미 JSON 형태인지 확인
                    if cleaned_item['prompt_result'].strip().startswith('{') and cleaned_item['prompt_result'].strip().endswith('}'):
                        try:
                            # JSON 파싱 시도
                            parsed_json = json.loads(cleaned_item['prompt_result'])
                            cleaned_item['prompt_result_parsed'] = parsed_json
                        except json.JSONDecodeError:
                            # JSON 파싱 실패 시 텍스트 파싱 시도
                            cleaned_item['prompt_result_parsed'] = self.parser.parse_gemini_text_to_json(cleaned_item['prompt_result'])
                    else:
                        # 텍스트 형태의 응답을 구조화된 데이터로 변환
                        cleaned_item['prompt_result_parsed'] = self.parser.parse_gemini_text_to_json(cleaned_item['prompt_result'])
                except Exception as json_err:
                    logger.warning(f"Gemini 응답 변환 실패: {str(json_err)}")
                
            cleaned_results.append(cleaned_item)
            
        return cleaned_results

    def save_results(self, items, keyword=None):
        """
        결과 저장
        
        Args:
            items: 저장할 항목 리스트
            keyword: 검색 키워드 (None이면 self.keyword 사용)
            
        Returns:
            str: 저장된 파일 경로
        """
        try:
            # 저장할 키워드 결정
            save_keyword = keyword if keyword is not None else self.keyword
            
            # 타임스탬프 생성
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # 저장 파일명 생성
            result_filename = f"search_results_{save_keyword}_{timestamp}.json"
            result_file_path = RESULTS_DIR / result_filename
            
            # 결과 데이터 전처리
            cleaned_results = self._prepare_results_for_save(items)
            
            # JSON 파일로 저장
            with open(result_file_path, 'w', encoding='utf-8') as f:
                json.dump(cleaned_results, f, ensure_ascii=False, indent=2)
            
            logger.info(f"검색 결과 저장 완료: {result_file_path}")
            
            # Gemini 분석 결과만 별도 파일로 저장
            gemini_results = []
            for item in cleaned_results:
                if 'prompt_result_parsed' in item:
                    gemini_results.append({
                        'title': item.get('title', '제목 없음'),
                        'bid_number': item.get('bid_number', '번호 없음'),
                        'result': item['prompt_result_parsed']
                    })
            
            if gemini_results:
                gemini_filename = f"gemini_results_{save_keyword}_{timestamp}.json"
                gemini_file_path = RESULTS_DIR / gemini_filename
                
                with open(gemini_file_path, 'w', encoding='utf-8') as f:
                    json.dump(gemini_results, f, ensure_ascii=False, indent=2)
                
                logger.info(f"Gemini 분석 결과 저장 완료: {gemini_file_path}")
            
            return str(result_file_path)
            
        except Exception as e:
            logger.error(f"결과 저장 중 오류: {str(e)}")
            logger.debug(traceback.format_exc())
            return None

    async def run(self, keyword="AI", max_items=10000):
        """
        전체 크롤링 작업 실행
        
        Args:
            keyword: 검색 키워드
            max_items: 처리할 최대 항목 수
            
        Returns:
            str: 저장된 결과 파일 경로 또는 None
        """
        try:
            # 키워드 설정
            self.keyword = keyword
            
            logger.info(f"=== 나라장터 크롤링 시작 (키워드: {keyword}, 최대 항목: {max_items}) ===")
            
            # 초기화
            if not await self.initialize():
                logger.error("크롤러 초기화 실패")
                return None
            
            # 키워드 검색
            if not await self.search_keyword(keyword):
                logger.error("키워드 검색 실패")
                return None
            
            # 검색 결과 추출
            search_results = await self.extract_search_results(max_items)
            if not search_results:
                logger.warning("검색 결과 없음 또는 추출 실패")
                return None

            # 상세 페이지 처리
            detailed_results = await self.process_detail_pages(search_results)
            
            # 결과 저장
            result_file = self.save_results(detailed_results, keyword)
            
            logger.info(f"=== 나라장터 크롤링 완료 (처리 항목: {len(detailed_results)}) ===")
            return result_file
            
        except Exception as e:
            logger.error(f"크롤링 실행 중 오류: {str(e)}")
            logger.debug(traceback.format_exc())
            return None
        finally:
            # 리소스 정리
            await self.close()

# 직접 실행 시
if __name__ == "__main__":
    # Windows에서 올바른 이벤트 루프 정책 설정
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # 명령행 인자 처리
    import argparse
    parser = argparse.ArgumentParser(description='나라장터 크롤러')
    parser.add_argument('--keyword', '-k', type=str, default='AI', help='검색 키워드')
    parser.add_argument('--max_items', '-m', type=int, default=100, help='처리할 최대 항목 수')
    parser.add_argument('--headless', '-H', action='store_true', help='헤드리스 모드 사용')
    args = parser.parse_args()
    
    # 비동기 메인 함수
    async def main():
        # 크롤러 인스턴스 생성
        crawler = G2BCrawler(headless=args.headless)
        
        # 크롤링 실행
        result_file = await crawler.run(keyword=args.keyword, max_items=args.max_items)
        
        # 결과 출력
        if result_file:
            print(f"크롤링 결과가 저장되었습니다: {result_file}")
        else:
            print("크롤링 실패")
    
    # 메인 함수 실행
    asyncio.run(main()) 