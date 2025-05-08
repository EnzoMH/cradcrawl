"""
나라장터 크롤러 패키지

나라장터(G2B) 크롤링 기능을 제공하는 모듈들을 담고 있는 패키지입니다.
"""
# 실제로 사용하는 모듈만 임포트
from backend.crawler.crawler_base import CrawlerBase

# G2BCrawler 클래스를 외부에서 직접 임포트할 수 있도록 설정
from backend.crawler.g2b_crawler import G2BCrawler

# 패키지 버전 정보
__version__ = '1.0.0' 