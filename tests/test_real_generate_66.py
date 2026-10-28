"""Issue 66: a real `generate` run with ACadSharp and LibreDWG, and the interrupt with a conversion in flight."""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECORD = ROOT / "docs" / "reports" / "generate-real-run.md"
FIXTURE = "bspline-d3-001"


def service(name):
    text = (ROOT / "docker-compose.yml").read_text()
    m = re.search(r"^  %s:\n((?:    .*\n|\n)+)" % re.escape(name), text, re.M)
    return m.group(1) if m else ""


class Compose(unittest.TestCase):
    def test_libredwg_service_takes_the_runner_arguments_directly(self):
        # runner.generate runs `compose run --rm SERVICE --in ... --out ... --status ...`, so the service
        # needs an entrypoint that is the converter; the image itself has none
        self.assertRegex(service("libredwg-converter"), r'entrypoint: \["dwg2step"\]')

    def test_acadsharp_service_relies_on_the_image_entrypoint(self):
        self.assertNotIn("entrypoint:", service("acadsharp-converter"))


class Record(unittest.TestCase):
    def setUp(self):
        self.assertTrue(RECORD.exists(), "docs/reports/generate-real-run.md has not been written")
        self.text = RECORD.read_text()

    def test_it_names_the_fixture_and_every_artifact(self):
        self.assertIn(FIXTURE, self.text)
        for n in ("primary.step", "secondary.step", "primary.status.json", "secondary.status.json",
                  "primary.verification.json", "secondary.verification.json", "primary.signature.json",
                  "secondary.signature.json", "verdict.json", "manifest.json", "checksums.sha256"):
            self.assertIn(n, self.text, n)

    def test_it_names_both_converters_and_the_verdict(self):
        self.assertIn("acadsharp-converter", self.text)
        self.assertIn("libredwg-converter", self.text)
        self.assertRegex(self.text, r"KNOWN_TRUTH_EXACT")

    def test_the_clean_run_ends_with_the_leak_check(self):
        self.assertIn("leak check: docker ps -a and docker volume ls are as they were", self.text)

    def test_the_interrupt_run_was_in_flight_and_left_nothing(self):
        self.assertIn("interrupted: containers torn down", self.text)
        self.assertRegex(self.text, r"(?i)converter container (was )?running when")
        self.assertRegex(self.text, r"(?i)no container and no volume")

    def test_it_pins_the_images_by_id_not_by_registry(self):
        self.assertRegex(self.text, r"sha256:[0-9a-f]{64}")
        self.assertNotIn("ghcr.io", self.text.replace("ghcr.io/libviprs/pvec-gold-dwg2step-acadsharp", ""))


class RunnerEnvironment(unittest.TestCase):
    def test_the_runner_sees_the_libredwg_image_choice(self):
        # runner.generate calls `docker compose config` from inside the container, so a LIBREDWG_IMAGE set on
        # the host only counts if compose hands it on
        s = service("fixture-runner")
        self.assertRegex(s, r"LIBREDWG_IMAGE: \$\{LIBREDWG_IMAGE:-[^}]+\}")
        self.assertRegex(s, r"LIBREDWG_PLATFORM: \$\{LIBREDWG_PLATFORM:-[^}]+\}")
