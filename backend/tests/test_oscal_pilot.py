"""Synthetic fixtures only: no LLM calls, remote requests, or real documents."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[2]/"scripts"/"oscal_pilot.py"
spec=importlib.util.spec_from_file_location("oscal_pilot",SCRIPT)
pilot=importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot)

class PilotTests(unittest.TestCase):
    def test_catalogs_and_scoring(self):
        with tempfile.TemporaryDirectory() as d:
            candidate=pilot.generate(Path(d))
            self.assertEqual(len(pilot.DATA["nis2"]),3)
            self.assertEqual(len(pilot.DATA["iso27002"]),10)
            m=pilot.score(candidate)
            self.assertEqual((m["true_positives"],m["false_positives"],m["false_negatives"]),(9,1,1))
            self.assertEqual((m["precision"],m["recall"],m["f1"]),(0.9,0.9,0.9))

    def test_perfect_baseline(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"perfect.json"
            pilot.write_json(path,pilot.mapping(pilot.GOLD))
            m=pilot.score(path)
            self.assertEqual((m["precision"],m["recall"],m["f1"]),(1.,1.,1.))

    def test_unknown_control_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"bad.json"
            pilot.write_json(path,pilot.mapping({("nis2-04","iso-99-99")}))
            with self.assertRaisesRegex(ValueError,"unknown"):
                pilot.score(path)

    def test_duplicate_pair_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"dup.json"
            m=pilot.mapping({("nis2-04","iso-5-19")})
            m["mapping-collection"]["mappings"][0]["maps"] *= 2
            pilot.write_json(path,m)
            with self.assertRaisesRegex(ValueError,"Duplicate"):
                pilot.score(path)

    def test_output_must_be_external_to_repo(self):
        with self.assertRaisesRegex(ValueError,"uden for Git"):
            pilot.assert_external_folder(pilot.PROJECT/"generated-data")

    def test_deterministic_identifiers(self):
        self.assertEqual(pilot.mapping(pilot.GOLD),pilot.mapping(pilot.GOLD))
        self.assertEqual(pilot.catalog("nis2",pilot.DATA["nis2"]),
                         pilot.catalog("nis2",pilot.DATA["nis2"]))
