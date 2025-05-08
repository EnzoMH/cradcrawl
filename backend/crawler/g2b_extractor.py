import logging
import traceback


# 로거 설정
logger = logging.getLogger("backend.crawler.extractor")

class G2BExtractor:
    """나라장터 입찰 정보 추출 클래스"""
    
    def __init__(self, driver=None):
        """
        초기화
        
        Args:
            driver: Selenium WebDriver 인스턴스
        """
        self.driver = driver
    
    def _js_extract_values(self):
        """
        JavaScript를 사용하여 브라우저에서 직접 input, select, textarea 등의 값을 추출합니다.
        
        Returns:
            추출된 값들이 담긴 딕셔너리
        """
        try:
            # JavaScript 코드 작성
            js_code = """
            function extractFormData() {
                let result = {};
                
                // getSiblings 함수 정의 (필요한 곳에서 사용)
                function getSiblings(element) {
                    if (!element.parentNode) return [];
                    return Array.from(element.parentNode.children).filter(child => child !== element);
                }
                
                // 모든 폼 요소에서 값 추출 (input, select, textarea)
                document.querySelectorAll('input, select, textarea').forEach(el => {
                    // 요소의 속성 기반 라벨 찾기
                    let label = '';
                    
                    // 1. id, name, 또는 placeholder 속성 사용
                    if (el.id) {
                        label = el.id;
                        result[label] = el.value;
                    }
                    
                    if (el.name) {
                        label = el.name;
                        result[label] = el.value;
                    }
                    
                    if (el.placeholder) {
                        label = el.placeholder;
                        result[label] = el.value;
                    }
                    
                    // 2. label 요소 찾기
                    if (el.id) {
                        const labelElement = document.querySelector(`label[for="${el.id}"]`);
                        if (labelElement) {
                            label = labelElement.textContent.trim();
                            result[label] = el.value;
                        }
                    }
                    
                    // 3. 인접한 th 요소 찾기
                    const closestTh = el.closest('td')?.previousElementSibling;
                    if (closestTh && closestTh.tagName === 'TH') {
                        label = closestTh.textContent.trim();
                        result[label] = el.value;
                    }
                    
                    // 4. 인접한 div나 span으로 된 라벨 찾기
                    const parentDiv = el.closest('div');
                    if (parentDiv) {
                        const siblingsLabels = Array.from(parentDiv.querySelectorAll('label, span, div[class*="label"]'))
                            .filter(elem => !elem.contains(el) && !el.contains(elem));
                        
                        if (siblingsLabels.length > 0) {
                            label = siblingsLabels[0].textContent.trim();
                            result[label] = el.value;
                        }
                    }
                    
                    // 5. aria-label 속성 확인
                    if (el.getAttribute('aria-label')) {
                        label = el.getAttribute('aria-label');
                        result[label] = el.value;
                    }
                    
                    // 6. 자동 생성 라벨 사용
                    if (!label && el.value) {
                        // 특성에 따른 자동 라벨 생성
                        if (el.type === 'file') label = 'file_upload';
                        else if (el.type === 'submit') label = 'submit_button';
                        else if (el.type === 'checkbox') label = `checkbox_${el.checked ? 'checked' : 'unchecked'}`;
                        else if (el.type === 'radio') label = `radio_${el.checked ? 'selected' : 'unselected'}`;
                        else label = `unlabeled_${el.tagName.toLowerCase()}_${Math.random().toString(36).substring(2, 7)}`;
                        
                        result[label] = el.value;
                    }
                });
                
                // 테이블 데이터에서 라벨과 값 쌍 추출
                document.querySelectorAll('table').forEach((table, tableIndex) => {
                    result[`table_${tableIndex}`] = {};
                    
                    table.querySelectorAll('tr').forEach((row, rowIndex) => {
                        const headers = Array.from(row.querySelectorAll('th')).map(th => th.textContent.trim());
                        const values = Array.from(row.querySelectorAll('td')).map(td => {
                            // input이 있으면 input 값 사용
                            const input = td.querySelector('input, select, textarea');
                            if (input && input.value) {
                                return input.value;
                            }
                            // 아니면 텍스트 내용 사용
                            return td.textContent.trim();
                        });
                        
                        // 각 헤더와 값을 쌍으로 매핑
                        headers.forEach((header, index) => {
                            if (header && index < values.length && values[index]) {
                                result[`table_${tableIndex}`][header] = values[index];
                                // 전역 결과에도 추가
                                result[header] = values[index];
                            }
                        });
                        
                        // 첫 번째 셀이 헤더처럼 사용되는 경우
                        const firstCell = row.querySelector('td, th');
                        const otherCells = Array.from(row.querySelectorAll('td')).slice(1);
                        
                        if (firstCell && otherCells.length > 0) {
                            const key = firstCell.textContent.trim();
                            if (key && key.length > 0 && key.length < 50) { // 합리적인 길이의 키만
                                const value = otherCells[0].textContent.trim();
                                if (value) {
                                    result[key] = value;
                                }
                            }
                        }
                    });
                });
                
                // 입찰 관련 주요 필드 추출
                // 1. 공고명/입찰건명
                const titleFields = [
                    '공고명', '입찰건명', '사업명', '공사명', '물품명', '용역명', 
                    '계약명', '제목', '건명', '공고제목', '사업제목', '입찰명', 
                    '프로젝트명', '공고건명', '입찰공고명', '제안요청명', '사업공고명',
                    '과업명', '서비스명', '구매명', '조달물품명'
                ];
                titleFields.forEach(field => {
                    const el = Array.from(document.querySelectorAll('th, label, div[class*="title"], span[class*="title"], h1, h2, h3, h4'))
                        .find(el => el.textContent.includes(field));
                    
                    if (el) {
                        const parentRow = el.closest('tr');
                        if (parentRow) {
                            const valueCell = parentRow.querySelector('td');
                            if (valueCell) {
                                result[field] = valueCell.textContent.trim();
                            }
                        } else {
                            // 주변 요소에서 값 찾기
                            const parentDiv = el.closest('div');
                            if (parentDiv) {
                                const valueElement = Array.from(parentDiv.querySelectorAll('div, span, p'))
                                    .find(elem => !elem.contains(el) && !el.contains(elem));
                                
                                if (valueElement) {
                                    result[field] = valueElement.textContent.trim();
                                }
                            }
                        }
                    }
                });
                
                // 2. 입찰공고번호
                const bidNumFields = [
                    '입찰공고번호', '공고번호', '입찰번호', '계약번호', 
                    '관리번호', '공고관리번호', '입찰관리번호', '공고ID',
                    '사업번호', '발주번호', '제안번호', '접수번호',
                    '계약관리번호', '조달요청번호', '조달계약번호'
                ];
                bidNumFields.forEach(field => {
                    const el = Array.from(document.querySelectorAll('th, label, div, span'))
                        .find(el => el.textContent.includes(field));
                    
                    if (el) {
                        const parentRow = el.closest('tr');
                        if (parentRow) {
                            const valueCell = parentRow.querySelector('td');
                            if (valueCell) {
                                result[field] = valueCell.textContent.trim();
                            }
                        } else {
                            // 주변 요소에서 값 찾기
                            const siblings = getSiblings(el);
                            if (siblings.length > 0) {
                                result[field] = siblings[0].textContent.trim();
                            }
                        }
                    }
                });
                
                // 3. 계약방법, 입찰방식, 낙찰자선정방법
                const methodFields = [
                    '계약방법', '입찰방식', '낙찰자선정방법', '계약구분', 
                    '공동계약', '참가자격', '실적제한', '경쟁방법',
                    '낙찰방법', '예정가격방식', '계약체결방법', '입찰방법',
                    '계약방식', '입찰구분', '계약유형', '경쟁형태',
                    '협상방식', '낙찰자결정방법', '계약방식구분', '입찰자격',
                    '입찰형태', '공고형태', '입찰유형'
                ];
                methodFields.forEach(field => {
                    const el = Array.from(document.querySelectorAll('th, label, div, span'))
                        .find(el => el.textContent.includes(field));
                    
                    if (el) {
                        const parentRow = el.closest('tr');
                        if (parentRow) {
                            const valueCell = parentRow.querySelector('td');
                            if (valueCell) {
                                result[field] = valueCell.textContent.trim();
                            }
                        } else {
                            // 주변 요소에서 값 찾기
                            const siblings = getSiblings(el);
                            if (siblings.length > 0) {
                                result[field] = siblings[0].textContent.trim();
                            }
                        }
                    }
                });
                
                // 4. 날짜 관련 필드
                const dateFields = [
                    '게시일시', '공고일시', '입찰공고일', '투찰일시',
                    '마감일시', '입찰마감일', '개찰일시', '입찰개시일시',
                    '제안서제출마감일시', '낙찰자발표일시', '입찰시작일시',
                    '계약체결일', '완료일', '납품기한', '수행기간', '계약기간',
                    '이행기간', '사업기간', '공사기간', '용역기간',
                    '입찰등록마감일시', '제안서평가일시', '협상일시', '입찰참가등록마감일시',
                    '제안발표일', '현장설명일', '사전심사마감일', '입찰참가신청마감일시',
                    '작업시작일', '작업종료일', '계약시작일', '계약종료일'
                ];
                dateFields.forEach(field => {
                    const el = Array.from(document.querySelectorAll('th, label, div, span'))
                        .find(el => el.textContent.includes(field));
                    
                    if (el) {
                        const parentRow = el.closest('tr');
                        if (parentRow) {
                            const valueCell = parentRow.querySelector('td');
                            if (valueCell) {
                                result[field] = valueCell.textContent.trim();
                            }
                        } else {
                            // 주변 요소에서 값 찾기
                            const siblings = getSiblings(el);
                            if (siblings.length > 0) {
                                result[field] = siblings[0].textContent.trim();
                            }
                        }
                    }
                });
                
                // 5. 가격 관련 필드
                const priceFields = [
                    '추정가격', '사업금액', '기초금액', '예정가격', '계약금액',
                    '예산금액', '낙찰금액', '사업예산', '총사업비', '총계약금액',
                    '예가', '설계금액', '총액', '단가', '입찰가격',
                    '공사비', '용역비', '물품대금', '납품금액', '제안금액',
                    '예산액', '도급금액', '공급가액', '부가세', '합계금액',
                    '예가공개여부', '예정가격결정방법'
                ];
                priceFields.forEach(field => {
                    const el = Array.from(document.querySelectorAll('th, label, div, span'))
                        .find(el => el.textContent.includes(field));
                    
                    if (el) {
                        const parentRow = el.closest('tr');
                        if (parentRow) {
                            const valueCell = parentRow.querySelector('td');
                            if (valueCell) {
                                result[field] = valueCell.textContent.trim();
                            }
                        } else {
                            // 주변 요소에서 값 찾기
                            const siblings = getSiblings(el);
                            if (siblings.length > 0) {
                                result[field] = siblings[0].textContent.trim();
                            }
                        }
                    }
                });
                
                // 6. 발주기관 및 업체 정보
                const organizationFields = [
                    '발주기관', '공고기관', '수요기관', '계약기관', '담당부서',
                    '담당자', '계약담당자', '수요담당자', '담당자연락처', '담당자이메일',
                    '업체명', '계약업체', '낙찰업체', '대표자', '사업자등록번호',
                    '법인등록번호', '업종', '업태', '소재지', '연락처',
                    '조달청연계번호', '전자입찰여부', '조달사이트', '기관유형',
                    '공공기관코드', '기관코드', '공고기관코드', '담당자부서',
                    '수요기관코드', '수요기관명', '수요기관담당자'
                ];
                organizationFields.forEach(field => {
                    const el = Array.from(document.querySelectorAll('th, label, div, span'))
                        .find(el => el.textContent.includes(field));
                    
                    if (el) {
                        const parentRow = el.closest('tr');
                        if (parentRow) {
                            const valueCell = parentRow.querySelector('td');
                            if (valueCell) {
                                result[field] = valueCell.textContent.trim();
                            }
                        } else {
                            // 주변 요소에서 값 찾기
                            const siblings = getSiblings(el);
                            if (siblings.length > 0) {
                                result[field] = siblings[0].textContent.trim();
                            }
                        }
                    }
                });
                
                // 7. 장소 관련 필드
                const locationFields = [
                    '제안서제출장소', '입찰장소', '개찰장소', '납품장소', 
                    '사업장소', '공사현장', '용역제공장소', '현장설명장소', 
                    '협상장소', '실적증명제출처', '제안발표장소', '기술제안서제출처',
                    '이행장소', '설치장소', '배송장소', '검수장소', '인도조건',
                    '배송지', '배송조건', '도착지', '입고장소', '근무장소'
                ];
                locationFields.forEach(field => {
                    const el = Array.from(document.querySelectorAll('th, label, div, span'))
                        .find(el => el.textContent.includes(field));
                    
                    if (el) {
                        const parentRow = el.closest('tr');
                        if (parentRow) {
                            const valueCell = parentRow.querySelector('td');
                            if (valueCell) {
                                result[field] = valueCell.textContent.trim();
                            }
                        } else {
                            // 주변 요소에서 값 찾기
                            const siblings = getSiblings(el);
                            if (siblings.length > 0) {
                                result[field] = siblings[0].textContent.trim();
                            }
                        }
                    }
                });
                
                // 8. 인증 및 자격 관련 필드
                const qualificationFields = [
                    '참가자격', '등록자격', '입찰참가자격', '참가자격제한', 
                    '업종등록', '등록분야', '면허', '참가적격', '적격심사',
                    '자격요건', '입찰참가자격사전심사', '실적제한', '지역제한',
                    '입찰참가자격제한', '자격증', '제한조건', '자격요구사항',
                    '참가자격사전심사', '입찰적격심사', '지명경쟁', '제한경쟁'
                ];
                qualificationFields.forEach(field => {
                    const el = Array.from(document.querySelectorAll('th, label, div, span'))
                        .find(el => el.textContent.includes(field));
                    
                    if (el) {
                        const parentRow = el.closest('tr');
                        if (parentRow) {
                            const valueCell = parentRow.querySelector('td');
                            if (valueCell) {
                                result[field] = valueCell.textContent.trim();
                            }
                        } else {
                            // 주변 요소에서 값 찾기
                            const siblings = getSiblings(el);
                            if (siblings.length > 0) {
                                result[field] = siblings[0].textContent.trim();
                            }
                        }
                    }
                });
                
                // 9. 첨부파일 관련 필드
                const attachmentFields = [
                    '첨부파일', '서류', '제출서류', '공고문파일', '입찰공고문', 
                    '제안요청서', '과업지시서', '시방서', '설계서', '규격서',
                    '사업설명서', '입찰유의서', '계약특수조건', '시행세칙',
                    '도면', '설계도면', '필수제출서류', '제출서류목록',
                    '계약서', '표준계약서', '특수계약조건', '일반계약조건'
                ];
                attachmentFields.forEach(field => {
                    const el = Array.from(document.querySelectorAll('th, label, div, span'))
                        .find(el => el.textContent.includes(field));
                    
                    if (el) {
                        const parentRow = el.closest('tr');
                        if (parentRow) {
                            const valueCell = parentRow.querySelector('td');
                            if (valueCell) {
                                // 파일 다운로드 링크 찾기
                                const links = Array.from(valueCell.querySelectorAll('a'));
                                if (links.length > 0) {
                                    result[field] = links.map(link => {
                                        return {
                                            text: link.textContent.trim(),
                                            href: link.href
                                        };
                                    });
                                } else {
                                    result[field] = valueCell.textContent.trim();
                                }
                            }
                        } else {
                            // 주변 요소에서 값 찾기
                            const siblings = getSiblings(el);
                            if (siblings.length > 0) {
                                result[field] = siblings[0].textContent.trim();
                            }
                        }
                    }
                });
                
                // 추가 정보로부터 특정 패턴이 있는 텍스트 추출
                // 예: 정책 지정, 우대 조건 등
                document.querySelectorAll('div, p, span, td').forEach(el => {
                    const text = el.textContent.trim();
                    
                    // 신용등급 정보
                    if (text.includes('신용등급') || text.includes('재무상태')) {
                        result['신용등급정보'] = text;
                    }
                    
                    // 정책지정 여부
                    if (text.includes('정책지정') || text.includes('가산점')) {
                        result['정책지정정보'] = text;
                    }
                    
                    // 제안서 관련 정보
                    if (text.includes('제안서') && (text.includes('작성') || text.includes('제출') || text.includes('평가'))) {
                        result['제안서정보'] = text;
                    }
                    
                    // 보증금 정보
                    if (text.includes('입찰보증금') || text.includes('계약보증금') || text.includes('하자보증금')) {
                        const key = text.includes('입찰보증금') ? '입찰보증금' : 
                                  text.includes('계약보증금') ? '계약보증금' : '하자보증금';
                        result[key] = text;
                    }
                });
                
                console.log(`추출된 값 수: ${Object.keys(result).length}`);
                return result;
            }
            
            return extractFormData();
            """
            
            # JavaScript 코드 실행
            extracted_values = self.driver.execute_script(js_code)
            
            # 로그 출력
            logger.info(f"JavaScript로 총 {len(extracted_values)} 개의 값 추출됨")
            
            return extracted_values
        except Exception as e:
            logger.error(f"JavaScript로 값 추출 실패: {str(e)}")
            logger.debug(traceback.format_exc())
            return {}


