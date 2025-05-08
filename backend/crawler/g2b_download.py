"""
나라장터 파일 다운로더 모듈

나라장터 첨부 파일 다운로드 기능을 제공합니다.
"""

import os
import time
import logging
import traceback
from pathlib import Path
from typing import List, Dict, Any, Optional

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException

# 로거 설정
logger = logging.getLogger("backend.crawler.download")

class G2BDownloader:
    """나라장터 첨부파일 다운로더 클래스"""
    
    def __init__(self, driver, wait=None):
        """
        초기화
        
        Args:
            driver: Selenium WebDriver 인스턴스
            wait: WebDriverWait 인스턴스 (None이면 기본값 사용)
        """
        self.driver = driver
        self.wait = wait if wait else self._create_default_wait()
        
        # 다운로드 디렉토리 설정
        self.download_dir = Path("downloads")
        self.download_dir.mkdir(exist_ok=True)
    
    def _create_default_wait(self, timeout=10):
        """기본 WebDriverWait 생성"""
        from selenium.webdriver.support.ui import WebDriverWait
        return WebDriverWait(self.driver, timeout)
    
    async def download_attachments(self, bid_number: str) -> List[str]:
        """
        공고의 첨부파일 다운로드
        
        Args:
            bid_number: 입찰공고 번호
            
        Returns:
            List[str]: 다운로드된 파일 경로 목록
        """
        try:
            logger.info(f"입찰공고 {bid_number}의 첨부파일 다운로드 시작")
            
            # 첨부파일 목록 확인
            attachments = []
            try:
                # 첨부파일 테이블 또는 첨부파일 링크 찾기
                file_links = self.driver.find_elements(By.CSS_SELECTOR, "a.file_link, a[title*='다운로드'], a[onclick*='download']")
                
                if not file_links:
                    logger.info("첨부파일이 없거나 찾을 수 없습니다.")
                    return []
                
                logger.info(f"{len(file_links)}개의 첨부파일 링크 발견")
                
                # 각 첨부파일 다운로드
                for idx, link in enumerate(file_links):
                    try:
                        file_name = link.text.strip() or f"attachment_{idx+1}"
                        logger.info(f"첨부파일 다운로드 시도: {file_name}")
                        
                        # 다운로드 링크 클릭
                        link.click()
                        time.sleep(2)  # 다운로드 시작 대기
                        
                        # 다운로드된 파일 경로 추정 (브라우저 설정에 따라 다를 수 있음)
                        expected_path = self.download_dir / file_name
                        attachments.append(str(expected_path))
                        
                    except Exception as e:
                        logger.warning(f"파일 '{file_name}' 다운로드 중 오류: {str(e)}")
                        continue
                
            except NoSuchElementException:
                logger.info("첨부파일 목록을 찾을 수 없습니다.")
            except WebDriverException as e:
                logger.warning(f"첨부파일 접근 중 드라이버 오류: {str(e)}")
            
            return attachments
            
        except Exception as e:
            logger.error(f"첨부파일 다운로드 중 오류: {str(e)}")
            logger.debug(traceback.format_exc())
            return []
    
    async def download_contract_files(self, contract_number: str) -> List[str]:
        """
        계약 관련 파일 다운로드
        
        Args:
            contract_number: 계약 번호
            
        Returns:
            List[str]: 다운로드된 파일 경로 목록
        """
        try:
            logger.info(f"계약 {contract_number}의 관련 파일 다운로드 시작")
            
            # 계약 관련 파일 목록 확인
            contract_files = []
            try:
                # 계약 파일 링크 찾기
                file_links = self.driver.find_elements(By.CSS_SELECTOR, "a.file_link, a[title*='다운로드'], a[onclick*='download']")
                
                if not file_links:
                    logger.info("계약 관련 파일이 없거나 찾을 수 없습니다.")
                    return []
                
                logger.info(f"{len(file_links)}개의 계약 관련 파일 링크 발견")
                
                # 각 파일 다운로드
                for idx, link in enumerate(file_links):
                    try:
                        file_name = link.text.strip() or f"contract_{idx+1}"
                        logger.info(f"계약 관련 파일 다운로드 시도: {file_name}")
                        
                        # 다운로드 링크 클릭
                        link.click()
                        time.sleep(2)  # 다운로드 시작 대기
                        
                        # 다운로드된 파일 경로 추정
                        expected_path = self.download_dir / file_name
                        contract_files.append(str(expected_path))
                        
                    except Exception as e:
                        logger.warning(f"파일 '{file_name}' 다운로드 중 오류: {str(e)}")
                        continue
                
            except NoSuchElementException:
                logger.info("계약 관련 파일 목록을 찾을 수 없습니다.")
            except WebDriverException as e:
                logger.warning(f"계약 관련 파일 접근 중 드라이버 오류: {str(e)}")
            
            return contract_files
            
        except Exception as e:
            logger.error(f"계약 관련 파일 다운로드 중 오류: {str(e)}")
            logger.debug(traceback.format_exc())
            return []
