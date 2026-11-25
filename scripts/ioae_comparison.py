"""Align IOAE with a documented, seasonally adjusted annual IGAE observation."""
import math
from urllib.parse import urlsplit

from sources import inegi

BASIS = 'annual_seasonally_adjusted'


def align_igae_observed(ioae, igae):
    comparable = {}
    columns = (igae or {}).get('columns', [])
    label = next((c.get('label', '').lower() for c in columns if c.get('index') == 9), '')
    if 'anual' in label and 'desest' in label:
        for row in igae.get('observations', []):
            ym = inegi.label_to_ym(row.get('period', ''))
            values = row.get('values', [])
            source = igae.get('boletin_cifras', {}).get(ym, {}).get('9', {})
            url = urlsplit(source.get('url', ''))
            value = values[9] if len(values) > 9 else None
            evidence = source.get('value')
            if (isinstance(value, (float, int)) and not isinstance(value, bool)
                    and math.isfinite(value) and isinstance(evidence, (float, int))
                    and not isinstance(evidence, bool) and math.isfinite(evidence)
                    and math.isclose(evidence, value, rel_tol=0, abs_tol=1e-9)
                    and url.scheme == 'https' and url.hostname in ('www.inegi.org.mx', 'inegi.org.mx')
                    and '/boletines/' in url.path):
                comparable[ym] = {'value': value, 'url': source['url'],
                                  'publication_date': source.get('publication_date')}
    sources = {}
    for row in ioae.get('observations', []):
        values = list(row.get('values', []))
        values.extend([None] * max(0, 13 - len(values)))
        ym = inegi.label_to_ym(row.get('period', ''))
        source = comparable.get(ym)
        # Replace old original-series copies, including when no comparable exists.
        values[12] = source['value'] if source else None
        row['values'] = values
        if source:
            sources[ym] = source
    ioae['observed_basis'] = BASIS
    ioae['observed_sources'] = sources
    return len(sources)
