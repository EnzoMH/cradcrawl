"""
나라장터 크롤링 데이터 모델

이 모듈은 나라장터 크롤링 결과를 저장하기 위한 데이터 모델을 정의합니다.
"""

from enum import Enum
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field

class BidStatus(str, Enum):
    """입찰 상태"""
    
    OPEN = "공고중"  # 공고 진행 중
    CLOSED = "마감"  # 입찰 마감
    AWARDED = "낙찰"  # 낙찰 완료
    CANCELLED = "취소"  # 공고 취소
    UNKNOWN = "알 수 없음"  # 상태 알 수 없음

class BidItem(BaseModel):
    """입찰 공고 항목 모델"""
    
    id: str = Field(..., description="항목 ID")
    bid_number: str = Field(..., description="공고번호")
    bid_title: str = Field(..., description="공고명")
    organization: Optional[str] = Field(None, description="공고기관")
    bid_method: Optional[str] = Field(None, description="입찰방식")
    bid_type: Optional[str] = Field(None, description="계약방식")
    date_start: Optional[str] = Field(None, description="공고일시")
    date_end: Optional[str] = Field(None, description="마감일시")
    status: Optional[BidStatus] = Field(BidStatus.UNKNOWN, description="입찰 상태")
    detail_url: Optional[str] = Field(None, description="상세 페이지 URL")
    extracted_time: str = Field(default_factory=lambda: datetime.now().isoformat(), description="정보 추출 시간")
    
    # 추가 정보 필드들 (상세 페이지 정보)
    budget: Optional[str] = Field(None, description="예산금액")
    estimated_price: Optional[str] = Field(None, description="추정가격")
    contact_info: Optional[str] = Field(None, description="담당자 정보")
    requirements: Optional[str] = Field(None, description="요구사항")
    additional_info: Optional[Dict[str, Any]] = Field(None, description="추가 정보")

class SearchResult(BaseModel):
    """검색 결과 모델"""
    
    keyword: str = Field(..., description="검색어")
    total_count: int = Field(0, description="총 검색 결과 수")
    items: List[BidItem] = Field(default_factory=list, description="검색된 입찰 항목 목록")
    search_time: str = Field(default_factory=lambda: datetime.now().isoformat(), description="검색 시간") 