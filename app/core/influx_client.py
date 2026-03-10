"""
InfluxDB bağlantısı ve yazma/okuma işlemleri.
"""
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from datetime import datetime, timezone
import logging

from app.core.config import get_settings
settings = get_settings()

logger = logging.getLogger(__name__)


class InfluxService:

    def __init__(self):
        self.client = InfluxDBClient(
            url=settings.influxdb_url,
            token=settings.influxdb_token,
            org=settings.influxdb_org,
        )
        self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
        self.query_api = self.client.query_api()

    def write_status(self, plug_id: int, plug_name: str, status: dict) -> None:
        """Bir prizin anlık durumunu InfluxDB'ye yazar."""
        try:
            point = (
                Point("plug_status")
                .tag("plug_id", str(plug_id))
                .tag("plug_name", plug_name)
                .field("is_on", int(status.get("is_on", False)))
                .field("is_online", int(status.get("is_online", False)))
            )

            # Enerji metrikleri (HS110 gibi destekleyen modeller için)
            if status.get("current_watt") is not None:
                point = point.field("watt", float(status["current_watt"]))
            if status.get("voltage") is not None:
                point = point.field("voltage", float(status["voltage"]))
            if status.get("current_ampere") is not None:
                point = point.field("ampere", float(status["current_ampere"]))
            if status.get("total_kwh") is not None:
                point = point.field("total_kwh", float(status["total_kwh"]))

            self.write_api.write(
                bucket=settings.influxdb_bucket,
                org=settings.influxdb_org,
                record=point,
            )
        except Exception as e:
            logger.error(f"InfluxDB yazma hatası (plug_id={plug_id}): {e}")

    def query_watt_history(self, plug_id: int, days: int = 1) -> list[dict]:
        """Belirtilen gün sayısı kadar geçmiş watt verisi döner."""
        query = f"""
        from(bucket: "{settings.influxdb_bucket}")
          |> range(start: -{days}d)
          |> filter(fn: (r) => r._measurement == "plug_status")
          |> filter(fn: (r) => r.plug_id == "{plug_id}")
          |> filter(fn: (r) => r._field == "watt")
          |> aggregateWindow(every: 10m, fn: mean, createEmpty: false)
          |> yield(name: "mean")
        """
        return self._run_query(query)

    def query_daily_kwh(self, plug_id: int, days: int = 30) -> list[dict]:
        """Son N günün günlük kWh tüketimini döner."""
        query = f"""
        from(bucket: "{settings.influxdb_bucket}")
          |> range(start: -{days}d)
          |> filter(fn: (r) => r._measurement == "plug_status")
          |> filter(fn: (r) => r.plug_id == "{plug_id}")
          |> filter(fn: (r) => r._field == "total_kwh")
          |> aggregateWindow(every: 1d, fn: max, createEmpty: false)
          |> difference()
          |> yield(name: "daily_kwh")
        """
        return self._run_query(query)

    def query_total_watt_history(self, days: int = 1) -> list[dict]:
        """Tüm prizlerin toplam anlık watt geçmişi."""
        query = f"""
        from(bucket: "{settings.influxdb_bucket}")
          |> range(start: -{days}d)
          |> filter(fn: (r) => r._measurement == "plug_status")
          |> filter(fn: (r) => r._field == "watt")
          |> aggregateWindow(every: 10m, fn: sum, createEmpty: false)
          |> yield(name: "total")
        """
        return self._run_query(query)

    def query_online_count_history(self, days: int = 1) -> list[dict]:
        """Çevrimiçi priz sayısı geçmişi."""
        query = f"""
        from(bucket: "{settings.influxdb_bucket}")
          |> range(start: -{days}d)
          |> filter(fn: (r) => r._measurement == "plug_status")
          |> filter(fn: (r) => r._field == "is_online")
          |> aggregateWindow(every: 10m, fn: sum, createEmpty: false)
          |> yield(name: "online_count")
        """
        return self._run_query(query)

    def _run_query(self, query: str) -> list[dict]:
        try:
            tables = self.query_api.query(query, org=settings.influxdb_org)
            result = []
            for table in tables:
                for record in table.records:
                    result.append({
                        "time": record.get_time().isoformat(),
                        "value": record.get_value(),
                        "field": record.get_field(),
                        "plug_id": record.values.get("plug_id"),
                        "plug_name": record.values.get("plug_name"),
                    })
            return result
        except Exception as e:
            logger.error(f"InfluxDB sorgu hatası: {e}")
            return []


# Singleton instance
influx = InfluxService()