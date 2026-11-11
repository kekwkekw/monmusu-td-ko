"""Publication checks: reviewed graphics, exact source bindings and PNG integrity."""
import base64
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from image_catalog import validate

ROOT = Path(__file__).resolve().parents[1]


class ImageCatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='.test-images-', dir=ROOT)
        self.root = Path(self.temp.name)
        self.png = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jY9sAAAAASUVORK5CYII=')
        digest = hashlib.sha256(self.png).hexdigest()
        self.entry = dict(id='label', kind='sprite', name='label', width=1, height=1,
                          file='images/' + digest + '.png', sha256=digest, bytes=len(self.png),
                          source_ids=['fixture:1'], context_suffixes=['Footer/Label'],
                          source_textures=[dict(name='atlas', width=4096, height=4096)],
                          jp='原文', ko='번역', review_status='reviewed', review_id='synthetic-review')
        (self.root / 'images').mkdir()
        (self.root / self.entry['file']).write_bytes(self.png)

    def tearDown(self):
        self.temp.cleanup()

    def write(self, entry):
        (self.root / 'images.json').write_text(json.dumps(dict(schema='monmusu-images-v1', entries=[entry])), encoding='utf-8')

    def test_reviewed_catalog_validates_and_drift_is_rejected(self):
        self.write(self.entry)
        self.assertEqual(validate(self.root)[self.entry['file']], self.png)
        (self.root / self.entry['file']).write_bytes(self.png[:-1] + b'!')
        with self.assertRaisesRegex(ValueError, 'checksum'):
            validate(self.root)

    def test_unreviewed_or_unbound_images_cannot_publish(self):
        for key, value in [('review_status', 'pending'), ('review_id', ''), ('source_ids', []),
                           ('context_suffixes', []), ('source_textures', []), ('file', '../escape.png')]:
            with self.subTest(key=key):
                entry = copy.deepcopy(self.entry); entry[key] = value; self.write(entry)
                with self.assertRaises(ValueError):
                    validate(self.root)

    def test_full_original_canvas_is_required(self):
        entry = copy.deepcopy(self.entry); entry['width'] = 2; self.write(entry)
        with self.assertRaisesRegex(ValueError, 'dimensions'):
            validate(self.root)


if __name__ == '__main__':
    unittest.main()
