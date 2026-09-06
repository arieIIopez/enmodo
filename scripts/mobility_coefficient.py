"""Reproducible core for the mobility coefficient research proposal.

The module keeps trips per day and average trip duration as separate axes while
also calculating daily travel time as their exact product. It intentionally
uses cautious labels ("compatible with") for privileged/excluded immobility:
those mechanisms cannot be identified causally from travel diaries alone.
"""

from dataclasses import asdict, dataclass
from typing import Optional, Sequence

import numpy as np
import pandas as pd


STATE_HIGH_FAVORABLE = "alta_interaccion_favorable"
STATE_HIGH_COSTLY = "alta_interaccion_costosa"
STATE_LOW_FAVORABLE = "baja_interaccion_favorable"
STATE_LOW_COSTLY = "baja_interaccion_costosa"
STATE_IMMOBILE_PRIVILEGE = "inmovilidad_privilegio_compatible"
STATE_IMMOBILE_EXCLUSION = "inmovilidad_exclusion_compatible"
STATE_IMMOBILE_UNKNOWN = "inmovilidad_no_identificada"

FAVORABLE_STATES = {
    STATE_HIGH_FAVORABLE,
    STATE_LOW_FAVORABLE,
    STATE_IMMOBILE_PRIVILEGE,
}


@dataclass(frozen=True)
class ReferenceModel:
    """Parameters defining the common empirical classification frontier."""

    slope: float
    intercept: float
    weighted_median_duration: float
    interaction_cutoff: float
    cutoff_method: str
    sample_size: int
    expanded_population: float

    def predict(self, trips: pd.Series) -> pd.Series:
        return self.intercept + self.slope * trips

    def to_dict(self) -> dict:
        return asdict(self)


def _require_columns(frame: pd.DataFrame, columns: Sequence[str]) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"Faltan columnas requeridas: {missing}")


def _validate_weights(weights: pd.Series) -> None:
    if weights.isna().any() or (~np.isfinite(weights)).any():
        raise ValueError("Los factores de expansión deben ser finitos y no nulos.")
    if (weights <= 0).any():
        raise ValueError("Los factores de expansión deben ser mayores que cero.")


def weighted_quantile(values: pd.Series, weights: pd.Series, quantile: float) -> float:
    """Return a weighted quantile using the inverted empirical CDF."""

    if not 0 <= quantile <= 1:
        raise ValueError("El cuantil debe estar entre 0 y 1.")

    data = pd.DataFrame({"value": values, "weight": weights}).dropna()
    if data.empty:
        raise ValueError("No hay observaciones válidas para calcular el cuantil.")
    _validate_weights(data["weight"])

    data = data.sort_values("value", kind="mergesort")
    cumulative = data["weight"].cumsum()
    cutoff = quantile * data["weight"].sum()
    return float(data.loc[cumulative >= cutoff, "value"].iloc[0])


def build_person_day(
    trips: pd.DataFrame,
    *,
    person_id: str,
    duration: str,
    weight: str,
    trip_id: Optional[str] = None,
    persons: Optional[pd.DataFrame] = None,
    attributes: Sequence[str] = (),
) -> pd.DataFrame:
    """Aggregate valid trip records to one record per person-day.

    Pass ``persons`` to preserve people with zero trips. When trip data contain
    stages, ``trip_id`` must identify the complete trip; durations are first
    summed within each trip and trips are then counted uniquely.
    """

    required_trip_columns = [person_id, duration]
    if persons is None:
        required_trip_columns.append(weight)
        required_trip_columns.extend(attributes)
    if trip_id:
        required_trip_columns.append(trip_id)
    _require_columns(trips, required_trip_columns)

    working = trips.copy()
    working[duration] = pd.to_numeric(working[duration], errors="coerce")
    if working[duration].isna().any() or (~np.isfinite(working[duration])).any():
        raise ValueError("Las duraciones deben ser numéricas y finitas.")
    if (working[duration] < 0).any():
        raise ValueError("Las duraciones no pueden ser negativas.")

    if trip_id:
        working = (
            working.groupby([person_id, trip_id], as_index=False, dropna=False)
            .agg(**{duration: (duration, "sum")})
        )

    summary = (
        working.groupby(person_id, as_index=False, dropna=False)
        .agg(
            n_viajes=(duration, "size"),
            tiempo_promedio=(duration, "mean"),
            tiempo_total=(duration, "sum"),
        )
    )

    if persons is None:
        base_columns = [person_id, weight, *attributes]
        base = trips[base_columns].drop_duplicates(subset=[person_id]).copy()
    else:
        _require_columns(persons, [person_id, weight, *attributes])
        if persons[person_id].duplicated().any():
            raise ValueError("La tabla de personas debe tener una fila por persona.")
        base = persons[[person_id, weight, *attributes]].copy()

    base[weight] = pd.to_numeric(base[weight], errors="coerce")
    _validate_weights(base[weight])
    result = base.merge(summary, on=person_id, how="left", validate="one_to_one")
    result["n_viajes"] = result["n_viajes"].fillna(0).astype(int)
    result["tiempo_total"] = result["tiempo_total"].fillna(0.0)

    mobile = result["n_viajes"] > 0
    product = result.loc[mobile, "n_viajes"] * result.loc[mobile, "tiempo_promedio"]
    if not np.allclose(product, result.loc[mobile, "tiempo_total"]):
        raise AssertionError("tiempo_total no coincide con n_viajes * tiempo_promedio.")

    return result


def fit_reference_model(
    person_day: pd.DataFrame,
    *,
    weight: str,
    trips: str = "n_viajes",
    average_duration: str = "tiempo_promedio",
) -> ReferenceModel:
    """Fit a weighted linear reference on people with at least one trip."""

    _require_columns(person_day, [weight, trips, average_duration])
    data = person_day[[weight, trips, average_duration]].copy()
    data[trips] = pd.to_numeric(data[trips], errors="coerce")
    data[average_duration] = pd.to_numeric(
        data[average_duration], errors="coerce"
    )
    data = data.loc[(data[trips] > 0) & data[average_duration].notna()].copy()
    if (~np.isfinite(data[[trips, average_duration]])).any().any():
        raise ValueError("Viajes y duración media deben ser valores finitos.")
    if len(data) < 2 or data[trips].nunique() < 2:
        raise ValueError("Se requieren al menos dos cantidades de viaje distintas.")

    data[weight] = pd.to_numeric(data[weight], errors="coerce")
    _validate_weights(data[weight])
    x = data[trips].to_numpy(dtype=float)
    y = data[average_duration].to_numpy(dtype=float)
    w = data[weight].to_numpy(dtype=float)

    design = np.column_stack([np.ones(len(data)), x])
    coefficients = np.linalg.lstsq(
        design * np.sqrt(w)[:, None], y * np.sqrt(w), rcond=None
    )[0]
    intercept, slope = coefficients
    median_duration = weighted_quantile(data[average_duration], data[weight], 0.5)

    if np.isfinite(slope) and abs(slope) > 1e-12:
        cutoff = (median_duration - intercept) / slope
        cutoff_method = "interseccion_recta_mediana"
    else:
        cutoff = weighted_quantile(data[trips], data[weight], 0.5)
        cutoff_method = "mediana_viajes_respaldo"

    minimum = float(data[trips].min())
    maximum = float(data[trips].max())
    if not np.isfinite(cutoff) or cutoff < minimum or cutoff > maximum:
        cutoff = weighted_quantile(data[trips], data[weight], 0.5)
        cutoff_method = "mediana_viajes_respaldo"

    return ReferenceModel(
        slope=float(slope),
        intercept=float(intercept),
        weighted_median_duration=median_duration,
        interaction_cutoff=float(cutoff),
        cutoff_method=cutoff_method,
        sample_size=len(data),
        expanded_population=float(data[weight].sum()),
    )


def classify_person_days(
    person_day: pd.DataFrame,
    reference: ReferenceModel,
    *,
    low_trip_threshold: int = 1,
    trips: str = "n_viajes",
    average_duration: str = "tiempo_promedio",
) -> pd.DataFrame:
    """Classify people using one common reference model.

    Zero-trip cases remain unidentified because no trip duration is observed.
    One-trip cases are labelled as mechanisms *compatible* with privilege or
    exclusion; these labels are hypotheses to validate, not causal findings.
    """

    if low_trip_threshold < 1:
        raise ValueError("low_trip_threshold debe ser al menos 1.")
    _require_columns(person_day, [trips, average_duration])

    result = person_day.copy()
    result["duracion_referencia"] = reference.predict(result[trips])
    result["estado_movilidad"] = pd.Series(pd.NA, index=result.index, dtype="string")

    zero = result[trips] == 0
    low = result[trips].between(1, low_trip_threshold)
    regular = result[trips] > low_trip_threshold
    favorable = result[average_duration] <= result["duracion_referencia"]
    high_interaction = result[trips] >= reference.interaction_cutoff

    result.loc[zero, "estado_movilidad"] = STATE_IMMOBILE_UNKNOWN
    result.loc[low & favorable, "estado_movilidad"] = STATE_IMMOBILE_PRIVILEGE
    result.loc[low & ~favorable, "estado_movilidad"] = STATE_IMMOBILE_EXCLUSION
    result.loc[regular & high_interaction & favorable, "estado_movilidad"] = STATE_HIGH_FAVORABLE
    result.loc[regular & high_interaction & ~favorable, "estado_movilidad"] = STATE_HIGH_COSTLY
    result.loc[regular & ~high_interaction & favorable, "estado_movilidad"] = STATE_LOW_FAVORABLE
    result.loc[regular & ~high_interaction & ~favorable, "estado_movilidad"] = STATE_LOW_COSTLY

    if result["estado_movilidad"].isna().any():
        raise AssertionError("Hay personas que no recibieron una clasificación.")
    return result


def calculate_profile(
    classified: pd.DataFrame,
    *,
    weight: str,
    group_by: Sequence[str] = (),
) -> pd.DataFrame:
    """Calculate weighted state shares and a provisional favorable coefficient."""

    _require_columns(classified, [weight, "estado_movilidad", *group_by])
    data = classified.copy()
    data[weight] = pd.to_numeric(data[weight], errors="coerce")
    _validate_weights(data[weight])

    grouping = [*group_by, "estado_movilidad"]
    profile = data.groupby(grouping, dropna=False)[weight].sum().rename("poblacion").reset_index()
    denominators = (
        data.groupby(list(group_by), dropna=False)[weight].sum()
        if group_by
        else pd.Series({"__total__": data[weight].sum()})
    )

    if group_by:
        profile = profile.merge(
            denominators.rename("poblacion_total").reset_index(), on=list(group_by), how="left"
        )
    else:
        profile["poblacion_total"] = float(denominators.iloc[0])
    profile["proporcion"] = profile["poblacion"] / profile["poblacion_total"]

    def coefficient(frame: pd.DataFrame) -> pd.Series:
        classifiable_population = frame.loc[
            frame["estado_movilidad"] != STATE_IMMOBILE_UNKNOWN, weight
        ].sum()
        favorable_population = frame.loc[
            frame["estado_movilidad"].isin(FAVORABLE_STATES), weight
        ].sum()
        value = (
            favorable_population / classifiable_population
            if classifiable_population > 0
            else np.nan
        )
        return pd.Series(
            {
                "coeficiente_favorable": value,
                "proporcion_no_identificada": frame.loc[
                    frame["estado_movilidad"] == STATE_IMMOBILE_UNKNOWN, weight
                ].sum()
                / frame[weight].sum(),
            }
        )

    if group_by:
        metric_rows = []
        for keys, frame in data.groupby(list(group_by), dropna=False):
            keys = keys if isinstance(keys, tuple) else (keys,)
            row = dict(zip(group_by, keys))
            row.update(coefficient(frame).to_dict())
            metric_rows.append(row)
        metrics = pd.DataFrame(metric_rows)
        profile = profile.merge(metrics, on=list(group_by), how="left")
    else:
        metrics = coefficient(data)
        profile["coeficiente_favorable"] = metrics["coeficiente_favorable"]
        profile["proporcion_no_identificada"] = metrics["proporcion_no_identificada"]

    return profile.sort_values(grouping).reset_index(drop=True)
