import logging
import traceback
import asyncio
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from datetime import datetime
from urllib.parse import urlparse, urljoin
import json
import re

# 로거 설정
logger = logging.getLogger(__name__)

class G2BDetailProcessor:
    """나라장터 상세 페이지 처리 클래스"""
    
    def __init__(self, driver, extractor=None):
        """
        초기화
        
        Args:
            driver: Selenium WebDriver 인스턴스
            extractor: JavaScript 값 추출을 위한 G2BExtractor 인스턴스 (선택사항)
        """
        self.driver = driver
        self.extractor = extractor
        self.search_results_url = None  # 검색 결과 페이지 URL 저장용
        self.recovery_attempts = 0  # 복구 시도 횟수 추적용
    
    async def process_detail_page(self, item):
        """
        항목의 상세 페이지 처리
        
        Args:
            item: 처리할 항목 데이터
            
        Returns:
            상세 정보 (성공 시) 또는 None (실패 시)
        """
        try:
            logger.info(f"상세 페이지 처리 시작 - {item['title']}")
            
            # 실제 행 인덱스 값 획득
            row_index = item.get('index', 0)
            
            # 상세 페이지 이동 - 셀 ID를 사용하여 직접 접근
            try:
                # 현재 페이지의 행에 맞는 셀 ID를 생성
                cell_id = f"mf_wfm_container_tacBidPbancLst_contents_tab2_body_gridView1_cell_{row_index}_6"
                title_element = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.ID, cell_id))
                )
                
                # 셀 내부의 링크 찾기
                link_element = title_element.find_element(By.TAG_NAME, "a")
                
                # 직접 클릭
                link_element.click()
                logger.info("셀 ID로 링크 클릭 성공")
            except Exception as e:
                logger.error(f"상세 페이지 이동 실패: {str(e)}")
                return None
            
            # 상세 페이지 로딩 대기
            await asyncio.sleep(3)
            
            # 상세 페이지에서 정보 추출
            detail_data = await self._extract_detail_data()
            
            # 목록으로 돌아가기 - 항상 브라우저 뒤로가기 사용
            self.driver.back()
            logger.info("브라우저 뒤로가기로 목록 페이지 복귀")
            
            # 목록 페이지 로딩 대기
            await asyncio.sleep(3)
            
            return detail_data
            
        except Exception as e:
            logger.error(f"상세 페이지 처리 중 오류: {str(e)}")
            logger.debug(traceback.format_exc())
            
            # 오류 발생 시 브라우저 뒤로가기 시도
            try:
                self.driver.back()
                await asyncio.sleep(2)
                logger.info("오류 복구: 브라우저 뒤로가기 실행")
            except Exception as back_error:
                logger.error(f"뒤로가기 실패: {str(back_error)}")
                      
    async def _extract_detail_data(self):
        """
        상세 페이지에서 데이터 추출
        
        Returns:
            Dict: 추출된 데이터
        """
        try:
            logger.info("상세 페이지 데이터 추출 시작")
            
            # 현재 URL이 실제로 상세 페이지인지 확인
            current_url = self.driver.current_url
            if not ("Detail" in current_url or "detail" in current_url or "inqire" in current_url):
                logger.warning(f"현재 URL이 상세 페이지가 아닌 것으로 보임: {current_url}")
            
            # 페이지 로딩 대기
            await asyncio.sleep(2)
            
            # 데이터 컨테이너 초기화
            detail_data = {}
            
            # 방법 1: 표준 HTML 테이블에서 데이터 추출 시도
            try:
                # 상세 정보 테이블 찾기
                tables = self.driver.find_elements(By.CSS_SELECTOR, ".table_list, .detail_table, .bid_table")
                
                if tables:
                    logger.info(f"{len(tables)}개의 정보 테이블 발견")
                    
                    # 각 테이블에서 데이터 추출
                    for table_idx, table in enumerate(tables):
                        try:
                            rows = table.find_elements(By.TAG_NAME, "tr")
                            logger.info(f"테이블 {table_idx+1}: {len(rows)}개 행 발견")
                            
                            for row in rows:
                                try:
                                    # 제목 셀(th)과 데이터 셀(td) 찾기
                                    th_cells = row.find_elements(By.TAG_NAME, "th")
                                    td_cells = row.find_elements(By.TAG_NAME, "td")
                                    
                                    if th_cells and td_cells:
                                        field_name = th_cells[0].text.strip()
                                        field_value = td_cells[0].text.strip()
                                        
                                        # 필드명 정제 및 데이터 저장
                                        field_name = field_name.replace(":", "").strip()
                                        if field_name and field_value:
                                            detail_data[field_name] = field_value
                                            logger.debug(f"필드 추출: {field_name} = {field_value[:30]}...")
                                except Exception as row_err:
                                    logger.debug(f"행 처리 중 오류 (무시): {str(row_err)}")
                                    continue
                        except Exception as table_err:
                            logger.debug(f"테이블 {table_idx+1} 처리 중 오류 (무시): {str(table_err)}")
                            continue
                else:
                    logger.warning("표준 정보 테이블을 찾을 수 없음")
            except Exception as tables_err:
                logger.warning(f"HTML 테이블 추출 중 오류: {str(tables_err)}")
            
            # 방법 2: 특정 ID 패턴을 가진 요소에서 데이터 추출 시도
            try:
                # 나라장터 특유의 ID 패턴을 가진 요소들 찾기
                detail_elements = self.driver.find_elements(By.CSS_SELECTOR, 
                    "[id*='detail'], [id*='Detail'], [id*='Info'], [id*='info'], [class*='detail'], [class*='info']")
                
                if detail_elements:
                    logger.info(f"{len(detail_elements)}개의 ID 패턴 요소 발견")
                    
                    for element in detail_elements:
                        try:
                            # 요소 ID와 텍스트 가져오기
                            element_id = element.get_attribute("id") or ""
                            element_text = element.text.strip()
                            
                            if element_text and ":" in element_text:
                                # 텍스트에 "필드명: 값" 패턴이 있는 경우 분리
                                parts = element_text.split(":", 1)
                                field_name = parts[0].strip()
                                field_value = parts[1].strip() if len(parts) > 1 else ""
                                
                                if field_name and field_value:
                                    detail_data[field_name] = field_value
                                    logger.debug(f"ID 요소에서 필드 추출: {field_name} = {field_value[:30]}...")
                        except Exception as element_err:
                            logger.debug(f"요소 처리 중 오류 (무시): {str(element_err)}")
                            continue
                else:
                    logger.warning("ID 패턴 요소를 찾을 수 없음")
            except Exception as id_err:
                logger.warning(f"ID 패턴 요소 추출 중 오류: {str(id_err)}")
            
            # 결과 확인
            if detail_data:
                logger.info(f"총 {len(detail_data)}개 필드 추출 성공")
                return detail_data
            else:
                logger.warning("추출된 데이터 없음")
                return None
                
        except Exception as e:
            logger.error(f"상세 데이터 추출 중 오류: {str(e)}")
            logger.debug(traceback.format_exc())
            return None

