from dataclasses import dataclass

from django.utils import timezone


@dataclass(frozen=True)
class LicenceStatus:
    code: str
    label: str
    days_until_expiry: int | None


LICENCE_EXPIRED = 'expired'
LICENCE_EXPIRING_SOON = 'expiring_soon'
LICENCE_VALID = 'valid'
LICENCE_MISSING = 'missing'


def get_licence_status(expiry_date):
    """
    Return licence status using an inclusive 30-day warning window.

    Boundary decision:
    - before today: expired
    - today through today + 30 days: expiring soon
    - later than today + 30 days: valid
    - missing date: missing
    """
    if expiry_date is None:
        return LicenceStatus(LICENCE_MISSING, 'Missing expiry date', None)

    today = timezone.localdate()
    days_until_expiry = (expiry_date - today).days

    if days_until_expiry < 0:
        return LicenceStatus(LICENCE_EXPIRED, 'Expired', days_until_expiry)
    if days_until_expiry <= 30:
        return LicenceStatus(LICENCE_EXPIRING_SOON, 'Expiring soon', days_until_expiry)
    return LicenceStatus(LICENCE_VALID, 'Valid', days_until_expiry)
