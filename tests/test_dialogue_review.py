import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from translation import Codec
from formats import text_units


class DialogueReviewTest(unittest.TestCase):
    def test_coverage_encoding_and_unchanged_controls(self):
        review = json.loads((ROOT / 'docs/dialogue-review-20261027.json').read_text())
        rooms = json.loads((ROOT / 'translation/text/rooms.json').read_text())['rooms']
        slots = [slot for row in review['coverage'] for slot in row['where']]
        slots += review['empty_or_control_only']
        expected = {f'{r:03}_{m:02}' for r, room in enumerate(rooms) for m in range(len(room['messages']))}
        self.assertEqual(len(slots), len(set(slots)))
        self.assertEqual(set(slots), expected)
        for change in review['changes']:
            r, m = map(int, change['id'].split('_'))
            codec = Codec(rooms[r]['stage'])
            self.assertEqual(rooms[r]['messages'][m], change['after'])
            for text in (change['before'], change['after']):
                controls = [u.hex().upper() for _, u in text_units(codec.encode(text))
                            if u[0] >= 0xF1 and u[0] != 0xF6]
                self.assertEqual(controls, change['controls'])
