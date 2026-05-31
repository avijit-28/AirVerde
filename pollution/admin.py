from django.contrib import admin
from .models import QueryLog, EstimationResult

@admin.register(QueryLog)
class QueryLogAdmin(admin.ModelAdmin):
    list_display = ['id', 'place_name', 'latitude', 'longitude', 'created_at']

@admin.register(EstimationResult)
class EstimationResultAdmin(admin.ModelAdmin):
    list_display = ['id', 'query', 'open_land_acres', 'trees_possible', 'co2_absorbed_kg_year', 'aqi', 'created_at']