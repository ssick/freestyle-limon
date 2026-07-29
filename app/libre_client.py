import os
import warnings

from pylibrelinkup import PyLibreLinkUp
from pylibrelinkup.exceptions import RedirectError

from app.state import GlucoseReading, HistoryPoint


def build_client() -> tuple[PyLibreLinkUp, object]:
    """Authenticate against the LibreLinkUp API and resolve the first connected patient.

    Retries once against the region returned by RedirectError, since accounts
    outside the US default region get redirected on first login.
    """
    email = os.environ["LIBRE_EMAIL"]
    password = os.environ["LIBRE_PASSWORD"]

    client = PyLibreLinkUp(email=email, password=password)
    try:
        client.authenticate()
    except RedirectError as redirect:
        client = PyLibreLinkUp(email=email, password=password, api_url=redirect.region)
        client.authenticate()

    patients = client.get_patients()
    if not patients:
        raise RuntimeError("No connected patients found in LibreLinkUp account")
    return client, patients[0]


def fetch_reading_and_history(
    client: PyLibreLinkUp, patient: object
) -> tuple[GlucoseReading, list[HistoryPoint], int, int]:
    """Fetch the latest reading and recent history from a single API call.

    Uses the deprecated `read()` method rather than `latest()` + `graph()`
    because both of those hit the same underlying endpoint independently -
    calling `read()` once gets the same data without doubling the API calls
    made against LibreLinkUp on every poll.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        response = client.read(patient_identifier=patient)

    measurement = response.current
    trend = measurement.trend.indicator if measurement.trend is not None else None
    timestamp = measurement.timestamp.isoformat() if measurement.timestamp is not None else None
    reading = GlucoseReading(
        value=measurement.value,
        trend=trend,
        timestamp=timestamp,
        is_high=measurement.is_high,
        is_low=measurement.is_low,
    )

    # LibreLinkUp doesn't populate isHigh/isLow on historical graph points (always
    # False), unlike the current reading, so range status has to be derived from
    # the patient's own target range instead of trusting the flag on each point.
    target_low = response.data.connection.target_low
    target_high = response.data.connection.target_high
    history = [
        HistoryPoint(
            value=point.value,
            timestamp=point.timestamp.isoformat() if point.timestamp is not None else None,
            is_high=point.value > target_high,
            is_low=point.value < target_low,
        )
        for point in response.history
    ]

    return reading, history, target_low, target_high
