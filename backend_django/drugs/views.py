from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .repositories import DrugRepository

class DrugSearchView(APIView):
    """의약품 검색 API (Repository 활용)"""
    def get(self, request):
        query = request.query_params.get('q', '').strip()
        
        if not query:
            return Response({"error": "검색어가 필요합니다."}, status=status.HTTP_400_BAD_REQUEST)

        # Repository를 통해 데이터 조회 로직 캡슐화
        drugs = DrugRepository.search_by_keyword(query)
        
        results = []
        for drug in drugs:
            results.append({
                "item_seq": drug.item_seq,
                "item_name": drug.item_name,
                "entp_name": drug.entp_name,
                "main_ingr_kor": drug.main_ingr_kor,
                "efficacy": drug.efficacy,
            })

        return Response({
            "results": results,
            "count": len(results)
        })
