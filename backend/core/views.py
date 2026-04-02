from rest_framework.views import APIView
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema

class HealthView(APIView):
    @extend_schema(
        summary='Health check', 
        description='Check if the server is running',
    )
    def get(self, request):
        return Response({'status': 'ok'})