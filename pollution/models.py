from django.db import models

class QueryLog(models.Model):
    place_name     = models.CharField(max_length=255, blank=True, null=True)
    latitude       = models.FloatField(blank=True, null=True)
    longitude      = models.FloatField(blank=True, null=True)
    created_at     = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.place_name or f"{self.latitude}, {self.longitude}"


class EstimationResult(models.Model):
    query          = models.OneToOneField(QueryLog, on_delete=models.CASCADE, related_name='result')
    open_land_acres        = models.FloatField()
    trees_possible         = models.IntegerField()
    co2_absorbed_kg_year   = models.FloatField()
    aqi                    = models.FloatField(blank=True, null=True)
    aqi_category           = models.CharField(max_length=50, blank=True, null=True)
    dominant_pollutant     = models.CharField(max_length=50, blank=True, null=True)
    tiles_analyzed         = models.IntegerField(default=1)
    created_at             = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Result for {self.query}"