import logging
import traceback
import asyncio
from bs4 import BeautifulSoup
from datetime import datetime
import os

# 로거 설정
logger = logging.getLogger(__name__)

# Gemini API 키 설정
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

class G2BContractAnalyzer:
    """나라장터 계약 정보 분석 클래스"""
    
    def __init__(self):
        """초기화"""
        self.logger = logging.getLogger(__name__)
    
    import logging
import traceback
import asyncio
from bs4 import BeautifulSoup
from datetime import datetime
import os
import json

# 로거 설정
logger = logging.getLogger(__name__)

# Gemini API 키 설정
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# AI 헬퍼 모듈 임포트
from backend.utils.ai_helpers import extract_with_gemini_text, parse_gemini_text_to_json

class G2BContractAnalyzer:
    """나라장터 계약 정보 분석 클래스"""
    
    def __init__(self):
        """초기화"""
        self.logger = logging.getLogger(__name__)
    
    async def extract_contract_details(self, soup, logger=None):
        """
        세부 계약 정보 추출 함수
        
        Args:
            soup: BeautifulSoup 객체
            logger: 외부에서 제공된 로거 (선택사항)
            
        Returns:
            dict: 추출된 계약 상세 정보
        """
        log = logger or self.logger
        try:
            log.info("G2BContractAnalyzer로 계약 상세 정보 추출 중...")
            contract_details = {}
            
            # 공고명/입찰공고 제목 추출 - 다양한 클래스와 태그 조합 시도
            title_selectors = [
                'h1.tit_detail', 'h2.tit_detail', 'h3.tit_detail',
                'div.bid_detail_info h1', 'div.bid_detail_info h2',
                'td.bidTitle', 'td.tdBidTitle',
                'div.detail_title', 'p.detail_title',
                'title', '.detail-title', '#bidNtceDtlForm', '.bidNtceDtl'
            ]
            
            # 다양한 선택자로 제목 찾기 시도
            for selector in title_selectors:
                title_elem = soup.select_one(selector)
                if title_elem and title_elem.text and len(title_elem.text.strip()) > 5:
                    # models.py의 BidItem 클래스에 맞게 bid_title로 저장
                    contract_details['bid_title'] = title_elem.text.strip()
                    log.info(f"공고명 추출: {contract_details['bid_title']}")
                    break
            
            # 테이블에서 정보 추출
            tables = soup.find_all('table')
            for table in tables:
                rows = table.find_all('tr')
                    for row in rows:
                    headers = row.find_all('th')
                    values = row.find_all('td')
                    
                    for i, header in enumerate(headers):
                        if i < len(values):
                            header_text = header.get_text(strip=True)
                            value_text = values[i].get_text(strip=True)
                            
                            # 필드 매핑 - models.py와 일치하도록 수정
                                if any(keyword in header_text for keyword in ["계약방법", "계약형태", "계약구분"]):
                                # contract_method -> bid_method 매핑
                                contract_details["bid_method"] = value_text
                                log.info(f"계약방법(bid_method) 추출: {value_text}")
                            elif any(keyword in header_text for keyword in ["입찰방법", "낙찰방법", "경쟁방법"]):
                                # bidding_method -> bid_type으로 매핑
                                contract_details["bid_type"] = value_text
                                log.info(f"입찰방법(bid_type) 추출: {value_text}")
                            elif any(keyword in header_text for keyword in ["추정가격", "예정가격", "기초금액"]):
                                    contract_details["estimated_price"] = value_text
                                    log.info(f"추정가격 추출: {value_text}")
                            elif any(keyword in header_text for keyword in ["계약기간", "이행기간", "납품기한"]):
                                # contract_period는 additional_info에 저장
                                if 'additional_info' not in contract_details:
                                    contract_details['additional_info'] = {}
                                contract_details['additional_info']['contract_period'] = value_text
                                    log.info(f"계약기간 추출: {value_text}")
                                elif any(keyword in header_text for keyword in ["납품장소", "이행장소", "설치장소"]):
                                # delivery_location은 additional_info에 저장
                                if 'additional_info' not in contract_details:
                                    contract_details['additional_info'] = {}
                                contract_details['additional_info']['delivery_location'] = value_text
                                    log.info(f"납품장소 추출: {value_text}")
                            elif any(keyword in header_text for keyword in ["참가자격", "입찰참가자격", "참가제한"]):
                                # qualification -> requirements 매핑
                                contract_details["requirements"] = value_text
                                log.info(f"참가자격(requirements) 추출: {value_text}")
                            elif any(keyword in header_text for keyword in ["공고기관", "발주기관", "수요기관"]):
                                contract_details["organization"] = value_text
                                log.info(f"공고기관 추출: {value_text}")
                            elif any(keyword in header_text for keyword in ["공고일", "입찰공고일"]):
                                contract_details["date_start"] = value_text
                                log.info(f"공고일자 추출: {value_text}")
                            elif any(keyword in header_text for keyword in ["마감일", "입찰마감일"]):
                                contract_details["date_end"] = value_text
                                log.info(f"마감일자 추출: {value_text}")
            
            # 첨부파일 목록 추출
            file_attachments = []
            file_links = soup.select("a[href*='fileDown']")
            for link in file_links:
                file_name = link.get_text(strip=True)
                if file_name:
                    file_attachments.append(file_name)
            
            if file_attachments:
                # file_attachments는 additional_info에 저장
                if 'additional_info' not in contract_details:
                    contract_details['additional_info'] = {}
                contract_details['additional_info']['file_attachments'] = file_attachments
                log.info(f"첨부파일 {len(file_attachments)}개 추출")
            
            # 페이지 URL 추출
            for link in soup.find_all("meta", {"property": "og:url"}):
                if link.get("content"):
                    contract_details["detail_url"] = link.get("content")
                    log.info(f"상세 페이지 URL 추출: {contract_details['detail_url']}")
                    break
            
            # AI를 사용한 추가 정보 추출 시도
            try:
                # HTML을 텍스트로 변환
                html_text = str(soup)
                
                # 파일 첨부 정보 포맷팅
                file_info = ""
                if file_attachments:
                    file_info += "[파일첨부]\n"
                    for file_name in file_attachments:
                        file_info += f"- {file_name}\n"
                
                # Gemini 프롬프트 템플릿 구성
                prompt_template = """
입찰 상세 정보 추출 전문가로서, 다음 HTML 정보에서 중요 정보를 추출해주세요.

다음은 입찰공고 상세페이지의 테이블 데이터와 전체 페이지 텍스트입니다:

            {text_content}

다음 중요 정보를 확인하여 저장해주세요.(JSON 형식으로 응답 X)
1. 게시일시
2. 입찰공고번호
3. 공고명
4. 입찰방식
5. 낙찰방법
6. 계약방법
7. 계약구분
8. 공동계약 및 구성방식(컨소시엄 여부)
9. 실적제한 여부, 제한여부
10. 가격과 관련된 모든정보(예가방법, 사업금액, 배정에산, 추정가격)
11. 기관담당자정보(담당자 이름, 팩스번호, 전화번호)
12. 계약기간/납품기한
13. 납품장소
14. 참가자격
15. 파일첨부

위 형식대로 각 항목에 해당하는 정보를 추출해주세요. 정보가 없는 경우 "정보 없음"으로 표시해주세요.
JSON 형식이 아닌 일반 텍스트로 응답해주세요.
"""
                
                # 너무 긴 HTML을 전달하지 않기 위해 길이 제한
                max_length = 30000  # Gemini가 처리할 수 있는 최대 길이보다 약간 적게 설정
                html_text_trimmed = html_text
                if len(html_text) > max_length:
                    # 텍스트가 너무 길면 잘라냄
                    html_text_trimmed = html_text[:int(max_length * 0.8)] + "\n...[잘림]...\n" + html_text[-int(max_length * 0.2):]
                    log.warning(f"HTML 텍스트가 너무 길어 {len(html_text)}자에서 {len(html_text_trimmed)}자로 잘랐습니다.")
                
                # 첨부파일 정보 추가
                html_text_trimmed += "\n\n" + file_info
            
            # Gemini API 호출
                log.info("AI 모델을 사용하여 상세 정보 추출 시도")
                gemini_response = await extract_with_gemini_text(html_text_trimmed, prompt_template)
                
                if gemini_response:
                    # Gemini 응답을 contract_details에 저장
                    if 'additional_info' not in contract_details:
                        contract_details['additional_info'] = {}
                    
                    # 원본 응답 저장
                    contract_details['additional_info']['ai_analysis'] = gemini_response
                    
                    # 응답 파싱 및 구조화
                    parsed_result = parse_gemini_text_to_json(gemini_response)
                    contract_details['additional_info']['ai_structured'] = parsed_result
                    
                    # BidItem 모델에 맞게 핵심 필드 매핑
                    for key, value in parsed_result.items():
                        # 이미 값이 있는 경우 추가 또는 업데이트하지 않음
                        key_lower = key.lower()
                        
                        # 공고명
                        if ('공고명' in key_lower or '입찰공고' in key_lower) and not contract_details.get('bid_title'):
                            contract_details['bid_title'] = value
                            log.info(f"AI 분석 - 공고명 추출: {value}")
                            
                        # 계약방법/입찰방식
                        elif ('계약방법' in key_lower or '계약형태' in key_lower) and not contract_details.get('bid_method'):
                            contract_details['bid_method'] = value
                            log.info(f"AI 분석 - 계약방법 추출: {value}")
                            
                        # 입찰방식/낙찰방법
                        elif ('입찰방식' in key_lower or '낙찰방법' in key_lower) and not contract_details.get('bid_type'):
                            contract_details['bid_type'] = value
                            log.info(f"AI 분석 - 입찰방식 추출: {value}")
                            
                        # 추정가격
                        elif ('추정가격' in key_lower or '사업금액' in key_lower or '기초금액' in key_lower) and not contract_details.get('estimated_price'):
                            contract_details['estimated_price'] = value
                            log.info(f"AI 분석 - 추정가격 추출: {value}")
                        
                        # 공고기관
                        elif ('공고기관' in key_lower or '발주기관' in key_lower or '수요기관' in key_lower) and not contract_details.get('organization'):
                            contract_details['organization'] = value
                            log.info(f"AI 분석 - 공고기관 추출: {value}")
                        
                        # 참가자격
                        elif ('참가자격' in key_lower or '입찰참가' in key_lower) and not contract_details.get('requirements'):
                            contract_details['requirements'] = value
                            log.info(f"AI 분석 - 참가자격 추출: {value}")
                        
                        # 계약기간/납품기한 - additional_info에 저장
                        elif ('계약기간' in key_lower or '납품기한' in key_lower) and not contract_details.get('additional_info', {}).get('contract_period'):
                            if 'additional_info' not in contract_details:
                                contract_details['additional_info'] = {}
                            contract_details['additional_info']['contract_period'] = value
                            log.info(f"AI 분석 - 계약기간 추출: {value}")
                        
                        # 납품장소/이행장소 - additional_info에 저장
                        elif ('납품장소' in key_lower or '이행장소' in key_lower) and not contract_details.get('additional_info', {}).get('delivery_location'):
                            if 'additional_info' not in contract_details:
                                contract_details['additional_info'] = {}
                            contract_details['additional_info']['delivery_location'] = value
                            log.info(f"AI 분석 - 납품장소 추출: {value}")
                        
                        # 담당자 정보
                        elif ('담당자' in key_lower or '기관담당자' in key_lower) and not contract_details.get('contact_info'):
                            contract_details['contact_info'] = value
                            log.info(f"AI 분석 - 담당자 정보 추출: {value}")
                        
                        # 공고일(시작일)
                        elif ('공고일' in key_lower or '게시일' in key_lower) and not contract_details.get('date_start'):
                            contract_details['date_start'] = value
                            log.info(f"AI 분석 - 공고일 추출: {value}")
                        
                        # 마감일(종료일)
                        elif ('마감일' in key_lower or '입찰마감' in key_lower) and not contract_details.get('date_end'):
                            contract_details['date_end'] = value
                            log.info(f"AI 분석 - 마감일 추출: {value}")
                
                    log.info(f"AI 분석을 통해 추출된 정보: {len(parsed_result)} 필드")
                else:
                    log.warning("AI 분석 실패: 응답이 없거나 비어있습니다.")
                
            except Exception as ai_err:
                log.error(f"AI 분석 중 오류 발생: {str(ai_err)}")
                log.debug(traceback.format_exc())
                # AI 분석 실패해도 기존 추출 결과는 반환
            
            log.info(f"G2BContractAnalyzer 분석 완료: {len(contract_details)} 필드")
            return contract_details
            
        except Exception as e:
            log.error(f"G2BContractAnalyzer 분석 중 오류: {str(e)}")
            log.debug(traceback.format_exc())
            return {} 