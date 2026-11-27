"""Read national monthly occupation and comparable rates from the ENOE bulletin."""
from urllib.parse import urlsplit
import re

import notas_enoe
from sources.base import http_get_bytes

RATE_IDS = ('unemployment', 'participation', 'informality', 'underemployment')


def refresh(indicator, fetch=http_get_bytes):
    period = indicator.get('last_observation')
    url = indicator.get('url_boletin_oficial') or ''
    previous = indicator.get('enoe_mensual', {})
    if previous.get('periodo') == period and previous.get('fuente') == url:
        return False

    source = urlsplit(url)
    if (source.scheme != 'https' or source.netloc != 'www.inegi.org.mx'
            or source.query or source.fragment
            or not re.fullmatch(r'/contenidos/saladeprensa/boletines/(\d{4})/iooe/IOE\1_\d{2}\.pdf',
                                source.path, re.IGNORECASE)):
        raise ValueError('Boletín mensual ENOE no identificado')
    pdf = fetch(url, timeout=12)
    if not pdf.startswith(b'%PDF'):
        raise ValueError('El boletín ENOE no devolvió un PDF')
    facts = notas_enoe.extract(pdf)
    if facts['period'] != period:
        raise ValueError(f"El boletín ENOE contiene {facts['period']} y la ficha {period}")

    occupied = notas_enoe.get(facts, 'occupied')
    rates = {}
    for key in RATE_IDS:
        original = notas_enoe.rate(facts, key)
        adjusted = notas_enoe.rate(facts, key, adjusted=True)
        rates[key] = {'anual_original_pp': original['difference'],
                      'nivel_desest': adjusted['current'], 'mensual_desest_pp': adjusted['mom']}
    indicator['enoe_mensual'] = {
        'periodo': period, 'fuente': url, 'boletin': facts['bulletin'],
        'publicado_en': facts['publication_date'], 'ocupados': occupied['current'],
        'ocupados_anterior': occupied['previous'], 'cambio_ocupados_anual': occupied['difference'],
        'tasas': rates,
    }
    return True
