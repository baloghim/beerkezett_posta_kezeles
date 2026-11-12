from collections import OrderedDict
import pymupdf
from .models import EDPDError


class PDFService:
    def __init__(self, data):
        self.cache = OrderedDict()
        try:
            self.document = pymupdf.open(stream=data, filetype='pdf')
            if self.document.needs_pass or not self.document.page_count:
                self.document.close()
                raise EDPDError('A PDF jelszóval védett, vagy nem tartalmaz oldalt.')
        except (RuntimeError, ValueError) as exc:
            raise EDPDError('A PDF sérült vagy nem olvasható.') from exc

    @property
    def pages(self):
        return self.document.page_count

    def render(self, page, scale=1.0):
        if not 0 <= page < self.pages:
            raise EDPDError('Érvénytelen oldalszám.')
        rect = self.document[page].rect
        scale = min(max(scale, 0.1), 5.0, (20_000_000 / max(rect.width * rect.height, 1)) ** 0.5)
        key = (page, round(scale, 3))
        if key not in self.cache:
            self.cache[key] = self.document[page].get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
        self.cache.move_to_end(key)
        while len(self.cache) > 1 and sum(p.width * p.height * p.n for p in self.cache.values()) > 64 * 1024 * 1024:
            self.cache.popitem(last=False)
        return self.cache[key]

    def close(self):
        self.cache.clear()
        self.document.close()
