from typing import Any

from meteorite_pipeline.db.connection import get_dash_connection


VALID_FALL_TYPES = {"all", "Fell", "Found"}
MAP_POINT_LIMIT = 4000


def _where_clause(fall_type: str, include_flagged: bool) -> tuple[str, tuple[Any, ...]]:
    if fall_type not in VALID_FALL_TYPES:
        raise ValueError("fall_type must be 'all', 'Fell', or 'Found'.")

    conditions: list[str] = []
    parameters: list[Any] = []
    if fall_type != "all":
        conditions.append("fall = %s")
        parameters.append(fall_type)
    if not include_flagged:
        conditions.append("quality_any_issue = FALSE")

    return " AND ".join(conditions) if conditions else "TRUE", tuple(parameters)


def _fetch_dicts(cursor) -> list[dict[str, Any]]:
    columns = [column.name for column in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def load_dashboard_data(
    fall_type: str = "all",
    include_flagged: bool = False,
) -> dict[str, Any]:
    where, parameters = _where_clause(fall_type, include_flagged)
    connection = get_dash_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT
                    COUNT(*)::bigint AS total_records,
                    COUNT(DISTINCT id)::bigint AS unique_ids,
                    COUNT(*) FILTER (WHERE fall = 'Fell')::bigint AS fell_records,
                    COUNT(*) FILTER (WHERE fall = 'Found')::bigint AS found_records,
                    COUNT(*) FILTER (WHERE quality_any_issue)::bigint AS flagged_records
                FROM public.meteorite_landings
                WHERE {where}
                """,
                parameters,
            )
            summary_row = cursor.fetchone()
            summary = dict(
                zip(
                    [column.name for column in cursor.description],
                    summary_row,
                    strict=True,
                )
            )

            cursor.execute(
                f"""
                SELECT year::integer AS year, COUNT(*)::bigint AS records
                FROM public.meteorite_landings
                WHERE {where}
                  AND year IS NOT NULL
                  AND quality_future_year = FALSE
                GROUP BY year::integer
                ORDER BY year
                """,
                parameters,
            )
            by_year = _fetch_dicts(cursor)

            cursor.execute(
                f"""
                SELECT recclass, COUNT(*)::bigint AS records
                FROM public.meteorite_landings
                WHERE {where}
                GROUP BY recclass
                ORDER BY records DESC, recclass
                LIMIT 12
                """,
                parameters,
            )
            by_class = _fetch_dicts(cursor)

            cursor.execute(
                f"""
                SELECT name, id, recclass, fall, "mass (g)" AS mass_g, reclat, reclong
                FROM public.meteorite_landings
                WHERE {where}
                  AND quality_missing_coordinates = FALSE
                  AND quality_zero_coordinates = FALSE
                  AND quality_invalid_latitude = FALSE
                  AND quality_longitude_outside_range = FALSE
                  AND reclat BETWEEN -90 AND 90
                  AND reclong BETWEEN -180 AND 180
                ORDER BY random()
                LIMIT %s
                """,
                (*parameters, MAP_POINT_LIMIT),
            )
            map_points = _fetch_dicts(cursor)

        return {
            "summary": summary,
            "by_year": by_year,
            "by_class": by_class,
            "map_points": map_points,
        }
    finally:
        connection.close()
