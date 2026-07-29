import os

from pylibrelinkup import PyLibreLinkUp
from pylibrelinkup.exceptions import RedirectError

from app.state import GlucoseReading


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


def fetch_latest_reading(client: PyLibreLinkUp, patient: object) -> GlucoseReading:
    measurement = client.latest(patient_identifier=patient)
    trend = measurement.trend.indicator if measurement.trend is not None else None
    timestamp = measurement.timestamp.isoformat() if measurement.timestamp is not None else None
    return GlucoseReading(value=measurement.value, trend=trend, timestamp=timestamp)
