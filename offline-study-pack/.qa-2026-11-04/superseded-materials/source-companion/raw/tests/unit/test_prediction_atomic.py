"""Publication survives temporary Windows readers and permanent rename failures."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from pipeline.prediction.contracts import atomic_json


class AtomicPublicationTests(unittest.TestCase):
    def test_transient_reader_lock_retries_without_truncating_publication(self):
        with TemporaryDirectory() as directory:
            path=Path(directory)/"index.json"
            atomic_json(path,{"release":"previous"})
            real_replace=os.replace
            calls=[]
            def replace(source,target):
                calls.append(source)
                self.assertEqual(json.loads(path.read_text()),{"release":"previous"})
                if len(calls)<3:
                    raise PermissionError("simulated Windows reader")
                real_replace(source,target)
            with patch("pipeline.prediction.contracts.os.replace",side_effect=replace),patch("pipeline.prediction.contracts.time.sleep") as sleep:
                atomic_json(path,{"release":"next"})
            self.assertEqual(len(calls),3)
            self.assertEqual(sleep.call_count,2)
            self.assertEqual(json.loads(path.read_text()),{"release":"next"})
            self.assertEqual(list(Path(directory).iterdir()),[path])

    def test_permanent_failure_retains_previous_publication_and_cleans_unique_temp(self):
        with TemporaryDirectory() as directory:
            path=Path(directory)/"index.json"
            atomic_json(path,{"release":"previous"})
            with patch("pipeline.prediction.contracts.os.replace",side_effect=PermissionError("permanent")) as replace,patch("pipeline.prediction.contracts.time.sleep") as sleep:
                with self.assertRaises(PermissionError):
                    atomic_json(path,{"release":"unpublished"})
            self.assertEqual(replace.call_count,8)
            self.assertEqual(sleep.call_count,7)
            self.assertTrue(all(call.args[0]<=1 for call in sleep.call_args_list))
            self.assertEqual(json.loads(path.read_text()),{"release":"previous"})
            self.assertEqual(list(Path(directory).iterdir()),[path])
