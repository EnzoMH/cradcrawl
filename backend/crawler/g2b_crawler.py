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
import uuid
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
from backend.crawler.g2b_contract import G2BContractAnalyzer
from backend.crawler.g2b_parser import G2BParser
from backend.crawler.g2b_extractor import G2BExtractor

# 모델 임포트 추가
from backend.models import BidItem, SearchResult, BidStatus

# 유틸리티 모듈 임포트
from backend.utils.ai_helpers import extract_with_gemini_text, check_relevance_with_ai, ai_model_manager
from backend.utils.parsing_helpers import extract_detail_page_data_from_soup

# 로깅 설정
logger = logging.getLogger("g2b-crawler")

# 환경 변수 확인
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
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
        
        # 검색 결과 모델 초기화
        self.search_result_model = None
        
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
            
            # 각 모듈 인스턴스 초기화 (driver와 wait 객체만 전달)
            self.navigator = G2BNavigator(driver=self.driver, wait=self.wait)
            self.searcher = G2BSearcher(driver=self.driver, wait=self.wait)
            self.extractor = G2BExtractor(driver=self.driver)
            self.detail_processor = G2BDetailProcessor(driver=self.driver, extractor=self.extractor)
            self.parser = G2BParser()
            
            logger.info("크롤러 모듈 초기화 성공")
            return True
        except Exception as e:
            logger.error(f"크롤러 초기화 실패: {str(e)}")
            logger.debug(traceback.format_exc())
            return False
    
    async def close(self):
        """크롤러 종료 및 리소스 정리"""
        if self.base:
            await self.base.close()
            self.driver = None
            self.wait = None
            # 페이지 상태도 초기화
            if hasattr(self.base, 'current_page'):
                self.base.current_page = None
    
    async def navigate_to_main(self):
        """나라장터 메인 페이지로 이동"""
        try:
            logger.info("나라장터 메인 페이지로 이동 시도")
            result = await self.navigator.navigate_to_main()
            if result:
                self.base.set_page_state("main")
            return result
        except Exception as e:
            logger.error(f"메인 페이지 이동 중 오류: {str(e)}")
            logger.debug(traceback.format_exc())
            return False
    
    async def navigate_to_bid_list(self):
        """입찰공고 목록 페이지로 이동"""
        try:
            # 이미 입찰공고 목록 페이지에 있는 경우 건너뛰기
            if self.base.is_on_page("bid_list"):
                logger.info("이미 입찰공고 목록 페이지에 있습니다.")
                return True
                
            logger.info("입찰공고 목록 페이지로 이동 시도")
            result = await self.navigator.navigate_to_bid_list()
            if result:
                self.base.set_page_state("bid_list")
            return result
        except Exception as e:
            logger.error(f"입찰공고 목록 페이지 이동 중 오류: {str(e)}")
            logger.debug(traceback.format_exc())
            return False
            
    async def setup_search_conditions(self):
        """검색 조건 설정"""
        try:
            logger.info("검색 조건 설정 시도")
            return await self.searcher.setup_search_conditions()
        except Exception as e:
            logger.error(f"검색 조건 설정 중 오류: {str(e)}")
            logger.debug(traceback.format_exc())
            return False
    
    async def search_keyword(self, keyword=None, skip_navigation=False):
        """
        키워드로 입찰공고 검색 수행 (전체 흐름 조율)
        
        Args:
            keyword: 검색할 키워드
            skip_navigation: 페이지 이동 단계를 건너뛸지 여부
        
        Returns:
            bool: 검색 성공 여부
        """
        # 매개변수로 전달받은 keyword가 있으면 해당 값 사용, 없으면 self.keyword 사용
        search_keyword = keyword if keyword is not None else self.keyword
        self.keyword = search_keyword  # 현재 키워드 업데이트
        
        try:
            logger.info(f"키워드 '{search_keyword}' 검색 시작")
            
            # 1. 페이지 이동 (G2BCrawler가 직접 담당)
            if not skip_navigation:
                if not self.base.is_on_page("bid_list"):
                    logger.info("입찰공고 목록 페이지로 이동합니다.")
                    if not await self.navigator.navigate_to_bid_list():
                        logger.error("입찰공고 목록 페이지 이동 실패")
                        return False
                    
                    # 페이지 이동 성공 시 상태 설정
                    self.base.set_page_state("bid_list")
                else:
                    logger.info("이미 입찰공고 목록 페이지에 있습니다.")
            
            # 2. 검색 조건 설정
            if not await self.searcher.setup_search_conditions():
                logger.warning("검색 조건 설정 실패 (계속 진행)")
            
            # 3. 실제 검색 수행 (G2BSearcher에 위임)
            if not await self.searcher.search_keyword(search_keyword):
                logger.error("키워드 검색 실패")
                return False
            
            # 4. 검색 결과 페이지 상태 설정 (G2BCrawler가 담당)
            self.base.set_page_state("search_results")
            return True
        except Exception as e:
            logger.error(f"키워드 검색 중 오류 발생: {str(e)}")
            logger.debug(traceback.format_exc())
            return False
    
    async def process_detail_page(self, item):
        """단일 항목의 상세 페이지 처리"""
        try:
            logger.info(f"항목 상세 페이지 처리: {item['title']}")
            
            # 상세 페이지 HTML 소스 가져오기
            page_source = None
            try:
                page_source = self.detail_processor.driver.page_source
            except Exception as source_err:
                logger.warning(f"페이지 소스 가져오기 실패: {str(source_err)}")
                
            if not page_source:
                logger.error("페이지 소스를 가져올 수 없습니다.")
                return {'title': item.get('title', ''), 'error': '페이지 소스 없음'}
                
            # G2BParser를 활용한 상세 정보 추출
            bid_number = item.get('bid_number', '')
            bid_title = item.get('title', '')
            
            # G2BParser의 parse_detail_page 메서드 활용
            detail_data = await self.parser.parse_detail_page(
                page_source, bid_number, bid_title
            )
            
            # 결과가 없는 경우 기존 방식으로 백업 추출
            if not detail_data:
                logger.info("G2BParser 추출 실패, 기존 방식 시도")
                # 기존 코드 유지 (G2BContractAnalyzer 및 detail_processor)
                
            # 기본 메타데이터 추가
            if 'title' not in detail_data and 'title' in item:
                detail_data['title'] = item['title']
            if 'bid_number' not in detail_data and 'bid_number' in item:
                detail_data['bid_number'] = item['bid_number']
            if 'keyword' not in detail_data and 'keyword' in item:
                detail_data['keyword'] = item['keyword']
            
            # 추출 시간 및 URL 정보 추가
            detail_data['extraction_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            detail_data['detail_url'] = self.detail_processor.driver.current_url
            
            # 모델 필드 매핑 위해 필요한 필드 이름 확인 및 매핑
            # bid_method, contract_method 등 필드 이름 통일
            if 'contract_method' in detail_data and 'bid_method' not in detail_data:
                detail_data['bid_method'] = detail_data['contract_method']
            
            # 페이지 상태 추적 업데이트
            self.base.set_page_state("detail_page")
            
            logger.info(f"상세 정보 추출 성공: {len(detail_data)} 필드")
            return detail_data
                
        except Exception as e:
            logger.error(f"항목 상세 페이지 처리 중 오류: {str(e)}")
            logger.debug(traceback.format_exc())
            return {'title': item.get('title', ''), 'error': str(e)}
 
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
            
            for index, item in enumerate(all_items):
                if max_items > 0 and len(valid_items) >= max_items:
                    logger.info(f"최대 항목 수({max_items})에 도달하여 처리 중단")
                    break
                
                # 연관성 확인 코드 제거 - 모든 항목을 유효한 것으로 처리
                valid_items.append(item)
                logger.info(f"항목 #{len(valid_items)} 추가: {item['title']}")
            
            logger.info(f"총 {len(all_items)}개 중 {len(valid_items)}개 항목 처리 대상")
            
            # 딕셔너리를 BidItem 모델로 변환하여 저장
            model_items = await self._convert_dict_results_to_model(valid_items)
            
            # 검색 결과 모델 생성
            self.search_result_model = SearchResult(
                keyword=self.keyword,
                total_count=len(valid_items),
                items=model_items,
            )
            
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

    def _convert_to_bid_item(self, item_dict: Dict[str, Any]) -> BidItem:
        """
        딕셔너리를 BidItem 모델로 변환
        
        Args:
            item_dict: 변환할 항목 딕셔너리
            
        Returns:
            BidItem: 변환된 모델 인스턴스
        """
        try:
            # ID 필드가 없으면 생성
            if 'id' not in item_dict or not item_dict['id']:
                item_dict['id'] = str(uuid.uuid4())
            
            # 필수 필드 확인
            bid_number = item_dict.get('bid_number', '')
            if not bid_number:
                bid_number = item_dict.get('number', str(uuid.uuid4()))
                
            bid_title = item_dict.get('title', '')
            if not bid_title:
                bid_title = item_dict.get('bid_title', '제목 없음')
            
            # 상태 변환
            status_str = item_dict.get('status', '')
            status = BidStatus.UNKNOWN
            
            if status_str:
                if '공고중' in status_str:
                    status = BidStatus.OPEN
                elif '마감' in status_str:
                    status = BidStatus.CLOSED
                elif '낙찰' in status_str:
                    status = BidStatus.AWARDED
                elif '취소' in status_str:
                    status = BidStatus.CANCELLED
            
            # 필드 매핑
            bid_item = BidItem(
                id=item_dict.get('id', str(uuid.uuid4())),
                bid_number=bid_number,
                bid_title=bid_title,
                organization=item_dict.get('department') or item_dict.get('organization') or item_dict.get('agency', None),
                bid_method=item_dict.get('bid_method', None),
                bid_type=item_dict.get('bid_type', None),
                date_start=item_dict.get('date_start') or item_dict.get('start_date', None),
                date_end=item_dict.get('date_end') or item_dict.get('deadline', None),
                status=status,
                detail_url=item_dict.get('detail_url', None),
                budget=item_dict.get('budget', None),
                estimated_price=item_dict.get('estimated_price', None),
                contact_info=item_dict.get('contact_info', None),
                requirements=item_dict.get('qualification', None),
                additional_info=item_dict.get('additional_info', {})
            )
            
            return bid_item
            
        except Exception as e:
            logger.error(f"BidItem 모델 변환 중 오류: {str(e)}")
            logger.debug(traceback.format_exc())
            
            # 오류 발생시 기본 값으로 생성
            return BidItem(
                id=str(uuid.uuid4()),
                bid_number=str(uuid.uuid4()),
                bid_title=item_dict.get('title', '변환 오류') or '변환 오류'
            )

    async def _convert_dict_results_to_model(self, items: List[Dict[str, Any]]) -> List[BidItem]:
        """
        딕셔너리 결과 목록을 BidItem 모델 목록으로 변환
        
        Args:
            items: 변환할 항목 딕셔너리 목록
            
        Returns:
            List[BidItem]: 변환된 모델 인스턴스 목록
        """
        model_items = []
        
        for item_dict in items:
            try:
                bid_item = self._convert_to_bid_item(item_dict)
                model_items.append(bid_item)
            except Exception as e:
                logger.error(f"항목 변환 중 오류: {str(e)}")
        
        return model_items

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
            
            # 모델 기반 결과 저장
            if self.search_result_model:
                # 모델을 JSON으로 직렬화
                model_json = self.search_result_model.model_dump_json(indent=2)
                
                # 모델 저장 파일명 생성
                model_filename = f"model_results_{save_keyword}_{timestamp}.json"
                model_file_path = RESULTS_DIR / model_filename
                
                # 모델 저장
                with open(model_file_path, 'w', encoding='utf-8') as f:
                    f.write(model_json)
                
                logger.info(f"모델 기반 검색 결과 저장 완료: {model_file_path}")
            
            # 원래의 JSON 파일 저장 (역호환성 유지)
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

    async def get_model_results(self) -> List[BidItem]:
        """
        BidItem 모델 형태의 결과 목록 반환
        
        Returns:
            List[BidItem]: 모델 기반 결과 목록
        """
        if self.search_result_model and self.search_result_model.items:
            return self.search_result_model.items
        
        # 모델이 없는 경우 현재 결과를 변환하여 반환
        return await self._convert_dict_results_to_model(self.results)
