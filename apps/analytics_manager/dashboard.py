from datetime import timedelta

from django.db.models import Sum
from django.urls import reverse
from django.utils import timezone

from .models import AnalyticsSettings, DailyPageStat, DailySiteStat


def analytics_dashboard_context(request, admin_site):
    """Return a compact, permission-aware analytics summary for admin index."""
    model_admin = admin_site._registry.get(DailyPageStat)
    if model_admin is None or not model_admin.has_view_permission(request):
        return None

    configuration = AnalyticsSettings.get_solo()
    today = timezone.localdate()
    chart_start = today - timedelta(days=13)
    month_start = today - timedelta(days=29)
    rows = {
        row["date"]: row
        for row in DailySiteStat.objects.filter(date__gte=chart_start).values(
            "date", "views", "unique_visitors"
        )
    }
    raw_points = []
    for offset in range(14):
        day = chart_start + timedelta(days=offset)
        row = rows.get(day, {})
        raw_points.append(
            {
                "date": day,
                "label": day.strftime("%d.%m"),
                "views": row.get("views") or 0,
                "visitors": row.get("unique_visitors") or 0,
            }
        )

    maximum = max((point["views"] for point in raw_points), default=0) or 1
    for point in raw_points:
        point["views_height"] = (
            max(4, round(point["views"] / maximum * 100)) if point["views"] else 0
        )
        point["visitors_height"] = (
            max(4, round(point["visitors"] / maximum * 100))
            if point["visitors"]
            else 0
        )

    month_site_rows = DailySiteStat.objects.filter(date__gte=month_start)
    month_totals = month_site_rows.aggregate(
        views=Sum("views"), visitors=Sum("unique_visitors")
    )
    month_page_rows = DailyPageStat.objects.filter(date__gte=month_start)
    today_row = rows.get(today, {})
    top_page = (
        month_page_rows.values("path")
        .annotate(views=Sum("views"))
        .order_by("-views", "path")
        .first()
    )
    month_views = month_totals["views"] or 0

    return {
        "enabled": configuration.enabled,
        "mode": configuration.get_collection_mode_display(),
        "today_views": today_row.get("views") or 0,
        "today_visitors": today_row.get("unique_visitors") or 0,
        "month_views": month_views,
        "month_daily_visitors": month_totals["visitors"] or 0,
        "average_views": round(month_views / 30, 1),
        "top_page": top_page,
        "chart": raw_points,
        "chart_max": maximum,
        "statistics_url": reverse(
            "admin:analytics_manager_dailypagestat_changelist"
        ),
        "settings_url": reverse(
            "admin:analytics_manager_analyticssettings_change", args=[1]
        ),
    }

