import unittest

import numpy as np
import pandas as pd

from scripts.mobility_coefficient import (
    STATE_IMMOBILE_UNKNOWN,
    build_person_day,
    calculate_profile,
    classify_person_days,
    fit_reference_model,
    weighted_quantile,
)


class MobilityCoefficientTests(unittest.TestCase):
    def setUp(self):
        self.persons = pd.DataFrame(
            {
                "person_id": [1, 2, 3, 4, 5],
                "weight": [1.0, 2.0, 1.0, 1.0, 1.0],
                "sex": ["M", "F", "F", "M", "F"],
            }
        )
        durations = {
            1: [10],
            2: [20, 20],
            3: [30, 30, 30],
            4: [15, 15, 15, 15],
        }
        rows = []
        for person_id, values in durations.items():
            for trip_id, duration in enumerate(values, start=1):
                rows.append(
                    {
                        "person_id": person_id,
                        "trip_id": trip_id,
                        "duration": duration,
                    }
                )
        self.trips = pd.DataFrame(rows)

    def test_person_day_preserves_zero_trips_and_time_identity(self):
        result = build_person_day(
            self.trips,
            persons=self.persons,
            person_id="person_id",
            trip_id="trip_id",
            duration="duration",
            weight="weight",
            attributes=("sex",),
        )

        zero_trip = result.loc[result["person_id"] == 5].iloc[0]
        self.assertEqual(zero_trip["n_viajes"], 0)
        self.assertEqual(zero_trip["tiempo_total"], 0)
        self.assertTrue(np.isnan(zero_trip["tiempo_promedio"]))
        mobile = result[result["n_viajes"] > 0]
        np.testing.assert_allclose(
            mobile["tiempo_total"], mobile["n_viajes"] * mobile["tiempo_promedio"]
        )

    def test_trip_id_prevents_counting_stages_as_trips(self):
        stages = pd.DataFrame(
            {
                "person_id": [1, 1, 1],
                "trip_id": [10, 10, 11],
                "duration": [5, 7, 8],
                "weight": [1, 1, 1],
            }
        )
        result = build_person_day(
            stages,
            person_id="person_id",
            trip_id="trip_id",
            duration="duration",
            weight="weight",
        )
        self.assertEqual(result.loc[0, "n_viajes"], 2)
        self.assertEqual(result.loc[0, "tiempo_total"], 20)
        self.assertEqual(result.loc[0, "tiempo_promedio"], 10)

    def test_weighted_quantile_uses_expansion_weights(self):
        value = weighted_quantile(
            pd.Series([10, 20, 30]), pd.Series([1, 8, 1]), 0.5
        )
        self.assertEqual(value, 20)

    def test_common_reference_classifies_every_person(self):
        person_day = build_person_day(
            self.trips,
            persons=self.persons,
            person_id="person_id",
            trip_id="trip_id",
            duration="duration",
            weight="weight",
            attributes=("sex",),
        )
        reference = fit_reference_model(person_day, weight="weight")
        classified = classify_person_days(person_day, reference)

        self.assertFalse(classified["estado_movilidad"].isna().any())
        state = classified.loc[
            classified["person_id"] == 5, "estado_movilidad"
        ].iloc[0]
        self.assertEqual(state, STATE_IMMOBILE_UNKNOWN)

        profile = calculate_profile(classified, weight="weight")
        self.assertAlmostEqual(profile["proporcion"].sum(), 1.0)
        self.assertTrue(profile["coeficiente_favorable"].between(0, 1).all())

    def test_invalid_weights_are_rejected(self):
        persons = self.persons.copy()
        persons.loc[0, "weight"] = 0
        with self.assertRaises(ValueError):
            build_person_day(
                self.trips,
                persons=persons,
                person_id="person_id",
                trip_id="trip_id",
                duration="duration",
                weight="weight",
            )


if __name__ == "__main__":
    unittest.main()
